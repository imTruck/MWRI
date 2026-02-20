import logging
import sys
from pathlib import Path
from src.collector import ConfigCollector
from src.tester import ConfigTester
from src.cleaner import load_clean_ips, apply_clean_ips, filter_cdn_configs
from src.antifilter import fix_all_configs
from src.fragment import generate_fragment_configs
from src.warp import save_warp
from src.utils import save_txt, save_base64, save_json, save_by_protocol, generate_readme

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


def main():
    OUTPUT_DIR = "output"
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    # Collect
    logger.info("=== Collecting ===")
    collector = ConfigCollector(sources_file="sources.json")
    all_configs = collector.collect_all()
    if not all_configs:
        sys.exit(1)

    # Quick test
    logger.info("=== Testing ===")
    tester = ConfigTester(timeout=3, max_workers=200)
    tested = tester.test_batch(all_configs)
    alive_all = [c for c in tested if c.is_alive]

    best = tester.get_best(tested, top_n=200, max_latency=2000)
    if not best:
        save_txt(all_configs, OUTPUT_DIR + "/all.txt")
        sys.exit(1)

    best = fix_all_configs(best)
    save_txt(best, OUTPUT_DIR + "/best.txt")
    save_base64(best, OUTPUT_DIR + "/best_base64.txt")
    save_json(best, OUTPUT_DIR + "/best.json")
    save_txt(all_configs, OUTPUT_DIR + "/all.txt")
    save_by_protocol(best, OUTPUT_DIR)

    # CDN from ALL configs (not just alive)
    logger.info("=== CDN ===")
    cdn_all = filter_cdn_configs(all_configs)

    cdn_count = 0
    if cdn_all:
        seen = set()
        cdn_unique = []
        for c in cdn_all:
            key = c.address + ":" + str(c.port)
            if key not in seen:
                seen.add(key)
                cdn_unique.append(c)

        cdn_fixed = fix_all_configs(cdn_unique[:500])
        cdn_count = len(cdn_fixed)

        cdn_dir = OUTPUT_DIR + "/cdn"
        Path(cdn_dir).mkdir(parents=True, exist_ok=True)
        save_txt(cdn_fixed, cdn_dir + "/best.txt")
        save_base64(cdn_fixed, cdn_dir + "/best_sub.txt")
        save_by_protocol(cdn_fixed, cdn_dir)

    # Clean IP from ALL CDN configs
    logger.info("=== Clean IP ===")
    clean_ips = load_clean_ips("clean_ips.txt")
    if clean_ips:
        # Use all CDN configs, not just fixed
        all_cdn_for_clean = cdn_all if cdn_all else []
        cleaned = apply_clean_ips(all_cdn_for_clean, clean_ips)
        if cleaned:
            clean_dir = OUTPUT_DIR + "/clean"
            Path(clean_dir).mkdir(parents=True, exist_ok=True)
            save_txt(cleaned, clean_dir + "/best.txt")
            save_base64(cleaned, clean_dir + "/best_sub.txt")
            save_by_protocol(cleaned, clean_dir)
            logger.info("Clean total: " + str(len(cleaned)))
        else:
            logger.warning("No clean configs generated!")

    # Fragment
    if cdn_all:
        frag = generate_fragment_configs(cdn_fixed[:50] if cdn_count > 0 else [])
        if frag:
            frag_dir = OUTPUT_DIR + "/fragment"
            Path(frag_dir).mkdir(parents=True, exist_ok=True)
            save_txt(frag, frag_dir + "/best.txt")
            save_base64(frag, frag_dir + "/best_sub.txt")

    # WARP
    logger.info("=== WARP ===")
    warp_count = save_warp(OUTPUT_DIR)

    # README
    with open("README.md", "w") as f:
        f.write(generate_readme(tested, best, len(alive_all), cdn_count, warp_count))

    logger.info("=== DONE ===")
    logger.info("Best: " + str(len(best)))
    logger.info("CDN: " + str(cdn_count))
    logger.info("Clean: " + str(len(cleaned) if clean_ips and cleaned else 0))
    logger.info("WARP: " + str(warp_count))


if __name__ == "__main__":
    main()
