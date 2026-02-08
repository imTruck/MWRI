import base64
import json
import re
import urllib.parse


class ProxyConfig:
    def __init__(self, raw, protocol, address="", port=0, name=""):
        self.raw = raw
        self.protocol = protocol
        self.address = address
        self.port = port
        self.name = name
        self.latency = -1
        self.is_alive = False


def safe_b64decode(data):
    try:
        data = data.strip()
        padding = 4 - len(data) % 4
        if padding != 4:
            data += "=" * padding
        try:
            return base64.b64decode(data).decode("utf-8", errors="ignore")
        except Exception:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def parse_vmess(config_str):
    try:
        raw = config_str.strip()
        b64_part = raw.replace("vmess://", "")
        decoded = safe_b64decode(b64_part)
        if not decoded:
            return None
        data = json.loads(decoded)
        return ProxyConfig(
            raw=raw, protocol="vmess",
            address=data.get("add", ""),
            port=int(data.get("port", 0)),
            name=data.get("ps", "")
        )
    except Exception:
        return None


def parse_vless(config_str):
    try:
        raw = config_str.strip()
        parsed = urllib.parse.urlparse(raw)
        return ProxyConfig(
            raw=raw, protocol="vless",
            address=parsed.hostname or "",
            port=parsed.port or 0,
            name=urllib.parse.unquote(parsed.fragment) if parsed.fragment else ""
        )
    except Exception:
        return None


def parse_config(config_str):
    config_str = config_str.strip()
    if config_str.startswith("vmess://"):
        return parse_vmess(config_str)
    elif config_str.startswith("vless://"):
        return parse_vless(config_str)
    return None


def extract_configs_from_text(text):
    configs = []

    decoded = safe_b64decode(text)
    if decoded and ("vmess://" in decoded or "vless://" in decoded):
        text = decoded

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("vmess://") or line.startswith("vless://"):
            configs.append(line)

    for protocol in ["vmess://", "vless://"]:
        escaped = re.escape(protocol)
        pattern = escaped + r'[A-Za-z0-9+/=_\-%.@:?&#!,;\[\]()~]+'
        matches = re.findall(pattern, text)
        configs.extend(matches)

    seen = set()
    unique = []
    for c in configs:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    return unique
