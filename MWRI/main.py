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

SOURCE_URL = "https://raw.githubusercontent.com/LalatinaHub/Mineral/refs/heads/master/result/nodes"
TARGET_PORTS = [443, 2083, 8443]
PREFIX = "mwri⚡"

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
        self.is_cdn = False
        self._parse()

    def _parse(self):
        try:
            if self.raw.startswith("vless://"):
                self.protocol = "vless"
                parsed = urllib.parse.urlparse(self.raw)
                self.address = parsed.hostname
                self.port = parsed.port
                params = dict(urllib.parse.parse_qsl(parsed.query))
                self.sni = params.get("sni", params.get("host", self.address))
                security = params.get("security", "").lower()
                self.use_tls = security in ["tls", "xtls", "reality"] or self.port in TARGET_PORTS
                self.is_cdn = params.get("type", "").lower() in ["ws", "grpc", "httpupgrade", "splithttp"]
                
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
                self.use_tls = tls_val in ["tls", "reality"] or self.port in TARGET_PORTS
                self.is_cdn = str(data.get("net", "")).lower() in ["ws", "grpc", "httpupgrade", "splithttp"]
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

def write_sub_files(configs, plain_path, b64_path):
    # اگر لیست خالی بود، یک کانفیگ نمونه می‌گذاریم تا فایل‌ها خالی نمانند و ساخته شوند
    if not configs:
        configs = ["vless://dummy@1.1.1.1:443?security=tls#No-Configs-Found-Try-Again-Later"]
        
    with open(plain_path, "w", encoding="utf-8") as f:
        for c in configs:
            f.write(c + "\n")
            
    b64_data = base64.b64encode(("\n".join(configs)).encode("utf-8")).decode("utf-8")
    with open(b64_path, "w", encoding="utf-8") as f:
        f.write(b64_data)

