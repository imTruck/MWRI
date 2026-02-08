import base64
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def save_txt(configs, filepath):
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        for config in configs:
            f.write(config.raw + '\n')
    logger.info(f"Saved {len(configs)} configs -> {filepath}")


def save_base64(configs, filepath):
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    raw_text = '\n'.join(c.raw for c in configs)
    encoded = base64.b64encode(raw_text.encode('utf-8')).decode('utf-8')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(encoded)
    logger.info(f"Saved {len(configs)} configs (base64 sub) -> {filepath}")


def save_json(configs, filepath):
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    data = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total": len(configs),
        "configs": [{
            "protocol": c.protocol,
            "address": c.address,
            "port": c.port,
            "name": c.name,
            "latency_ms": c.latency,
            "alive": c.is_alive,
            "raw": c.raw,
        } for c in configs]
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

    readme = f"""# MWRI - V2Ray Config Collector

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

    return readme