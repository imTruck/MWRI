import logging
import sys
from pathlib import Path
from src.collector import ConfigCollector
from src.tester import ConfigTester
from src.utils import save_txt, save_base64, save_json, save_by_protocol, generate_readme
from src.cleaner import load_clean_ips, apply_clean_ips

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

BEST_COUNT = 300


def main():
    OUTPUT_DIR = "output"
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    # Step 1: Collect
    logger.info("========== Step 1: Collecting ==========")
    collector = ConfigCollector(sources_file="sources.json")
    all_configs = collector.collect_all()
    if not all_configs:
        logger.error("No configs found!")
        sys.exit(1)

    # Step 2: Test - round 1 (fast filter)
    logger.info("========== Step 2: Testing (Round 1) ==========")
    tester = ConfigTester(timeout=4, max_workers=150)
    tested = tester.test_batch(all_configs)
    candidates = tester.get_best(tested, top_n=500, max_latency=2000)

    if not candidates:
        logger.warning("No alive configs in round 1!")
        save_txt(all_configs, OUTPUT_DIR + "/all.txt")
        sys.exit(1)

    # Step 3: Retest top candidates (accurate)
    logger.info("========== Step 3: Retest Top " + str(len(candidates)) + " ==========")
    tester2 = ConfigTester(timeout=5, max_workers=80)
    retested = tester2.test_batch(candidates)
    best = tester2.get_best(retested, top_n=BEST_COUNT, max_latency=1500)

    if not best:
        logger.warning("No alive after retest, using round 1 results")
        best = candidates[:BEST_COUNT]

    # Step 4: Save
    logger.info("========== Step 4: Saving (top " + str(len(best)) + ") ==========")
    save_txt(best, OUTPUT_DIR + "/best.txt")
    save_base64(best, OUTPUT_DIR + "/best_base64.txt")
    save_json(best, OUTPUT_DIR + "/best.json")
    save_txt(all_configs, OUTPUT_DIR + "/all.txt")
    save_by_protocol(best, OUTPUT_DIR)

    # Step 5: Clean IPs
    logger.info("========== Step 5: Clean IPs ==========")
    clean_ips = load_clean_ips("clean_ips.txt")

    if clean_ips:
        cleaned = apply_clean_ips(best, clean_ips)
        if cleaned:
            clean_dir = OUTPUT_DIR + "/clean"
            Path(clean_dir).mkdir(parents=True, exist_ok=True)
            save_txt(cleaned, clean_dir + "/best.txt")
            save_base64(cleaned, clean_dir + "/best_sub.txt")
            save_by_protocol(cleaned, clean_dir)
            logger.info("Clean: " + str(len(cleaned)) + " configs saved!")
    else:
        logger.info("No clean IPs, skipping...")

    # README
    alive_count = len([c for c in tested if c.is_alive])
    with open("README.md", "w") as f:
        f.write(generate_readme(tested, best, alive_count))

    logger.info("========================================")
    logger.info("  Total:     " + str(len(all_configs)))
    logger.info("  Alive:     " + str(alive_count))
    logger.info("  Best:      " + str(len(best)))
    logger.info("  Fastest:   " + str(best[0].latency) + "ms")
    logger.info("  Slowest:   " + str(best[-1].latency) + "ms")
    if clean_ips:
        logger.info("  Clean IPs: " + str(len(clean_ips)))
    logger.info("========================================")


if __name__ == "__main__":
    main()
