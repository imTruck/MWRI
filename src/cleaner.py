import base64
import json
import logging
import urllib.parse
import copy
from src.geoip import get_flag

logger = logging.getLogger(__name__)

PREFIX = "mwri\U0001F9D8\U0001F3FD"

CDN_PORTS = [80, 443, 8080, 8443, 2052, 2053, 2082, 2083, 2086, 2087, 2095, 2096]
CDN_NETWORKS = ["ws", "xhttp", "grpc", "httpupgrade", "splithttp"]


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


def _decode_vmess(raw):
    try:
        b64 = raw.replace("vmess://", "")
        padding = 4 - len(b64) % 4
        if padding != 4:
            b64 += "=" * padding
        try:
            decoded = base64.b64decode(b64).decode("utf-8", errors="ignore")
        except Exception:
            decoded = base64.urlsafe_b64decode(b64).decode("utf-8", errors="ignore")
        return json.loads(decoded)
    except Exception:
        return None


def is_cdn_vmess(raw):
    data = _decode_vmess(raw)
    if not data:
        return False
    net = data.get("net", "")
    port = int(data.get("port", 0))
    # Relaxed: any ws/grpc config is CDN candidate
    if net in CDN_NETWORKS:
        return True
    if port in CDN_PORTS and net in CDN_NETWORKS:
        return True
    return False


def is_cdn_vless(raw):
    try:
        parsed = urllib.parse.urlparse(raw)
        params = dict(urllib.parse.parse_qsl(parsed.query))
        net_type = params.get("type", "")
        if net_type in CDN_NETWORKS:
            return True
        return False
    except Exception:
        return False


def filter_cdn_configs(configs):
    cdn = []
    for c in configs:
        if c.protocol == "vmess" and is_cdn_vmess(c.raw):
            cdn.append(c)
        elif c.protocol == "vless" and is_cdn_vless(c.raw):
            cdn.append(c)
    logger.info("CDN configs: " + str(len(cdn)) + " / " + str(len(configs)))
    return cdn


def apply_clean_ip_vmess(raw, clean_ip, name):
    data = _decode_vmess(raw)
    if not data:
        return None

    try:
        original = data.get("add", "")
        host = data.get("host", "")
        port = int(data.get("port", 0))

        # host must be the domain, not IP
        if not host:
            host = original
        
        # If host is also IP, skip this config
        if host and host[0].isdigit():
            return None

        data["add"] = clean_ip
        data["host"] = host
        data["sni"] = host
        data["ps"] = name

        # TLS based on port
        if port in [443, 8443, 2053, 2083, 2087, 2096]:
            data["tls"] = "tls"
            data["alpn"] = "h2,http/1.1"
            data["fp"] = "chrome"
            data["allowInsecure"] = True
        else:
            data["tls"] = ""
            if "sni" in data:
                del data["sni"]

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

        host = params.get("host", "")
        if not host:
            host = original

        # If host is IP, skip
        if host and host[0].isdigit():
            return None

        params["host"] = host

        if port in [443, 8443, 2053, 2083, 2087, 2096]:
            params["security"] = "tls"
            params["sni"] = host
            params["alpn"] = "h2,http/1.1"
            params["fp"] = "chrome"
            params["allowInsecure"] = "1"
        else:
            params["security"] = "none"
            params.pop("sni", None)
            params.pop("alpn", None)

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
        logger.warning("No CDN configs for clean IP!")
        return []

    # Filter: only configs with domain host (not IP)
    good_cdn = []
    for c in cdn:
        if c.protocol == "vmess":
            data = _decode_vmess(c.raw)
            if data:
                host = data.get("host", data.get("add", ""))
                if host and not host[0].isdigit():
                    good_cdn.append(c)
        elif c.protocol == "vless":
            try:
                parsed = urllib.parse.urlparse(c.raw)
                params = dict(urllib.parse.parse_qsl(parsed.query))
                host = params.get("host", parsed.hostname or "")
                if host and not host[0].isdigit():
                    good_cdn.append(c)
            except Exception:
                pass

    if not good_cdn:
        logger.warning("No CDN configs with domain host!")
        return []

    logger.info("Good CDN (with domain): " + str(len(good_cdn)))

    cleaned = []
    for i, ip in enumerate(clean_ips):
        flag = get_flag(ip)
        # Use each clean IP with multiple configs
        for j in range(min(5, len(good_cdn))):
            config = good_cdn[(i * 5 + j) % len(good_cdn)]
            num = i * 5 + j + 1
            name = flag + " " + PREFIX + " clean#" + str(num)

            if config.protocol == "vmess":
                new_raw = apply_clean_ip_vmess(config.raw, ip, name)
            elif config.protocol == "vless":
                new_raw = apply_clean_ip_vless(config.raw, ip, name)
            else:
                continue

            if new_raw:
                new_c = copy.copy(config)
                new_c.raw = new_raw
                new_c.address = ip
                new_c.name = name
                new_c.is_alive = True
                new_c.latency = 0
                cleaned.append(new_c)

    logger.info("Clean configs: " + str(len(cleaned)))
    return cleaned
