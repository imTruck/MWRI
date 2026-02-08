import logging
import sys
from pathlib import Path
from src.collector import ConfigCollector
from src.tester import ConfigTester
from src.utils import save_txt, save_base64, save_json, save_by_protocol, generate_readme

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)


def main():
    TOP_N = 500
    MAX_LATENCY = 3000
    TEST_WORKERS = 100
    TEST_TIMEOUT = 5
    OUTPUT_DIR = "output"

    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    logger.info("=" * 55)
    logger.info("V2Ray Config Collector (Port 80 & 443 Only)")
    logger.info("=" * 55)

    # Step 1: Collect
    logger.info("\n--- Step 1: Collecting ---")
    collector = ConfigCollector(sources_file="sources.json")
    all_configs = collector.collect_all()
    if not all_configs:
        logger.error("No configs found!")
        sys.exit(1)

    # Step 2: Test
    logger.info("\n--- Step 2: Testing (port 80 & 443 only) ---")
    tester = ConfigTester(timeout=TEST_TIMEOUT, max_workers=TEST_WORKERS)
    tested_configs = tester.test_batch(all_configs)
    best_configs = tester.get_best(tested_configs, top_n=TOP_N, max_latency=MAX_LATENCY)

    if not best_configs:
        logger.warning("No alive configs!")
        save_txt(all_configs, f"{OUTPUT_DIR}/all.txt")
        sys.exit(1)

    # Step 3: Save
    logger.info("\n--- Step 3: Saving ---")

    # همه با هم
    save_txt(best_configs, f"{OUTPUT_DIR}/best.txt")
    save_base64(best_configs, f"{OUTPUT_DIR}/best_base64.txt")
    save_json(best_configs, f"{OUTPUT_DIR}/best.json")
    save_txt(all_configs, f"{OUTPUT_DIR}/all.txt")
    save_base64(all_configs, f"{OUTPUT_DIR}/all_base64.txt")

    # جدا جدا بر اساس پروتکل (هم txt هم sub)
    by_protocol = save_by_protocol(best_configs, OUTPUT_DIR)

    # README
    readme = generate_readme(tested_configs, best_configs)
    with open("README.md", 'w', encoding='utf-8') as f:
        f.write(readme)

    # نتیجه نهایی
    alive_count = len([c for c in tested_configs if c.is_alive])

    logger.info("\n" + "=" * 55)
    logger.info("DONE!")
    logger.info(f"  Total collected:  {len(all_configs)}")
    logger.info(f"  Port 80/443:      {len(tested_configs)}")
    logger.info(f"  Alive:            {alive_count}")
    logger.info(f"  Best saved:       {len(best_configs)}")
    logger.info(f"\n  Files:")
    logger.info(f"    output/best.txt          <- all best configs")
    logger.info(f"    output/best_base64.txt   <- all best (sub link)")
    for proto, configs in sorted(by_protocol.items()):
        logger.info(f"    output/splitted/{proto}.txt       <- {len(configs)} {proto} configs")
        logger.info(f"    output/splitted/{proto}_sub.txt   <- {len(configs)} {proto} (sub link)")
    logger.info("=" * 55)


if __name__ == "__main__":
    main()
