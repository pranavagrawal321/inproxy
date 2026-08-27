import re
import ast
import sys
import json
import base64
import signal
import operator
import pandas as pd
from lxml import html
from io import StringIO
from queue import Queue, Empty
from copy import deepcopy
from curl_cffi import requests
from fake_useragent import UserAgent
from threading import Thread, Event, Lock

try:
    from config import PROXY_CONFIG
except ImportError:
    from .config import PROXY_CONFIG

ua = UserAgent()


class NoProxyFoundException(Exception):
    pass


class Proxy:
    def __init__(
        self,
        source_workers=20,
        proxy_workers=100,
        source_timeout=3,
        proxy_timeout=2,
    ):
        self._proxy_config = deepcopy(PROXY_CONFIG)

        self.proxy = None

        self.source_workers = source_workers
        self.proxy_workers = proxy_workers
        self.source_timeout = source_timeout
        self.proxy_timeout = proxy_timeout

        self.stop_event = Event()
        self.result_event = Event()

        self.validation_queue = Queue(maxsize=proxy_workers * 4)

        self.seen = set()
        self.seen_lock = Lock()

        self.proxy_lock = Lock()

        self.sources_remaining = 0
        self.sources_lock = Lock()

        self.source_threads = []
        self.validation_threads = []

        self.install_signal_handlers()

    def install_signal_handlers(self):
        signal_handlers = {
            signal.SIGINT: self.shutdown,
            signal.SIGTERM: self.shutdown,
        }

        for signum, handler in signal_handlers.items():
            signal.signal(signum, handler)

    def shutdown(self, signum=None, frame=None):
        if self.stop_event.is_set():
            return

        self.stop_event.set()

    def make_request(
        self,
        session,
        method,
        url,
        headers=None,
        params=None,
        payload=None,
        proxies=None,
        timeout=None,
    ):
        if self.stop_event.is_set():
            return None

        try:
            response = session.request(
                method=method,
                url=url,
                headers=headers or {},
                params=params or {},
                json=payload or {},
                proxies=proxies,
                timeout=timeout,
            )

            return response

        except KeyboardInterrupt:
            raise

        except requests.RequestsError:
            return None

    def fetch_data(self, session, site_config):
        if self.stop_event.is_set():
            return None

        url = site_config.get("URL")

        if not url:
            return None

        method = site_config.get("METHOD", "GET").upper()
        headers = deepcopy(site_config.get("HEADERS", {}))
        params = deepcopy(site_config.get("PARAMS", {}))
        payload = deepcopy(site_config.get("PAYLOAD", {}))

        if "User-Agent" not in headers:
            headers["User-Agent"] = ua.chrome

        response = self.make_request(
            session=session,
            method=method,
            url=url,
            headers=headers,
            params=params,
            payload=payload,
            timeout=self.source_timeout,
        )

        if response is None:
            return None

        if not response.ok:
            return None

        return response.text

    def normalize_proxy(self, ip, port=None, proxy=None):
        if proxy:
            return proxy

        if ip is None:
            return None

        ip = str(ip).strip()

        if not ip:
            return None

        if port is not None:
            port = str(port).strip()

            if port:
                return f"{ip}:{port}"

        return ip

    def submit_proxy(self, proxy):
        if not proxy:
            return

        if self.stop_event.is_set():
            return

        proxy = str(proxy).strip()

        if not proxy:
            return

        with self.seen_lock:
            if proxy in self.seen:
                return

            self.seen.add(proxy)

        while not self.stop_event.is_set():
            try:
                self.validation_queue.put(proxy, timeout=0.1)

                return

            except Exception:
                continue

    def validation_worker(self):
        session = requests.Session(impersonate="chrome")

        try:
            while not self.stop_event.is_set():
                try:
                    proxy = self.validation_queue.get(timeout=0.1)

                except Empty:
                    continue

                try:
                    if self.stop_event.is_set():
                        continue

                    result = self.check_working_proxy(session=session, proxy=proxy)

                    if result:
                        with self.proxy_lock:
                            if self.proxy is None:
                                self.proxy = result
                                self.result_event.set()
                                self.stop_event.set()

                finally:
                    self.validation_queue.task_done()

        finally:
            session.close()

    def check_working_proxy(self, session, proxy):
        print(proxy, flush=True)
        if self.stop_event.is_set():
            return None

        proxies = {
            "http": proxy,
            "https": proxy,
        }

        try:
            response = session.post(
                url="https://api3.pvrcinemas.com/api/v1/booking/content/city",
                params={
                    "lat": "0.000",
                    "lng": "0.000",
                },
                headers={
                    "accept": "application/json, text/plain, */*",
                    "accept-language": "en-GB,en;q=0.6",
                    "appversion": "1.0",
                    "cache-control": "no-cache",
                    "chain": "PVR",
                    "city": "",
                    "content-type": "application/json",
                    "country": "INDIA",
                    "dnt": "1",
                    "flow": "PVRINOX",
                    "origin": "https://www.pvrcinemas.com",
                    "platform": "WEBSITE",
                    "pragma": "no-cache",
                    "priority": "u=1, i",
                },
                proxies=proxies,
                timeout=self.proxy_timeout,
            )

            if response.ok:
                return proxy

        except KeyboardInterrupt:
            raise

        except requests.RequestsError:
            return None

        return None

    def process_json(self, site_config):
        data = site_config.get("DATA", "")

        if not data:
            return

        if isinstance(data, (dict, list)):
            site_config["FORMATTED_DATA"] = data
            return

        try:
            site_config["FORMATTED_DATA"] = json.loads(data)

        except Exception:
            return

    def process_html(self, site_config):
        html_config = site_config.get("RULE_HTML", {})
        html_data = site_config.get("DATA", "")

        if html_data is None:
            return

        if hasattr(html_data, "xpath"):
            site_config["FORMATTED_DATA"] = html_data
            return

        if isinstance(html_data, bytes):
            html_data = html_data.decode("utf-8", errors="ignore")

        if not isinstance(html_data, str):
            html_data = str(html_data)

        if "XPATH" not in html_config and "FIELDS" not in html_config:
            return

        try:
            tree = html.fromstring(html_data)

        except Exception:
            return

        site_config["FORMATTED_DATA"] = tree

    def process_html_pandas(self, site_config):
        html_data = site_config.get("DATA", "")
        html_config = site_config.get("RULE_HTML", {})
        index = html_config.get("INDEX", 0)

        try:
            if isinstance(html_data, str):
                tables = pd.read_html(StringIO(html_data))
            else:
                tables = pd.read_html(StringIO(str(html_data)))

        except Exception:
            return

        if index >= len(tables):
            return

        table = tables[index].copy()
        header_row = html_config.get("HEADER_ROW")
        data_start = html_config.get("DATA_START")

        if header_row is not None:
            if header_row >= len(table):
                return

            table.columns = table.iloc[header_row]

        if data_start is not None:
            table = table.iloc[data_start:].copy()

        table = table.reset_index(drop=True)

        if "FIELDS" in html_config:
            site_config["FORMATTED_DATA"] = [
                row.tolist() for _, row in table.iterrows()
            ]

            return

        json_data = json.loads(table.to_json(orient="records"))
        filters = site_config.get("FILTERS")

        if filters:
            json_data = [row for row in json_data if self.check_filters(row, filters)]

        site_config["FORMATTED_DATA"] = json_data

    def process_html_script(self, site_config):
        html_config = site_config.get("RULE_HTML", {})
        script_config = html_config.get("SCRIPT")
        html_data = site_config.get("DATA", "")

        if not script_config:
            return {}

        pattern = script_config.get("REGEX")
        separator = script_config.get("SEP", ";")
        assignment_separator = script_config.get("ASSIGNMENT", "=")

        if not pattern:
            return {}

        match = re.search(pattern, html_data, re.DOTALL)

        if not match:
            return {}

        script = match.group(1)

        variables = {}

        for item in script.split(separator):
            item = item.strip()

            if not item or assignment_separator not in item:
                continue

            key, value = item.split(assignment_separator, 1)

            key = key.strip()
            value = value.strip()

            if not key:
                continue

            try:
                variables[key] = self.evaluate_expression(value, variables)

            except Exception:
                continue

        site_config["SCRIPT_VARS"] = variables

        return variables

    def process_csv(self, site_config):
        csv_config = site_config.get("RULE_CSV", {})
        data = site_config.get("DATA", "")

        if data is None:
            return

        try:
            if isinstance(data, pd.DataFrame):
                table = data.copy()

            else:
                table = pd.read_csv(StringIO(str(data)), sep=csv_config.get("SEP", ","))

        except Exception:
            return

        header_row = csv_config.get("HEADER_ROW")
        data_start = csv_config.get("DATA_START")

        if header_row is not None:
            if header_row >= len(table):
                return

            table.columns = table.iloc[header_row]

        if data_start is not None:
            table = table.iloc[data_start:].copy()

        table = table.reset_index(drop=True)

        site_config["FORMATTED_DATA"] = json.loads(table.to_json(orient="records"))

    def get_generic_source_value(self, record, source):
        source_type = source.get("TYPE", "KEY").upper()

        if source_type == "KEY":
            if not isinstance(record, dict):
                return None

            return record.get(source.get("KEY"))

        if source_type == "COLUMN":
            index = source.get("INDEX")

            if index is None:
                return None

            try:
                return record[index]

            except Exception:
                return None

        if source_type == "XPATH":
            if not hasattr(record, "xpath"):
                return None

            value = record.xpath(source.get("XPATH", ""))

            if "INDEX" in source:
                index = source["INDEX"]

                if not isinstance(value, (list, tuple)) or len(value) <= index:
                    return None

                value = value[index]

            if isinstance(value, (list, tuple)):
                if not value:
                    return None

                value = value[0]

            if hasattr(value, "text_content"):
                value = value.text_content()

            elif hasattr(value, "text"):
                value = value.text or ""

            return value

        if source_type == "VALUE":
            return source.get("VALUE")

        if source_type == "TEXT":
            return record

        return None

    def apply_generic_extract(self, value, extract):
        if value is None or not extract:
            return value

        extract_type = extract.get("TYPE", "REGEX").upper()

        if extract_type == "REGEX":
            pattern = extract.get("PATTERN")
            group = extract.get("GROUP", 1)

            if not pattern:
                return value

            match = re.search(pattern, str(value), re.DOTALL)

            if not match:
                return None

            try:
                return match.group(group)

            except IndexError:
                return None

        return value

    def apply_generic_transform(self, value, transform, variables=None):
        if value is None or not transform:
            return value

        if isinstance(transform, str):
            transform = {"TYPE": transform}

        transform_type = transform.get("TYPE", "").upper()

        if transform_type == "BASE64":
            try:
                return base64.b64decode(str(value)).decode()

            except Exception:
                return None

        if transform_type == "STRIP":
            return str(value).strip()

        if transform_type == "EVAL_EXPRESSION":
            separator = transform.get("SEP", "+")
            parts = str(value).split(separator)
            variables = variables or {}

            result = []

            for part in parts:
                part = part.strip()

                if not part:
                    continue

                try:
                    evaluated = self.evaluate_expression(part, variables)

                except Exception:
                    return None

                result.append(str(evaluated))

            return "".join(result)

        return value

    def extract_generic_fields(self, site_config, record):
        rule = (
            site_config.get("RULE_HTML")
            or site_config.get("RULE_JSON")
            or site_config.get("RULE_TXT")
            or site_config.get("RULE_CSV")
            or {}
        )

        fields = rule.get("FIELDS", {})

        if not fields:
            return

        variables = site_config.get("SCRIPT_VARS", {})

        output = {}

        for field_name, field_config in fields.items():
            source = field_config.get("SOURCE", {})

            value = self.get_generic_source_value(record, source)
            value = self.apply_generic_extract(value, field_config.get("EXTRACT"))
            value = self.apply_generic_transform(
                value, field_config.get("TRANSFORM"), variables
            )

            if isinstance(value, str):
                value = value.strip()

            output[field_name] = value

        ip = output.get("ip")
        port = output.get("port")
        proxy = output.get("proxy")

        proxy = self.normalize_proxy(ip, port, proxy)

        if proxy:
            self.submit_proxy(proxy)

    def extract_generic(self, site_config):
        formatted_data = site_config.get("FORMATTED_DATA")

        if formatted_data is None:
            return

        filters = site_config.get("FILTERS")

        if not isinstance(formatted_data, list):
            formatted_data = [formatted_data]

        for record in formatted_data:
            if self.stop_event.is_set():
                return

            if filters and not self.check_filters(record, filters):
                continue

            self.extract_generic_fields(site_config, record)

    def safe_eval_node(self, node, variables):
        binary_operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
        }

        unary_operators = {
            ast.UAdd: operator.pos,
            ast.USub: operator.neg,
        }

        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            if node.id not in variables:
                raise NameError(node.id)

            return variables[node.id]

        if isinstance(node, ast.BinOp):
            operation = binary_operators.get(type(node.op))

            if operation is None:
                raise ValueError("Unsupported operator")

            return operation(
                self.safe_eval_node(node.left, variables),
                self.safe_eval_node(node.right, variables),
            )

        if isinstance(node, ast.UnaryOp):
            operation = unary_operators.get(type(node.op))

            if operation is None:
                raise ValueError("Unsupported unary operator")

            return operation(self.safe_eval_node(node.operand, variables))

        raise ValueError("Unsupported expression")

    def evaluate_expression(self, expression, variables=None):
        variables = variables or {}

        expression = str(expression).strip()

        if not expression:
            raise ValueError("Empty expression")

        if expression.isdigit():
            return int(expression)

        tree = ast.parse(expression, mode="eval")

        return self.safe_eval_node(tree.body, variables)

    def check_filters(self, data, filters):
        if not filters:
            return True

        def get_value(rule):
            if hasattr(data, "xpath"):
                value = data.xpath(rule["XPATH"])

                if "INDEX" in rule:
                    index = rule["INDEX"]

                    if len(value) <= index:
                        return None

                    value = value[index]

                if hasattr(value, "text_content"):
                    return value.text_content().strip()

                if hasattr(value, "text"):
                    return (value.text or "").strip()

                return str(value).strip()

            if "COLUMN" in rule:
                try:
                    return data[rule["COLUMN"]]

                except Exception:
                    return None

            if isinstance(data, dict):
                return data.get(rule.get("KEY"))

            return None

        if "AND" in filters:
            for rule in filters["AND"]:
                if get_value(rule) != rule["VALUE"]:
                    return False

        if "OR" in filters:
            matched = False

            for rule in filters["OR"]:
                if get_value(rule) == rule["VALUE"]:
                    matched = True
                    break

            if not matched:
                return False

        if "CONTAINS" in filters:
            rules = filters["CONTAINS"]

            if isinstance(rules, dict):
                rules = [rules]

            for rule in rules:
                value = get_value(rule)

                if value is None:
                    return False

                if isinstance(value, (list, tuple, set)):
                    if rule["VALUE"] not in value:
                        return False

                elif str(rule["VALUE"]) not in str(value):
                    return False

        if "EQUALS" in filters:
            rules = filters["EQUALS"]

            if isinstance(rules, dict):
                rules = [rules]

            for rule in rules:
                value = get_value(rule)

                if value is None:
                    return False

                if str(value).strip().lower() != str(rule["VALUE"]).strip().lower():
                    return False

        return True

    def extract_json(self, site_config):
        json_conf = site_config.get("RULE_JSON") or site_config.get("RULE_HTML")

        if not json_conf:
            return

        if "FIELDS" in json_conf:
            self.extract_generic(site_config)
            return

        formatted_data = site_config.get("FORMATTED_DATA", {})

        if "PARENT" in json_conf:
            for key in json_conf["PARENT"].split(","):
                if not isinstance(formatted_data, dict):
                    return

                formatted_data = formatted_data.get(key, {})

        field_keys = json_conf.get("FIELD_KEYS", {})
        filters = site_config.get("FILTERS")

        if not isinstance(formatted_data, list):
            formatted_data = [formatted_data]

        for data in formatted_data:
            if self.stop_event.is_set():
                return

            if not isinstance(data, dict):
                continue

            if filters and not self.check_filters(data, filters):
                continue

            output = {}

            for field, key in field_keys.items():
                output[field] = data.get(key)

            ip = output.get("ip")
            port = output.get("port")
            proxy = output.get("proxy")

            if "DECODE" in json_conf:
                if ip:
                    ip = self.decode(ip, json_conf["DECODE"])

                if port:
                    port = self.decode(port, json_conf["DECODE"])

            proxy = self.normalize_proxy(ip, port, proxy)

            if proxy:
                self.submit_proxy(proxy)

    def extract_html(self, site_config):
        tree = site_config.get("FORMATTED_DATA")

        if tree is None:
            return

        rule_html = site_config.get("RULE_HTML", {})
        field_keys = rule_html.get("FIELD_KEYS", {})
        xpath = rule_html.get("XPATH")

        if not xpath:
            return

        rows = tree.xpath(xpath)
        filters = site_config.get("FILTERS")

        for row in rows:
            if self.stop_event.is_set():
                return

            if filters and not self.check_filters(row, filters):
                continue

            data = {}

            for field_name, field_config in field_keys.items():
                value = row.xpath(field_config["XPATH"])

                if "INDEX" in field_config:
                    index = field_config["INDEX"]

                    if len(value) <= index:
                        value = None
                    else:
                        value = value[index]

                if value is not None and field_config.get("TEXT") == "YES":
                    if hasattr(value, "text_content"):
                        value = value.text_content().strip()

                    elif hasattr(value, "text"):
                        value = (value.text or "").strip()

                    else:
                        value = str(value).strip()

                data[field_name] = value

            ip = data.get("ip")
            port = data.get("port")
            proxy = data.get("proxy")

            if "DECODE" in rule_html:
                if ip:
                    ip = self.decode(ip, rule_html["DECODE"])

                if port:
                    port = self.decode(port, rule_html["DECODE"])

                if proxy:
                    proxy = self.decode(proxy, rule_html["DECODE"])

            proxy = self.normalize_proxy(ip, port, proxy)

            if proxy:
                self.submit_proxy(proxy)

    def process_text(self, site_config):
        txt_config = site_config.get("RULE_TXT", {})
        txt_data = site_config.get("DATA", "")
        separator = txt_config.get("SEP")

        if separator is None:
            return

        site_config["FORMATTED_DATA"] = [
            item.strip() for item in txt_data.split(separator) if item.strip()
        ]

    def extract_txt(self, site_config):
        formatted_data = site_config.get("FORMATTED_DATA", [])

        for proxy in formatted_data:
            if self.stop_event.is_set():
                return

            if proxy:
                self.submit_proxy(proxy)

    def extract_csv(self, site_config):
        csv_config = site_config.get("RULE_CSV", {})
        formatted_data = site_config.get("FORMATTED_DATA")

        if formatted_data is None:
            return

        if not isinstance(formatted_data, list):
            formatted_data = [formatted_data]

        fields = csv_config.get("FIELD_KEYS", {})
        filters = site_config.get("FILTERS")

        for row in formatted_data:
            if self.stop_event.is_set():
                return

            if not isinstance(row, dict):
                continue

            if filters and not self.check_filters(row, filters):
                continue

            ip = row.get(fields.get("ip", "ip"))
            port = row.get(fields.get("port", "port"))
            proxy = row.get(fields.get("proxy", "proxy"))

            proxy = self.normalize_proxy(ip, port, proxy)

            if proxy:
                self.submit_proxy(proxy)

    @staticmethod
    def decode(text, decode_algo):
        if text is None:
            return None

        if decode_algo == "BASE64":
            try:
                return base64.b64decode(text).decode()

            except Exception:
                return None

        return text

    def process_rule(self, site_config):
        if self.stop_event.is_set():
            return

        rule_key = next(
            (key for key in site_config if key.startswith("RULE_")),
            None,
        )

        if not rule_key:
            return

        rule_config = site_config.get(rule_key)

        if not isinstance(rule_config, dict):
            return

        if rule_key == "RULE_JSON":
            self.process_json(site_config)

        elif rule_key == "RULE_HTML":
            if rule_config.get("SCRIPT"):
                self.process_html_script(site_config)

            if rule_config.get("PANDAS") == "YES":
                self.process_html_pandas(site_config)

            else:
                self.process_html(site_config)

        elif rule_key == "RULE_TXT":
            self.process_text(site_config)

        elif rule_key == "RULE_CSV":
            self.process_csv(site_config)

        else:
            return

        nested_rule_key = next(
            (key for key in rule_config if key.startswith("RULE_")),
            None,
        )

        if nested_rule_key:
            nested_config = deepcopy(site_config)

            nested_config["DATA"] = site_config.get("FORMATTED_DATA")
            nested_config["FORMATTED_DATA"] = None

            nested_config.pop(rule_key, None)

            nested_config[nested_rule_key] = rule_config[nested_rule_key]

            self.process_rule(nested_config)

            return

        if rule_key == "RULE_JSON":
            self.extract_json(site_config)

        elif rule_key == "RULE_HTML":
            if rule_config.get("FIELDS"):
                self.extract_generic(site_config)

            elif rule_config.get("PANDAS") == "YES":
                self.extract_json(site_config)

            else:
                self.extract_html(site_config)

        elif rule_key == "RULE_TXT":
            if rule_config.get("FIELDS"):
                self.extract_generic(site_config)

            else:
                self.extract_txt(site_config)

        elif rule_key == "RULE_CSV":
            if rule_config.get("FIELDS"):
                self.extract_generic(site_config)

            else:
                self.extract_csv(site_config)

    def format_data(self, site_config):
        self.process_rule(site_config)

    def format_config(self, site_config):
        config = deepcopy(site_config)

        rule_keys = [key for key in config if key.startswith("RULE_")]

        for rule_key in rule_keys:
            child_config = config[rule_key]

            for key, value in config.items():
                if not key.startswith("RULE_"):
                    child_config.setdefault(key, value)

        return config

    def process_site(self, site):
        if self.stop_event.is_set():
            return

        site_config = self._proxy_config.get(site, {})

        if not site_config:
            return

        session = requests.Session(impersonate="chrome")

        try:
            site_config = self.format_config(site_config)
            data = self.fetch_data(session=session, site_config=site_config)

            if not data:
                return

            site_config["DATA"] = data

            self.format_data(site_config)

        except KeyboardInterrupt:
            raise

        except Exception as exc:
            print(f"[{site}] failed: {exc}", flush=True)

        finally:
            session.close()

    def source_worker(self, site):
        try:
            self.process_site(site)

        except KeyboardInterrupt:
            return

        finally:
            with self.sources_lock:
                self.sources_remaining -= 1

    def start_validation_workers(self):
        self.validation_threads = []

        for _ in range(self.proxy_workers):
            thread = Thread(target=self.validation_worker, daemon=True)

            thread.start()

            self.validation_threads.append(thread)

    def start_source_workers(self, sites):
        self.source_threads = []

        with self.sources_lock:
            self.sources_remaining = len(sites)

        for site in sites:
            if self.stop_event.is_set():
                break

            thread = Thread(target=self.source_worker, args=(site,), daemon=True)

            thread.start()

            self.source_threads.append(thread)

    def wait_for_result(self):
        while True:
            if self.result_event.wait(timeout=0.01):
                with self.proxy_lock:
                    return self.proxy

            if self.stop_event.is_set():
                with self.proxy_lock:
                    return self.proxy

            with self.sources_lock:
                sources_remaining = self.sources_remaining

            if sources_remaining == 0 and self.validation_queue.empty():
                return None

    def fetch(self, site_list=None):
        if site_list:
            sites = [site.strip() for site in site_list.split(",") if site.strip()]

        else:
            sites = list(self._proxy_config.keys())

        self.stop_event.clear()
        self.result_event.clear()

        with self.proxy_lock:
            self.proxy = None

        with self.seen_lock:
            self.seen.clear()

        self.source_threads = []
        self.validation_threads = []

        self.start_validation_workers()
        self.start_source_workers(sites)

        try:
            result = self.wait_for_result()

            if result:
                return result

            raise NoProxyFoundException("No working proxy found")

        except KeyboardInterrupt:
            self.stop_event.set()
            raise SystemExit(130)

        finally:
            self.stop_event.set()

            self.source_threads.clear()
            self.validation_threads.clear()

    def check_required(self):
        with self.proxy_lock:
            return not self.proxy


def get_new_ua():
    return ua.chrome


if __name__ == "__main__":
    proxy = Proxy(
        source_workers=20,
        proxy_workers=100,
        source_timeout=3,
        proxy_timeout=2,
    )

    try:
        result = proxy.fetch()

        if result:
            print(result, flush=True)

    except NoProxyFoundException:
        print("No working proxy found.", flush=True)

        sys.exit(1)
