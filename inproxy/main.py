import ast
import base64
import json
import operator
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import asdict, dataclass
from io import StringIO
from threading import Event, Lock
from urllib.parse import urlsplit

import pandas as pd
from curl_cffi import requests
from fake_useragent import UserAgent
from lxml import html

try:
    from config import PROXY_CONFIG
    from exceptions import InvalidDataTypeException, NoProxyFoundException
except ImportError:
    from .config import PROXY_CONFIG
    from .exceptions import InvalidDataTypeException

ua = UserAgent()


@dataclass
class Proxy:
    ip: str
    port: int | None = None
    protocol: str = "http"
    country: str | None = None
    country_code: str | None = None
    state: str | None = None
    state_code: str | None = None
    city: str | None = None
    region: str | None = None
    continent: str | None = None
    timezone: str | None = None
    isp: str | None = None
    organization: str | None = None
    asn: int | None = None
    anonymity: str | None = None
    latency: float | None = None
    source: str | None = None
    continent_code: str | None = None
    pincode: str | None = None
    google: bool | None = None

    @property
    def proxy(self):
        protocol = (self.protocol or "http").lower()
        ip = str(self.ip).strip()

        if ":" in ip and not ip.startswith("["):
            ip = f"[{ip}]"

        if self.port is None:
            return f"{protocol}://{ip}"

        return f"{protocol}://{ip}:{self.port}"

    def __str__(self):
        return self.proxy

    def __repr__(self):
        return self.proxy

    def to_dict(self):
        data = asdict(self)
        data["proxy"] = self.proxy
        return data


