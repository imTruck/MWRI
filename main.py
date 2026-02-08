import logging
import sys
from pathlib import Path
from src.collector import ConfigCollector
from src.tester import ConfigTester
from src.utils import save_txt, save_base64, save_json, save_by_protocol, generate_readme

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


def main():
    OUTPUT_DIR = "output"
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    logger.info("Starting...")

    collector = ConfigCollector(sources_file="sources.json")
    all_configs = collector.collect_all()
    if not all_configs:
        logger.error("No configs found!")
        sys.exit(1)

    tester = ConfigTester(timeout=5, max_workers=100)
    tested = tester.test_batch(all_configs)
    best = tester.get_best(tested, top_n=500, max_latency=3000)

    if not best:
        logger.warning("No alive configs!")
        save_txt(all_configs, OUTPUT_DIR + "/all.txt")
        sys.exit(1)

    save_txt(best, OUTPUT_DIR + "/best.txt")
    save_base64(best, OUTPUT_DIR + "/best_base64.txt")
    save_json(best, OUTPUT_DIR + "/best.json")
    save_txt(all_configs, OUTPUT_DIR + "/all.txt")
    save_by_protocol(best, OUTPUT_DIR)

    with open("README.md", "w") as f:
        f.write(generate_readme(tested, best))

    alive = len([c for c in tested if c.is_alive])
    logger.info("Done! Total:" + str(len(all_configs)) + " Alive:" + str(alive) + " Best:" + str(len(best)))


if __name__ == "__main__":
    main()