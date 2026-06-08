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


def raw_output_url(file_name: str) -> str:
    return f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{REPO_BRANCH}/output/{file_name}"


def github_output_url(file_name: str) -> str:
    return f"https://github.com/{REPO_OWNER}/{REPO_NAME}/blob/{REPO_BRANCH}/output/{file_name}"


def write_readme(total_subs: int, total_configs: int) -> None:
    card_blocks: list[str] = []

    for index in range(1, total_subs + 1):
        file_name = f"sub{index}_sub.txt"
        raw_url = raw_output_url(file_name)
        open_url = github_output_url(file_name)
        card_blocks.append(
            f"## 🔗 Subscription {index}\n\n"
            f"- **Open:** [{file_name}]({open_url})\n"
            f"- **Raw:** [{raw_url}]({raw_url})\n\n"
            f"> برای کپی سریع، از دکمه `Copy` گوشه‌ی باکس پایین استفاده کن.\n\n"
            f"```text\n{raw_url}\n```"
        )

    if not card_blocks:
        card_blocks.append(
            "## 🔗 Subscription Links\n\n"
            "هنوز هیچ فایلی ساخته نشده. بعد از اجرای اسکریپت، لینک‌ها اینجا به‌صورت خودکار قرار می‌گیرند."
        )

    content = f'''# MWRI

<p align="center">
  <b>Dynamic Subscription Builder</b>
  <br>
  Extract • Rename • Split • Publish
</p>

<p align="center">
  کانفیگ‌ها از چند سورس جمع می‌شوند، تکراری‌ها حذف می‌شوند، اسم همه به فرمت یکسان تغییر می‌کند و خروجی‌ها به‌صورت خودکار در فایل‌های ۳۰۰تایی ساخته می‌شوند.
</p>

---

## ✨ Features

- استخراج کانفیگ از چند Subscription Source
- حذف کانفیگ‌های تکراری
- Rename کردن همه کانفیگ‌ها با فرمت زیر:

```text
mwri 🧘🏽 1
mwri 🧘🏽 2
mwri 🧘🏽 3
```

- تقسیم خودکار خروجی‌ها به فایل‌های ۳۰۰تایی
- ساخت نسخه متنی و Base64 برای هر ساب
- به‌روزرسانی خودکار README با لینک‌های قابل کپی

---

## 📊 Current Build

- **Total Configs:** `{total_configs}`
- **Chunk Size:** `{CHUNK_SIZE}`
- **Total Subs:** `{total_subs}`
- **Output Folder:** [`output/`](https://github.com/{REPO_OWNER}/{REPO_NAME}/tree/{REPO_BRANCH}/output)

---

## 🚀 Quick Copy Links

لینک‌های زیر مستقیماً به فایل‌های Subscription اشاره می‌کنند.
روی هر باکس می‌توانی با یک کلیک `Copy` بزنی و لینک را کپی کنی.

{chr(10).join(card_blocks)}

---

## 📁 Output Files

برای هر ساب، دو فایل ساخته می‌شود:

- `subX.txt` → نسخه متنی خام کانفیگ‌ها
- `subX_sub.txt` → نسخه Base64 برای استفاده به‌عنوان Subscription URL

---

## 🧠 Split Logic

تعداد فایل‌ها کاملاً داینامیک است:

```text
total_subs = ceil(total_configs / 300)
```

### مثال
- `900` config → `3` sub
- `1000` config → `4` sub
- `1200` config → `4` sub
- `600` config → `2` sub

---

## ⚙️ Run Locally

```bash
pip install -r requirements.txt
python .\\src\\main.py
```

---

## 🛠 Sources

```text
https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt
https://key.zarazaex.xyz/sub
https://raw.githubusercontent.com/Efration/ZerondOne/refs/heads/main/ZerondOne.txt
https://raw.githubusercontent.com/iampedii/whitedns-sub/refs/heads/main/base64.txt
https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_SS+All_RUS.txt
```

---

## ❤️ MWRI

Simple, clean, dynamic.
'''
    README_PATH.write_text(content, encoding="utf-8")


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
    write_readme(total_subs, total_configs)


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
    print(f"README: {README_PATH.resolve()}")
    print("Done.")


if __name__ == "__main__":
    main()
