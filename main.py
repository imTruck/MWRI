import logging
import sys
from pathlib import Path
from src.collector import ConfigCollector
from src.tester import ConfigTester
from src.utils import save_txt, save_base64, save_json, save_by_protocol, generate_readme
from src.cleaner import load_clean_ips, apply_clean_ips, filter_cdn_configs
from src.fragment import generate_fragment_configs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

BEST_COUNT = 200


def main():
    OUTPUT_DIR = "output"
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    # Step 1: Collect
    logger.info("=== Step 1: Collecting ===")
    collector = ConfigCollector(sources_file="sources.json")
    all_configs = collector.collect_all()
    if not all_configs:
        logger.error("No configs!")
        sys.exit(1)

    # Step 2: Test
    logger.info("=== Step 2: Testing ===")
    tester = ConfigTester(timeout=3, max_workers=200)
    tested = tester.test_batch(all_configs)
    best = tester.get_best(tested, top_n=BEST_COUNT, max_latency=2000)

    if not best:
        logger.warning("No alive!")
        save_txt(all_configs, OUTPUT_DIR + "/all.txt")
        sys.exit(1)

    # Step 3: Save best
    logger.info("=== Step 3: Saving best ===")
    save_txt(best, OUTPUT_DIR + "/best.txt")
    save_base64(best, OUTPUT_DIR + "/best_base64.txt")
    save_json(best, OUTPUT_DIR + "/best.json")
    save_txt(all_configs, OUTPUT_DIR + "/all.txt")
    save_by_protocol(best, OUTPUT_DIR)

    # Step 4: CDN only
    logger.info("=== Step 4: CDN configs ===")
    alive_all = [c for c in tested if c.is_alive]
    cdn_configs = filter_cdn_configs(alive_all)

    cdn_best = []
    if cdn_configs:
        cdn_configs.sort(key=lambda x: x.latency)
        cdn_best = cdn_configs[:BEST_COUNT]

        cdn_dir = OUTPUT_DIR + "/cdn"
        Path(cdn_dir).mkdir(parents=True, exist_ok=True)
        save_txt(cdn_best, cdn_dir + "/best.txt")
        save_base64(cdn_best, cdn_dir + "/best_sub.txt")
        save_by_protocol(cdn_best, cdn_dir)

    # Step 5: Clean IP
    logger.info("=== Step 5: Clean IPs ===")
    clean_ips = load_clean_ips("clean_ips.txt")
    if clean_ips and cdn_best:
        cleaned = apply_clean_ips(cdn_best, clean_ips)
        if cleaned:
            clean_dir = OUTPUT_DIR + "/clean"
            Path(clean_dir).mkdir(parents=True, exist_ok=True)
            save_txt(cleaned, clean_dir + "/best.txt")
            save_base64(cleaned, clean_dir + "/best_sub.txt")
            save_by_protocol(cleaned, clean_dir)

    # Step 6: Fragment
    logger.info("=== Step 6: Fragment ===")
    if cdn_best:
        frag_configs = generate_fragment_configs(cdn_best[:50])
        if frag_configs:
            frag_dir = OUTPUT_DIR + "/fragment"
            Path(frag_dir).mkdir(parents=True, exist_ok=True)
            save_txt(frag_configs, frag_dir + "/best.txt")
            save_base64(frag_configs, frag_dir + "/best_sub.txt")

    # README
    alive_count = len(alive_all)
    cdn_count = len(cdn_configs) if cdn_configs else 0
    with open("README.md", "w") as f:
        f.write(generate_readme(tested, best, alive_count, cdn_count))

    logger.info("=== DONE ===")
    logger.info("Total: " + str(len(all_configs)))
    logger.info("Alive: " + str(alive_count))
    logger.info("Best: " + str(len(best)))
    logger.info("CDN: " + str(cdn_count))


if __name__ == "__main__":
    main()
