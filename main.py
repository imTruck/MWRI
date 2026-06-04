#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import concurrent.futures as futures
import io
import json
import math
import os
import platform
import queue
import random
import shutil
import socket
import statistics
import subprocess
import sys
import time
import urllib.parse
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests

try:
    import urllib3.contrib.socks  # noqa: F401
    SOCKS_SUPPORT = True
except ImportError:
    SOCKS_SUPPORT = False


DEFAULT_SOURCES = [
    "https://raw.githubusercontent.com/masir-sefid/Sub/main/@Masir_Sefid.txt",
    "https://raw.githubusercontent.com/fitexgit/v2raysub/refs/heads/main/sub.txt",
    "https://gorgi.nimadarkorg.workers.dev/",
    "https://raw.githubusercontent.com/Mahdi0024/ProxyCollector/master/sub/proxies.txt",
    "https://raw.githubusercontent.com/iampedii/whitedns-sub/refs/heads/main/base64.txt",
]

DEFAULT_TEST_URLS = [
    "http://www.google.com/generate_204",
]

USER_AGENT = "Mozilla/5.0 (MWRI-Xray-Tester)"
SUCCESS_STATUS_CODES = {200, 204}
WINDOWS = platform.system() == "Windows"
PORT_QUEUE: queue.Queue[int] | None = None


@dataclass(slots=True)
class ConfigItem:
    link: str
    source: str
    source_index: int


@dataclass(slots=True)
class ProbeResult:
    item: ConfigItem
    ok: bool
    ping_ms: int | None
    samples: list[int]
    error: str | None = None


def log(message: str) -> None:
    print(message, flush=True)


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
    value = "".join(value.split())
    if not value:
        return None
    padding = (-len(value)) % 4
    try:
        decoded = base64.b64decode(value + ("=" * padding), validate=False)
    except Exception:
        return None
    if not decoded:
        return None
    try:
        return decoded.decode("utf-8", errors="ignore")
    except Exception:
        return None


def maybe_decode_subscription_blob(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    if any(proto in text for proto in ("vmess://", "vless://", "trojan://")):
        return text
    decoded = decode_base64_loose(text)
    if decoded and any(proto in decoded for proto in ("vmess://", "vless://", "trojan://")):
        return decoded
    return text


def extract_links(text: str) -> list[str]:
    text = maybe_decode_subscription_blob(text)
    links: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip().replace("\ufeff", "")
        if not line:
            continue
        if line.startswith(("vmess://", "vless://", "trojan://")):
            links.append(line)
            continue
        decoded = decode_base64_loose(line)
        if decoded and decoded.startswith(("vmess://", "vless://", "trojan://")):
            links.append(decoded.strip())
    return links


def fetch_text(session: requests.Session, url: str, timeout: float, retries: int) -> str:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, timeout=(timeout, timeout), headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            response.encoding = response.encoding or "utf-8"
            return response.text
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.4 * attempt)
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def build_sources(session: requests.Session, sources: list[str], timeout: float, retries: int) -> list[ConfigItem]:
    items: list[ConfigItem] = []
    seen: set[str] = set()

    for source_index, source in enumerate(sources, start=1):
        clean_url = unwrap_markdown_url(source)
        try:
            text = fetch_text(session, clean_url, timeout=timeout, retries=retries)
            extracted = extract_links(text)
            added = 0
            for link in extracted:
                normalized = link.strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    items.append(ConfigItem(link=normalized, source=clean_url, source_index=source_index))
                    added += 1
            log(f"[+] Source {source_index}: {added} unique configs from {clean_url}")
        except Exception as exc:
            log(f"[!] Source {source_index} failed: {clean_url} -> {exc}")
    return items


def rename_config(raw_config: str, new_name: str) -> str | None:
    raw_config = raw_config.strip()
    if not raw_config:
        return None

    if raw_config.startswith("vmess://"):
        try:
            encoded = raw_config[len("vmess://") :]
            decoded = decode_base64_loose(encoded)
            if not decoded:
                return None
            data = json.loads(decoded)
            data["ps"] = new_name
            payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            return "vmess://" + base64.b64encode(payload).decode("utf-8")
        except Exception:
            return raw_config

    base = raw_config.split("#", 1)[0]
    return f"{base}#{urllib.parse.quote(new_name)}"


