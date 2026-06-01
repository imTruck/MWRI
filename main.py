import os
import json
import base64
import logging
import urllib.parse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

# منابع فعال و باکیفیت شما برای جمع‌آوری آسان بالای ۸۰۰ کانفیگ زنده
SOURCES = [
    "https://raw.githubusercontent.com/LalatinaHub/Mineral/refs/heads/master/result/nodes",
    "https://raw.githubusercontent.com/SoliSpirit/v2ray-configs/main/sub.txt",
    "https://raw.githubusercontent.com/Mahdi0024/v2ray-collector/main/sub/mix"
]

PREFIX = "mwri"
EMOJI = "🧘🏽"

def rename_config(raw_config, new_name):
    """تغییر نام بسیار تمیز کانفیگ‌ها بدون تغییر در پارامترهای فنی"""
    raw_config = raw_config.strip()
    if not raw_config:
        return None
    
    # برای پروتکل‌های VLESS, Trojan, Shadowsocks
    if not raw_config.startswith("vmess://"):
        parts = raw_config.split("#", 1)
        return f"{parts[0]}#{urllib.parse.quote(new_name)}"
    
    # برای پروتکل VMESS (بیس۶۴)
    try:
        b64 = raw_config.replace("vmess://", "")
        padding = 4 - len(b64) % 4
        if padding != 4:
            b64 += "=" * padding
        data = json.loads(base64.b64decode(b64).decode("utf-8", errors="ignore"))
        data["ps"] = new_name
        new_json = json.dumps(data, ensure_ascii=False)
        return "vmess://" + base64.b64encode(new_json.encode("utf-8")).decode("utf-8")
    except:
        return raw_config

def main():
    import requests
    os.makedirs("output", exist_ok=True)
    
    # ۱. دانلود کانفیگ‌ها
    raw_lines = []
    for url in SOURCES:
        logger.info(f"Downloading from {url.split('/')[-2]}...")
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                raw_lines.extend(res.text.splitlines())
        except Exception as e:
            logger.warning(f"Failed to download: {e}")

    # ۲. حذف کانفیگ‌های تکراری
    unique_raw_configs = []
    seen_raws = set()
    for line in raw_lines:
        line = line.strip()
        if not line or line in seen_raws:
            continue
        if any(line.startswith(p) for p in ["vless://", "vmess://", "trojan://", "ss://"]):
            unique_raw_configs.append(line)
            seen_raws.add(line)

    logger.info(f"Total unique configs collected: {len(unique_raw_configs)}")
    
    # تضمین استفاده از حداکثر ۸۰۰ کانفیگ برای ۸ ساب ۱۰۰ تایی
    max_configs_needed = 800
    selected_raws = unique_raw_configs[:max_configs_needed]
    
    # ۳. تقسیم‌بندی و تغییر نام شیک
    CHUNK_SIZE = 100
    MAX_SUBS = 8
    
    for sub_idx in range(MAX_SUBS):
        sub_number = sub_idx + 1
        start_pos = sub_idx * CHUNK_SIZE
        end_pos = start_pos + CHUNK_SIZE
        
        chunk_raws = selected_raws[start_pos:end_pos]
        
        if not chunk_raws:
            logger.warning(f"No configs left for Sub {sub_number}")
            continue
            
        renamed_chunk = []
        for item_idx, raw_link in enumerate(chunk_raws):
            item_number = item_idx + 1
            # فرمت دقیق نام‌گذاری شیک شما: mwri🧘🏽 | S1 - 1
            new_name = f"{PREFIX}{EMOJI} | S{sub_number} - {item_number}"
            renamed = rename_config(raw_link, new_name)
            if renamed:
                renamed_chunk.append(renamed)
                
        # ذخیره مستقیم به صورت متنی (Plain Text) که خواسته بودی
        plain_file = f"output/sub{sub_number}.txt"
        with open(plain_file, "w", encoding="utf-8") as f:
            for c in renamed_chunk:
                f.write(c + "\n")
                
        # همچنین ذخیره به صورت بیس۶۴ جهت همگام‌سازی کامل
        b64_file = f"output/sub{sub_number}_sub.txt"
        b64_data = base64.b64encode(("\n".join(renamed_chunk)).encode("utf-8")).decode("utf-8")
        with open(b64_file, "w", encoding="utf-8") as f:
            f.write(b64_data)
            
        logger.info(f"[+] Sub {sub_number} successfully saved with {len(renamed_chunk)} configs.")

    logger.info("=== SUCCESS: All 8 sub files generated successfully! ===")

if __name__ == "__main__":
    main()