class InProxy:
    _OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.BitXor: operator.xor,
        ast.LShift: operator.lshift,
        ast.RShift: operator.rshift,
        ast.BitOr: operator.or_,
        ast.BitAnd: operator.and_,
    }

    _UNARY_OPERATORS = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
        ast.Invert: operator.invert,
    }

    def __init__(self, source_workers=20, source_timeout=3):
        self._proxy_config = deepcopy(PROXY_CONFIG)
        self._source_workers = source_workers
        self.source_timeout = source_timeout
        self.output = {}
        self.output_count = 0
        self.set_lock = Lock()
        self.count_lock = Lock()
        self.stop_event = Event()
        self.count = 0
        self.filters = {}

    def _normalize_sites(self, sites):
        if isinstance(sites, str):
            return [site.lower().strip() for site in sites.split(",") if site.strip()]

        if isinstance(sites, list):
            return [site.lower().strip() for site in sites]

        return list(self._proxy_config.keys())

    def _validate_sites(self, sites):
        unknown = [site for site in sites if site not in self._proxy_config]

        if unknown:
            raise InvalidDataTypeException(
                f"Unknown sources: {unknown}\n"
                f"Available sources: {list(self._proxy_config.keys())}"
            )

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
        try:
            kwargs = {
                "method": method,
                "url": url,
                "headers": headers or {},
                "params": params or {},
                "timeout": timeout,
                "impersonate": "chrome",
            }

            if proxies:
                kwargs["proxies"] = proxies

            if payload is not None:
                kwargs["json"] = payload

            return session.request(**kwargs)

        except KeyboardInterrupt:
            raise

        except requests.RequestsError:
            return None

    def fetch_data(self, session, url, site_config):
        method = site_config.get("METHOD", "GET").upper()
        headers = deepcopy(site_config.get("HEADERS", {}))
        params = deepcopy(site_config.get("PARAMS", {}))
        payload = deepcopy(site_config.get("PAYLOAD"))
        timeout = deepcopy(site_config.get("TIMEOUT", self.source_timeout))

        if not any(key.lower() == "user-agent" for key in headers):
            headers["User-Agent"] = ua.chrome

        response = self.make_request(
            session=session,
            method=method,
            url=url,
            headers=headers,
            params=params,
            payload=payload,
            timeout=timeout,
        )

        if response is None or not response.ok:
            return None

        encoding = site_config.get("ENCODING")

        if encoding:
            try:
                return response.content.decode(encoding, errors="replace")
            except (LookupError, UnicodeDecodeError):
                pass

        return response.text

    def extract_path(self, data, path):
        if path is None or path == "":
            return data

        if isinstance(path, dict):
            return self.extract_field(data, path)

        if isinstance(path, (list, tuple)):
            path = ",".join(map(str, path))

        if not isinstance(path, str):
            return None

        for key in path.split(","):
            key = key.strip()

            try:
                if isinstance(data, dict):
                    if key in data:
                        data = data[key]
                    elif key.isdigit() and int(key) in data:
                        data = data[int(key)]
                    else:
                        return None

                elif isinstance(data, (list, tuple)):
                    if not key.isdigit():
                        return None

                    data = data[int(key)]

                else:
                    return None

            except (KeyError, IndexError, ValueError, TypeError):
                return None

        return data

    def _xpath_value(self, node, xpath, index=0, text=False):
        if not xpath:
            return None

        try:
            values = node.xpath(xpath)

            if not isinstance(values, list):
                values = [values]

            if not 0 <= index < len(values):
                return None

            value = values[index]

            if isinstance(value, bytes):
                return value.decode(errors="replace").strip()

            if isinstance(value, str):
                return value.strip()

            if hasattr(value, "text_content"):
                return value.text_content().strip()

            if text:
                return str(value).strip()

            return value

        except (ValueError, TypeError, IndexError):
            return None

    def _decode_value(self, value, encoding):
        if value is None:
            return None

        if not isinstance(value, str):
            return value

        encoding = str(encoding).upper()

        if encoding == "BASE64":
            try:
                padded = value.strip()
                padded += "=" * (-len(padded) % 4)
                decoded = base64.b64decode(padded).decode("utf-8", errors="replace")
                return decoded.strip()
            except Exception:
                return value

        return value

    def _safe_eval(self, expression, variables=None):
        variables = variables or {}

        if isinstance(expression, (int, float)):
            return expression

        if not isinstance(expression, str):
            raise InvalidDataTypeException("Invalid expression")

        tree = ast.parse(expression.strip(), mode="eval")

        def evaluate(node):
            if isinstance(node, ast.Expression):
                return evaluate(node.body)

            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)):
                    return node.value
                raise InvalidDataTypeException("Invalid expression value")

            if isinstance(node, ast.Name):
                if node.id in variables and isinstance(
                    variables[node.id], (int, float)
                ):
                    return variables[node.id]

                raise InvalidDataTypeException(
                    f"Unknown expression variable: {node.id}"
                )

            if isinstance(node, ast.BinOp):
                operation = self._OPERATORS.get(type(node.op))

                if operation is None:
                    raise InvalidDataTypeException("Unsupported operator")

                left = evaluate(node.left)
                right = evaluate(node.right)

                if isinstance(node.op, ast.Pow) and abs(right) > 10:
                    raise InvalidDataTypeException("Exponent too large")

                return operation(left, right)

            if isinstance(node, ast.UnaryOp):
                operation = self._UNARY_OPERATORS.get(type(node.op))

                if operation is None:
                    raise InvalidDataTypeException("Unsupported unary operator")

                return operation(evaluate(node.operand))

            raise InvalidDataTypeException("Unsupported expression")

        result = evaluate(tree)

        if not isinstance(result, (int, float)):
            raise InvalidDataTypeException("Invalid expression result")

        return result

    def _extract_regex(self, value, config):
        if value is None:
            return None

        if not isinstance(value, str):
            value = str(value)

        pattern = config.get("PATTERN")

        if not pattern:
            return None

        match = re.search(pattern, value, re.DOTALL)

        if not match:
            return None

        group = config.get("GROUP", 1)

        try:
            return match.group(group)
        except (IndexError, KeyError):
            return None

    def _get_source_value(self, data, config):
        if not isinstance(config, dict):
            return self.extract_path(data, config)

        source = config.get("SOURCE")

        if source is None:
            if "XPATH" in config:
                return self._xpath_value(
                    data,
                    config.get("XPATH"),
                    config.get("INDEX", 0),
                    config.get("TEXT") == "YES",
                )

            return self.extract_path(data, config)

        source_type = str(source.get("TYPE", "")).upper()

        if source_type == "KEY":
            value = self.extract_path(data, source.get("KEY"))

        elif source_type == "COLUMN":
            index = source.get("INDEX", 0)

            try:
                if hasattr(data, "iloc"):
                    value = data.iloc[index]
                elif isinstance(data, dict):
                    value = list(data.values())[index]
                else:
                    value = data[index]
            except (IndexError, KeyError, TypeError):
                value = None

        elif source_type == "XPATH":
            value = self._xpath_value(
                data, source.get("XPATH"), source.get("INDEX", 0), True
            )

        else:
            value = None

        if source.get("RAW") != "YES" and isinstance(value, str):
            value = value.strip()

        return value

    def _transform_value(self, value, field_config, site_config=None):
        if value is None:
            return None

        decode = field_config.get("DECODE")

        if decode:
            value = self._decode_value(value, decode)

        extract = field_config.get("EXTRACT")

        if extract:
            extract_type = str(extract.get("TYPE", "")).upper()

            if extract_type == "REGEX":
                value = self._extract_regex(value, extract)

        transform = field_config.get("TRANSFORM")

        if transform and value is not None:
            transform_type = str(transform.get("TYPE", "")).upper()

            if transform_type == "EVAL_EXPRESSION":
                separator = transform.get("SEP")
                variables = (site_config or {}).get("SCRIPT_VARS", {})

                if isinstance(value, str):
                    value = value.strip()

                    if separator and separator in value:
                        value = value.split(separator)[-1].strip()

                    expressions = re.findall(r"\(([^()]*)\)", value)

                    if expressions:
                        value = "".join(
                            str(self._safe_eval(expression, variables))
                            for expression in expressions
                        )
                    else:
                        value = self._safe_eval(value, variables)
                else:
                    value = self._safe_eval(value, variables)

        return value

    def extract_field(self, data, field_config, site_config=None):
        if not isinstance(field_config, dict):
            return self.extract_path(data, field_config)

        value = self._get_source_value(data, field_config)

        if value is None:
            return None

        return self._transform_value(value, field_config, site_config)

    def _parse_script(self, data, script_config, site_config=None):
        if not isinstance(data, str):
            return None

        pattern = script_config.get("REGEX")
        value = data

        if pattern:
            match = re.search(pattern, data, re.DOTALL)

            if match:
                group = script_config.get("GROUP", 1)

                try:
                    value = match.group(group)
                except (IndexError, KeyError):
                    value = match.group(0)

        script_type = str(script_config.get("TYPE", "")).upper()

        if script_type == "JSON":
            candidates = [value, value.strip().rstrip(";")]

            for candidate in candidates:
                try:
                    return json.loads(candidate)
                except (json.JSONDecodeError, TypeError):
                    continue

            return None

        variables = {}

        assignment_pattern = re.compile(
            r"(?:\b(?:var|let|const)\s+)?([A-Za-z_$][\w$]*)\s*=\s*([^;]+);"
        )

        assignments = assignment_pattern.findall(data)
        pending = list(assignments)

        for _ in range(len(pending) + 1):
            unresolved = []
            changed = False

            for name, expression in pending:
                expression = expression.strip()
                expression = re.sub(
                    r"\bparseInt\s*\(\s*([^()]+)\s*\)", r"(\1)", expression
                )

                try:
                    variables[name] = self._safe_eval(expression, variables)
                    changed = True

                except (
                    SyntaxError,
                    ValueError,
                    TypeError,
                    InvalidDataTypeException,
                    ZeroDivisionError,
                ):
                    unresolved.append((name, expression))

            pending = unresolved

            if not pending or not changed:
                break

        if site_config is not None:
            site_config["SCRIPT_VARS"] = variables

        return value

    def _decode_indexed_json(self, data):
        if not isinstance(data, list) or len(data) < 3:
            return data

        records = []

        for item in data:
            if not isinstance(item, dict):
                continue

            record = {}

            for key, index in item.items():
                if (
                    isinstance(index, int)
                    and not isinstance(index, bool)
                    and 0 <= index < len(data)
                ):
                    record[key] = data[index]

            if "ip" in record and "port" in record:
                records.append(record)

        return records

    def _parse_json(self, site_config):
        data = site_config.get("DATA", "")

        try:
            formatted = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            formatted = {}

        rule = site_config.get("RULE_JSON", {})

        if rule.get("INDEXED") == "YES":
            formatted = self._decode_indexed_json(formatted)

        site_config["FORMATTED_DATA"] = formatted

        nested_html = rule.get("RULE_HTML")

        if nested_html:
            html_data = self.extract_path(formatted, rule.get("PARENT"))

            if isinstance(html_data, str):
                nested_config = {
                    "DATA": html_data,
                    "RULE_HTML": nested_html,
                    "SOURCE": site_config.get("SOURCE"),
                }

                self._parse_html(nested_config)

                site_config["FORMATTED_DATA"] = nested_config.get("FORMATTED_DATA", [])

    def _parse_html(self, site_config):
        data = site_config.get("DATA", "")
        rule = site_config.get("RULE_HTML", {})

        if not isinstance(data, str) or not data.strip():
            site_config["FORMATTED_DATA"] = []
            return

        script_config = rule.get("SCRIPT")

        if script_config:
            script_data = self._parse_script(data, script_config, site_config)

            if str(script_config.get("TYPE", "")).upper() == "JSON":
                site_config["FORMATTED_DATA"] = (
                    script_data if isinstance(script_data, list) else []
                )
                return

        if rule.get("REGEX"):
            try:
                rows = re.findall(rule["REGEX"], data, re.DOTALL)
                result = []

                for row in rows:
                    if isinstance(row, tuple):
                        row = "".join(str(value) for value in row)

                    item = {}

                    for key, field_config in rule.get("FIELD_KEYS", {}).items():
                        if isinstance(field_config, dict):
                            item[key] = self._transform_value(
                                row,
                                field_config,
                                site_config,
                            )
                        else:
                            item[key] = self._extract_regex(
                                row,
                                {"PATTERN": field_config},
                            )

                    result.append(item)

                site_config["FORMATTED_DATA"] = result

            except (re.error, TypeError, AttributeError):
                site_config["FORMATTED_DATA"] = []

            return

        if rule.get("PANDAS") == "YES":
            self._parse_html_pandas(site_config)
            return

        xpath = rule.get("XPATH")

        if not xpath:
            site_config["FORMATTED_DATA"] = []
            return

        try:
            tree = html.fromstring(data)
            rows = tree.xpath(xpath)
            result = []

            for row in rows:
                item = {}

                for key, field_config in rule.get("FIELD_KEYS", {}).items():
                    item[key] = self.extract_field(
                        row,
                        field_config,
                        site_config,
                    )

                result.append(item)

            site_config["FORMATTED_DATA"] = result

        except (ValueError, TypeError, KeyError) as e:
            site_config["FORMATTED_DATA"] = []
            print(f"HTML parsing failed: {e}")

    def _parse_html_pandas(self, site_config):
        data = site_config.get("DATA", "")
        rule = site_config.get("RULE_HTML", {})
        table_index = rule.get("INDEX", 0)

        try:
            tables = pd.read_html(StringIO(data))

            if not 0 <= table_index < len(tables):
                site_config["FORMATTED_DATA"] = []
                return

            table = tables[table_index]
            table.columns = [str(column).strip() for column in table.columns]

            records = table.to_dict(orient="records")
            data_start = int(rule.get("DATA_START", 0) or 0)
            records = records[max(data_start, 0) :]

            site_config["FORMATTED_DATA"] = records

        except (ValueError, TypeError, ImportError, IndexError):
            site_config["FORMATTED_DATA"] = []

    def _parse_txt(self, site_config):
        data = site_config.get("DATA", "")
        rule = site_config.get("RULE_TXT", {})

        if not isinstance(data, str):
            site_config["FORMATTED_DATA"] = []
            return

        separator = rule.get("SEP", rule.get("SEPARATOR", "\n"))

        if not separator:
            separator = "\n"

        site_config["FORMATTED_DATA"] = [
            item.strip() for item in data.split(separator) if item.strip()
        ]

    def process_rules(self, site_config):
        for key in list(site_config):
            if not key.startswith("RULE_"):
                continue

            rule_type = key[5:]

            if rule_type == "JSON":
                self._parse_json(site_config)

            elif rule_type == "HTML":
                self._parse_html(site_config)

            elif rule_type == "TXT":
                self._parse_txt(site_config)

        return site_config

    def _normalize_proxy_url(self, value):
        if not isinstance(value, str):
            return None

        value = value.strip()

        if not value or "://" not in value:
            return None

        try:
            parsed = urlsplit(value)

            if not parsed.hostname:
                return None

            protocol = parsed.scheme.lower()

            if protocol not in (
                "http",
                "https",
                "socks4",
                "socks5",
                "socks4a",
                "socks5h",
            ):
                return None

            return {
                "ip": parsed.hostname,
                "port": parsed.port,
                "protocol": protocol,
            }

        except ValueError:
            return None

    def _normalize_proxy_address(self, value):
        if not isinstance(value, str):
            return None

        value = value.strip()

        if not value:
            return None

        full_url = self._normalize_proxy_url(value)

        if full_url:
            return full_url

        match = re.match(
            r"^(?P<ip>\[[^\]]+\]|[^:\s]+):(?P<port>\d+)$",
            value,
        )

        if not match:
            return None

        ip = match.group("ip").strip("[]")
        port = int(match.group("port"))

        if not 1 <= port <= 65535:
            return None

        return {"ip": ip, "port": port}

    def create_ip_object(self, ip_data, extraction_keys, site_config=None):
        if not isinstance(ip_data, dict):
            raise InvalidDataTypeException("Invalid proxy data")

        field_keys = extraction_keys.get("FIELD_KEYS", extraction_keys)
        field_keys = {
            field: config
            for field, config in field_keys.items()
            if field in Proxy.__dataclass_fields__
        }

        list_path = None

        for field_config in field_keys.values():
            if not isinstance(field_config, str):
                continue

            keys = [key.strip() for key in field_config.split(",") if key.strip()]
            current = ip_data

            for index, key in enumerate(keys[:-1]):
                if isinstance(current, dict):
                    current = current.get(key)
                elif isinstance(current, (list, tuple)):
                    break
                else:
                    break

                if isinstance(current, (list, tuple)):
                    list_path = ",".join(keys[:index + 1])
                    break

            if list_path:
                break

        records = self.extract_path(ip_data, list_path) if list_path else [ip_data]

        if isinstance(records, dict):
            records = [records]

        if not isinstance(records, (list, tuple)):
            records = [ip_data]

        proxies = []

        for record in records:
            if not isinstance(record, dict):
                continue

            proxy_data = {}

            for field, field_config in field_keys.items():
                if isinstance(field_config, str) and list_path:
                    prefix = list_path + ","

                    if field_config.startswith(prefix):
                        field_config = field_config[len(prefix):]
                        source_data = record
                    else:
                        source_data = ip_data
                else:
                    source_data = record if not list_path else ip_data

                value = self.extract_field(source_data, field_config, site_config)

                if value is not None and value != "":
                    proxy_data[field] = value

            if not proxy_data.get("ip"):
                continue

            proxy_value = str(proxy_data["ip"]).strip()
            normalized = self._normalize_proxy_address(proxy_value)

            if normalized:
                proxy_data["ip"] = normalized["ip"]

                if normalized.get("port") is not None:
                    proxy_data["port"] = normalized["port"]

                if normalized.get("protocol"):
                    proxy_data["protocol"] = normalized["protocol"]
            else:
                proxy_data["ip"] = proxy_value.strip("[]")

            if proxy_data.get("port") is not None:
                proxy_data["port"] = int(proxy_data["port"])

                if not 1 <= proxy_data["port"] <= 65535:
                    continue

            if proxy_data.get("asn") is not None:
                proxy_data["asn"] = int(
                    re.sub(
                        r"^AS",
                        "",
                        str(proxy_data["asn"]).strip(),
                        flags=re.IGNORECASE,
                    )
                )

            if proxy_data.get("latency") is not None:
                proxy_data["latency"] = float(proxy_data["latency"])

            if "protocol" in proxy_data:
                protocol = proxy_data["protocol"]

                if isinstance(protocol, (list, tuple)):
                    protocol = protocol[0] if protocol else None

                protocol = str(protocol).strip().lower() if protocol is not None else None

                if protocol not in {
                    "http",
                    "https",
                    "socks4",
                    "socks5",
                    "socks4a",
                    "socks5h",
                }:
                    proxy_data.pop("protocol", None)
                else:
                    proxy_data["protocol"] = protocol

            try:
                proxies.append(Proxy(**proxy_data))
            except (TypeError, ValueError):
                continue

        if not proxies:
            raise InvalidDataTypeException(f"Proxy IP is missing. Input: {ip_data}")

        for proxy in proxies[1:]:
            self._collect_proxy(proxy)

        return proxies[0]

    def _collect_proxy(self, proxy):
        if self.stop_event.is_set():
            return False

        if not self._matches_filters(proxy):
            return False

        with self.set_lock:
            if self.stop_event.is_set():
                return False

            if proxy.proxy in self.output:
                return False

            if self.output_count >= self.count:
                self.stop_event.set()
                return False

            self.output[proxy.proxy] = proxy
            self.output_count += 1

            if self.output_count >= self.count:
                self.stop_event.set()

            return True

    def _extract_proxies(self, data, extraction_keys, site_config=None):
        if data is None:
            return

        parent = extraction_keys.get("PARENT")

        if parent:
            data = self.extract_path(data, parent)

        if isinstance(data, dict):
            data = [data]

        if not isinstance(data, (list, tuple)):
            return

        for item in data:
            if self.stop_event.is_set():
                break

            if not isinstance(item, dict):
                continue

            try:
                proxy = self.create_ip_object(item, extraction_keys, site_config)
                self._collect_proxy(proxy)
            except (TypeError, ValueError, InvalidDataTypeException):
                continue

    def _extract_txt_proxies(self, data, extraction_keys):
        if not isinstance(data, list):
            return

        pattern = extraction_keys.get(
            "REGEX",
            extraction_keys.get(
                "PATTERN",
                r"(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s*:\s*(?P<port>\d+)",
            ),
        )

        source_url = str(extraction_keys.get("SOURCE_URL", "")).lower()
        protocol = extraction_keys.get("PROTOCOL")

        if not protocol:
            if "socks5" in source_url:
                protocol = "socks5"
            elif "socks4" in source_url:
                protocol = "socks4"
            elif "http" in source_url:
                protocol = "http"
            else:
                protocol = "http"

        field_keys = {
            "ip": "ip",
            "port": "port",
            "protocol": "protocol",
        }

        field_keys.update(extraction_keys.get("FIELD_KEYS", {}))
        object_config = {"FIELD_KEYS": field_keys}

        for item in data:
            if self.stop_event.is_set():
                break

            if not isinstance(item, str):
                continue

            item = item.strip()

            if not item:
                continue

            match = re.search(pattern, item)

            if match:
                proxy_data = {
                    key: value
                    for key, value in match.groupdict().items()
                    if value is not None
                }

                if not proxy_data.get("ip") or not proxy_data.get("port"):
                    if match.lastindex and match.lastindex >= 2:
                        proxy_data = {
                            "ip": match.group(1),
                            "port": match.group(2),
                        }
                    else:
                        proxy_data = self._normalize_proxy_address(
                            match.group(0).strip()
                        )

            else:
                proxy_data = self._normalize_proxy_address(item)

            if not isinstance(proxy_data, dict):
                continue

            proxy_data.setdefault("protocol", protocol)

            try:
                proxy = self.create_ip_object(
                    proxy_data,
                    object_config,
                )

                self._collect_proxy(proxy)

            except (TypeError, ValueError, InvalidDataTypeException):
                continue

    def extract_keys(self, site_config):
        source = site_config.get("SOURCE")
        formatted_data = site_config.get("FORMATTED_DATA")

        if source not in self._proxy_config:
            return

        if not isinstance(formatted_data, (list, tuple, dict)):
            return

        rule_type = next(
            (key for key in site_config if key.startswith("RULE_")),
            None,
        )

        if not rule_type:
            return

        extraction_keys = site_config.get(rule_type, {})

        if rule_type == "RULE_TXT":
            self._extract_txt_proxies(
                formatted_data,
                extraction_keys,
            )

        elif rule_type == "RULE_HTML" and extraction_keys.get("REGEX"):
            normalized_keys = {
                "FIELD_KEYS": {
                    key: key for key in extraction_keys.get("FIELD_KEYS", {})
                }
            }

            self._extract_proxies(
                formatted_data,
                normalized_keys,
                site_config,
            )

        elif (
            rule_type == "RULE_HTML"
            and extraction_keys.get("XPATH")
            and extraction_keys.get("PANDAS") != "YES"
            and not extraction_keys.get("SCRIPT")
        ):
            normalized_keys = {
                "FIELD_KEYS": {
                    key: key for key in extraction_keys.get("FIELD_KEYS", {})
                }
            }

            self._extract_proxies(
                formatted_data,
                normalized_keys,
                site_config,
            )

        elif rule_type == "RULE_JSON" and extraction_keys.get("RULE_HTML"):
            nested_keys = extraction_keys["RULE_HTML"].get(
                "FIELD_KEYS",
                {},
            )

            normalized_keys = {"FIELD_KEYS": {key: key for key in nested_keys}}

            self._extract_proxies(
                formatted_data,
                normalized_keys,
                site_config,
            )

        else:
            self._extract_proxies(
                formatted_data,
                extraction_keys,
                site_config,
            )

    def _matches_filters(self, proxy):
        for field in (
            "country",
            "country_code",
            "state",
            "state_code",
            "city",
            "region",
            "continent",
            "timezone",
            "isp",
            "organization",
            "anonymity",
        ):
            expected = self.filters.get(field)

            if expected is None:
                continue

            actual = getattr(proxy, field)

            if actual is None:
                return False

            if isinstance(expected, str):
                if expected.lower() not in str(actual).lower():
                    return False

            elif isinstance(expected, (list, tuple, set)):
                if not any(
                    str(value).lower() == str(actual).lower() for value in expected
                ):
                    return False

        asn = self.filters.get("asn")

        if asn is not None and proxy.asn != asn:
            return False

        min_latency = self.filters.get("min_latency")

        if min_latency is not None:
            if proxy.latency is None or proxy.latency < min_latency:
                return False

        max_latency = self.filters.get("max_latency")

        if max_latency is not None:
            if proxy.latency is None or proxy.latency > max_latency:
                return False

        return True

    def format_data(self, site_config):
        self.process_rules(site_config)
        self.extract_keys(site_config)

    def process_site(self, site, url, site_config):
        if self.stop_event.is_set():
            return

        session = requests.Session(impersonate="chrome")

        try:
            site_config["SOURCE"] = site

            if isinstance(site_config.get("RULE_TXT"), dict):
                site_config["RULE_TXT"]["SOURCE_URL"] = url

            data = self.fetch_data(session, url, site_config)

            if not data or self.stop_event.is_set():
                return

            site_config["DATA"] = data
            self.format_data(site_config)

        finally:
            session.close()

    def _start_source(self, job):
        import traceback

        site, url, site_config = job

        try:
            self.process_site(site, url, site_config)

        except KeyboardInterrupt:
            raise

        except Exception as e:
            print(
                f"Worker error | source={site} | "
                f"url={url} | error={type(e).__name__}: {e}"
            )

            traceback.print_exc()

    def format_config(self, site_config):
        site_config = deepcopy(site_config)

        for key, value in site_config.items():
            if key.startswith("RULE_") and isinstance(value, dict):
                parent_config = {k: v for k, v in value.items() if k != "FIELD_KEYS"}

                for config_key, config_value in site_config.items():
                    if config_key != key:
                        parent_config.setdefault(
                            config_key,
                            config_value,
                        )

                for field_config in value.get("FIELD_KEYS", {}).values():
                    if isinstance(field_config, dict):
                        field_config.update(
                            {
                                k: v
                                for k, v in parent_config.items()
                                if k not in field_config
                            }
                        )

        return site_config

    def _start_source_worker(self, sites):
        jobs = []

        for site in sites:
            site_config = self._proxy_config.get(site, {})
            urls = site_config.get("URL", [])

            if isinstance(urls, str):
                urls = [urls]

            for url in urls:
                jobs.append((site, url, self.format_config(site_config)))

        if not jobs:
            return

        executor = ThreadPoolExecutor(max_workers=self._source_workers)

        futures = [executor.submit(self._start_source, job) for job in jobs]

        try:
            for future in as_completed(futures):
                try:
                    future.result()

                except Exception as e:
                    print(f"Worker error: {type(e).__name__}: {e}")

                if self.stop_event.is_set():
                    for pending in futures:
                        pending.cancel()

                    break

        except KeyboardInterrupt:
            self.stop_event.set()

            for pending in futures:
                pending.cancel()

            executor.shutdown(
                wait=False,
                cancel_futures=True,
            )

            raise

        else:
            executor.shutdown(
                wait=True,
                cancel_futures=True,
            )

    def fetch(
        self,
        count: int = 1,
        sites: str | list | None = None,
        country: str | None = None,
        country_code: str | None = None,
        state: str | None = None,
        state_code: str | None = None,
        city: str | None = None,
        region: str | None = None,
        continent: str | None = None,
        timezone: str | None = None,
        isp: str | None = None,
        organization: str | None = None,
        asn: int | None = None,
        anonymity: str | None = None,
        min_latency: float | None = None,
        max_latency: float | None = None,
        google: bool | None = None,
    ):
        if not isinstance(count, int) or isinstance(count, bool):
            raise InvalidDataTypeException("Count must be an integer")

        if count < 1:
            raise InvalidDataTypeException("Count must be greater than 0")

        if min_latency is not None and max_latency is not None:
            if min_latency > max_latency:
                raise InvalidDataTypeException("min_latency cannot exceed max_latency")

        self.count = count
        self.output = {}
        self.output_count = 0
        self.stop_event.clear()

        self.filters = {
            "country": country,
            "country_code": country_code,
            "state": state,
            "state_code": state_code,
            "city": city,
            "region": region,
            "continent": continent,
            "timezone": timezone,
            "isp": isp,
            "organization": organization,
            "asn": asn,
            "anonymity": anonymity,
            "min_latency": min_latency,
            "max_latency": max_latency,
            "google": google,
        }

        sites = self._normalize_sites(sites)
        self._validate_sites(sites)

        self._start_source_worker(sites)

        return list(self.output.values())
