import base64
import json
import logging
import urllib.parse
import copy
import requests
import time

logger = logging.getLogger(__name__)


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


def get_country_flag(country_code):
    if not country_code or len(country_code) != 2:
        return ""
    country_code = country_code.upper()
    first = chr(0x1F1E6 + ord(country_code[0]) - ord("A"))
    second = chr(0x1F1E6 + ord(country_code[1]) - ord("A"))
    return first + second


def get_ip_country(ip):
    try:
        url = "http://ip-api.com/json/" + ip + "?fields=countryCode"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        return data.get("countryCode", "")
    except Exception:
        return ""


def get_all_countries(clean_ips):
    logger.info("Getting countries for clean IPs...")
    countries = {}
    for ip in clean_ips:
        country = get_ip_country(ip)
        flag = get_country_flag(country)
        countries[ip] = {"code": country, "flag": flag}
        logger.info("  " + ip + " -> " + country + " " + flag)
        time.sleep(0.5)
    return countries


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

    # Get country for each IP
    countries = get_all_countries(clean_ips)

    PREFIX = "mwri\U0001F9D8\U0001F3FD"

    cleaned_configs = []

    for i, ip in enumerate(clean_ips):
        # Pick a config (round-robin through best configs)
        config = best_configs[i % len(best_configs)]

        # Build name with flag
        flag = countries[ip]["flag"]
        country = countries[ip]["code"]
        name = flag + " " + PREFIX + " #" + str(i + 1)

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
            cleaned_configs.append(new_config)
            logger.info("  #" + str(i + 1) + " " + flag + " " + country + " " + ip + " [" + config.protocol + "]")

    logger.info("Generated " + str(len(cleaned_configs)) + " clean IP configs (1 per IP)")
    return cleaned_configs
