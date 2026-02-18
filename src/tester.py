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
    def __init__(self, timeout=4, max_workers=150):
        self.timeout = timeout
        self.max_workers = max_workers

    def _resolve_address(self, config):
        """Extract real connection address and port"""
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

            elif config.protocol == "vless":
                parsed = urllib.parse.urlparse(config.raw)
                return parsed.hostname or "", parsed.port or 0

            elif config.protocol == "trojan":
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

    def _test_tcp(self, host, port):
        """TCP handshake test - measures real latency"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            start = time.perf_counter()
            sock.connect((host, port))
            latency = (time.perf_counter() - start) * 1000
            sock.close()
            return latency
        except Exception:
            return -1

    def _test_tls(self, host, port, sni=None):
        """TLS handshake test - more accurate for TLS configs"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            start = time.perf_counter()
            sock.connect((host, port))

            if port in [443, 8443, 2053, 2083, 2087, 2096]:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                hostname = sni or host
                sock = ctx.wrap_socket(sock, server_hostname=hostname)

            latency = (time.perf_counter() - start) * 1000
            sock.close()
            return latency
        except Exception:
            return -1

    def _get_sni(self, config):
        """Extract SNI from config"""
        try:
            if config.protocol == "vless" or config.protocol == "trojan":
                parsed = urllib.parse.urlparse(config.raw)
                params = dict(urllib.parse.parse_qsl(parsed.query))
                return params.get("sni", "")
            elif config.protocol == "vmess":
                b64 = config.raw.replace("vmess://", "")
                padding = 4 - len(b64) % 4
                if padding != 4:
                    b64 += "=" * padding
                decoded = base64.b64decode(b64).decode("utf-8", errors="ignore")
                data = json.loads(decoded)
                return data.get("sni", data.get("host", ""))
        except Exception:
            pass
        return ""

    def test_single(self, config):
        """Test a single config with multiple methods"""
        host, port = self._resolve_address(config)

        if not host or not port:
            config.latency = -1
            config.is_alive = False
            return config

        # Try DNS resolution first
        try:
            socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        except socket.gaierror:
            config.latency = -1
            config.is_alive = False
            return config

        # Test 3 times, take best
        results = []
        sni = self._get_sni(config)

        for _ in range(3):
            if port in [443, 8443, 2053, 2083, 2087, 2096]:
                lat = self._test_tls(host, port, sni)
            else:
                lat = self._test_tcp(host, port)

            if lat > 0:
                results.append(lat)

        if results:
            config.latency = round(min(results), 1)
            config.is_alive = True
        else:
            config.latency = -1
            config.is_alive = False

        return config

    def test_batch(self, configs):
        """Test all configs concurrently"""
        logger.info("Testing " + str(len(configs)) + " configs with " + str(self.max_workers) + " workers...")
        tested = []
        alive_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for c in configs:
                f = executor.submit(self.test_single, c)
                futures[f] = c

            done = 0
            total = len(futures)
            for future in as_completed(futures):
                done += 1
                try:
                    result = future.result(timeout=self.timeout + 2)
                    tested.append(result)
                    if result.is_alive:
                        alive_count += 1
                except Exception:
                    c = futures[future]
                    c.latency = -1
                    c.is_alive = False
                    tested.append(c)

                if done % 200 == 0:
                    logger.info("  Progress: " + str(done) + "/" + str(total) + " | Alive: " + str(alive_count))

        logger.info("Done! Alive: " + str(alive_count) + "/" + str(len(configs)))
        return tested

    def get_best(self, configs, top_n=200, max_latency=2000):
        """Get best configs sorted by latency"""
        alive = [c for c in configs if c.is_alive and 0 < c.latency <= max_latency]
        alive.sort(key=lambda x: x.latency)

        # Remove duplicates by address
        seen = set()
        unique = []
        for c in alive:
            key = c.address + ":" + str(c.port)
            if key not in seen:
                seen.add(key)
                unique.append(c)

        best = unique[:top_n]
        if best:
            logger.info("Best " + str(len(best)) + " configs: " + str(best[0].latency) + "ms ~ " + str(best[-1].latency) + "ms")
        return best
