import base64
import json
import urllib.parse
import copy
import logging
from src.geoip import get_flag

logger = logging.getLogger(__name__)

PREFIX = "mwri\U0001F9D8\U0001F3FD"


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
        host = data.get("host", "")
        sni = data.get("sni", "")
        net = data.get("net", "")
        port = int(data.get("port", 0))
        tls = data.get("tls", "")

        # Fix 1: host empty
        if not host and address:
            data["host"] = address

        # Fix 2: sni empty or wrong
        if tls == "tls":
            if not sni:
                data["sni"] = data.get("host", address)
            # Fix 3: alpn
            if not data.get("alpn"):
                data["alpn"] = "h2,http/1.1"

        # Fix 4: fp (fingerprint)
        if not data.get("fp"):
            data["fp"] = "chrome"

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

        security = params.get("security", "")
        sni = params.get("sni", "")
        host_param = params.get("host", "")
        net_type = params.get("type", "")

        # Fix 1: host empty
        if not host_param and host:
            params["host"] = host

        # Fix 2: sni empty
        if security in ["tls", "reality"]:
            if not sni:
                params["sni"] = params.get("host", host)

            # Fix 3: alpn
            if not params.get("alpn"):
                params["alpn"] = "h2,http/1.1"

            # Fix 4: fingerprint
            if not params.get("fp"):
                params["fp"] = "chrome"

            # Fix 5: allowInsecure
            params["allowInsecure"] = "1"

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

        sni = params.get("sni", "")

        # Fix 1: sni
        if not sni:
            params["sni"] = host

        # Fix 2: alpn
        if not params.get("alpn"):
            params["alpn"] = "h2,http/1.1"

        # Fix 3: fingerprint
        if not params.get("fp"):
            params["fp"] = "chrome"

        # Fix 4: allowInsecure
        params["allowInsecure"] = "1"

        flag = get_flag(host)
        name = flag + " " + PREFIX + " #" + str(number)

        query = urllib.parse.urlencode(params)
        encoded_name = urllib.parse.quote(name, safe="")
        return "trojan://" + password + "@" + host + ":" + str(port) + "?" + query + "#" + encoded_name
    except Exception:
        return None


def fix_all_configs(configs):
    """Fix TLS/SNI/fingerprint issues for all configs"""
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

    logger.info("Fixed " + str(len(fixed)) + " configs (SNI/TLS/FP)")
    return fixed
