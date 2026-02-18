import json
import logging
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.parser import parse_config, extract_configs_from_text

logger = logging.getLogger(__name__)


class ConfigCollector:
    def __init__(self, sources_file="sources.json"):
        self.sources_file = sources_file
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def _load_sources(self):
        with open(self.sources_file, "r") as f:
            data = json.load(f)
        return data.get("subscription_urls", [])

    def _fetch_url(self, url):
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            text = resp.text
            configs = extract_configs_from_text(text)
            if configs:
                logger.info("  [+] " + str(len(configs)) + " configs from " + url.split("/")[-1])
            return configs
        except Exception as e:
            logger.debug("  [-] Failed: " + url.split("/")[-1] + " | " + str(e))
            return []

    def collect_all(self):
        urls = self._load_sources()
        logger.info("Fetching from " + str(len(urls)) + " sources...")

        all_configs = []

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(self._fetch_url, url): url for url in urls}
            for future in as_completed(futures):
                try:
                    raw_configs = future.result(timeout=20)
                    for raw in raw_configs:
                        parsed = parse_config(raw)
                        if parsed:
                            all_configs.append(parsed)
                except Exception:
                    pass

        # Remove duplicates
        seen = set()
        unique = []
        for c in all_configs:
            if c.raw not in seen:
                seen.add(c.raw)
                unique.append(c)

        logger.info("Total unique configs: " + str(len(unique)))
        return unique
