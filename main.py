import os
import json
import base64
import logging
import urllib.parse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

# منابع فعال و عالی شما
SOURCES = [
    "https://raw.githubusercontent.com/LalatinaHub/Mineral/refs/heads/master/result/nodes",
    "https://raw.githubusercontent.com/SoliSpirit/v2ray-configs/main/sub.txt",
    "https://raw.githubusercontent.com/Mahdi0024/v2ray-collector/main/sub/mix"
]

PREFIX = "mwri"
EMOJI = "🧘🏽"

def rename_config(raw_config, new_name):
    """تغییر نام کانفیگ‌ها به mwri🧘🏽 بدون دستکاری در پارامترهای فنی دیگر"""
    raw_config = raw_config.strip()
    if not raw_config:
        return None
    
    # برای پروتکل‌های VLESS, Trojan, Shadowsocks
    if not raw_config.startswith("vmess://"):
        parts = raw_config.split("#", 1)
        return f"{parts[0]}#{urllib.parse.quote(new_name)}"
    
    # برای پروتکل VMESS
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
    
    # ۱. دانلود کانفیگ‌ها از منابع
    raw_lines = []
    for url in SOURCES:
        logger.info(f"Downloading from {url.split('/')[-2]}...")
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                raw_lines.extend(res.text.splitlines())
        except Exception as e:
            logger.warning(f"Failed to download: {e}")

    # ۲. حذف کدهای تکراری و تغییر نام همزمان
    final_configs = []
    seen_raws = set()
    count = 1
    
    for line in raw_lines:
        line = line.strip()
        if not line or line in seen_raws:
            continue
            
        # بررسی فرمت کلی کانفیگ‌ها
        if any(line.startswith(p) for p in ["vless://", "vmess://", "trojan://", "ss://"]):
            new_name = f"{PREFIX}{EMOJI} | {count}"
            renamed = rename_config(line, new_name)
            if renamed:
                final_configs.append(renamed)
                seen_raws.add(line)
                count += 1
                
    logger.info(f"Collected and renamed {len(final_configs)} unique configs.")

    # ۳. ذخیره در فایل متنی
    with open("output/clean.txt", "w", encoding="utf-8") as f:
        for c in final_configs:
            f.write(c + "\n")
            
    # ۴. ذخیره به صورت Base64 (اشتراک سابسکریپشن)
    b64_data = base64.b64encode(("\n".join(final_configs)).encode("utf-8")).decode("utf-8")
    with open("output/clean_sub.txt", "w", encoding="utf-8") as f:
        f.write(b64_data)

    logger.info("=== SUCCESS: All configs successfully collected and renamed! ===")

if __name__ == "__main__":
    main()