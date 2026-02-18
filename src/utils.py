import base64
import json
import logging
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from src.geoip import get_flag

logger = logging.getLogger(__name__)

PREFIX = "mwri\U0001F9D8\U0001F3FD"
REPO = "imTruck/MWRI"
RAW_BASE = "https://raw.githubusercontent.com/" + REPO + "/main/"


def rename_config(raw, protocol, number, flag=""):
    new_name = flag + " " + PREFIX + " #" + str(number) if flag else PREFIX + " #" + str(number)
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
            return "vmess://" + base64.b64encode(new_json.encode("utf-8")).decode("utf-8")
        else:
            if "#" in raw:
                base_part = raw.rsplit("#", 1)[0]
            else:
                base_part = raw
            return base_part + "#" + urllib.parse.quote(new_name, safe="")
    except Exception:
        if "#" in raw:
            base_part = raw.rsplit("#", 1)[0]
        else:
            base_part = raw
        return base_part + "#" + urllib.parse.quote(new_name, safe="")


def rename_all(configs):
    renamed = []
    for i, c in enumerate(configs, 1):
        flag = get_flag(c.address)
        renamed.append(rename_config(c.raw, c.protocol, i, flag))
    return renamed


def save_txt(configs, filepath):
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    renamed = rename_all(configs)
    with open(filepath, "w", encoding="utf-8") as f:
        for line in renamed:
            f.write(line + "\n")
    logger.info("Saved " + str(len(configs)) + " -> " + filepath)


def save_base64(configs, filepath):
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    renamed = rename_all(configs)
    raw_text = "\n".join(renamed)
    encoded = base64.b64encode(raw_text.encode("utf-8")).decode("utf-8")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(encoded)
    logger.info("Saved " + str(len(configs)) + " (b64) -> " + filepath)


def save_json(configs, filepath):
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    renamed = rename_all(configs)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    data = {"updated_at": now, "total": len(configs), "configs": []}
    for i, c in enumerate(configs, 1):
        flag = get_flag(c.address)
        name = flag + " " + PREFIX + " #" + str(i) if flag else PREFIX + " #" + str(i)
        data["configs"].append({
            "name": name, "protocol": c.protocol,
            "address": c.address, "port": c.port,
            "latency_ms": c.latency, "raw": renamed[i - 1],
        })
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Saved " + str(len(configs)) + " (json) -> " + filepath)


def save_by_protocol(configs, output_dir="output"):
    Path(output_dir + "/splitted").mkdir(parents=True, exist_ok=True)
    by_protocol = {}
    for c in configs:
        if c.protocol not in by_protocol:
            by_protocol[c.protocol] = []
        by_protocol[c.protocol].append(c)
    for protocol, pcs in sorted(by_protocol.items()):
        save_txt(pcs, output_dir + "/splitted/" + protocol + ".txt")
        save_base64(pcs, output_dir + "/splitted/" + protocol + "_sub.txt")
    return by_protocol


def generate_readme(all_configs, best_configs, alive_count, cdn_count=0):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    protocols = {}
    for c in best_configs:
        protocols[c.protocol] = protocols.get(c.protocol, 0) + 1
    latencies = [c.latency for c in best_configs if c.latency > 0]
    avg = round(sum(latencies) / len(latencies), 1) if latencies else 0
    mn = round(min(latencies), 1) if latencies else 0

    md = "# \U0001F9D8\U0001F3FD MWRI Config Collector\n\n"
    md += "> Auto-updated V2Ray/Xray configs | Tested & Sorted by latency\n\n---\n\n"

    md += "## \U0001F4CA Stats\n\n"
    md += "| | |\n|---|---|\n"
    md += "| \U0001F552 Updated | `" + now + "` |\n"
    md += "| \U0001F4E6 Total | " + str(len(all_configs)) + " |\n"
    md += "| \u2705 Alive | " + str(alive_count) + " |\n"
    md += "| \U0001F3C6 Best | " + str(len(best_configs)) + " |\n"
    md += "| \u2601\uFE0F CDN (Iran) | " + str(cdn_count) + " |\n"
    md += "| \U0001F3CE\uFE0F Fastest | " + str(mn) + "ms |\n"
    md += "| \U0001F4C8 Average | " + str(avg) + "ms |\n\n"

    md += "## \U0001F4E5 For Iranian Users \U0001F1EE\U0001F1F7\n\n"
    md += "| Type | Link |\n|---|---|\n"
    md += "| \u2601\uFE0F CDN (Best for Iran) | `" + RAW_BASE + "output/cdn/best_sub.txt` |\n"
    md += "| \U0001F9F9 Clean IP | `" + RAW_BASE + "output/clean/best_sub.txt` |\n\n"

    md += "## \U0001F310 All Configs\n\n"
    md += "| Type | Link |\n|---|---|\n"
    md += "| Best (Base64) | `" + RAW_BASE + "output/best_base64.txt` |\n"
    md += "| JSON | `" + RAW_BASE + "output/best.json` |\n\n"

    md += "### By Protocol\n\n| Protocol | Count | Sub |\n|---|---|---|\n"
    for p, c in sorted(protocols.items()):
        md += "| " + p.upper() + " | " + str(c) + " | `" + RAW_BASE + "output/splitted/" + p + "_sub.txt` |\n"

    md += "\n---\n> \u26A0\uFE0F Educational purposes only\n"
    return md
