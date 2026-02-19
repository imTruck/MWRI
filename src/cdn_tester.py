import socket
import ssl
import time
import logging
import base64
import json
import urllib.parse
import copy
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.geoip import get_flag

logger = logging.getLogger(__name__)

PREFIX = "mwri\U0001F9D8\U0001F3FD"
TLS_PORTS = [443, 8443, 2053, 2083, 2087, 2096]
HTTP_PORTS = [80, 8080, 2052, 2082, 2086, 2095]
ALL_PORTS = TLS_PORTS + HTTP_PORTS

# Target per port: ~40 configs
TARGET_PER_PORT = 42


def _resolve(config):
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


def _get_sni(config):
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
        return ""


def _get_host(config):
    try:
        if config.protocol in ["vless", "trojan"]:
            parsed = urllib.parse.urlparse(config.raw)
            params = dict(urllib.parse.parse_qsl(parsed.query))
            return params.get("host", parsed.hostname or "")
        elif config.protocol == "vmess":
            b64 = config.raw.replace("vmess://", "")
            padding = 4 - len(b64) % 4
            if padding != 4:
                b64 += "=" * padding
            decoded = base64.b64decode(b64).decode("utf-8", errors="ignore")
            data = json.loads(decoded)
            return data.get("host", data.get("add", ""))
    except Exception:
        return ""


def download_test(config):
    """Real download test through CDN"""
    host, port = _resolve(config)
    if not host or not port:
        config.latency = -1
        config.is_alive = False
        return config

    sni = _get_sni(config) or _get_host(config) or host
    cdn_host = _get_host(config) or sni

    try:
        # Step 1: TCP connect
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(4)
        start = time.perf_counter()
        sock.connect((host, port))
        tcp_time = (time.perf_counter() - start) * 1000

        # Step 2: TLS if needed
        if port in TLS_PORTS:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            tls_start = time.perf_counter()
            sock = ctx.wrap_socket(sock, server_hostname=sni)
            tls_time = (time.perf_counter() - tls_start) * 1000
        else:
            tls_time = 0

        # Step 3: HTTP request through socket
        scheme = "https" if port in TLS_PORTS else "http"
        http_req = "GET / HTTP/1.1\r\nHost: " + cdn_host + "\r\nUser-Agent: Mozilla/5.0\r\nConnection: close\r\n\r\n"

        dl_start = time.perf_counter()
        sock.sendall(http_req.encode())

        response = b""
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
                if len(response) > 1024:
                    break
            except Exception:
                break

        dl_time = (time.perf_counter() - dl_start) * 1000
        sock.close()

        total = round(tcp_time + tls_time + dl_time, 1)

        # Must get some response
        if len(response) > 0:
            config.latency = total
            config.is_alive = True
        else:
            config.latency = -1
            config.is_alive = False

    except Exception:
        config.latency = -1
        config.is_alive = False

    return config


def test_cdn_batch(configs):
    """Test CDN configs with real download"""
    logger.info("CDN download testing " + str(len(configs)) + " configs...")
    tested = []
    alive = 0

    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(download_test, c): c for c in configs}
        done = 0
        for future in as_completed(futures):
            done += 1
            try:
                result = future.result(timeout=15)
                tested.append(result)
                if result.is_alive:
                    alive += 1
            except Exception:
                c = futures[future]
                c.latency = -1
                c.is_alive = False
                tested.append(c)

            if done % 200 == 0:
                logger.info("  " + str(done) + "/" + str(len(configs)) + " alive:" + str(alive))

    logger.info("CDN alive: " + str(alive) + "/" + str(len(configs)))
    return tested


def clone_vmess(raw, new_port, name):
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

        # TLS→TLS only, HTTP→HTTP only
        if old_port in TLS_PORTS and new_port in HTTP_PORTS:
            return None
        if old_port in HTTP_PORTS and new_port in TLS_PORTS:
            return None

        data["port"] = new_port
        data["ps"] = name
        if new_port in TLS_PORTS:
            data["tls"] = "tls"
        else:
            data["tls"] = ""
        new_json = json.dumps(data, ensure_ascii=False)
        return "vmess://" + base64.b64encode(new_json.encode("utf-8")).decode("utf-8")
    except Exception:
        return None


def clone_vless(raw, new_port, name):
    try:
        parsed = urllib.parse.urlparse(raw)
        old_port = parsed.port or 0
        userinfo = parsed.username or ""
        host = parsed.hostname
        params = dict(urllib.parse.parse_qsl(parsed.query))

        if old_port in TLS_PORTS and new_port in HTTP_PORTS:
            return None
        if old_port in HTTP_PORTS and new_port in TLS_PORTS:
            return None

        if new_port in TLS_PORTS:
            params["security"] = "tls"
            if not params.get("sni"):
                params["sni"] = params.get("host", host)
        else:
            params["security"] = "none"
            params.pop("sni", None)

        query = urllib.parse.urlencode(params)
        encoded_name = urllib.parse.quote(name, safe="")
        return "vless://" + userinfo + "@" + host + ":" + str(new_port) + "?" + query + "#" + encoded_name
    except Exception:
        return None


def generate_all_port_variants(configs):
    """Clone configs with ALL CDN ports"""
    variants = []
    counter = 0
    for c in configs:
        _, old_port = _resolve(c)
        target_ports = TLS_PORTS if old_port in TLS_PORTS else HTTP_PORTS

        for new_port in target_ports:
            if new_port == old_port:
                continue
            counter += 1
            flag = get_flag(c.address)
            name = flag + " " + PREFIX + " p" + str(new_port) + "#" + str(counter)

            if c.protocol == "vmess":
                new_raw = clone_vmess(c.raw, new_port, name)
            elif c.protocol == "vless":
                new_raw = clone_vless(c.raw, new_port, name)
            else:
                continue

            if new_raw:
                new_c = copy.copy(c)
                new_c.raw = new_raw
                new_c.port = new_port
                new_c.name = name
                new_c.latency = -1
                new_c.is_alive = False
                variants.append(new_c)

    logger.info("Generated " + str(len(variants)) + " port variants")
    return variants


def balance_ports(configs, total=500):
    """Balance configs across all ports, ~40 per port"""
    by_port = {}
    for c in configs:
        _, port = _resolve(c)
        if port not in by_port:
            by_port[port] = []
        by_port[port].append(c)

    # Sort each port group by latency
    for port in by_port:
        by_port[port].sort(key=lambda x: x.latency)

    active_ports = len(by_port)
    if active_ports == 0:
        return []

    per_port = max(total // active_ports, 10)
    result = []

    for port in sorted(by_port.keys()):
        group = by_port[port][:per_port]
        result.extend(group)
        logger.info("  Port " + str(port) + ": " + str(len(group)) + " configs")

    # Fill remaining from best overall
    if len(result) < total:
        all_sorted = sorted(configs, key=lambda x: x.latency)
        existing = set(c.raw for c in result)
        for c in all_sorted:
            if c.raw not in existing:
                result.append(c)
                existing.add(c.raw)
            if len(result) >= total:
                break

    result.sort(key=lambda x: x.latency)
    return result[:total]
