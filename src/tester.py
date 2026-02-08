import logging
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALLOWED_PORTS = [
    80, 443,
    8080, 8443,
    2052, 2053,
    2082, 2083,
    2086, 2087,
    2095, 2096
]


class ConfigTester:
    def __init__(self, timeout=5, max_workers=100):
        self.timeout = timeout
        self.max_workers = max_workers

    def test_single(self, config):
        if config.port not in ALLOWED_PORTS:
            config.is_alive = False
            return config

        try:
            socket.getaddrinfo(config.address, config.port)
        except Exception:
            config.is_alive = False
            return config

        try:
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((config.address, config.port))
            latency = (time.time() - start) * 1000
            sock.close()

            if result == 0:
                config.is_alive = True
                config.latency = round(latency, 2)
            else:
                config.is_alive = False
        except Exception:
            config.is_alive = False

        return config

    def test_batch(self, configs):
        port_filtered = [c for c in configs if c.port in ALLOWED_PORTS]
        skipped = len(configs) - len(port_filtered)

        logger.info("Port filter: " + str(len(configs)) + " total -> " + str(len(port_filtered)) + " accepted (" + str(skipped) + " skipped)")

        vmess_count = len([c for c in port_filtered if c.protocol == "vmess"])
        vless_count = len([c for c in port_filtered if c.protocol == "vless"])
        logger.info("  VMess: " + str(vmess_count) + " | VLESS: " + str(vless_count))

        total = len(port_filtered)
        if total == 0:
            logger.warning("No configs to test!")
            return []

        logger.info("Testing " + str(total) + " configs...")

        tested = []
        alive_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.test_single, c): c for c in port_filtered}

            for i, future in enumerate(as_completed(futures), 1):
                try:
                    result = future.result(timeout=self.timeout + 5)
                    tested.append(result)
                    if result.is_alive:
                        alive_count += 1
                    if i % 50 == 0 or i == total:
                        logger.info("  [" + str(i) + "/" + str(total) + "] Alive: " + str(alive_count))
                except Exception:
                    pass

        vmess_alive = len([c for c in tested if c.is_alive and c.protocol == "vmess"])
        vless_alive = len([c for c in tested if c.is_alive and c.protocol == "vless"])
        logger.info("Done! Alive: " + str(alive_count) + " (VMess:" + str(vmess_alive) + " VLESS:" + str(vless_alive) + ")")

        return tested

    @staticmethod
    def get_best(configs, top_n=500, max_latency=3000):
        alive = [c for c in configs if c.is_alive and 0 < c.latency <= max_latency]
        alive.sort(key=lambda c: c.latency)
        best = alive[:top_n]

        if best:
            vmess_count = len([c for c in best if c.protocol == "vmess"])
            vless_count = len([c for c in best if c.protocol == "vless"])
            logger.info("Best " + str(len(best)) + " configs (VMess:" + str(vmess_count) + " VLESS:" + str(vless_count) + ")")

        return best
