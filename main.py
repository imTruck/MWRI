import logging
import sys
from pathlib import Path
from src.collector import ConfigCollector
from src.tester import ConfigTester
from src.cleaner import load_clean_ips, apply_clean_ips, filter_cdn_configs
from src.cdn_tester import CDNTester, diversify_ports, generate_port_variants
from src.fragment import generate_fragment_configs
from src.utils import save_txt, save_base64, save_json, save_by_protocol, generate_readme

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

    # Step 2: Quick test all
    logger.info("=== Step 2: Quick test ===")
    tester = ConfigTester(timeout=3, max_workers=200)
    tested = tester.test_batch(all_configs)
    best = tester.get_best(tested, top_n=BEST_COUNT, max_latency=2000)

    if not best:
        logger.warning("No alive!")
        save_txt(all_configs, OUTPUT_DIR + "/all.txt")
        sys.exit(1)

    # Step 3: Save normal best
    logger.info("=== Step 3: Save best ===")
    save_txt(best, OUTPUT_DIR + "/best.txt")
    save_base64(best, OUTPUT_DIR + "/best_base64.txt")
    save_json(best, OUTPUT_DIR + "/best.json")
    save_txt(all_configs, OUTPUT_DIR + "/all.txt")
    save_by_protocol(best, OUTPUT_DIR)

    # ============ CDN SECTION ============

    # Step 4: Filter CDN configs
    logger.info("=== Step 4: Filter CDN ===")
    alive_all = [c for c in tested if c.is_alive]
    cdn_configs = filter_cdn_configs(alive_all)

    if not cdn_configs:
        logger.warning("No CDN configs!")
        alive_count = len(alive_all)
        with open("README.md", "w") as f:
            f.write(generate_readme(tested, best, alive_count, 0))
        return

    # Step 5: Generate port variants from best CDN configs
    logger.info("=== Step 5: Port variants ===")
    cdn_configs.sort(key=lambda x: x.latency)
    port_variants = generate_port_variants(cdn_configs[:30])

    # Combine original CDN + port variants
    all_cdn = cdn_configs + port_variants
    logger.info("Total CDN to test: " + str(len(all_cdn)))

    # Step 6: Hardcore CDN test
    logger.info("=== Step 6: Hardcore CDN test (5 rounds) ===")
    cdn_tester = CDNTester()
    cdn_tested = cdn_tester.test_batch(all_cdn)
    cdn_best_raw = cdn_tester.get_best(cdn_tested, top_n=500)

    if not cdn_best_raw:
        logger.warning("No CDN passed hardcore test!")
    else:
        # Step 7: Diversify ports (443/80 max 40%)
        logger.info("=== Step 7: Diversify ports ===")
        cdn_best = diversify_ports(cdn_best_raw, max_common_ratio=0.4)
        cdn_best = cdn_best[:BEST_COUNT]

        cdn_dir = OUTPUT_DIR + "/cdn"
        Path(cdn_dir).mkdir(parents=True, exist_ok=True)
        save_txt(cdn_best, cdn_dir + "/best.txt")
        save_base64(cdn_best, cdn_dir + "/best_sub.txt")
        save_by_protocol(cdn_best, cdn_dir)

        # Step 8: Clean IP
        logger.info("=== Step 8: Clean IPs ===")
        clean_ips = load_clean_ips("clean_ips.txt")
        if clean_ips:
            cleaned = apply_clean_ips(cdn_best, clean_ips)
            if cleaned:
                clean_dir = OUTPUT_DIR + "/clean"
                Path(clean_dir).mkdir(parents=True, exist_ok=True)
                save_txt(cleaned, clean_dir + "/best.txt")
                save_base64(cleaned, clean_dir + "/best_sub.txt")
                save_by_protocol(cleaned, clean_dir)

        # Step 9: Fragment
        logger.info("=== Step 9: Fragment ===")
        frag = generate_fragment_configs(cdn_best[:50])
        if frag:
            frag_dir = OUTPUT_DIR + "/fragment"
            Path(frag_dir).mkdir(parents=True, exist_ok=True)
            save_txt(frag, frag_dir + "/best.txt")
            save_base64(frag, frag_dir + "/best_sub.txt")

    # README
    alive_count = len(alive_all)
    cdn_count = len(cdn_best_raw) if cdn_best_raw else 0
    with open("README.md", "w") as f:
        f.write(generate_readme(tested, best, alive_count, cdn_count))

    logger.info("========== DONE ==========")
    logger.info("Total:    " + str(len(all_configs)))
    logger.info("Alive:    " + str(alive_count))
    logger.info("Best:     " + str(len(best)))
    logger.info("CDN:      " + str(cdn_count))


if __name__ == "__main__":
    main()