def parse_vmess(link: str) -> dict:
    encoded = link[len("vmess://") :]
    decoded = decode_base64_loose(encoded)
    if not decoded:
        raise ValueError("vmess payload decode failed")
    data = json.loads(decoded)

    address = data.get("add")
    port = int(data.get("port"))
    user = {
        "id": data.get("id"),
        "alterId": int(data.get("aid", 0) or 0),
        "security": data.get("scy", "auto"),
        "level": 0,
    }

    stream: dict = {"network": data.get("net", "tcp") or "tcp"}
    network = stream["network"]
    host = data.get("host", "")
    path = data.get("path", "/") or "/"

    if network == "ws":
        headers = {"Host": host} if host else {}
        stream["wsSettings"] = {"path": path, "headers": headers}
    elif network == "grpc":
        stream["grpcSettings"] = {
            "serviceName": data.get("path", "") or "",
            "multiMode": False,
        }
    elif network in {"h2", "http"}:
        stream["network"] = "h2"
        stream["httpSettings"] = {
            "path": path,
            "host": [h.strip() for h in host.split(",") if h.strip()] or [],
        }

    tls_mode = (data.get("tls") or "").lower().strip()
    if tls_mode == "tls":
        stream["security"] = "tls"
        stream["tlsSettings"] = {
            "serverName": data.get("sni") or host or address,
            "allowInsecure": True,
            "alpn": [a.strip() for a in str(data.get("alpn", "")).split(",") if a.strip()] or None,
            "fingerprint": data.get("fp") or None,
        }
        stream["tlsSettings"] = {k: v for k, v in stream["tlsSettings"].items() if v not in (None, [], "")}

    return {
        "tag": "proxy",
        "protocol": "vmess",
        "settings": {
            "vnext": [
                {
                    "address": address,
                    "port": port,
                    "users": [user],
                }
            ]
        },
        "streamSettings": stream,
    }


def _qs_first(query: dict[str, list[str]], key: str, default: str = "") -> str:
    values = query.get(key)
    if not values:
        return default
    return values[0]


def build_common_stream(query: dict[str, list[str]], host_hint: str) -> dict:
    network = _qs_first(query, "type", "tcp") or "tcp"
    security = _qs_first(query, "security", "")

    stream: dict = {"network": network}
    host = _qs_first(query, "host", host_hint)
    path = _qs_first(query, "path", "/") or "/"

    if network == "ws":
        headers = {"Host": host} if host else {}
        stream["wsSettings"] = {"path": path, "headers": headers}
    elif network == "grpc":
        stream["grpcSettings"] = {
            "serviceName": _qs_first(query, "serviceName", ""),
            "multiMode": _qs_first(query, "mode", "gun") == "multi",
        }
    elif network in {"h2", "http"}:
        stream["network"] = "h2"
        hosts = [h.strip() for h in host.split(",") if h.strip()] if host else []
        stream["httpSettings"] = {"path": path, "host": hosts}

    if security == "tls":
        stream["security"] = "tls"
        tls_settings = {
            "serverName": _qs_first(query, "sni", host or host_hint),
            "allowInsecure": True,
            "alpn": [a.strip() for a in _qs_first(query, "alpn", "").split(",") if a.strip()] or None,
            "fingerprint": _qs_first(query, "fp", "") or None,
        }
        stream["tlsSettings"] = {k: v for k, v in tls_settings.items() if v not in (None, [], "")}
    elif security == "reality":
        stream["security"] = "reality"
        reality_settings = {
            "serverName": _qs_first(query, "sni", host or host_hint),
            "fingerprint": _qs_first(query, "fp", "chrome"),
            "publicKey": _qs_first(query, "pbk", ""),
            "shortId": _qs_first(query, "sid", ""),
            "spiderX": urllib.parse.unquote(_qs_first(query, "spx", "")),
        }
        stream["realitySettings"] = {k: v for k, v in reality_settings.items() if v != ""}

    return stream


