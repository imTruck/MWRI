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
                self.use_tls = params.get("security", "").lower() in ["tls", "reality"] or self.port in TARGET_PORTS
            elif self.raw.startswith("vmess://"):
                self.protocol = "vmess"
                b64 = self.raw.replace("vmess://", "")
                padding = 4 - len(b64) % 4
                if padding != 4: b64 += "=" * padding
                data = json.loads(base64.b64decode(b64).decode("utf-8", errors="ignore"))
                self.address = data.get("add", "")
                self.port = int(data.get("port", 0))
                self.sni = data.get("sni", data.get("host", self.address))
                self.use_tls = str(data.get("tls", "")).lower() in ["tls", "reality"] or self.port in TARGET_PORTS
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

    # 2. Parse & Filter
    configs = []
    for line in raw_lines:
        c = Config(line)
        if c.protocol in ["vless", "vmess"] and c.use_tls and c.address:
            if not c.address[0].isdigit():
                configs.append(c)
            
    logger.info(f"Filtered {len(configs)} high-quality TLS configs.")

    # 3. High-Speed Test (500 Workers)
    logger.info("Testing with 500 workers (TLS Handshake Test)...")
    tested_configs = []
    with ThreadPoolExecutor(max_workers=500) as executor:
        futures = {executor.submit(test_config, c): c for c in configs}
        for future in as_completed(futures):
            tested_configs.append(future.result())

    alive_configs = [c for c in tested_configs if c.is_alive]
    alive_configs.sort(key=lambda x: x.latency)
    logger.info(f"Alive configs: {len(alive_configs)} / {len(configs)}")

    if not alive_configs:
        logger.warning("No alive configs found on your connection! Please check your network/VPN status.")
        return

    # 4. Save Best Original Configs
    best_file = "output/best.txt"
    with open(best_file, "w", encoding="utf-8") as f:
        for c in alive_configs[:100]:
            f.write(c.raw + "\n")
    logger.info(f"Saved top 100 working configs to {best_file}")

    # 5. Apply Clean IPs with 3 Ports (443, 2083, 8443)
    clean_ips = []
    if os.path.exists("clean_ips.txt"):
        with open("clean_ips.txt", "r") as f:
            clean_ips = [line.strip() for line in f if line.strip()]

    if clean_ips and alive_configs:
        logger.info(f"Applying 3 Ports (443, 2083, 8443) to {len(clean_ips)} Clean IPs...")
        clean_configs = []
        for i, ip in enumerate(clean_ips):
            for p_idx, port in enumerate(TARGET_PORTS):
                template = alive_configs[(i * len(TARGET_PORTS) + p_idx) % len(alive_configs)]
                name = f"{PREFIX}clean-{i+1}-{port}"
                
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
                        clean_configs.append(new_raw)
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
                        clean_configs.append(new_raw)
                    except: pass

        clean_file = "output/clean.txt"
        with open(clean_file, "w", encoding="utf-8") as f:
            for c in clean_configs:
                f.write(c + "\n")
        
        # Save Base64 subscription
        b64_clean = base64.b64encode(("\n".join(clean_configs)).encode("utf-8")).decode("utf-8")
        with open("output/clean_sub.txt", "w", encoding="utf-8") as f:
            f.write(b64_clean)
            
        logger.info(f"Generated {len(clean_configs)} clean IP configs with 3 ports in {clean_file}")

if __name__ == "__main__":
    main()