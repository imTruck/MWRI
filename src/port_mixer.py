import base64
import json
import urllib.parse
import copy
import logging
from src.geoip import get_flag

logger = logging.getLogger(__name__)

PREFIX = "mwri\U0001F9D8\U0001F3FD"
TLS_PORTS = [8443, 2053, 2083, 2087, 2096]
HTTP_PORTS = [8080, 2052, 2082, 2086, 2095]


def _clone_vmess(raw, new_port, name):
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
        old_port = int(data.get("port", 0))

        # Only clone TLS→TLS or HTTP→HTTP
        if old_port in [443] + TLS_PORTS and new_port not in TLS_PORTS:
            return None
        if old_port in [80] + HTTP_PORTS and new_port not in HTTP_PORTS:
            return None

        data["port"] = new_port
        data["ps"] = name
        if new_port in TLS_PORTS:
            data["tls"] = "tls"
        else:
            data["tls"] = ""
        new_json = json.dumps(data, ensure_ascii=False)
        return "vmess://" + base64.b64encode(new_json.encode("utf-8")).decode("utf-8")
    except Exception:
        return None


def _clone_vless(raw, new_port, name):
    try:
        parsed = urllib.parse.urlparse(raw)
        old_port = parsed.port or 0
        userinfo = parsed.username or ""
        host = parsed.hostname
        params = dict(urllib.parse.parse_qsl(parsed.query))

        if old_port in [443] + TLS_PORTS and new_port not in TLS_PORTS:
            return None
        if old_port in [80] + HTTP_PORTS and new_port not in HTTP_PORTS:
            return None

        if new_port in TLS_PORTS:
            params["security"] = "tls"
            if not params.get("sni"):
                params["sni"] = params.get("host", host)
        else:
            params["security"] = "none"
            params.pop("sni", None)

        query = urllib.parse.urlencode(params)
        encoded_name = urllib.parse.quote(name, safe="")
        return "vless://" + userinfo + "@" + host + ":" + str(new_port) + "?" + query + "#" + encoded_name
    except Exception:
        return None


def mix_ports(configs):
    """Clone working configs with alternative ports"""
    mixed = []
    counter = 0

    for c in configs:
        ports = TLS_PORTS if c.port in [443] + TLS_PORTS else HTTP_PORTS

        for new_port in ports:
            if new_port == c.port:
                continue

            counter += 1
            flag = get_flag(c.address)
            name = flag + " " + PREFIX + " p" + str(new_port) + "#" + str(counter)

            if c.protocol == "vmess":
                new_raw = _clone_vmess(c.raw, new_port, name)
            elif c.protocol == "vless":
                new_raw = _clone_vless(c.raw, new_port, name)
            else:
                continue

            if new_raw:
                new_c = copy.copy(c)
                new_c.raw = new_raw
                new_c.port = new_port
                new_c.name = name
                mixed.append(new_c)

    logger.info("Port mixer: " + str(len(mixed)) + " variants from " + str(len(configs)) + " configs")
    return mixed
