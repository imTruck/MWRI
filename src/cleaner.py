import base64
import json
import logging
import urllib.parse
import copy

logger = logging.getLogger(__name__)

PREFIX = "mwri\U0001F9D8\U0001F3FD"

FLAGS = {
    "162.159": "\U0001F1E9\U0001F1EA",
    "172.64": "\U0001F1FA\U0001F1F8",
    "172.65": "\U0001F1FA\U0001F1F8",
    "172.66": "\U0001F1FA\U0001F1F8",
    "172.67": "\U0001F1FA\U0001F1F8",
    "172.68": "\U0001F1FA\U0001F1F8",
    "172.69": "\U0001F1FA\U0001F1F8",
    "172.70": "\U0001F1FA\U0001F1F8",
    "172.71": "\U0001F1FA\U0001F1F8",
    "104.16": "\U0001F1FA\U0001F1F8",
    "104.17": "\U0001F1FA\U0001F1F8",
    "104.18": "\U0001F1FA\U0001F1F8",
    "104.19": "\U0001F1FA\U0001F1F8",
    "104.20": "\U0001F1FA\U0001F1F8",
    "104.21": "\U0001F1FA\U0001F1F8",
    "104.22": "\U0001F1FA\U0001F1F8",
    "104.23": "\U0001F1FA\U0001F1F8",
    "104.24": "\U0001F1FA\U0001F1F8",
    "104.25": "\U0001F1FA\U0001F1F8",
    "104.26": "\U0001F1FA\U0001F1F8",
    "104.27": "\U0001F1FA\U0001F1F8",
    "141.101": "\U0001F1EA\U0001F1FA",
    "188.114": "\U0001F1EA\U0001F1FA",
    "190.93": "\U0001F1FA\U0001F1F8",
    "198.41": "\U0001F1FA\U0001F1F8",
}

CDN_PORTS = [80, 443, 8080, 8443, 2052, 2053, 2082, 2083, 2086, 2087, 2095, 2096]
CDN_NETWORKS = ["ws", "xhttp", "grpc", "httpupgrade"]


def get_flag(ip):
    parts = ip.split(".")
    key = parts[0] + "." + parts[1]
    return FLAGS.get(key, "\U00002601")


def load_clean_ips(filepath="clean_ips.txt"):
    ips = []
    try:
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    ips.append(line)
    except FileNotFoundError:
        logger.warning("clean_ips.txt not found!")
    logger.info("Loaded " + str(len(ips)) + " clean IPs")
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
        net = data.get("net", "")
        port = int(data.get("port", 0))

        if net in CDN_NETWORKS and port in CDN_PORTS:
            return True
        return False
    except Exception:
        return False


def is_cdn_vless(raw):
    try:
        parsed = urllib.parse.urlparse(raw)
        params = dict(urllib.parse.parse_qsl(parsed.query))
        net_type = params.get("type", "")
        port = parsed.port or 0

        if net_type in CDN_NETWORKS and port in CDN_PORTS:
            return True
        return False
    except Exception:
        return False


def filter_cdn_configs(configs):
    cdn_configs = []
    for c in configs:
        if c.protocol == "vmess" and is_cdn_vmess(c.raw):
            cdn_configs.append(c)
        elif c.protocol == "vless" and is_cdn_vless(c.raw):
            cdn_configs.append(c)

    logger.info("CDN configs: " + str(len(cdn_configs)) + " out of " + str(len(configs)))
    return cdn_configs


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
        original_address = data.get("add", "")

        # host رو تنظیم کن
        if not data.get("host", ""):
            data["host"] = original_address

        # SNI باید برابر host باشه نه آیپی
        host = data.get("host", original_address)
        data["sni"] = host

        # آیپی تمیز رو جایگزین کن
        data["add"] = clean_ip
        data["ps"] = name

        new_json = json.dumps(data, ensure_ascii=False)
        new_b64 = base64.b64encode(new_json.encode("utf-8")).decode("utf-8")
        return "vmess://" + new_b64
    except Exception:
        return None


def apply_clean_ip_vless(raw, clean_ip, name):
    try:
        parsed = urllib.parse.urlparse(raw)
        original_host = parsed.hostname
        port = parsed.port
        userinfo = parsed.username or ""

        params = dict(urllib.parse.parse_qsl(parsed.query))

        # host رو تنظیم کن
        if "host" not in params or not params["host"]:
            params["host"] = original_host

        # SNI باید برابر host باشه
        host = params.get("host", original_host)
        params["sni"] = host

        # security تنظیم
        if port == 443 or port in [8443, 2053, 2083, 2087, 2096]:
            params["security"] = "tls"
        else:
            params["security"] = "none"
            if "sni" in params:
                del params["sni"]

        new_query = urllib.parse.urlencode(params)
        encoded_name = urllib.parse.quote(name, safe="")

        new_url = "vless://" + userinfo + "@" + clean_ip + ":" + str(port) + "?" + new_query + "#" + encoded_name
        return new_url
    except Exception:
        return None


def apply_clean_ips(best_configs, clean_ips):
    if not clean_ips:
        logger.warning("No clean IPs!")
        return []

    if not best_configs:
        logger.warning("No best configs!")
        return []

    cdn_configs = filter_cdn_configs(best_configs)

    if not cdn_configs:
        logger.warning("No CDN configs found!")
        return []

    logger.info("Applying " + str(len(clean_ips)) + " clean IPs to " + str(len(cdn_configs)) + " CDN configs")

    cleaned_configs = []

    for i, ip in enumerate(clean_ips):
        flag = get_flag(ip)
        name = flag + " " + PREFIX + " #" + str(i + 1)

        config = cdn_configs[i % len(cdn_configs)]

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
            cleaned_configs.append(new_config)
            logger.info("  #" + str(i + 1) + " " + flag + " " + ip + " [" + config.protocol + "]")

    logger.info("Generated " + str(len(cleaned_configs)) + " clean configs")
    return cleaned_configs
