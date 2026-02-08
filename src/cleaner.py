import base64
import json
import logging
import urllib.parse
import copy
import random

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


def apply_clean_ip_vmess(raw, clean_ip):
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

        # آدرس اصلی رو بذار توی host (برای CDN)
        if not data.get("host", ""):
            data["host"] = original_address

        # آیپی تمیز رو بذار جای آدرس
        data["add"] = clean_ip

        new_json = json.dumps(data, ensure_ascii=False)
        new_b64 = base64.b64encode(new_json.encode("utf-8")).decode("utf-8")
        return "vmess://" + new_b64

    except Exception as e:
        logger.debug("Failed to apply clean IP to vmess: " + str(e))
        return None


def apply_clean_ip_vless(raw, clean_ip):
    try:
        # vless://uuid@address:port?params#name
        # باید address رو عوض کنیم و host رو بذاریم آدرس اصلی

        parsed = urllib.parse.urlparse(raw)
        original_host = parsed.hostname
        port = parsed.port
        userinfo = parsed.username or ""

        params = dict(urllib.parse.parse_qsl(parsed.query))

        # آدرس اصلی رو بذار توی host
        if "host" not in params or not params["host"]:
            params["host"] = original_host

        # SNI هم باید آدرس اصلی باشه
        if "sni" not in params or not params["sni"]:
            params["sni"] = original_host

        # کوئری جدید بساز
        new_query = urllib.parse.urlencode(params)

        # فرگمنت (اسم)
        fragment = parsed.fragment or ""

        # لینک جدید با آیپی تمیز
        new_url = "vless://" + userinfo + "@" + clean_ip + ":" + str(port) + "?" + new_query
        if fragment:
            new_url += "#" + fragment

        return new_url

    except Exception as e:
        logger.debug("Failed to apply clean IP to vless: " + str(e))
        return None


def apply_clean_ips(configs, clean_ips):
    if not clean_ips:
        logger.warning("No clean IPs! Skipping...")
        return []

    cleaned_configs = []

    for config in configs:
        for ip in clean_ips:
            if config.protocol == "vmess":
                new_raw = apply_clean_ip_vmess(config.raw, ip)
            elif config.protocol == "vless":
                new_raw = apply_clean_ip_vless(config.raw, ip)
            else:
                continue

            if new_raw:
                new_config = copy.copy(config)
                new_config.raw = new_raw
                new_config.address = ip
                cleaned_configs.append(new_config)

    logger.info("Generated " + str(len(cleaned_configs)) + " clean IP configs")
    return cleaned_configs
