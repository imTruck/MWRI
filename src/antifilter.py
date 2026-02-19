import base64
import json
import urllib.parse
import copy
import logging
from src.geoip import get_flag

logger = logging.getLogger(__name__)

PREFIX = "mwri\U0001F9D8\U0001F3FD"
TLS_PORTS = [443, 8443, 2053, 2083, 2087, 2096]


def fix_vmess(raw, number):
    try:
        b64 = raw.replace("vmess://", "")
        padding = 4 - len(b64) % 4
        if padding != 4:
            b64 += "=" * padding
        try:
            decoded = base64.b64decode(b64).decode("utf-8", errors="ignore")
        except Exception:
            decoded = base64.urlsafe_b64decode(b64).decode("utf-8", errors="ignore")
        data = json.loads(decoded)

        address = data.get("add", "")
        port = int(data.get("port", 0))

        if not data.get("host"):
            data["host"] = address

        if port in TLS_PORTS:
            data["tls"] = "tls"
            if not data.get("sni"):
                data["sni"] = data.get("host", address)
            if not data.get("alpn"):
                data["alpn"] = "h2,http/1.1"
            if not data.get("fp"):
                data["fp"] = "chrome"
            # Fix EOF: allowInsecure
            data["allowInsecure"] = True
        else:
            data["tls"] = ""

        flag = get_flag(address)
        data["ps"] = flag + " " + PREFIX + " #" + str(number)

        new_json = json.dumps(data, ensure_ascii=False)
        return "vmess://" + base64.b64encode(new_json.encode("utf-8")).decode("utf-8")
    except Exception:
        return None


def fix_vless(raw, number):
    try:
        parsed = urllib.parse.urlparse(raw)
        host = parsed.hostname or ""
        port = parsed.port or 0
        userinfo = parsed.username or ""
        params = dict(urllib.parse.parse_qsl(parsed.query))

        if not params.get("host"):
            params["host"] = host

        if port in TLS_PORTS:
            if params.get("security", "") != "reality":
                params["security"] = "tls"
            if not params.get("sni"):
                params["sni"] = params.get("host", host)
            if not params.get("alpn"):
                params["alpn"] = "h2,http/1.1"
            if not params.get("fp"):
                params["fp"] = "chrome"
            params["allowInsecure"] = "1"
        else:
            params["security"] = "none"
            params.pop("sni", None)
            params.pop("alpn", None)

        flag = get_flag(host)
        name = flag + " " + PREFIX + " #" + str(number)
        query = urllib.parse.urlencode(params)
        encoded_name = urllib.parse.quote(name, safe="")
        return "vless://" + userinfo + "@" + host + ":" + str(port) + "?" + query + "#" + encoded_name
    except Exception:
        return None


def fix_trojan(raw, number):
    try:
        parsed = urllib.parse.urlparse(raw)
        host = parsed.hostname or ""
        port = parsed.port or 0
        password = parsed.username or ""
        params = dict(urllib.parse.parse_qsl(parsed.query))

        if not params.get("sni"):
            params["sni"] = host
        if not params.get("alpn"):
            params["alpn"] = "h2,http/1.1"
        if not params.get("fp"):
            params["fp"] = "chrome"
        params["allowInsecure"] = "1"

        flag = get_flag(host)
        name = flag + " " + PREFIX + " #" + str(number)
        query = urllib.parse.urlencode(params)
        encoded_name = urllib.parse.quote(name, safe="")
        return "trojan://" + password + "@" + host + ":" + str(port) + "?" + query + "#" + encoded_name
    except Exception:
        return None


def fix_all_configs(configs):
    fixed = []
    for i, c in enumerate(configs, 1):
        new_raw = None
        if c.protocol == "vmess":
            new_raw = fix_vmess(c.raw, i)
        elif c.protocol == "vless":
            new_raw = fix_vless(c.raw, i)
        elif c.protocol == "trojan":
            new_raw = fix_trojan(c.raw, i)

        if new_raw:
            new_c = copy.copy(c)
            new_c.raw = new_raw
            fixed.append(new_c)
        else:
            fixed.append(c)

    logger.info("Fixed " + str(len(fixed)) + " configs")
    return fixed
