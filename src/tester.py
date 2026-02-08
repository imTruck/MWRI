import logging
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# فقط این پورتا قبوله
ALLOWED_PORTS = [80, 443]


class ConfigTester:
    def __init__(self, timeout=5, max_workers=100):
        self.timeout = timeout
        self.max_workers = max_workers

    def test_single(self, config):
        """یه کانفیگ رو تست میکنه"""

        # فیلتر پورت: فقط 80 و 443
        if config.port not in ALLOWED_PORTS:
            config.is_alive = False
            return config

        # DNS check
        try:
            socket.getaddrinfo(config.address, config.port)
        except Exception:
            config.is_alive = False
            return config

        # TCP connect + latency
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
        """همه کانفیگ‌ها رو تست میکنه"""

        # اول فیلتر پورت بزن
        port_filtered = [c for c in configs if c.port in ALLOWED_PORTS]
        skipped = len(configs) - len(port_filtered)

        logger.info(f"Port filter: {len(configs)} total -> {len(port_filtered)} with port 80/443 ({skipped} skipped)")

        total = len(port_filtered)
        if total == 0:
            logger.warning("No configs with port 80 or 443!")
            return []

        logger.info(f"Testing {total} configs with {self.max_workers} workers...")

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
                        logger.info(f"  [{i}/{total}] Alive: {alive_count} ({alive_count/i*100:.1f}%)")
                except Exception:
                    pass

        logger.info(f"Done: {alive_count}/{total} alive")
        return tested

    @staticmethod
    def get_best(configs, top_n=500, max_latency=3000):
        """بهترین کانفیگ‌ها رو برمیگردونه"""
        alive = [c for c in configs if c.is_alive and 0 < c.latency <= max_latency]
        alive.sort(key=lambda c: c.latency)
        best = alive[:top_n]

        logger.info(f"Selected {len(best)} best configs")
        if best:
            logger.info(f"  Best:  {best[0].latency}ms")
            logger.info(f"  Worst: {best[-1].latency}ms")
            avg = sum(c.latency for c in best) / len(best)
            logger.info(f"  Avg:   {avg:.0f}ms")

        return best
