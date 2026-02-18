import socket
import ssl
import time
import logging
import urllib.parse
import base64
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class ConfigTester:
    def __init__(self, timeout=3, max_workers=200):
        self.timeout = timeout
        self.max_workers = max_workers

    def _resolve_address(self, config):
        try:
            if config.protocol == "vmess":
                b64 = config.raw.replace("vmess://", "")
                padding = 4 - len(b64) % 4
                if padding != 4:
                    b64 += "=" * padding
                try:
                    decoded = base64.b64decode(b64).decode("utf-8", errors="ignore")
                except Exception:
                    decoded = base64.urlsafe_b64decode(b64).decode("utf-8", errors="ignore")
                data = json.loads(decoded)
                return data.get("add", ""), int(data.get("port", 0))
            elif config.protocol in ["vless", "trojan"]:
                parsed = urllib.parse.urlparse(config.raw)
                return parsed.hostname or "", parsed.port or 0
            elif config.protocol == "ss":
                raw = config.raw.replace("ss://", "")
                if "#" in raw:
                    raw = raw.split("#")[0]
                if "@" in raw:
                    server_part = raw.split("@")[1]
                    host, port = server_part.rsplit(":", 1)
                    return host, int(port)
        except Exception:
            pass
        return config.address, config.port

    def test_single(self, config):
        host, port = self._resolve_address(config)

        if not host or not port:
            config.latency = -1
            config.is_alive = False
            return config

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            start = time.perf_counter()
            sock.connect((host, port))
            latency = (time.perf_counter() - start) * 1000
            sock.close()

            config.latency = round(latency, 1)
            config.is_alive = True
        except Exception:
            config.latency = -1
            config.is_alive = False

        return config

    def test_batch(self, configs):
        logger.info("Testing " + str(len(configs)) + " configs...")
        tested = []
        alive = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.test_single, c): c for c in configs}

            for future in as_completed(futures):
                try:
                    result = future.result(timeout=self.timeout + 1)
                    tested.append(result)
                    if result.is_alive:
                        alive += 1
                except Exception:
                    c = futures[future]
                    c.latency = -1
                    c.is_alive = False
                    tested.append(c)

        logger.info("Alive: " + str(alive) + "/" + str(len(configs)))
        return tested

    def get_best(self, configs, top_n=300, max_latency=2000):
        alive = [c for c in configs if c.is_alive and 0 < c.latency <= max_latency]
        alive.sort(key=lambda x: x.latency)

        seen = set()
        unique = []
        for c in alive:
            key = c.address + ":" + str(c.port)
            if key not in seen:
                seen.add(key)
                unique.append(c)

        best = unique[:top_n]
        if best:
            logger.info("Best " + str(len(best)) + ": " + str(best[0].latency) + "ms ~ " + str(best[-1].latency) + "ms")
        return best