def parse_vless(link: str) -> dict:
    parsed = urllib.parse.urlsplit(link)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    if not parsed.hostname or not parsed.port or not parsed.username:
        raise ValueError("invalid vless link")

    user: dict = {"id": parsed.username, "encryption": "none", "level": 0}
    flow = _qs_first(query, "flow", "")
    if flow:
        user["flow"] = flow

    return {
        "tag": "proxy",
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": parsed.hostname,
                    "port": parsed.port,
                    "users": [user],
                }
            ]
        },
        "streamSettings": build_common_stream(query, parsed.hostname),
    }


def parse_trojan(link: str) -> dict:
    parsed = urllib.parse.urlsplit(link)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    if not parsed.hostname or not parsed.port or not parsed.username:
        raise ValueError("invalid trojan link")

    if not _qs_first(query, "security", ""):
        query["security"] = ["tls"]

    return {
        "tag": "proxy",
        "protocol": "trojan",
        "settings": {
            "servers": [
                {
                    "address": parsed.hostname,
                    "port": parsed.port,
                    "password": parsed.username,
                    "level": 0,
                }
            ]
        },
        "streamSettings": build_common_stream(query, parsed.hostname),
    }


def parse_link_to_outbound(link: str) -> dict | None:
    try:
        if link.startswith("vmess://"):
            return parse_vmess(link)
        if link.startswith("vless://"):
            return parse_vless(link)
        if link.startswith("trojan://"):
            return parse_trojan(link)
    except Exception:
        return None
    return None


def wait_for_port(host: str, port: int, timeout: float, process: subprocess.Popen[bytes]) -> bool:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if process.poll() is not None:
            return False
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.25)
        try:
            if sock.connect_ex((host, port)) == 0:
                return True
        finally:
            sock.close()
        time.sleep(0.05)
    return False


def kill_process(process: subprocess.Popen[bytes] | None) -> None:
    if process is None:
        return
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1.0)
    except Exception:
        pass


def median_int(values: list[int]) -> int | None:
    if not values:
        return None
    return int(statistics.median(values))


def build_xray_config(outbound: dict, local_port: int) -> dict:
    return {
        "log": {"loglevel": "none"},
        "inbounds": [
            {
                "tag": "socks-in",
                "listen": "127.0.0.1",
                "port": local_port,
                "protocol": "socks",
                "settings": {"udp": False},
                "sniffing": {"enabled": False},
            }
        ],
        "outbounds": [
            outbound,
            {"tag": "direct", "protocol": "freedom"},
            {"tag": "block", "protocol": "blackhole"},
        ],
    }


def probe_once(
    session: requests.Session,
    proxies: dict[str, str],
    test_urls: list[str],
    timeout: float,
) -> int | None:
    for url in test_urls:
        start = time.perf_counter()
        try:
            response = session.get(
                url,
                proxies=proxies,
                timeout=(timeout, timeout),
                allow_redirects=False,
                headers={"User-Agent": USER_AGENT, "Connection": "close"},
            )
            status = response.status_code
            response.close()
            if status in SUCCESS_STATUS_CODES:
                return int((time.perf_counter() - start) * 1000)
        except Exception:
            continue
    return None


