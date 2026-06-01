import os
import ssl
import json
import time
import socket
import base64
import logging
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

# منابع طلایی و سوپر فعال
SOURCES = [
    "https://raw.githubusercontent.com/LalatinaHub/Mineral/refs/heads/master/result/nodes",
    "https://raw.githubusercontent.com/SoliSpirit/v2ray-configs/main/sub.txt",
    "https://raw.githubusercontent.com/Mahdi0024/v2ray-collector/main/sub/mix"
]

PREFIX = "mwri🧘🏽"

class Config:
    def __init__(self, raw):
        self.raw = raw.strip()
        self.protocol = ""
        self.address = ""
        self.port = 0
        self.sni = ""
        self.use_tls = False
        self.is_alive = False
        self.latency = -1
        self._parse()

    def _parse(self):
        try:
            if self.raw.startswith("vless://") or self.raw.startswith("vles://"):
                self.protocol = "vless"
                parsed = urllib.parse.urlparse(self.raw)
                self.address = parsed.hostname
                self.port = parsed.port
                params = dict(urllib.parse.parse_qsl(parsed.query))
                self.sni = params.get("sni", params.get("host", self.address))
                self.use_tls = params.get("security", "").lower() in ["tls", "xtls", "reality"] or self.port in [443, 2083, 8443, 2053, 2087, 2096]
                
            elif self.raw.startswith("vmess://"):
                self.protocol = "vmess"
                b64 = self.raw.replace("vmess://", "")
                padding = 4 - len(b64) % 4
                if padding != 4: b64 += "=" * padding
                data = json.loads(base64.b64decode(b64).decode("utf-8", errors="ignore"))
                self.address = data.get("add", "")
                self.port = int(data.get("port", 0))
                self.sni = data.get("sni", data.get("host", self.address))
                tls_val = str(data.get("tls", "")).lower()
                self.use_tls = tls_val in ["tls", "reality"] or self.port in [443, 2083, 8443, 2053, 2087, 2096]
                
            elif self.raw.startswith("trojan://"):
                self.protocol = "trojan"
                parsed = urllib.parse.urlparse(self.raw)
                self.address = parsed.hostname
                self.port = parsed.port
                params = dict(urllib.parse.parse_qsl(parsed.query))
                self.sni = params.get("sni", params.get("host", self.address))
                self.use_tls = True
                
            elif self.raw.startswith("ss://"):
                self.protocol = "ss"
                raw = self.raw.replace("ss://", "").split("#")[0]
                if "@" in raw:
                    host, p_str = raw.split("@")[1].rsplit(":", 1)
                    self.address, self.port = host.strip("[]"), int(p_str)
        except:
            pass

def test_config(config):
    if not config.address or not config.port:
        return config
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.5)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        
        start = time.perf_counter()
        sock.connect((config.address, config.port))
        
        if config.use_tls:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            ssl_sock = context.wrap_socket(sock, server_hostname=config.sni if config.sni else config.address)
            ssl_sock.do_handshake()
            ssl_sock.close()
        else:
            sock.close()
            
        config.latency = round((time.perf_counter() - start) * 1000, 1)
        config.is_alive = True
    except:
        if sock: sock.close()
        config.is_alive = False
    return config

def rename_config(raw_config, new_name):
    """تغییر نام کانفیگ بدون دستکاری در پارامترهای فنی اصلی"""
    raw_config = raw_config.strip()
    if not raw_config:
        return None
    
    # برای پروتکل‌های غیر vmess (مثل vless, trojan, ss)
    if not raw_config.startswith("vmess://"):
        parts = raw_config.split("#", 1)
        return f"{parts[0]}#{urllib.parse.quote(new_name)}"
    
    # برای پروتکل vmess که به صورت بیس۶۴ جی‌سان است
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
    
    # 1. Download
    raw_lines = []
    for url in SOURCES:
        logger.info(f"Downloading from {url.split('/')[-2]}...")
        try:
            res = requests.get(url, timeout=8)
            if res.status_code == 200:
                raw_lines.extend(res.text.splitlines())
        except Exception as e:
            logger.warning(f"Failed to download: {e}")

    # 2. Parse & Remove Duplicates
    configs = []
    seen_raws = set()
    for line in raw_lines:
        line = line.strip()
        if not line or line in seen_raws:
            continue
        c = Config(line)
        if c.protocol and c.address:
            configs.append(c)
            seen_raws.add(line)
            
    logger.info(f"Parsed {len(configs)} unique configs.")

    # 3. Test on your connection (500 workers)
    logger.info("Testing with 500 workers...")
    tested_configs = []
    with ThreadPoolExecutor(max_workers=500) as executor:
        futures = {executor.submit(test_config, c): c for c in configs}
        for future in as_completed(futures):
            tested_configs.append(future.result())

    alive_configs = [c for c in tested_configs if c.is_alive]
    alive_configs.sort(key=lambda x: x.latency)
    logger.info(f"Total Alive configs: {len(alive_configs)} / {len(configs)}")

    if not alive_configs:
        logger.warning("No alive configs found!")
        return

    # 4. Rename all alive configs to "mwri🧘🏽 | No."
    final_configs = []
    for idx, c in enumerate(alive_configs):
        new_name = f"{PREFIX} | {idx+1}"
        renamed = rename_config(c.raw, new_name)
        if renamed:
            final_configs.append(renamed)

    # 5. Save output files
    # ذخیره متنی عادی
    with open("output/clean.txt", "w", encoding="utf-8") as f:
        for c in final_configs:
            f.write(c + "\n")
            
    # ذخیره بیس ۶۴ (لینک سابسکریپشن اصلی شما)
    b64_data = base64.b64encode(("\n".join(final_configs)).encode("utf-8")).decode("utf-8")
    with open("output/clean_sub.txt", "w", encoding="utf-8") as f:
        f.write(b64_data)

    logger.info(f"=== SUCCESS: Generated {len(final_configs)} working nodes renamed to mwri🧘🏽 ===")

if __name__ == "__main__":
    main()