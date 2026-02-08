import base64
import json
import logging
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# اسم کانفیگ‌ها - این توی همه برنامه‌ها نشون داده میشه
PREFIX = "mwri🧘🏽"


def rename_config(raw, protocol, number):
    """
    اسم کانفیگ رو عوض میکنه
    نتیجه: mwri🧘🏽 VLESS #1
    این اسم توی همه برنامه‌ها نشون داده میشه چون
    توی خود کانفیگ تغییر میکنه نه فقط ظاهری
    """
    new_name = f"{PREFIX} #{number}"

    try:
        if protocol == "vmess":
            b64 = raw.replace("vmess://", "")
            padding = 4 - len(b64) % 4
            if padding != 4:
                b64 += '=' * padding
            try:
                decoded = base64.b64decode(b64).decode('utf-8', errors='ignore')
            except Exception:
                decoded = base64.urlsafe_b64decode(b64).decode('utf-8', errors='ignore')

            data = json.loads(decoded)
            # اسم رو عوض کن
            data["ps"] = new_name
            new_json = json.dumps(data, ensure_ascii=False)
            new_b64 = base64.b64encode(new_json.encode('utf-8')).decode('utf-8')
            return f"vmess://{new_b64}"

        else:
            # vless, trojan, ss, hysteria2, tuic, hy2
            # همشون اسم رو توی # دارن
            if '#' in raw:
                base_part = raw.rsplit('#', 1)[0]
            else:
                base_part = raw
            encoded_name = urllib.parse.quote(new_name, safe='')
            return f"{base_part}#{encoded_name}"

    except Exception as e:
        logger.debug(f"Rename failed: {e}")
        # حتی اگه خطا خورد، اسم رو اضافه کن
        if '#' in raw:
            base_part = raw.rsplit('#', 1)[0]
        else:
            base_part = raw
        encoded_name = urllib.parse.quote(new_name, safe='')
        return f"{base_part}#{encoded_name}"


def rename_all(configs):
    """همه کانفیگ‌ها رو rename میکنه و لیست خام جدید برمیگردونه"""
    renamed = []
    for i, config in enumerate(configs, 1):
        new_raw = rename_config(config.raw, config.protocol, i)
        renamed.append(new_raw)
    return renamed


def save_txt(configs, filepath):
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    renamed = rename_all(configs)
    with open(filepath, 'w', encoding='utf-8') as f:
        for line in renamed:
            f.write(line + '\n')
    logger.info(f"Saved {len(configs)} configs -> {filepath}")


def save_base64(configs, filepath):
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    renamed = rename_all(configs)
    raw_text = '\n'.join(renamed)
    encoded = base64.b64encode(raw_text.encode('utf-8')).decode('utf-8')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(encoded)
    logger.info(f"Saved {len(configs)} configs (base64 sub) -> {filepath}")


def save_json(configs, filepath):
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    renamed = rename_all(configs)
    data = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total": len(configs),
        "configs": [{
            "name": f"{PREFIX} {c.protocol.upper()} #{i}",
            "protocol": c.protocol,
            "address": c.address,
            "port": c.port,
            "latency_ms": c.latency,
            "alive": c.is_alive,
            "raw": renamed[i-1],
        } for i, c in enumerate(configs, 1)]
    }
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(configs)} configs (json) -> {filepath}")


def save_by_protocol(configs, output_dir="output"):
    Path(f"{output_dir}/splitted").mkdir(parents=True, exist_ok=True)

    by_protocol = {}
    for c in configs:
        proto = c.protocol
        if proto not in by_protocol:
            by_protocol[proto] = []
        by_protocol[proto].append(c)

    logger.info(f"\n--- Saving by protocol ---")

    for protocol, proto_configs in sorted(by_protocol.items()):
        txt_path = f"{output_dir}/splitted/{protocol}.txt"
        save_txt(proto_configs, txt_path)

        sub_path = f"{output_dir}/splitted/{protocol}_sub.txt"
        save_base64(proto_configs, sub_path)

        logger.info(f"  {protocol}: {len(proto_configs)} configs")

    return by_protocol


def generate_readme(all_configs, best_configs):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    alive = [c for c in all_configs if c.is_alive]

    protocols = {}
    for c in best_configs:
        protocols[c.protocol] = protocols.get(c.protocol, 0) + 1

    avg_latency = 0
    if best_configs:
        avg_latency = sum(c.latency for c in best_configs) / len(best_configs)

    readme = f"""# mwri🧘🏽 V2Ray Config Collector

> Last Updated: **{now}**

## Stats

| Metric | Value |
|--------|-------|
| Total Collected | {len(all_configs)} |
| Alive | {len(alive)} |
| Best Selected | {len(best_configs)} |
| Avg Latency | {avg_latency:.0f} ms |
| Ports | 80, 443 only |

## Protocols

| Protocol | Count |
|----------|-------|
"""
    for proto, count in sorted(protocols.items()):
        readme += f"| {proto} | {count} |\n"

    readme += """
| vless | 0 |
| trojan | 0 |

## Download

- [All Configs](./output/all.txt)
- [All Configs (Base64 Sub)](./output/all_sub.txt)
- [All Configs (JSON)](./output/all.json)

### By Protocol

- [VLESS](./output/splitted/vless.txt)
- [Trojan](./output/splitted/trojan.txt)
- [VMess](./output/splitted/vmess.txt)
- [Hysteria2](./output/splitted/hysteria2.txt)

## Features

✅ Auto collect from sources  
✅ Test latency & alive status  
✅ Auto rename with prefix  
✅ Multiple export formats  
✅ Split by protocol  
"""
    return readme