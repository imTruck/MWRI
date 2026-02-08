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

    def __str__(self):
        status = "alive" if self.is_alive else "dead"
        return f"[{self.protocol}] {self.address}:{self.port} ({self.latency}ms) {status}"


def safe_b64decode(data):
    try:
        data = data.strip()
        padding = 4 - len(data) % 4
        if padding != 4:
            data += '=' * padding
        try:
            return base64.b64decode(data).decode('utf-8', errors='ignore')
        except Exception:
            return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
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


def parse_trojan(config_str):
    try:
        raw = config_str.strip()
        parsed = urllib.parse.urlparse(raw)
        return ProxyConfig(
            raw=raw, protocol="trojan",
            address=parsed.hostname or "",
            port=parsed.port or 0,
            name=urllib.parse.unquote(parsed.fragment) if parsed.fragment else ""
        )
    except Exception:
        return None


def parse_ss(config_str):
    try:
        raw = config_str.strip()
        content = raw[5:]
        name = ""
        if '#' in content:
            content, name = content.rsplit('#', 1)
            name = urllib.parse.unquote(name)
        if '@' in content:
            _, server_part = content.rsplit('@', 1)
            if '?' in server_part:
                server_part = server_part.split('?')[0]
            parts = server_part.split(':')
            address = parts[0]
            port = int(parts[1]) if len(parts) > 1 else 0
        else:
            decoded = safe_b64decode(content)
            if '@' in decoded:
                _, server_part = decoded.rsplit('@', 1)
                parts = server_part.split(':')
                address = parts[0]
                port = int(parts[1]) if len(parts) > 1 else 0
            else:
                return None
        return ProxyConfig(raw=raw, protocol="ss", address=address, port=port, name=name)
    except Exception:
        return None


def parse_hysteria2(config_str):
    try:
        raw = config_str.strip()
        parsed = urllib.parse.urlparse(raw)
        return ProxyConfig(
            raw=raw, protocol="hysteria2",
            address=parsed.hostname or "",
            port=parsed.port or 0,
            name=urllib.parse.unquote(parsed.fragment) if parsed.fragment else ""
        )
    except Exception:
        return None


def parse_tuic(config_str):
    try:
        raw = config_str.strip()
        parsed = urllib.parse.urlparse(raw)
        return ProxyConfig(
            raw=raw, protocol="tuic",
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
    elif config_str.startswith("trojan://"):
        return parse_trojan(config_str)
    elif config_str.startswith("ss://"):
        return parse_ss(config_str)
    elif config_str.startswith(("hysteria2://", "hy2://")):
        return parse_hysteria2(config_str)
    elif config_str.startswith("tuic://"):
        return parse_tuic(config_str)
    return None


def extract_configs_from_text(text):
    protocols = ['vmess://', 'vless://', 'trojan://', 'ss://', 'ssr://',
                 'hysteria2://', 'hy2://', 'tuic://']
    configs = []
    decoded = safe_b64decode(text)
    if decoded and any(p in decoded for p in protocols):
        text = decoded
    for line in text.splitlines():
        line = line.strip()
        if any(line.startswith(p) for p in protocols):
            configs.append(line)
    for protocol in protocols:
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
