import sys
import json
import time
import base64
import signal
import pandas as pd
from lxml import html
from io import StringIO
from queue import Queue
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

        self.seen = set()
        self.seen_lock = Lock()

        self.proxy_lock = Lock()

        self.validation_queue = Queue(maxsize=proxy_workers * 4)

        self.sources_remaining = 0
        self.sources_lock = Lock()

        self.source_threads = []
        self.validation_threads = []

        self.install_signal_handlers()

    def install_signal_handlers(self):
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

    def shutdown(self, signum, frame):
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
        payload = deepcopy(site_config.get("PAYLOAD", {}))
        params = deepcopy(site_config.get("PARAMS", {}))

        if "User-Agent" not in headers:
            headers["User-Agent"] = ua.chrome

        pagination = site_config.get("PAGINATION")

        if pagination:
            return self.fetch_paginated_data(
                session=session,
                method=method,
                url=url,
                headers=headers,
                params=params,
                payload=payload,
                pagination=pagination,
            )

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

    def fetch_paginated_data(
        self, session, method, url, headers, params, payload, pagination
    ):
        page_param = pagination.get("PARAM", "page")
        start_page = pagination.get("START", 1)
        max_pages = pagination.get("MAX_PAGES", 10)

        pages = []

        for page in range(start_page, start_page + max_pages):
            if self.stop_event.is_set():
                break

            current_params = deepcopy(params)
            current_payload = deepcopy(payload)

            if method == "POST":
                current_payload[page_param] = page
            else:
                current_params[page_param] = page

            response = self.make_request(
                session=session,
                method=method,
                url=url,
                headers=headers,
                params=current_params,
                payload=current_payload,
                timeout=self.source_timeout,
            )

            if response is None:
                break

            if not response.ok:
                break

            if not response.text.strip():
                break

            pages.append(response.text)

            if not self.has_more_pages(
                response.text,
                pagination,
            ):
                break

        if not pages:
            return None

        return self.merge_paginated_json(
            pages,
            pagination,
        )

    def has_more_pages(self, response_text, pagination):
        parent = pagination.get("PARENT")

        if not parent:
            return True

        try:
            data = json.loads(response_text)

        except json.JSONDecodeError, TypeError:
            return False

        current = data

        for key in parent.split(","):
            if not isinstance(current, dict):
                return False

            current = current.get(key)

            if current is None:
                return False

        if isinstance(current, list):
            return len(current) > 0

        return True

    def merge_paginated_json(self, pages, pagination):
        if len(pages) == 1:
            return pages[0]

        parent = pagination.get("PARENT")

        if not parent:
            return pages[0]

        try:
            first = json.loads(pages[0])

        except json.JSONDecodeError, TypeError:
            return pages[0]

        parent_keys = parent.split(",")

        target = first

        for key in parent_keys:
            if not isinstance(target, dict):
                return pages[0]

            target = target.get(key)

        if not isinstance(target, list):
            return pages[0]

        for page_text in pages[1:]:
            try:
                page_data = json.loads(page_text)

            except json.JSONDecodeError, TypeError:
                continue

            source = page_data

            for key in parent_keys:
                if not isinstance(source, dict):
                    source = None
                    break

                source = source.get(key)

            if isinstance(source, list):
                target.extend(source)

        return json.dumps(first)

    def normalize_proxy(self, ip, port=None):
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

        while not self.stop_event.is_set():
            try:
                proxy = self.validation_queue.get(timeout=0.1)

            except Exception:
                continue

            try:
                if self.stop_event.is_set():
                    continue

                result = self.check_working_proxy(session=session, proxy=proxy)

                if result:
                    with self.proxy_lock:
                        if self.proxy is None:
                            self.proxy = result
                            self.stop_event.set()

            finally:
                self.validation_queue.task_done()

    def check_working_proxy(self, session, proxy):
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

    def extract_proxy_ip(self, proxy):
        proxy = proxy.strip()

        if proxy.startswith("["):
            closing = proxy.find("]")

            if closing != -1:
                return proxy[1:closing]

        if proxy.count(":") == 1:
            return proxy.split(":", 1)[0]

        return proxy

    def process_json(self, site_config):
        data = site_config.get("DATA", "")

        if not data:
            return

        try:
            site_config["FORMATTED_DATA"] = json.loads(data)

        except json.JSONDecodeError, TypeError:
            return

    def process_html(self, site_config):
        html_config = site_config.get("RULE_HTML", {})

        html_data = site_config.get("DATA", "")

        if "XPATH" not in html_config:
            return

        try:
            tree = html.fromstring(html_data)

        except ValueError, TypeError:
            return

        site_config["FORMATTED_DATA"] = tree

    def process_html_pandas(self, site_config):
        html_data = site_config.get("DATA", "")
        html_config = site_config.get("RULE_HTML", {})
        index = html_config.get("INDEX", 0)

        try:
            tables = pd.read_html(StringIO(html_data))

        except ValueError, TypeError:
            return

        if index >= len(tables):
            return

        table = tables[index]
        json_data = json.loads(table.to_json(orient="records"))
        filters = site_config.get("FILTERS")

        if filters:
            json_data = [row for row in json_data if self.check_filters(row, filters)]

        site_config["FORMATTED_DATA"] = json_data

    def process_text(self, site_config):
        txt_config = site_config.get("RULE_TXT", {})
        txt_data = site_config.get("DATA", "")
        separator = txt_config.get("SEP")

        if separator is None:
            return

        site_config["FORMATTED_DATA"] = [
            item.strip() for item in txt_data.split(separator) if item.strip()
        ]

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

            return data.get(rule["KEY"])

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
        formatted_data = site_config.get("FORMATTED_DATA", {})
        json_conf = site_config.get("RULE_JSON") or site_config.get("RULE_HTML")

        if not json_conf:
            return

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

            if "DECODE" in json_conf:
                if ip:
                    ip = self.decode(ip, json_conf["DECODE"])

                if port:
                    port = self.decode(port, json_conf["DECODE"])

            proxy = self.normalize_proxy(ip, port)

            if proxy:
                self.submit_proxy(proxy)

    def extract_html(self, site_config):
        tree = site_config.get("FORMATTED_DATA")

        if tree is None:
            return

        rule_html = site_config.get("RULE_HTML", {})
        field_keys = site_config.get("FIELD_KEYS", {})
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

            if "DECODE" in rule_html:
                if ip:
                    ip = self.decode(ip, rule_html["DECODE"])

                if port:
                    port = self.decode(port, rule_html["DECODE"])

            proxy = self.normalize_proxy(ip, port)

            if proxy:
                self.submit_proxy(proxy)

    def extract_txt(self, site_config):
        formatted_data = site_config.get("FORMATTED_DATA", [])

        for proxy in formatted_data:
            if self.stop_event.is_set():
                return

            if proxy:
                self.submit_proxy(proxy)

    def decode(self, text, decode_algo):
        if text is None:
            return None

        if decode_algo == "BASE64":
            try:
                return base64.b64decode(text).decode()

            except ValueError, TypeError:
                return None

        return text

    def format_data(self, site_config):
        if "RULE_JSON" in site_config:
            self.process_json(site_config)
            self.extract_json(site_config)

            return

        if "RULE_HTML" in site_config:
            html_config = site_config.get("RULE_HTML", {})

            if html_config.get("PANDAS") == "YES":
                self.process_html_pandas(site_config)

                self.extract_json(site_config)

            else:
                self.process_html(site_config)

                self.extract_html(site_config)

            return

        if "RULE_TXT" in site_config:
            self.process_text(site_config)

            self.extract_txt(site_config)

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
            data = self.fetch_data(
                session=session,
                site_config=site_config,
            )

            if not data:
                return

            site_config["DATA"] = data

            self.format_data(site_config)

        except KeyboardInterrupt:
            raise

        except Exception as exc:
            print(f"[{site}] failed: {exc}")

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
        while not self.stop_event.is_set():
            if self.proxy:
                return self.proxy

            with self.sources_lock:
                sources_remaining = self.sources_remaining

            if sources_remaining == 0:
                if self.validation_queue.empty():
                    return None

            time.sleep(0.005)

        return self.proxy

    def fetch(self, site_list=None):
        if site_list:
            sites = [site.strip() for site in site_list.split(",") if site.strip()]

        else:
            sites = list(self._proxy_config.keys())

        self.stop_event.clear()
        self.proxy = None

        with self.seen_lock:
            self.seen.clear()

        try:
            self.start_validation_workers()
            self.start_source_workers(sites)

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

    except NoProxyFoundException:
        print("No working proxy found.")

        sys.exit(1)
