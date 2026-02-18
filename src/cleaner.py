import base64
import json
import logging
import urllib.parse
import copy
from src.geoip import get_flag

logger = logging.getLogger(__name__)

PREFIX = "mwri\U0001F9D8\U0001F3FD"

CDN_PORTS = [80, 443, 8080, 8443, 2052, 2053, 2082, 2083, 2086, 2087, 2095, 2096]
CDN_NETWORKS = ["ws", "xhttp", "grpc", "httpupgrade"]


def load_clean_ips(filepath="clean_ips.txt"):
    ips = []
    try:
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    ips.append(line)
    except FileNotFoundError:
        pass
    logger.info("Clean IPs: " + str(len(ips)))
    return ips


def is_cdn_vmess(raw):
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
        return data.get("net", "") in CDN_NETWORKS and int(data.get("port", 0)) in CDN_PORTS
    except Exception:
        return False


def is_cdn_vless(raw):
    try:
        parsed = urllib.parse.urlparse(raw)
        params = dict(urllib.parse.parse_qsl(parsed.query))
        return params.get("type", "") in CDN_NETWORKS and (parsed.port or 0) in CDN_PORTS
    except Exception:
        return False


def filter_cdn_configs(configs):
    cdn = []
    for c in configs:
        if c.protocol == "vmess" and is_cdn_vmess(c.raw):
            cdn.append(c)
        elif c.protocol == "vless" and is_cdn_vless(c.raw):
            cdn.append(c)
    logger.info("CDN configs: " + str(len(cdn)))
    return cdn


def apply_clean_ip_vmess(raw, clean_ip, name):
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
        original = data.get("add", "")
        if not data.get("host", ""):
            data["host"] = original
        data["sni"] = data.get("host", original)
        data["add"] = clean_ip
        data["ps"] = name
        new_json = json.dumps(data, ensure_ascii=False)
        return "vmess://" + base64.b64encode(new_json.encode("utf-8")).decode("utf-8")
    except Exception:
        return None


def apply_clean_ip_vless(raw, clean_ip, name):
    try:
        parsed = urllib.parse.urlparse(raw)
        original = parsed.hostname
        port = parsed.port
        userinfo = parsed.username or ""
        params = dict(urllib.parse.parse_qsl(parsed.query))
        if "host" not in params or not params["host"]:
            params["host"] = original
        params["sni"] = params.get("host", original)
        if port in [443, 8443, 2053, 2083, 2087, 2096]:
            params["security"] = "tls"
        else:
            params["security"] = "none"
            params.pop("sni", None)
        query = urllib.parse.urlencode(params)
        encoded_name = urllib.parse.quote(name, safe="")
        return "vless://" + userinfo + "@" + clean_ip + ":" + str(port) + "?" + query + "#" + encoded_name
    except Exception:
        return None


def apply_clean_ips(best_configs, clean_ips):
    if not clean_ips or not best_configs:
        return []

    cdn = filter_cdn_configs(best_configs)
    if not cdn:
        logger.warning("No CDN configs!")
        return []

    cleaned = []
    for i, ip in enumerate(clean_ips):
        flag = get_flag(ip)
        name = flag + " " + PREFIX + " #" + str(i + 1)
        config = cdn[i % len(cdn)]

        if config.protocol == "vmess":
            new_raw = apply_clean_ip_vmess(config.raw, ip, name)
        elif config.protocol == "vless":
            new_raw = apply_clean_ip_vless(config.raw, ip, name)
        else:
            continue

        if new_raw:
            new_config = copy.copy(config)
            new_config.raw = new_raw
            new_config.address = ip
            new_config.name = name
            new_config.is_alive = True
            new_config.latency = 0
            cleaned.append(new_config)

    logger.info("Clean configs: " + str(len(cleaned)))
    return cleaned
