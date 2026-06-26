#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import random
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
MAX_STANDARD_SUBS = 4
OUTPUT_DIR = Path("output")
README_PATH = Path("README.md")
TIMEOUT = 20

REPO_OWNER = "imTruck"
REPO_NAME = "MWRI"
REPO_BRANCH = "main"

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

DISPLAY_QUERY_KEYS = {
    "remarks",
    "remark",
    "ps",
    "name",
    "title",
}

DISPLAY_JSON_KEYS = {
    "ps",
    "remark",
    "remarks",
    "name",
    "title",
}


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


def canonicalize_vmess(link: str) -> str:
    encoded = link[len("vmess://") :]
    decoded = decode_base64_loose(encoded)
    if not decoded:
        return link.split("#", 1)[0].strip()

    try:
        data = json.loads(decoded)
    except Exception:
        return link.split("#", 1)[0].strip()

    for key in DISPLAY_JSON_KEYS:
        data.pop(key, None)

    return "vmess://" + json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonicalize_ssr(link: str) -> str:
    encoded = link[len("ssr://") :]
    decoded = decode_base64_loose(encoded)
    if not decoded:
        return link.split("#", 1)[0].strip()

    base, sep, query = decoded.partition("/?")
    if not sep:
        return "ssr://" + base

    pairs = urllib.parse.parse_qsl(query, keep_blank_values=True)
    pairs = [(k, v) for k, v in pairs if k.lower() not in DISPLAY_QUERY_KEYS | {"group"}]
    pairs.sort()
    normalized_query = urllib.parse.urlencode(pairs, doseq=True)
    return f"ssr://{base}/?{normalized_query}" if normalized_query else f"ssr://{base}"


def canonicalize_generic_url(link: str) -> str:
    parsed = urllib.parse.urlsplit(link)
    pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    pairs = [(k, v) for k, v in pairs if k.lower() not in DISPLAY_QUERY_KEYS]
    pairs.sort()
    normalized_query = urllib.parse.urlencode(pairs, doseq=True)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, normalized_query, ""))


def canonical_key(link: str) -> str:
    link = link.strip()
    if link.startswith("vmess://"):
        return canonicalize_vmess(link)
    if link.startswith("ssr://"):
        return canonicalize_ssr(link)
    return canonicalize_generic_url(link)


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


def raw_output_url(file_name: str) -> str:
    return f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{REPO_BRANCH}/output/{file_name}"


def github_output_url(file_name: str) -> str:
    return f"https://github.com/{REPO_OWNER}/{REPO_NAME}/blob/{REPO_BRANCH}/output/{file_name}"


def split_links(links: list[str]) -> list[list[str]]:
    if not links:
        return []

    chunks: list[list[str]] = []
    first_part_limit = CHUNK_SIZE * MAX_STANDARD_SUBS

    for start in range(0, min(len(links), first_part_limit), CHUNK_SIZE):
        chunks.append(links[start : start + CHUNK_SIZE])

    if len(links) > first_part_limit:
        chunks.append(links[first_part_limit:])

    return chunks


