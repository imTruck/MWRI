import json
import logging
import time
import requests
from src.parser import extract_configs_from_text, parse_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConfigCollector:
    def __init__(self, sources_file="sources.json"):
        self.raw_configs = []
        self.parsed_configs = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        with open(sources_file, 'r') as f:
            self.sources = json.load(f)

    def fetch_url(self, url):
        try:
            resp = self.session.get(url, timeout=20)
            resp.raise_for_status()
            return resp.text
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 404:
                pass  # فایل وجود نداره، عادیه
            else:
                logger.warning(f"  HTTP Error: {resp.status_code} - {url[:60]}")
            return ""
        except Exception as e:
            logger.warning(f"  Failed: {url[:60]}...")
            return ""

    def collect_from_subscriptions(self):
        urls = self.sources.get("subscription_urls", [])
        logger.info(f"Collecting from {len(urls)} sources...")

        success = 0
        failed = 0

        for i, url in enumerate(urls, 1):
            logger.info(f"  [{i}/{len(urls)}] {url[:70]}...")
            content = self.fetch_url(url)

            if content and len(content) > 10:
                configs = extract_configs_from_text(content)
                if configs:
                    logger.info(f"    +{len(configs)} configs")
                    self.raw_configs.extend(configs)
                    success += 1
                else:
                    logger.info(f"    No configs found in response")
                    failed += 1
            else:
                failed += 1

            time.sleep(0.3)

        logger.info(f"Sources: {success} OK, {failed} failed")

    def remove_duplicates(self):
        before = len(self.raw_configs)
        self.raw_configs = list(dict.fromkeys(self.raw_configs))
        after = len(self.raw_configs)
        logger.info(f"Deduplicated: {before} -> {after} (-{before - after})")

    def parse_all(self):
        logger.info("Parsing...")
        for raw in self.raw_configs:
            parsed = parse_config(raw)
            if parsed and parsed.address and parsed.port > 0:
                self.parsed_configs.append(parsed)
        logger.info(f"Valid configs: {len(self.parsed_configs)}")

    def collect_all(self):
        logger.info("=" * 50)
        logger.info("Starting collection...")
        logger.info("=" * 50)

        self.collect_from_subscriptions()
        self.remove_duplicates()
        self.parse_all()

        # آمار پروتکل‌ها
        protocols = {}
        for c in self.parsed_configs:
            protocols[c.protocol] = protocols.get(c.protocol, 0) + 1

        # آمار پورت‌ها
        port_80 = len([c for c in self.parsed_configs if c.port == 80])
        port_443 = len([c for c in self.parsed_configs if c.port == 443])
        other_ports = len(self.parsed_configs) - port_80 - port_443

        logger.info(f"\n--- Collection Stats ---")
        logger.info(f"  Raw configs:   {len(self.raw_configs)}")
        logger.info(f"  Valid configs:  {len(self.parsed_configs)}")
        logger.info(f"  Port 80:       {port_80}")
        logger.info(f"  Port 443:      {port_443}")
        logger.info(f"  Other ports:   {other_ports} (will be skipped)")
        logger.info(f"  Protocols:")
        for p, count in sorted(protocols.items()):
            logger.info(f"    {p}: {count}")

        return self.parsed_configs