def test_config(
    item: ConfigItem,
    xray_path: str,
    temp_dir: Path,
    test_urls: list[str],
    timeout: float,
    startup_timeout: float,
    samples: int,
    min_success_samples: int,
) -> ProbeResult:
    global PORT_QUEUE
    if PORT_QUEUE is None:
        return ProbeResult(item=item, ok=False, ping_ms=None, samples=[], error="port queue not initialized")

    local_port = PORT_QUEUE.get()
    temp_path = temp_dir / f"xray_{local_port}_{time.time_ns()}.json"
    process: subprocess.Popen[bytes] | None = None
    session = requests.Session()
    session.trust_env = False

    try:
        outbound = parse_link_to_outbound(item.link)
        if not outbound:
            return ProbeResult(item=item, ok=False, ping_ms=None, samples=[], error="unsupported or invalid config")

        config = build_xray_config(outbound, local_port)
        temp_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if WINDOWS else {}
        process = subprocess.Popen(
            [xray_path, "run", "-c", str(temp_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **kwargs,
        )

        if not wait_for_port("127.0.0.1", local_port, startup_timeout, process):
            return ProbeResult(item=item, ok=False, ping_ms=None, samples=[], error="xray socks inbound did not start")

        proxies = {
            "http": f"socks5h://127.0.0.1:{local_port}",
            "https": f"socks5h://127.0.0.1:{local_port}",
        }

        sample_values: list[int] = []
        for _ in range(samples):
            ping = probe_once(session, proxies, test_urls, timeout)
            if ping is not None:
                sample_values.append(ping)

        if len(sample_values) >= min_success_samples:
            return ProbeResult(item=item, ok=True, ping_ms=median_int(sample_values), samples=sample_values)
        return ProbeResult(item=item, ok=False, ping_ms=None, samples=sample_values, error="probe failed")
    except Exception as exc:
        return ProbeResult(item=item, ok=False, ping_ms=None, samples=[], error=str(exc))
    finally:
        session.close()
        kill_process(process)
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass
        PORT_QUEUE.put(local_port)


def ensure_xray(xray_arg: str | None, allow_download: bool) -> str:
    candidates: list[str] = []
    if xray_arg:
        candidates.append(xray_arg)
    candidates.extend([
        "./xray.exe" if WINDOWS else "./xray",
        "xray.exe" if WINDOWS else "xray",
    ])

    for candidate in candidates:
        if not candidate:
            continue
        resolved = shutil.which(candidate) if candidate in {"xray", "xray.exe"} else None
        path = resolved or candidate
        if path and Path(path).exists():
            return str(Path(path).resolve())

    if not allow_download:
        raise SystemExit(
            "Xray پیدا نشد. یا مسیر را با --xray بده، یا فایل xray/xray.exe را کنار اسکریپت بگذار، یا --download-xray را فعال کن."
        )

    return download_xray_binary()


def download_xray_binary() -> str:
    if WINDOWS:
        zip_name = "Xray-windows-64.zip"
        binary_name = "xray.exe"
    else:
        zip_name = "Xray-linux-64.zip"
        binary_name = "xray"

    url = f"https://github.com/XTLS/Xray-core/releases/latest/download/{zip_name}"
    log(f"[*] Downloading Xray from {url}")
    response = requests.get(url, timeout=(20, 40), headers={"User-Agent": USER_AGENT})
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        data = archive.read(binary_name)

    output_path = Path(binary_name)
    output_path.write_bytes(data)
    if not WINDOWS:
        output_path.chmod(0o755)
    return str(output_path.resolve())


def write_subscription_files(
    output_dir: Path,
    items: list[ConfigItem],
    chunk_size: int,
    prefix: str,
    emoji: str,
) -> None:
    renamed_links: list[str] = []
    for index, item in enumerate(items, start=1):
        renamed = rename_config(item.link, f"{prefix}{emoji} {index}")
        if renamed:
            renamed_links.append(renamed)

    if not renamed_links:
        return

    total_parts = math.ceil(len(renamed_links) / chunk_size)
    for part in range(total_parts):
        start = part * chunk_size
        chunk = renamed_links[start : start + chunk_size]
        plain_path = output_dir / f"sub{part + 1}.txt"
        b64_path = output_dir / f"sub{part + 1}_sub.txt"
        plain_text = "\n".join(chunk)
        plain_path.write_text(plain_text, encoding="utf-8")
        b64_path.write_text(base64.b64encode(plain_text.encode("utf-8")).decode("utf-8"), encoding="utf-8")


def write_vip_files(output_dir: Path, results: list[ProbeResult], vip_prefix: str) -> None:
    vip_links: list[str] = []
    for index, result in enumerate(results, start=1):
        ping_label = result.ping_ms if result.ping_ms is not None else -1
        renamed = rename_config(result.item.link, f"{vip_prefix} [{ping_label}ms] {index}")
        if renamed:
            vip_links.append(renamed)

    plain_text = "\n".join(vip_links)
    (output_dir / "VIP_REAL.txt").write_text(plain_text, encoding="utf-8")
    (output_dir / "VIP_REAL_sub.txt").write_text(
        base64.b64encode(plain_text.encode("utf-8")).decode("utf-8"),
        encoding="utf-8",
    )


def write_results_json(
    output_dir: Path,
    sources: list[str],
    all_items: list[ConfigItem],
    phase1_results: list[ProbeResult],
    final_results: list[ProbeResult],
) -> None:
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sources": sources,
        "stats": {
            "total_unique": len(all_items),
            "phase1_ok": sum(1 for r in phase1_results if r.ok),
            "final_ok": sum(1 for r in final_results if r.ok),
        },
        "vip": [
            {
                "rank": rank,
                "ping_ms": result.ping_ms,
                "samples": result.samples,
                "source": result.item.source,
                "source_index": result.item.source_index,
                "link": result.item.link,
            }
            for rank, result in enumerate(final_results, start=1)
        ],
    }
    (output_dir / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_probe_stage(
    items: list[ConfigItem],
    xray_path: str,
    temp_dir: Path,
    test_urls: list[str],
    timeout: float,
    startup_timeout: float,
    samples: int,
    min_success_samples: int,
    workers: int,
    stage_name: str,
) -> list[ProbeResult]:
    results: list[ProbeResult] = []
    if not items:
        return results

    log(f"[*] {stage_name}: testing {len(items)} configs with {workers} workers...")
    tested = 0
    start_time = time.perf_counter()

    with futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(
                test_config,
                item,
                xray_path,
                temp_dir,
                test_urls,
                timeout,
                startup_timeout,
                samples,
                min_success_samples,
            ): item
            for item in items
        }

        for future in futures.as_completed(future_map):
            tested += 1
            result = future.result()
            results.append(result)
            if tested % 25 == 0 or tested == len(items):
                ok_count = sum(1 for r in results if r.ok)
                elapsed = time.perf_counter() - start_time
                rate = tested / elapsed if elapsed > 0 else 0.0
                log(f"    - {stage_name}: {tested}/{len(items)} tested | ok={ok_count} | {rate:.2f} cfg/s")

    results.sort(key=lambda r: (not r.ok, r.ping_ms if r.ping_ms is not None else 10**9))
    return results


def parse_args() -> argparse.Namespace:
    cpu = os.cpu_count() or 4
    default_workers = max(8, min(24, cpu * 2))

    parser = argparse.ArgumentParser(description="Fast Xray real-delay subscription tester")
    parser.add_argument("--xray", default="", help="path to xray binary")
    parser.add_argument("--download-xray", action="store_true", help="download xray automatically if not found")
    parser.add_argument("--limit", type=int, default=900, help="max unique configs to test")
    parser.add_argument("--top", type=int, default=100, help="how many VIP configs to export")
    parser.add_argument("--workers", type=int, default=default_workers, help="concurrent workers")
    parser.add_argument("--fetch-timeout", type=float, default=10.0, help="source download timeout")
    parser.add_argument("--fetch-retries", type=int, default=3, help="source download retries")
    parser.add_argument("--phase1-timeout", type=float, default=2.0, help="timeout for fast pre-check")
    parser.add_argument("--phase2-timeout", type=float, default=3.0, help="timeout for final real-delay check")
    parser.add_argument("--startup-timeout", type=float, default=1.5, help="wait time for xray socks inbound")
    parser.add_argument("--phase2-samples", type=int, default=2, help="how many real-delay samples for final stage")
    parser.add_argument("--retest-factor", type=int, default=2, help="phase2 candidates = top * factor")
    parser.add_argument("--chunk-size", type=int, default=300, help="standard sub chunk size")
    parser.add_argument("--prefix", default="mwri", help="standard name prefix")
    parser.add_argument("--emoji", default=" 🧘🏽", help="standard name suffix/prefix emoji part")
    parser.add_argument("--vip-prefix", default="🚀 VIP", help="VIP name prefix")
    parser.add_argument("--output", default="output", help="output directory")
    parser.add_argument("--port-start", type=int, default=20000, help="local port range start")
    parser.add_argument("--source", action="append", dest="sources", help="extra source URL (can be repeated)")
    parser.add_argument("--test-url", action="append", dest="test_urls", help="override/add probe url (can be repeated)")
    return parser.parse_args()


def main() -> None:
    global PORT_QUEUE
    args = parse_args()

    if not SOCKS_SUPPORT:
        raise SystemExit(
            "SOCKS support برای requests نصب نیست. این دستور را بزن:\n"
            "pip install -r requirements.txt\n"
            "یا:\n"
            "pip install 'requests[socks]'"
        )

    output_dir = Path(args.output)
    temp_dir = Path("temp_configs")
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    xray_path = ensure_xray(args.xray, args.download_xray)
    log(f"[+] Xray binary: {xray_path}")

    PORT_QUEUE = queue.Queue()
    for port in range(args.port_start, args.port_start + args.workers):
        PORT_QUEUE.put(port)

    sources = list(DEFAULT_SOURCES)
    if args.sources:
        sources.extend(args.sources)

    test_urls = list(DEFAULT_TEST_URLS)
    if args.test_urls:
        test_urls = args.test_urls

    log("========== MWRI FAST XRAY TESTER ==========")
    with requests.Session() as session:
        session.trust_env = False
        items = build_sources(session, sources, timeout=args.fetch_timeout, retries=args.fetch_retries)

    if not items:
        raise SystemExit("هیچ کانفیگ معتبری از سورس‌ها پیدا نشد.")

    random.shuffle(items)

    if args.limit > 0:
        items = items[: args.limit]

    log(f"[+] Total unique configs selected for test: {len(items)}")
    write_subscription_files(output_dir, items, args.chunk_size, args.prefix, args.emoji)
    log(f"[+] Standard subscription files written to: {output_dir}")

    phase1_results = run_probe_stage(
        items=items,
        xray_path=xray_path,
        temp_dir=temp_dir,
        test_urls=test_urls,
        timeout=args.phase1_timeout,
        startup_timeout=args.startup_timeout,
        samples=1,
        min_success_samples=1,
        workers=args.workers,
        stage_name="Phase 1",
    )

    phase1_ok = [result for result in phase1_results if result.ok and result.ping_ms is not None]
    if not phase1_ok:
        write_results_json(output_dir, sources, items, phase1_results, [])
        raise SystemExit("هیچ کانفیگی در مرحله اول جواب نداد.")

    phase1_ok.sort(key=lambda r: r.ping_ms or 10**9)
    retest_count = min(len(phase1_ok), max(args.top, args.top * args.retest_factor))
    phase2_items = [result.item for result in phase1_ok[:retest_count]]

    log(f"[+] Phase 1 ok: {len(phase1_ok)} | sending top {retest_count} to Phase 2")
    phase2_results = run_probe_stage(
        items=phase2_items,
        xray_path=xray_path,
        temp_dir=temp_dir,
        test_urls=test_urls,
        timeout=args.phase2_timeout,
        startup_timeout=args.startup_timeout,
        samples=args.phase2_samples,
        min_success_samples=1,
        workers=args.workers,
        stage_name="Phase 2",
    )

    final_ok = [result for result in phase2_results if result.ok and result.ping_ms is not None]
    final_ok.sort(key=lambda r: r.ping_ms or 10**9)
    best = final_ok[: args.top]

    write_vip_files(output_dir, best, args.vip_prefix)
    write_results_json(output_dir, sources, items, phase1_results, best)

    log(f"[SUCCESS] VIP configs exported: {len(best)}")
    if best:
        log(f"[SUCCESS] Best ping: {best[0].ping_ms} ms")
    log(f"[SUCCESS] Output directory: {output_dir.resolve()}")
    log("==========================================")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("\nStopped by user.")
