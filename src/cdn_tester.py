import socket
import ssl
import time
import logging
import base64
import json
import urllib.parse
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.geoip import get_flag

logger = logging.getLogger(__name__)

PREFIX = "mwri\U0001F9D8\U0001F3FD"

# All CDN ports
TLS_PORTS = [443, 8443, 2053, 2083, 2087, 2096]
HTTP_PORTS = [80, 8080, 2052, 2082, 2086, 2095]
ALL_CDN_PORTS = TLS_PORTS + HTTP_PORTS


class CDNTester:
    def __init__(self):
        self.timeout = 5

    def _resolve(self, config):
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
        except Exception:
            pass
        return config.address, config.port

    def _get_sni(self, config):
        try:
            if config.protocol in ["vless", "trojan"]:
                parsed = urllib.parse.urlparse(config.raw)
                params = dict(urllib.parse.parse_qsl(parsed.query))
                return params.get("sni", params.get("host", ""))
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

    def _tcp_test(self, host, port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            start = time.perf_counter()
            sock.connect((host, port))
            lat = (time.perf_counter() - start) * 1000
            sock.close()
            return lat
        except Exception:
            return -1

    def _tls_test(self, host, port, sni=""):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            start = time.perf_counter()
            sock.connect((host, port))
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            sock = ctx.wrap_socket(sock, server_hostname=sni or host)
            lat = (time.perf_counter() - start) * 1000
            sock.close()
            return lat
        except Exception:
            return -1

    def hardcore_test(self, config):
        """5 round test, all must pass"""
        host, port = self._resolve(config)
        if not host or not port:
            config.latency = -1
            config.is_alive = False
            return config

        # DNS check
        try:
            socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        except Exception:
            config.latency = -1
            config.is_alive = False
            return config

        sni = self._get_sni(config)
        is_tls = port in TLS_PORTS
        results = []

        # 5 rounds with delay
        for r in range(5):
            if is_tls:
                lat = self._tls_test(host, port, sni)
            else:
                lat = self._tcp_test(host, port)

            if lat <= 0:
                # Even 1 fail = reject
                config.latency = -1
                config.is_alive = False
                return config

            results.append(lat)
            if r < 4:
                time.sleep(0.3)

        # All 5 passed
        # Check consistency: max should not be 3x of min
        mn = min(results)
        mx = max(results)
        if mx > mn * 3:
            config.latency = -1
            config.is_alive = False
            return config

        # Average of middle 3 (remove best and worst)
        results.sort()
        middle = results[1:4]
        config.latency = round(sum(middle) / len(middle), 1)
        config.is_alive = True
        return config

    def test_batch(self, configs):
        logger.info("CDN Hardcore testing " + str(len(configs)) + " configs (5 rounds each)...")
        tested = []
        alive = 0

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = {executor.submit(self.hardcore_test, c): c for c in configs}
            done = 0
            total = len(futures)

            for future in as_completed(futures):
                done += 1
                try:
                    result = future.result(timeout=30)
                    tested.append(result)
                    if result.is_alive:
                        alive += 1
                except Exception:
                    c = futures[future]
                    c.latency = -1
                    c.is_alive = False
                    tested.append(c)

                if done % 100 == 0:
                    logger.info("  CDN Progress: " + str(done) + "/" + str(total) + " | Alive: " + str(alive))

        logger.info("CDN Done! Alive: " + str(alive) + "/" + str(len(configs)))
        return tested

    def get_best(self, configs, top_n=200):
        alive = [c for c in configs if c.is_alive and c.latency > 0]
        alive.sort(key=lambda x: x.latency)

        # Dedup
        seen = set()
        unique = []
        for c in alive:
            key = c.address + ":" + str(c.port)
            if key not in seen:
                seen.add(key)
                unique.append(c)

        best = unique[:top_n]
        if best:
            logger.info("CDN Best " + str(len(best)) + ": " + str(best[0].latency) + "ms ~ " + str(best[-1].latency) + "ms")
        return best


def diversify_ports(configs, max_common_ratio=0.4):
    """Make sure 443/80 is max 40%, rest from other ports"""
    common_ports = [443, 80]
    common = []
    rare = []

    for c in configs:
        _, port = CDNTester()._resolve(c)
        if port in common_ports:
            common.append(c)
        else:
            rare.append(c)

    total = len(configs)
    max_common = int(total * max_common_ratio)

    if len(common) > max_common:
        common = common[:max_common]

    remaining = total - len(common)
    if len(rare) < remaining:
        extra_needed = remaining - len(rare)
        common = common[:len(common) + extra_needed]
    else:
        rare = rare[:remaining]

    result = common + rare
    result.sort(key=lambda x: x.latency)

    # Log port distribution
    port_stats = {}
    tester = CDNTester()
    for c in result:
        _, port = tester._resolve(c)
        port_stats[port] = port_stats.get(port, 0) + 1

    logger.info("Port distribution:")
    for port, count in sorted(port_stats.items(), key=lambda x: x[1], reverse=True):
        pct = round(count / len(result) * 100, 1)
        logger.info("  Port " + str(port) + ": " + str(count) + " (" + str(pct) + "%)")

    return result


def change_port_vmess(raw, new_port, name):
    try:
        b64 = raw.replace("vmess://", "")
        padding = 4 - len(b64) % 4
        if padding != 4:
            b64 += "=" * padding
        try:
            decoded = base64.b64decode(b64).decode("utf-8", errors="ignore")
        except Exception:
            decoded = base64.urlsafe_b64decode(b64).decode("utf-8", errors="ignore")
        data = json.loads(decoded)
        old_port = int(data.get("port", 0))

        data["port"] = new_port
        data["ps"] = name

        # TLS settings
        if new_port in TLS_PORTS:
            data["tls"] = "tls"
        else:
            data["tls"] = ""

        new_json = json.dumps(data, ensure_ascii=False)
        return "vmess://" + base64.b64encode(new_json.encode("utf-8")).decode("utf-8")
    except Exception:
        return None


def change_port_vless(raw, new_port, name):
    try:
        parsed = urllib.parse.urlparse(raw)
        userinfo = parsed.username or ""
        host = parsed.hostname
        params = dict(urllib.parse.parse_qsl(parsed.query))

        # TLS settings
        if new_port in TLS_PORTS:
            params["security"] = "tls"
        else:
            params["security"] = "none"
            params.pop("sni", None)

        query = urllib.parse.urlencode(params)
        encoded_name = urllib.parse.quote(name, safe="")
        return "vless://" + userinfo + "@" + host + ":" + str(new_port) + "?" + query + "#" + encoded_name
    except Exception:
        return None


def generate_port_variants(configs):
    """Generate configs with different ports from working configs"""
    variants = []
    alt_ports = [8080, 8443, 2052, 2053, 2082, 2083, 2086, 2087, 2095, 2096]

    for c in configs[:30]:
        for port in alt_ports:
            flag = get_flag(c.address)
            name = flag + " " + PREFIX + " p" + str(port)

            if c.protocol == "vmess":
                new_raw = change_port_vmess(c.raw, port, name)
            elif c.protocol == "vless":
                new_raw = change_port_vless(c.raw, port, name)
            else:
                continue

            if new_raw:
                new_c = copy.copy(c)
                new_c.raw = new_raw
                new_c.port = port
                new_c.name = name
                new_c.latency = -1
                new_c.is_alive = False
                variants.append(new_c)

    logger.info("Generated " + str(len(variants)) + " port variants")
    return variants
