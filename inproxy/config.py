PROXY_CONFIG = {
    "proxyscrape": {
        "URL": "https://api.proxyscrape.com/v4/free-proxy-list/get",
        "PARAMS": {
            "request": "display_proxies",
            "proxy_format": "protocolipport",
            "format": "json",
            "protocol": "https",
            "country": "in",
        },
        "RULE_JSON": {"PARENT": "proxies", "FIELD_KEYS": {"ip": "ip", "port": "port"}},
    },
    "geonix": {
        "URL": "https://free.geonix.com/api/front/main/pagination/filtration",
        "PAYLOAD": {
            "page": 0,
            "size": 10,
            "countries": ["India"],
            "proxyProtocols": ["HTTPS"],
            "proxyTypes": [],
        },
        "HEADERS": {"Content-Type": "application/json"},
        "METHOD": "POST",
        "RULE_JSON": {"PARENT": "content", "FIELD_KEYS": {"ip": "ip"}},
    },
    "geonode": {
        "URL": "https://proxylist.geonode.com/api/proxy-list",
        "PARAMS": {
            "protocols": "https",
            "page": "1",
            "limit": "500",
            "sort_by": "responseTime",
            "country": "IN",
            "sort_type": "asc",
        },
        "RULE_JSON": {"PARENT": "data", "FIELD_KEYS": {"ip": "ip", "port": "port"}},
    },
    "proxyfreeonly": {
        "URL": "https://proxyfreeonly.com/api/free-proxy-list",
        "PARAMS": {
            "limit": "500",
            "page": "1",
            "country": "IN",
            "sortBy": "lastChecked",
            "sortType": "desc",
        },
        "RULE_JSON": {"FIELD_KEYS": {"ip": "ip", "port": "port"}},
    },
    "freeproxyupdate": {
        "URL": "https://freeproxyupdate.com/india-in/https-ssl",
        "RULE_HTML": {
            "PANDAS": "YES",
            "INDEX": 0,
            "FIELD_KEYS": {"ip": "IP address", "port": "Port"},
        },
    },
    "advanced_name": {
        "URL": "https://advanced.name/freeproxy?type=https&country=IN",
        "RULE_HTML": {
            "XPATH": '//table[@id="table_proxies"]/tbody/tr',
            "DECODE": "BASE64",
            "FIELD_KEYS": {
                "ip": {"XPATH": "./td[2]/@data-ip", "INDEX": 0},
                "port": {"XPATH": "./td[3]/@data-port", "INDEX": 0},
            },
        },
    },
    "chillyproxy": {
        "URL": "https://chillyproxy.com/api/tools/free-proxies?protocol=https&country=IN",
        "RULE_TXT": {"SEP": "\n"},
    },
    "free_proxy_list": {
        "URL": "https://free-proxy-list.net/en/",
        "RULE_HTML": {"XPATH": "//tbody/tr"},
        "FIELD_KEYS": {
            "ip": {"XPATH": "./td", "INDEX": 0, "TEXT": "YES"},
            "port": {"XPATH": "./td", "INDEX": 1, "TEXT": "YES"},
        },
        "FILTERS": {
            "AND": [
                {"XPATH": "./td", "INDEX": 2, "VALUE": "IN"},
                {"XPATH": "./td", "INDEX": 6, "VALUE": "yes"},
            ]
        },
    },
    "fineproxy": {
        "URL": "https://fineproxy.org/wp-json/fineproxy/v1/free-proxies/in",
        "RULE_JSON": {"PARENT": "rows", "FIELD_KEYS": {"ip": "ip", "port": "port"}},
        "FILTERS": {"CONTAINS": {"KEY": "protos", "VALUE": "HTTPS"}},
    },
    "freeproxydb": {
        "URL": "https://freeproxydb.com/api/proxy/search?country=IN&speed=0,60&https=1",
        "RULE_JSON": {
            "PARENT": "data,data",
            "FIELD_KEYS": {"ip": "ip", "port": "port"},
        },
    },
    "freevpnnode": {
        "URL": "https://www.freevpnnode.com/free-proxy-for-india/",
        "RULE_HTML": {
            "PANDAS": "YES",
            "INDEX": 0,
            "FIELD_KEYS": {"ip": "IP Address", "port": "Port"},
        },
        "FILTERS": {"EQUALS": {"KEY": "Protocols", "VALUE": "https"}},
    },
    "freeproxy": {
        "URL": "https://www.freeproxy.world/?type=https&anonymity=&country=IN&speed=&port=",
        "RULE_HTML": {
            "PANDAS": "YES",
            "INDEX": 0,
            "FIELD_KEYS": {"ip": "IP Address", "port": "Port"},
        },
    },
    "proxyhub": {
        "URL": "https://proxyhub.me/en/in-https-proxy-list.html",
        "RULE_HTML": {
            "PANDAS": "YES",
            "INDEX": 0,
            "FIELD_KEYS": {"ip": "IP", "port": "Port"},
        },
    },
    "proxydb": {
        "URL": "https://proxydb.net/?protocol=https&country=IN",
        "RULE_HTML": {
            "PANDAS": "YES",
            "INDEX": 0,
            "FIELD_KEYS": {"ip": "IP", "port": "Port"},
        },
    },
    "proxifly": {
        "URL": "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/countries/IN/data.json",
        "RULE_JSON": {"FIELD_KEYS": {"ip": "proxy"}},
        "FILTERS": {"EQUALS": {"KEY": "https", "VALUE": True}},
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
        "PARAMS": {"length": 50},
        "RULE_JSON": {"PARENT": "data", "FIELD_KEYS": {"ip": "ip", "port": "port"}},
        "FILTERS": {
            "AND": [
                {"KEY": "protocol", "VALUE": "Https"},
                {"KEY": "country", "VALUE": "IN"},
            ]
        },
    },
    "proxyshare": {
        "URL": "https://www.proxyshare.com/fetch-proxy/free",
        "PARAMS": {
            "page_size": 10,
            "page": 1,
            "country_code": "IN",
            "protocol": 2,
            "language": "en-us",
        },
        "RULE_JSON": {
            "PARENT": "data,list",
            "FIELD_KEYS": {"ip": "ip", "port": "port"},
        },
    },
    "proxiware": {
        "URL": "https://papi.proxiware.com/proxies",
        "PARAMS": {
            "page": 1,
            "country": "IN",
            "protocol": "https",
        },
        "RULE_JSON": {
            "PARENT": "proxies",
            "FIELD_KEYS": {"ip": "addr", "port": "port"},
        },
    },
    "proxyspace": {
        "URL": "https://proxyspace.pro/https.txt",
        "RULE_TXT": {"SEP": "\n"},
    },
    "roundproxies": {
        "URL": "https://roundproxies.com/api/get-free-proxies/",
        "PARAMS": {"country": "IN", "protocols": "https"},
        "RULE_JSON": {"PARENT": "data", "FIELD_KEYS": {"ip": "ip", "port": "port"}},
    },
    "spys_one": {"URL": "https://spys.one/free-proxy-list/IN/", "RULE_HTML": {}},
}
