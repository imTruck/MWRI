import base64
import json
import urllib.parse
import copy
import logging
from src.geoip import get_flag

logger = logging.getLogger(__name__)

PREFIX = "mwri\U0001F9D8\U0001F3FD"

FRAGMENT_SETTINGS = [
    {"length": "100-200", "interval": "10-20", "packets": "tlshello"},
    {"length": "1-3", "interval": "1-3", "packets": "tlshello"},
    {"length": "10-100", "interval": "10-50", "packets": "tlshello"},
]


def add_fragment_vmess(raw, fragment, name):
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

        port = int(data.get("port", 0))
        if port not in [443, 8443, 2053, 2083, 2087, 2096]:
            return None

        data["ps"] = name
        new_json = json.dumps(data, ensure_ascii=False)
        return "vmess://" + base64.b64encode(new_json.encode("utf-8")).decode("utf-8")
    except Exception:
        return None


def add_fragment_vless(raw, fragment, name):
    try:
        parsed = urllib.parse.urlparse(raw)
        params = dict(urllib.parse.parse_qsl(parsed.query))

        port = parsed.port or 0
        if port not in [443, 8443, 2053, 2083, 2087, 2096]:
            return None

        security = params.get("security", "")
        if security != "tls" and security != "reality":
            return None

        if "#" in raw:
            base_part = raw.rsplit("#", 1)[0]
        else:
            base_part = raw
        return base_part + "#" + urllib.parse.quote(name, safe="")
    except Exception:
        return None


def generate_fragment_configs(configs):
    if not configs:
        return []

    frag = FRAGMENT_SETTINGS[0]
    result = []

    for i, c in enumerate(configs):
        flag = get_flag(c.address)
        name = flag + " " + PREFIX + " frag#" + str(i + 1)

        if c.protocol == "vmess":
            new_raw = add_fragment_vmess(c.raw, frag, name)
        elif c.protocol == "vless":
            new_raw = add_fragment_vless(c.raw, frag, name)
        else:
            continue

        if new_raw:
            new_c = copy.copy(c)
            new_c.raw = new_raw
            new_c.name = name
            result.append(new_c)

    logger.info("Fragment configs: " + str(len(result)))
    return result
