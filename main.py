import logging
import sys
from pathlib import Path
from src.collector import ConfigCollector
from src.tester import ConfigTester
from src.utils import save_txt, save_base64, save_json, save_by_protocol, generate_readme
from src.cleaner import load_clean_ips, apply_clean_ips

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


def main():
    OUTPUT_DIR = "output"
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    logger.info("Starting...")

    # Step 1: Collect
    collector = ConfigCollector(sources_file="sources.json")
    all_configs = collector.collect_all()
    if not all_configs:
        logger.error("No configs found!")
        sys.exit(1)

    # Step 2: Test
    tester = ConfigTester(timeout=5, max_workers=100)
    tested = tester.test_batch(all_configs)
    best = tester.get_best(tested, top_n=500, max_latency=3000)

    if not best:
        logger.warning("No alive configs!")
        save_txt(all_configs, OUTPUT_DIR + "/all.txt")
        sys.exit(1)

    # Step 3: Save normal configs
    logger.info("--- Saving normal configs ---")
    save_txt(best, OUTPUT_DIR + "/best.txt")
    save_base64(best, OUTPUT_DIR + "/best_base64.txt")
    save_json(best, OUTPUT_DIR + "/best.json")
    save_txt(all_configs, OUTPUT_DIR + "/all.txt")
    save_by_protocol(best, OUTPUT_DIR)

    # Step 4: Apply clean IPs
    logger.info("--- Applying clean IPs ---")
    clean_ips = load_clean_ips("clean_ips.txt")

    if clean_ips:
        cleaned = apply_clean_ips(best, clean_ips)

        if cleaned:
            clean_dir = OUTPUT_DIR + "/clean"
            Path(clean_dir).mkdir(parents=True, exist_ok=True)

            save_txt(cleaned, clean_dir + "/all.txt")
            save_base64(cleaned, clean_dir + "/all_sub.txt")
            save_by_protocol(cleaned, clean_dir)

            logger.info("Clean IP configs saved!")
        else:
            logger.warning("No clean configs generated!")
    else:
        logger.info("No clean IPs found, skipping...")

    # README
    with open("README.md", "w") as f:
        f.write(generate_readme(tested, best))

    alive = len([c for c in tested if c.is_alive])
    logger.info("Done! Total:" + str(len(all_configs)) + " Alive:" + str(alive) + " Best:" + str(len(best)))


if __name__ == "__main__":
    main()