def build_readme_content(total_subs: int, total_configs: int) -> str:
    lines: list[str] = []

    lines.extend([
        "# MWRI",
        "",
        '<p align="center">',
        "  <b>Dynamic Subscription Builder</b>",
        "  <br>",
        "  Extract • Rename • Split • Publish",
        "</p>",
        "",
        '<p align="center">',
        "  کانفیگ‌ها از چند سورس جمع می‌شوند، موارد تکراری واقعی حذف می‌شوند، ترتیب خروجی‌ها رندوم می‌شود و اسم همه به فرمت یکسان تغییر می‌کند.",
        "</p>",
        "",
        "---",
        "",
        "## ✨ Features",
        "",
        "- استخراج کانفیگ از چند Subscription Source",
        "- حذف کانفیگ‌های تکراری واقعی حتی اگر اسمشان فرق داشته باشد",
        "- رندوم شدن ترتیب خروجی‌ها در هر آپدیت",
        "- Rename کردن همه کانفیگ‌ها با فرمت زیر:",
        "",
        "```text",
        "mwri 🧘🏽 1",
        "mwri 🧘🏽 2",
        "mwri 🧘🏽 3",
        "```",
        "",
        "- ساخت خروجی‌های داینامیک",
        "- `sub1` تا `sub4` هرکدام حداکثر `300` کانفیگ",
        "- باقی کانفیگ‌ها همگی داخل `sub5`",
        "- ساخت نسخه متنی و Base64 برای هر خروجی",
        "- آپدیت خودکار `README.md` با لینک‌های قابل کپی",
        "",
        "---",
        "",
        "## 📊 Current Build",
        "",
        f"- **Total Configs:** `{total_configs}`",
        f"- **Chunk Size:** `{CHUNK_SIZE}`",
        f"- **Total Subs:** `{total_subs}`",
        f"- **Output Folder:** [output/](https://github.com/{REPO_OWNER}/{REPO_NAME}/tree/{REPO_BRANCH}/output)",
        "",
        "---",
        "",
        "## 🚀 Quick Copy Links",
        "",
    ])

    if total_subs == 0:
        lines.extend([
            "هنوز هیچ خروجی‌ای ساخته نشده. بعد از اجرای اسکریپت، لینک‌ها اینجا قرار می‌گیرند.",
            "",
        ])
    else:
        for index in range(1, total_subs + 1):
            raw_file = f"sub{index}_sub.txt"
            text_file = f"sub{index}.txt"
            raw_url = raw_output_url(raw_file)
            open_raw_url = github_output_url(raw_file)
            open_text_url = github_output_url(text_file)

            lines.extend([
                f"### Subscription {index}",
                "",
                f"- **Base64 File:** [{raw_file}]({open_raw_url})",
                f"- **Text File:** [{text_file}]({open_text_url})",
                f"- **Raw Link:** [{raw_url}]({raw_url})",
                "",
                "> برای کپی سریع، از دکمه `Copy` بالای باکس استفاده کن.",
                "",
                "```text",
                raw_url,
                "```",
                "",
            ])

    lines.extend([
        "---",
        "",
        "## 🧠 Split Logic",
        "",
        "قانون تقسیم این پروژه این است:",
        "",
        "- `sub1` تا `sub4` → هرکدام حداکثر `300` کانفیگ",
        "- اگر کانفیگ اضافه بماند → همه داخل `sub5`",
        "",
        "### مثال",
        "- `850` config → `sub1=300`, `sub2=300`, `sub3=250`",
        "- `1200` config → `4` sub",
        "- `1400` config → `sub1..sub4=300`, `sub5=200`",
        "- `2500` config → `sub1..sub4=300`, `sub5=1300`",
        "",
        "---",
        "",
        "## ⚙️ Run Locally",
        "",
        "```bash",
        "pip install -r requirements.txt",
        "python .\\src\\main.py",
        "```",
        "",
        "---",
        "",
        "## 🛠 Sources",
        "",
        "```text",
    ])

    lines.extend(SOURCES)

    lines.extend([
        "```",
        "",
        "---",
        "",
        "## ❤️ MWRI",
        "",
        "Simple, clean, focused.",
        "",
    ])

    return "\n".join(lines)


def write_readme(total_subs: int, total_configs: int) -> None:
    README_PATH.write_text(build_readme_content(total_subs, total_configs), encoding="utf-8")


def write_outputs(renamed_links: list[str]) -> None:
    cleanup_old_outputs()

    chunks = split_links(renamed_links)
    total_configs = len(renamed_links)
    total_subs = len(chunks)

    for index, chunk in enumerate(chunks, start=1):
        plain_text = "\n".join(chunk)

        plain_path = OUTPUT_DIR / f"sub{index}.txt"
        b64_path = OUTPUT_DIR / f"sub{index}_sub.txt"

        plain_path.write_text(plain_text, encoding="utf-8")
        b64_path.write_text(base64.b64encode(plain_text.encode("utf-8")).decode("utf-8"), encoding="utf-8")

    summary = {
        "total_configs": total_configs,
        "chunk_size": CHUNK_SIZE,
        "total_subs": total_subs,
        "rule": "sub1..sub4 up to 300 configs each, everything else goes to sub5",
        "files": [f"sub{i + 1}.txt" for i in range(total_subs)],
        "base64_files": [f"sub{i + 1}_sub.txt" for i in range(total_subs)],
    }

    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_readme(total_subs, total_configs)


def main() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": "MWRI-Sub-Builder/1.0"})

    unique_links: list[str] = []
    seen_keys: set[str] = set()

    for source in SOURCES:
        url = unwrap_markdown_url(source)
        try:
            text = fetch_source(session, url)
            extracted = extract_links(text)

            added = 0
            for link in extracted:
                normalized = link.strip()
                if not normalized:
                    continue

                key = canonical_key(normalized)
                if key in seen_keys:
                    continue

                seen_keys.add(key)
                unique_links.append(normalized)
                added += 1

            print(f"[+] {url} -> {added} unique configs")
        except Exception as exc:
            print(f"[!] {url} -> {exc}")

    random.shuffle(unique_links)

    renamed_links: list[str] = []
    for index, link in enumerate(unique_links, start=1):
        new_name = f"{NAME_PREFIX} {EMOJI} {index}"
        renamed = rename_config(link, new_name)
        if renamed:
            renamed_links.append(renamed)

    write_outputs(renamed_links)

    total_subs = len(split_links(renamed_links))
    print("----------------------------------------")
    print(f"Total unique configs: {len(renamed_links)}")
    print(f"Chunk size: {CHUNK_SIZE}")
    print(f"Total subs: {total_subs}")
    print(f"Output dir: {OUTPUT_DIR.resolve()}")
    print(f"README: {README_PATH.resolve()}")
    print("Done.")


if __name__ == "__main__":
    main()
