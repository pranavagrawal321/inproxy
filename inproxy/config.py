PROXY_CONFIG = {
    "proxyscrape": {
        "URL": "https://api.proxyscrape.com/v4/free-proxy-list/get",
        "PARAMS": {
            "request": "display_proxies",
            "proxy_format": "protocolipport",
            "format": "json",
        },
        "RULE_JSON": {
            "PARENT": "proxies",
            "FIELD_KEYS": {
                "ip": "ip",
                "port": "port",
                "protocol": "protocol",
                "anonymity": "anonymity",
                "organization": "ip_data,org",
                "isp": "ip_data,isp",
                "city": "ip_data,city",
                "continent": "ip_data,continent",
                "continent_code": "ip_data,continentCode",
                "country": "ip_data,country",
                "country_code": "ip_data,countryCode",
                "state": "ip_data,regionName",
                "timezone": "ip_data,timezone",
                "pincode": "ip_data,zip",
            },
        },
    },
    "geonix": {
        "URL": "https://free.geonix.com/api/front/main/pagination/filtration",
        "PAYLOAD": {
            "page": 1,
            "size": 500,
            "countries": [],
            "proxyProtocols": [],
            "proxyTypes": [],
        },
        "HEADERS": {
            "Content-Type": "application/json",
        },
        "METHOD": "POST",
        "RULE_JSON": {
            "PARENT": "content",
            "FIELD_KEYS": {
                "ip": "ip",
            },
        },
    },
    "geonode": {
        "URL": "https://proxylist.geonode.com/api/proxy-list",
        "PARAMS": {
            "page": "1",
            "limit": "500",
            "sort_by": "responseTime",
            "sort_type": "asc",
        },
        "RULE_JSON": {
            "PARENT": "data",
            "FIELD_KEYS": {
                "ip": "ip",
                "port": "port",
            },
        },
    },
    "proxyfreeonly": {
        "URL": "https://proxyfreeonly.com/api/free-proxy-list",
        "PARAMS": {
            "limit": "500",
            "page": "1",
            "sortBy": "lastChecked",
            "sortType": "desc",
        },
        "RULE_JSON": {
            "FIELD_KEYS": {
                "ip": "ip",
                "port": "port",
            },
        },
    },
    "freeproxyupdate": {
        "URL": "https://freeproxyupdate.com/",
        "RULE_HTML": {
            "PANDAS": "YES",
            "INDEX": 0,
            "FIELD_KEYS": {
                "ip": "IP address",
                "port": "Port",
            },
        },
    },
    "advanced_name": {
        "URL": "https://advanced.name/freeproxy",
        "RULE_HTML": {
            "XPATH": '//table[@id="table_proxies"]/tbody/tr',
            "DECODE": "BASE64",
            "FIELD_KEYS": {
                "ip": {
                    "XPATH": "./td[2]/@data-ip",
                    "INDEX": 0,
                },
                "port": {
                    "XPATH": "./td[3]/@data-port",
                    "INDEX": 0,
                },
            },
        },
    },
    "chillyproxy": {
        "URL": "https://chillyproxy.com/api/tools/free-proxies",
        "RULE_TXT": {
            "SEP": "\n",
        },
    },
    "free_proxy_list": {
        "URL": "https://free-proxy-list.net/en/",
        "RULE_HTML": {
            "XPATH": "//tbody/tr",
            "FIELD_KEYS": {
                "ip": {
                    "XPATH": "./td",
                    "INDEX": 0,
                    "TEXT": "YES",
                },
                "port": {
                    "XPATH": "./td",
                    "INDEX": 1,
                    "TEXT": "YES",
                },
            },
        },
    },
    "fineproxy": {
        "URL": "https://fineproxy.org/data/free-proxies/all.json",
        "RULE_JSON": {
            "PARENT": "rows",
            "FIELD_KEYS": {
                "ip": "ip",
                "port": "port",
            },
        },
    },
    "freeproxydb": {
        "URL": "https://freeproxydb.com/api/proxy/search?country=&protocol=http,socks4,socks5&anonymity=&speed=0,60&https=1&page_index=1&page_size=100",
        "RULE_JSON": {
            "PARENT": "data,data",
            "FIELD_KEYS": {
                "ip": "ip",
                "port": "port",
            },
        },
    },
    "freevpnnode": {
        "URL": [
            "https://www.freevpnnode.com/free-proxy/",
            "https://www.freevpnnode.com/free-vpn/",
        ],
        "RULE_HTML": {
            "PANDAS": "YES",
            "INDEX": 0,
            "FIELD_KEYS": {
                "ip": "IP Address",
                "port": "Port",
            },
        },
    },
    "freeproxy": {
        "URL": "https://www.freeproxy.world/",
        "RULE_HTML": {
            "PANDAS": "YES",
            "INDEX": 0,
            "FIELD_KEYS": {
                "ip": "IP Address",
                "port": "Port",
            },
        },
    },
    "proxyhub": {
        "URL": "https://proxyhub.me/",
        "RULE_HTML": {
            "PANDAS": "YES",
            "INDEX": 0,
            "FIELD_KEYS": {
                "ip": "IP",
                "port": "Port",
            },
        },
    },
    "proxydb": {
        "URL": "https://proxydb.net/",
        "RULE_HTML": {
            "PANDAS": "YES",
            "INDEX": 0,
            "FIELD_KEYS": {
                "ip": "IP",
                "port": "Port",
            },
        },
    },
    "proxifly": {
        "URL": "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/all/data.json",
        "RULE_JSON": {
            "FIELD_KEYS": {
                "ip": "proxy",
            },
        },
    },
    "proxydaily": {
        "URL": "https://proxy-daily.com/api/serverside/proxies",
        "HEADERS": {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-language": "en-GB,en;q=0.5",
            "dnt": "1",
            "priority": "u=1, i",
            "referer": "https://proxy-daily.com/",
        },
        "PARAMS": {
            "draw": "3",
            "start": "0",
            "length": "100",
        },
        "RULE_JSON": {
            "PARENT": "data",
            "FIELD_KEYS": {
                "ip": "ip",
                "port": "port",
            },
        },
    },
    "proxiware": {
        "URL": "https://papi.proxiware.com/proxies",
        "RULE_JSON": {
            "PARENT": "proxies",
            "FIELD_KEYS": {
                "ip": "addr",
                "port": "port",
            },
        },
    },
    "proxyspace": {
        "URL": "https://proxyspace.pro/https.txt",
        "RULE_TXT": {
            "SEP": "\n",
        },
    },
    "roundproxies": {
        "URL": "https://roundproxies.com/api/get-free-proxies/",
        "RULE_JSON": {
            "PARENT": "data",
            "FIELD_KEYS": {
                "ip": "ip",
                "port": "port",
            },
        },
    },
    "spys_one": {
        "URL": "https://spys.one/en/free-proxy-list/",
        "TIMEOUT": 30,
        "RULE_HTML": {
            "PANDAS": "YES",
            "INDEX": 1,
            "DATA_START": 2,
            "SCRIPT": {
                "TYPE": "VARIABLES",
            },
            "FIELD_KEYS": {
                "ip": {
                    "SOURCE": {
                        "TYPE": "COLUMN",
                        "INDEX": 0,
                        "RAW": "YES",
                    },
                    "EXTRACT": {
                        "TYPE": "REGEX",
                        "PATTERN": r"^\s*((?:\d{1,3}\.){3}\d{1,3})",
                        "GROUP": 1,
                    },
                },
                "port": {
                    "SOURCE": {
                        "TYPE": "COLUMN",
                        "INDEX": 0,
                        "RAW": "YES",
                    },
                    "EXTRACT": {
                        "TYPE": "REGEX",
                        "PATTERN": r"document\.write\([^+]*\+\s*\(?([^)]+)\)?",
                        "GROUP": 1,
                    },
                    "TRANSFORM": {
                        "TYPE": "EVAL_EXPRESSION",
                    },
                },
            },
        },
    },
    "scdn": {
        "URL": "https://proxy.scdn.io/get_proxies.php",
        "HEADERS": {
            "accept": "*/*",
            "accept-language": "en-GB,en;q=0.7",
            "dnt": "1",
            "priority": "u=1, i",
            "referer": "https://proxy.scdn.io/",
        },
        "PARAMS": {
            "per_page": "100",
            "page": "1",
        },
        "RULE_JSON": {
            "PARENT": "table_html",
            "RULE_HTML": {
                "XPATH": "//tr",
                "FIELD_KEYS": {
                    "ip": {
                        "XPATH": "./td[1]",
                        "INDEX": 0,
                        "TEXT": "YES",
                    },
                    "port": {
                        "XPATH": "./td[2]",
                        "INDEX": 0,
                        "TEXT": "YES",
                    },
                },
            },
        },
    },
    "databay": {
        "URL": [
            "https://cdn.jsdelivr.net/gh/databay-labs/free-proxy-list@HEAD/http.txt",
            "https://cdn.jsdelivr.net/gh/databay-labs/free-proxy-list@HEAD/socks4.txt",
            "https://cdn.jsdelivr.net/gh/databay-labs/free-proxy-list@HEAD/socks5.txt",
        ],
        "RULE_TXT": {
            "SEP": "\n",
        },
    },
    "dpangestuw": {
        "URL": "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/refs/heads/main/All_proxies.txt",
        "RULE_TXT": {
            "SEP": "\n",
        },
    },
    "floppydata": {
        "URL": "https://geoxy.io/proxies",
        "HEADERS": {
            "accept": "*/*",
            "accept-language": "en-GB,en;q=0.8",
            "authorization": "BgPXfhUc8CAhK7wGOqzqz9m77j3sH7",
            "content-type": "application/json",
            "dnt": "1",
            "origin": "https://floppydata.com",
            "priority": "u=1, i",
            "referer": "https://floppydata.com/",
        },
        "RULE_JSON": {"FIELD_KEYS": {"ip": "address"}},
    },
    "goodips": {
        "URL": "https://www.goodips.com/",
        "TIMEOUT": 30,
        "RULE_HTML": {
            "XPATH": '//div[@class="table-list"]',
            "FIELD_KEYS": {
                "ip": {"XPATH": "ul/li", "INDEX": 0, "TEXT": "YES"},
                "port": {"XPATH": "ul/li", "INDEX": 1, "TEXT": "YES"},
            },
        },
    },
    "hide_my_name": {
        "URL": "https://hide.mn/en/proxy-list/",
        "RULE_HTML": {
            "XPATH": "//tbody/tr",
            "FIELD_KEYS": {
                "ip": {"XPATH": "td", "INDEX": 0, "TEXT": "YES"},
                "port": {"XPATH": "td", "INDEX": 1, "TEXT": "YES"},
            },
        },
    },
    "iplocate": {
        "URL": "https://raw.githubusercontent.com/iplocate/free-proxy-list/refs/heads/main/all-proxies.txt",
        "RULE_TXT": {
            "SEP": "\n",
        },
    },
    "ip3366": {
        "URL": "http://www.ip3366.net/free/?stype=2&page=1",
        "ENCODING": "gbk",
        "RULE_HTML": {
            "XPATH": "//tr[td]",
            "FIELD_KEYS": {
                "ip": {
                    "XPATH": "./td",
                    "INDEX": 0,
                    "TEXT": "YES",
                },
                "port": {
                    "XPATH": "./td",
                    "INDEX": 1,
                    "TEXT": "YES",
                },
            },
        },
    },
    "89ip": {
        "URL": "https://api.89ip.cn/tqdl.html",
        "PARAMS": {
            "api": "1",
            "num": "200",
            "port": "",
            "address": "",
            "isp": "",
        },
        "HEADERS": {
            "Referer": "https://api.89ip.cn/tqdl.html?api=1&num=200&port=&address=&isp=",
        },
        "RULE_TXT": {
            "SEP": "<br>",
        },
    },
    "iproyal": {
        "URL": "https://iproyal.com/_actions/getFreeProxyList/",
        "PARAMS": {"_action": "getFreeProxyList"},
        "HEADERS": {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": "https://iproyal.com",
            "Referer": "https://iproyal.com/free-proxy-list/",
        },
        "METHOD": "POST",
        "PAYLOAD": {"country": "", "page": 1},
        "RULE_JSON": {
            "INDEXED": "YES",
            "FIELD_KEYS": {
                "ip": "ip",
                "port": "port",
                "protocol": "protocol",
                "country": "country",
                "city": "city",
            },
        },
    },
    "jiliuip": {
        "URL": [f"https://www.jiliuip.com/free/page-{i}/" for i in range(1, 6)],
        "TIMEOUT": 30,
        "RULE_HTML": {
            "XPATH": (
                "//div[contains("
                "concat(' ', normalize-space(@class), ' '), "
                "' v2-free-table__row '"
                ")]"
            ),
            "FIELD_KEYS": {
                "ip": {
                    "XPATH": (
                        "./span[contains("
                        "concat(' ', normalize-space(@class), ' '), "
                        "' v2-free-table__ip '"
                        ")]"
                    ),
                    "INDEX": 0,
                    "TEXT": "YES",
                },
                "port": {
                    "XPATH": "./span[2]",
                    "INDEX": 0,
                    "TEXT": "YES",
                },
            },
        },
    },
    "kuaidaili": {
        "URL": [
            "https://www.kuaidaili.com/free/dps/",
            "https://www.kuaidaili.com/free/inha/",
            "https://www.kuaidaili.com/free/intr/",
        ],
        "TIMEOUT": 30,
        "RULE_HTML": {
            "PANDAS": "YES",
            "INDEX": 0,
            "FIELD_KEYS": {
                "ip": "IP",
                "port": "PORT",
            },
        },
    },
    "kxdaili": {
        "URL": [
            "http://www.kxdaili.com/dailiip.html",
            "http://www.kxdaili.com/dailiip/2/1.html",
        ],
        "RULE_HTML": {
            "PANDAS": "YES",
            "INDEX": 0,
            "FIELD_KEYS": {
                "ip": "IP地址",
                "port": "端口",
            },
        },
    },
    "litproxy": {
        "URL": "https://litport.net/api/free-proxy",
        "PARAMS": {
            "limit": "1000",
            "sortBy": "pingAt_desc",
            "page": "1",
            "format": "json",
        },
        "RULE_JSON": {
            "FIELD_KEYS": {
                "ip": "host",
                "port": "port",
            }
        },
    },
    "my_proxy": {
        "URL": [
            *[
                f"https://www.my-proxy.com/free-proxy-list-{i}.html"
                for i in range(1, 11)
            ],
            "https://www.my-proxy.com/free-elite-proxy.html",
            "https://www.my-proxy.com/free-anonymous-proxy.html",
            "https://www.my-proxy.com/free-transparent-proxy.html",
            "https://www.my-proxy.com/free-socks-4-proxy.html",
            "https://www.my-proxy.com/free-socks-5-proxy.html",
        ],
        "RULE_HTML": {
            "XPATH": '//div[@class="col-sm-9 text-center"]//div[@class="list"]',
            "FIELD_KEYS": {
                "ip": {
                    "SOURCE": {"TYPE": "XPATH", "XPATH": ".//text()"},
                    "EXTRACT": {
                        "TYPE": "REGEX",
                        "PATTERN": r"(\d{1,3}(?:\.\d{1,3}){3}:\d+)",
                    },
                }
            },
        },
    },
    "openproxylist": {
        "URL": [
            "https://api.openproxylist.xyz/http.txt",
            "https://api.openproxylist.xyz/https.txt",
            "https://api.openproxylist.xyz/socks4.txt",
            "https://api.openproxylist.xyz/socks5.txt",
        ],
        "RULE_TXT": {"SEP": "\n"},
    },
    "proxyelite": {
        "URL": [
            f"https://proxyelite.info/wp-json/fineproxy/v1/free-proxies/{i}"
            for i in [
                "ae",
                "at",
                "bd",
                "bg",
                "br",
                "ca",
                "ch",
                "cl",
                "cn",
                "co",
                "cy",
                "cz",
                "de",
                "do",
                "ee",
                "eg",
                "es",
                "fi",
                "fr",
                "gb",
                "gr",
                "hk",
                "hn",
                "id",
                "im",
                "in",
                "iq",
                "it",
                "jp",
                "ke",
                "kh",
                "kr",
                "kz",
                "lt",
                "lu",
                "lv",
                "ma",
                "mo",
                "mx",
                "my",
                "nl",
                "ph",
                "pk",
                "pl",
                "ro",
                "ru",
                "rw",
                "sa",
                "sc",
                "se",
                "sg",
                "sn",
                "sy",
                "th",
                "tr",
                "tw",
                "ua",
                "us",
                "ve",
                "vn",
                "xk",
                "za",
                "zw",
            ]
        ],
        "RULE_JSON": {
            "PARENT": "rows",
            "FIELD_KEYS": {
                "ip": "ip",
                "port": "port",
            },
        },
    },
    "proxyshare": {
        "URL": "https://www.proxyshare.com/fetch-proxy/free?page_size=1000",
        "RULE_JSON": {
            "PARENT": "data,list",
            "FIELD_KEYS": {
                "ip": "ip",
                "port": "port",
            },
        },
    },
    "pubproxy": {
        "URL": "http://pubproxy.com/api/proxy?limit=1000&format=json",
        "RULE_JSON": {"PARENT": "data", "FIELD_KEYS": {"ip": "ipPort"}},
    },
    "proxylister": {
        "URL": "https://proxylister.com/api/v1/proxies?limit=500",
        "TIMEOUT": 30,
        "RULE_JSON": {
            "PARENT": "results",
            "FIELD_KEYS": {
                "ip": "ip_address",
                "port": "port",
            },
        },
    },
    "thespeedx": {
        "URL": [
            "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
            "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks4.txt",
            "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        ],
        "RULE_TXT": {"SEP": "\n"},
    },
    "spys_me": {
        "URL": ["https://spys.me/proxy.txt", "https://spys.me/socks.txt"],
        "RULE_TXT": {
            "SEP": "\n",
            "EXTRACT": {
                "TYPE": "REGEX",
                "PATTERN": "(?:\\d{1,3}\\.){3}\\d{1,3}:\\d{1,5}",
            },
        },
    },
}
