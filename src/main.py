#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import math
import urllib.parse
from pathlib import Path

import requests

SOURCES = [
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
    "https://key.zarazaex.xyz/sub",
    "https://raw.githubusercontent.com/Efration/ZerondOne/refs/heads/main/ZerondOne.txt",
    "https://raw.githubusercontent.com/iampedii/whitedns-sub/refs/heads/main/base64.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_SS+All_RUS.txt",
]

NAME_PREFIX = "mwri"
EMOJI = "🧘🏽"
CHUNK_SIZE = 300
OUTPUT_DIR = Path("output")
TIMEOUT = 20
SUPPORTED_PREFIXES = (
    "vmess://",
    "vless://",
    "trojan://",
    "ss://",
    "ssr://",
    "hysteria://",
    "hy2://",
    "tuic://",
)


def unwrap_markdown_url(value: str) -> str:
    value = value.strip()
    if value.startswith("[") and "](" in value and value.endswith(")"):
        try:
            _, right = value.split("](", 1)
            return right[:-1].strip()
        except ValueError:
            return value
    return value


def decode_base64_loose(value: str) -> str | None:
    cleaned = "".join(value.split())
    if not cleaned:
        return None
    padding = (-len(cleaned)) % 4
    try:
        raw = base64.b64decode(cleaned + ("=" * padding), validate=False)
    except Exception:
        return None
    if not raw:
        return None
    try:
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        return None


def maybe_decode_blob(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    if any(prefix in text for prefix in SUPPORTED_PREFIXES):
        return text
    decoded = decode_base64_loose(text)
    if decoded and any(prefix in decoded for prefix in SUPPORTED_PREFIXES):
        return decoded
    return text


def extract_links(text: str) -> list[str]:
    text = maybe_decode_blob(text)
    links: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip().replace("\ufeff", "")
        if not line:
            continue
        if line.startswith(SUPPORTED_PREFIXES):
            links.append(line)
            continue
        decoded = decode_base64_loose(line)
        if decoded and decoded.startswith(SUPPORTED_PREFIXES):
            links.append(decoded.strip())
    return links


def rename_config(link: str, new_name: str) -> str | None:
    link = link.strip()
    if not link:
        return None

    if link.startswith("vmess://"):
        try:
            encoded = link[len("vmess://") :]
            decoded = decode_base64_loose(encoded)
            if not decoded:
                return None
            data = json.loads(decoded)
            data["ps"] = new_name
            payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            return "vmess://" + base64.b64encode(payload).decode("utf-8")
        except Exception:
            return link

    base = link.split("#", 1)[0]
    return f"{base}#{urllib.parse.quote(new_name)}"


def fetch_source(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    return response.text


def cleanup_old_outputs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in OUTPUT_DIR.glob("sub*.txt"):
        path.unlink(missing_ok=True)
    for path in OUTPUT_DIR.glob("sub*_sub.txt"):
        path.unlink(missing_ok=True)
    (OUTPUT_DIR / "summary.json").unlink(missing_ok=True)


def write_outputs(renamed_links: list[str]) -> None:
    cleanup_old_outputs()

    total_configs = len(renamed_links)
    total_subs = math.ceil(total_configs / CHUNK_SIZE) if total_configs else 0

    for part in range(total_subs):
        start = part * CHUNK_SIZE
        chunk = renamed_links[start : start + CHUNK_SIZE]
        plain_text = "\n".join(chunk)

        plain_path = OUTPUT_DIR / f"sub{part + 1}.txt"
        b64_path = OUTPUT_DIR / f"sub{part + 1}_sub.txt"

        plain_path.write_text(plain_text, encoding="utf-8")
        b64_path.write_text(base64.b64encode(plain_text.encode("utf-8")).decode("utf-8"), encoding="utf-8")

    summary = {
        "total_configs": total_configs,
        "chunk_size": CHUNK_SIZE,
        "total_subs": total_subs,
        "files": [f"sub{i + 1}.txt" for i in range(total_subs)],
        "base64_files": [f"sub{i + 1}_sub.txt" for i in range(total_subs)],
    }
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": "MWRI-Sub-Builder/1.0"})

    all_links: list[str] = []
    seen: set[str] = set()

    for source in SOURCES:
        url = unwrap_markdown_url(source)
        try:
            text = fetch_source(session, url)
            extracted = extract_links(text)
            added = 0
            for link in extracted:
                normalized = link.strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    all_links.append(normalized)
                    added += 1
            print(f"[+] {url} -> {added} configs")
        except Exception as exc:
            print(f"[!] {url} -> {exc}")

    renamed_links: list[str] = []
    for index, link in enumerate(all_links, start=1):
        new_name = f"{NAME_PREFIX} {EMOJI} {index}"
        renamed = rename_config(link, new_name)
        if renamed:
            renamed_links.append(renamed)

    write_outputs(renamed_links)

    total_subs = math.ceil(len(renamed_links) / CHUNK_SIZE) if renamed_links else 0
    print("----------------------------------------")
    print(f"Total configs: {len(renamed_links)}")
    print(f"Chunk size: {CHUNK_SIZE}")
    print(f"Total subs: {total_subs}")
    print(f"Output dir: {OUTPUT_DIR.resolve()}")
    print("Done.")


if __name__ == "__main__":
    main()
