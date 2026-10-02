"""``python -m crypto_agents <command>`` (run from the ClaudeTrader directory)."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from .assets import load_portfolio
from .runner import Runner


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="crypto_agents", description=__doc__)
    p.add_argument("command", choices=["run", "train", "status", "test-notify"])
    p.add_argument("--config", help="portfolio yaml (default: configs/portfolio.yaml)")
    p.add_argument("--notifier-config", help="notifier yaml (default: configs/notifier.yaml)")
    p.add_argument("--only", help="comma-separated symbols, e.g. PEPE,SHIB")
    p.add_argument("--loop", action="store_true", help="run forever instead of one pass")
    p.add_argument("--dry-run", action="store_true", help="print messages instead of sending")
    p.add_argument("--data-dir", help="override the state/candle directory")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    portfolio = load_portfolio(args.config, args.notifier_config)
    if args.data_dir:
        portfolio.data_dir = args.data_dir
    symbols = args.only.split(",") if args.only else None
    runner = Runner(portfolio, symbols, dry_run=args.dry_run)

    if args.command == "run":
        runner.run_forever() if args.loop else print(json.dumps(runner.run_once(), indent=1, default=str))
    elif args.command == "train":
        print(json.dumps(runner.run_once(force_train=True, evaluate=False), indent=1, default=str))
    elif args.command == "status":
        for row in runner.status():
            print(row)
    else:
        runner.test_notify()
    return 0


if __name__ == "__main__":
    sys.exit(main())
