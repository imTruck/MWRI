import base64
import json
import logging
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

PREFIX = "mwri\U0001F9D8\U0001F3FD"


def rename_config(raw, protocol, number):
    new_name = PREFIX + " #" + str(number)
    try:
        if protocol == "vmess":
            b64 = raw.replace("vmess://", "")
            padding = 4 - len(b64) % 4
            if padding != 4:
                b64 += "=" * padding
            try:
                decoded = base64.b64decode(b64).decode("utf-8", errors="ignore")
            except Exception:
                decoded = base64.urlsafe_b64decode(b64).decode("utf-8", errors="ignore")
            data = json.loads(decoded)
            data["ps"] = new_name
            new_json = json.dumps(data, ensure_ascii=False)
            new_b64 = base64.b64encode(new_json.encode("utf-8")).decode("utf-8")
            return "vmess://" + new_b64
        elif protocol == "vless":
            if "#" in raw:
                base_part = raw.rsplit("#", 1)[0]
            else:
                base_part = raw
            encoded_name = urllib.parse.quote(new_name, safe="")
            return base_part + "#" + encoded_name
    except Exception:
        if "#" in raw:
            base_part = raw.rsplit("#", 1)[0]
        else:
            base_part = raw
        encoded_name = urllib.parse.quote(new_name, safe="")
        return base_part + "#" + encoded_name


def rename_all(configs):
    renamed = []
    for i, config in enumerate(configs, 1):
        new_raw = rename_config(config.raw, config.protocol, i)
        renamed.append(new_raw)
    return renamed


def save_txt(configs, filepath):
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    renamed = rename_all(configs)
    with open(filepath, "w", encoding="utf-8") as f:
        for line in renamed:
            f.write(line + "\n")
    logger.info("Saved " + str(len(configs)) + " configs -> " + filepath)


def save_base64(configs, filepath):
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    renamed = rename_all(configs)
    raw_text = "\n".join(renamed)
    encoded = base64.b64encode(raw_text.encode("utf-8")).decode("utf-8")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(encoded)
    logger.info("Saved " + str(len(configs)) + " configs (base64) -> " + filepath)


def save_json(configs, filepath):
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    renamed = rename_all(configs)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    data = {"updated_at": now, "total": len(configs), "configs": []}
    for i, c in enumerate(configs, 1):
        data["configs"].append({
            "name": PREFIX + " #" + str(i),
            "protocol": c.protocol,
            "address": c.address,
            "port": c.port,
            "latency_ms": c.latency,
            "alive": c.is_alive,
            "raw": renamed[i - 1],
        })
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Saved " + str(len(configs)) + " configs (json) -> " + filepath)


def save_by_protocol(configs, output_dir="output"):
    Path(output_dir + "/splitted").mkdir(parents=True, exist_ok=True)
    by_protocol = {}
    for c in configs:
        if c.protocol not in by_protocol:
            by_protocol[c.protocol] = []
        by_protocol[c.protocol].append(c)
    for protocol, proto_configs in sorted(by_protocol.items()):
        save_txt(proto_configs, output_dir + "/splitted/" + protocol + ".txt")
        save_base64(proto_configs, output_dir + "/splitted/" + protocol + "_sub.txt")
    return by_protocol


def generate_readme(all_configs, best_configs):
    return "# mwri Config Collector"