def main():
    import requests
    
    os.makedirs("output", exist_ok=True)
    
    # 1. Download
    logger.info("Downloading configs from LalatinaHub...")
    try:
        res = requests.get(SOURCE_URL, timeout=10)
        raw_lines = res.text.splitlines()
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return

    # 2. Parse & Filter SNIs
    configs = []
    blocked_keywords = ["workers.dev", "pages.dev", "github.com", "githubusercontent.com"]
    
    for line in raw_lines:
        c = Config(line)
        if c.protocol in ["vless", "vmess"] and c.address:
            if c.address[0].isdigit():
                continue
            is_blocked = any(keyword in c.sni.lower() for keyword in blocked_keywords)
            if is_blocked:
                continue
            configs.append(c)
            
    logger.info(f"Parsed {len(configs)} clean configs (blocked domains excluded).")

    # 3. High-Speed Test
    logger.info("Testing with 500 workers...")
    tested_configs = []
    with ThreadPoolExecutor(max_workers=500) as executor:
        futures = {executor.submit(test_config, c): c for c in configs}
        for future in as_completed(futures):
            tested_configs.append(future.result())

    alive_configs = [c for c in tested_configs if c.is_alive]
    alive_configs.sort(key=lambda x: x.latency)
    logger.info(f"Total Alive: {len(alive_configs)} / {len(configs)}")

    # ================= SUB 1: DIRECT CONFIGS (NON-CF) =================
    logger.info("Generating Sub 1: Direct (Non-Cloudflare)...")
    direct_candidates = [c for c in alive_configs if not c.is_cdn]
    # اگر زنده نداشتیم از کل لیست استفاده کن
    if not direct_candidates:
        direct_candidates = [c for c in tested_configs if not c.is_cdn]
        
    direct_final = []
    for idx, c in enumerate(direct_candidates[:150]):
        name = f"{PREFIX}Direct-{idx+1}"
        if c.protocol == "vless":
            try:
                parsed = urllib.parse.urlparse(c.raw)
                params = dict(urllib.parse.parse_qsl(parsed.query))
                new_raw = f"vless://{parsed.username}@{parsed.hostname}:{parsed.port}?" + urllib.parse.urlencode(params) + f"#{name}"
                direct_final.append(new_raw)
            except: direct_final.append(c.raw)
        elif c.protocol == "vmess":
            try:
                b64 = c.raw.replace("vmess://", "")
                padding = 4 - len(b64) % 4
                if padding != 4: b64 += "=" * padding
                data = json.loads(base64.b64decode(b64).decode("utf-8", errors="ignore"))
                data["ps"] = name
                new_raw = "vmess://" + base64.b64encode(json.dumps(data, ensure_ascii=False).encode("utf-8")).decode("utf-8")
                direct_final.append(new_raw)
            except: direct_final.append(c.raw)
            
    write_sub_files(direct_final, "output/direct.txt", "output/direct_sub.txt")
    logger.info(f"[+] Saved {len(direct_final)} Direct configs.")

    # ================= SUB 2: CDN CONFIGS (ORIGINAL SNI) =================
    logger.info("Generating Sub 2: Cloudflare CDN (Original Domain)...")
    cdn_candidates = [c for c in alive_configs if c.is_cdn]
    # اگر زنده پیدا نشد، از کل کانفیگ‌های CDN دانلود شده استفاده کن تا سابسکریپشن هرگز خالی نماند
    if not cdn_candidates:
        cdn_candidates = [c for c in tested_configs if c.is_cdn]
    if not cdn_candidates:
        cdn_candidates = [c for c in configs if c.is_cdn]
        
    cdn_final = []
    for idx, c in enumerate(cdn_candidates[:150]):
        name = f"{PREFIX}CDN-{idx+1}"
        if c.protocol == "vless":
            try:
                parsed = urllib.parse.urlparse(c.raw)
                params = dict(urllib.parse.parse_qsl(parsed.query))
                new_raw = f"vless://{parsed.username}@{parsed.hostname}:{parsed.port}?" + urllib.parse.urlencode(params) + f"#{name}"
                cdn_final.append(new_raw)
            except: cdn_final.append(c.raw)
        elif c.protocol == "vmess":
            try:
                b64 = c.raw.replace("vmess://", "")
                padding = 4 - len(b64) % 4
                if padding != 4: b64 += "=" * padding
                data = json.loads(base64.b64decode(b64).decode("utf-8", errors="ignore"))
                data["ps"] = name
                new_raw = "vmess://" + base64.b64encode(json.dumps(data, ensure_ascii=False).encode("utf-8")).decode("utf-8")
                cdn_final.append(new_raw)
            except: cdn_final.append(c.raw)
            
    write_sub_files(cdn_final, "output/cdn.txt", "output/cdn_sub.txt")
    logger.info(f"[+] Saved {len(cdn_final)} CDN configs.")

    # ================= SUB 3: CLEAN IP CONFIGS (3 PORTS) =================
    logger.info("Generating Sub 3: Cloudflare Clean IP (3-Ports)...")
    cdn_templates = [c for c in tested_configs if c.is_cdn]
    if not cdn_templates:
        cdn_templates = [c for c in configs if c.is_cdn]
        
    clean_ips = []
    if os.path.exists("clean_ips.txt"):
        with open("clean_ips.txt", "r") as f:
            clean_ips = [line.strip() for line in f if line.strip()]

    clean_final = []
    if clean_ips and cdn_templates:
        limit = 300
        ip_index = 0
        port_index = 0
        
        while len(clean_final) < limit:
            ip = clean_ips[ip_index % len(clean_ips)]
            port = TARGET_PORTS[port_index % len(TARGET_PORTS)]
            template = cdn_templates[len(clean_final) % len(cdn_templates)]
            name = f"{PREFIX}CF-clean-{len(clean_final)+1}-{port}"
            
            new_raw = None
            if template.protocol == "vless":
                try:
                    parsed = urllib.parse.urlparse(template.raw)
                    params = dict(urllib.parse.parse_qsl(parsed.query))
                    params["host"] = template.sni
                    params["security"] = "tls"
                    params["sni"] = template.sni
                    params["alpn"] = "h2,http/1.1"
                    params["fp"] = "chrome"
                    params["allowInsecure"] = "1"
                    new_raw = f"vless://{parsed.username}@{ip}:{port}?" + urllib.parse.urlencode(params) + f"#{name}"
                except: pass
            elif template.protocol == "vmess":
                try:
                    b64 = template.raw.replace("vmess://", "")
                    padding = 4 - len(b64) % 4
                    if padding != 4: b64 += "=" * padding
                    data = json.loads(base64.b64decode(b64).decode("utf-8", errors="ignore"))
                    data["add"] = ip
                    data["port"] = port
                    data["tls"] = "tls"
                    data["ps"] = name
                    data["alpn"] = "h2,http/1.1"
                    data["fp"] = "chrome"
                    data["allowInsecure"] = True
                    new_raw = "vmess://" + base64.b64encode(json.dumps(data, ensure_ascii=False).encode("utf-8")).decode("utf-8")
                except: pass

            if new_raw:
                clean_final.append(new_raw)
                
            port_index += 1
            if port_index % len(TARGET_PORTS) == 0:
                ip_index += 1

    write_sub_files(clean_final, "output/clean.txt", "output/clean_sub.txt")
    logger.info(f"[+] Saved {len(clean_final)} Clean IP configs across 3 ports.")

    logger.info("=== ALL SUBSCRIPTIONS GENERATED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()