import base64
import json
import logging
import urllib.parse
import copy
import socket
import struct

logger = logging.getLogger(__name__)

# دیتابیس کشور بر اساس رنج آیپی کلودفلر
COUNTRY_MAP = {
    "162.159": "DE",
    "172.64": "US",
    "172.65": "US",
    "172.66": "US",
    "172.67": "US",
    "172.68": "US",
    "172.69": "US",
    "172.70": "US",
    "172.71": "US",
    "104.16": "US",
    "104.17": "US",
    "104.18": "US",
    "104.19": "US",
    "104.20": "US",
    "104.21": "US",
    "104.22": "US",
    "104.23": "US",
    "104.24": "US",
    "104.25": "US",
    "104.26": "US",
    "104.27": "US",
    "141.101": "EU",
    "188.114": "EU",
    "190.93": "US",
    "197.234": "AF",
    "198.41": "US",
    "170.114": "US",
    "131.0": "EU",
    "1.1": "AU",
    "1.0": "AU",
}

FLAGS = {
    "DE": "\U0001F1E9\U0001F1EA",
    "US": "\U0001F1FA\U0001F1F8",
    "EU": "\U0001F1EA\U0001F1FA",
    "AF": "\U0001F1E6\U0001F1EB",
    "AU": "\U0001F1E6\U0001F1FA",
    "NL": "\U0001F1F3\U0001F1F1",
    "FI": "\U0001F1EB\U0001F1EE",
    "GB": "\U0001F1EC\U0001F1E7",
    "FR": "\U0001F1EB\U0001F1F7",
    "JP": "\U0001F1EF\U0001F1F5",
    "SG": "\U0001F1F8\U0001F1EC",
    "CA": "\U0001F1E8\U0001F1E6",
    "CF": "\U00002601",
}


def get_flag_for_ip(ip):
    parts = ip.split(".")
    if len(parts) < 2:
        return FLAGS.get("CF", "")

    prefix2 = parts[0] + "." + parts[1]
    prefix1 = parts[0] + "." + parts[1][:1]

    if prefix2 in COUNTRY_MAP:
        code = COUNTRY_MAP[prefix2]
        return FLAGS.get(code, ""), code
    
    for key in COUNTRY_MAP:
        if ip.startswith(key):
            code = COUNTRY_MAP[key]
            return FLAGS.get(code, ""), code

    return "\U00002601", "CF"


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

        if not data.get("host", ""):
            data["host"] = original_address

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

        if "host" not in params or not params["host"]:
            params["host"] = original_host

        if "sni" not in params or not params["sni"]:
            params["sni"] = original_host

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

    PREFIX = "mwri\U0001F9D8\U0001F3FD"

    cleaned_configs = []
    config_index = 0

    for i, ip in enumerate(clean_ips):
        flag, country = get_flag_for_ip(ip)
        name = flag + " " + PREFIX + " #" + str(i + 1)

        config = best_configs[config_index % len(best_configs)]
        config_index += 1

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
            logger.info("  #" + str(i + 1) + " " + flag + " " + country + " " + ip + " [" + config.protocol + "]")

    logger.info("Generated " + str(len(cleaned_configs)) + " clean IP configs")
    return cleaned_configs
