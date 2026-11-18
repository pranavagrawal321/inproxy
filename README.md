# inproxy

A Python library to fetch free public proxies from multiple online sources, with support for filtering, concurrent fetching, and structured proxy data.

## Installation

```bash
pip install inproxy
```

## Quick Start

```python
from inproxy import InProxy

proxy = InProxy()

proxies = proxy.fetch(count=10)

for item in proxies:
    print(item.proxy)
```

## Filtering Proxies

You can filter proxies using location, network, anonymity, and latency attributes.

```python
from inproxy import InProxy

proxy = InProxy()

proxies = proxy.fetch(
    count=10,
    country="India",
    country_code="IN",
    anonymity="elite",
)

for item in proxies:
    print(item.proxy)
```

Available filters:

| Parameter | Description |
|---|---|
| `count` | Number of proxies to fetch |
| `sites` | Specific proxy sources to use |
| `country` | Filter by country |
| `country_code` | Filter by country code |
| `state` | Filter by state |
| `state_code` | Filter by state code |
| `city` | Filter by city |
| `region` | Filter by region |
| `continent` | Filter by continent |
| `timezone` | Filter by timezone |
| `isp` | Filter by ISP |
| `organization` | Filter by organization |
| `asn` | Filter by ASN |
| `anonymity` | Filter by anonymity level |
| `min_latency` | Minimum latency |
| `max_latency` | Maximum latency |

Note: Filtering depends on the metadata provided by each proxy source. Sources that do not provide a particular field cannot satisfy a filter on that field.

## Selecting Proxy Sources

By default, `inproxy` uses all configured sources.

You can specify individual sources using their names:

```python
from inproxy import InProxy

proxy = InProxy()

proxies = proxy.fetch(
    count=20,
    sites=["proxyscrape", "geonode", "iproyal"],
)

for item in proxies:
    print(item.proxy)
```

You can also provide multiple source names as a comma-separated string:

```python
proxies = proxy.fetch(
    count=20,
    sites="proxyscrape,geonode,iproyal",
)
```

## Working with Proxy Objects

Each result is a structured `Proxy` object.

```python
from inproxy import InProxy

proxy = InProxy()
proxies = proxy.fetch(count=5)

for item in proxies:
    print("Proxy:", item.proxy)
    print("IP:", item.ip)
    print("Port:", item.port)
    print("Protocol:", item.protocol)
    print("Country:", item.country)
    print("Country Code:", item.country_code)
    print("Anonymity:", item.anonymity)
    print("Latency:", item.latency)
    print()
```

### Proxy URL

The `.proxy` property returns the proxy in URL format:

```python
http://192.168.1.10:8080
```

The protocol and port are taken from the proxy data.

### Convert to Dictionary

Use `to_dict()` to convert a proxy object into a dictionary:

```python
proxies = proxy.fetch(count=5)

proxy_data = [item.to_dict() for item in proxies]

print(proxy_data)
```

Each dictionary includes the proxy fields and the formatted `proxy` URL.

## Using Proxies with Requests

```python
import requests
from inproxy import InProxy

proxy = InProxy()
proxies = proxy.fetch(count=1)

if proxies:
    proxy_url = proxies[0].proxy

    response = requests.get(
        "https://httpbin.org/ip",
        proxies={
            "http": proxy_url,
            "https": proxy_url,
        },
        timeout=15,
    )

    print(response.text)
```

## Configuration

You can configure the number of concurrent source workers and the timeout used for source requests:

```python
from inproxy import InProxy

proxy = InProxy(
    source_workers=20,
    source_timeout=5,
)

proxies = proxy.fetch(count=10)
```

| Parameter | Default | Description |
|---|---:|---|
| `source_workers` | `20` | Maximum number of concurrent source workers |
| `source_timeout` | `3` | Timeout in seconds for source requests |

## Important Notes

- Proxies are collected from public third-party sources.
- Proxy availability and response times can change at any moment.
- Not every source provides complete proxy metadata.
- A requested number of proxies is a target, not a guarantee. The returned list may contain fewer results.
- Public proxies are unreliable and should not be used for sensitive information or credentials.

## Requirements

- Python 3.10 or higher

## License

This project is licensed under the MIT License.

## Links

- [GitHub Repository](https://github.com/pranavagrawal321/inproxy)
- [Report an Issue](https://github.com/pranavagrawal321/inproxy/issues)