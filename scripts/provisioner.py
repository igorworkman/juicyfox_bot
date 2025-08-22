#!/usr/bin/env python3
"""Provisioner for JuicyFox bots (Plan A).

This script helps provision a new bot instance by creating a per‑bot
configuration file under ``configs/bots/`` and printing out the
environment variables you need to set.  It does not modify any
existing files if the target configuration already exists.

Usage (run from the repository root)::

    python scripts/provisioner.py --bot-id bella --token <telegram_token>

The script will copy ``configs/bots/sample_bot.yaml`` to
``configs/bots/<bot_id>.yaml`` and instruct you to update it.  The
provided token is printed as a suggested ``TELEGRAM_TOKEN`` value.
"""

import argparse
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision a new JuicyFox bot configuration")
    parser.add_argument("--bot-id", required=True, help="Identifier of the bot to create (e.g. 'bella')")
    parser.add_argument("--token", required=True, help="Telegram bot token for the new bot")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    src_cfg = repo_root / "configs" / "bots" / "sample_bot.yaml"
    dst_cfg = repo_root / "configs" / "bots" / f"{args.bot_id}.yaml"

    if not src_cfg.exists():
        raise SystemExit(f"Sample config not found at {src_cfg}. Please create it first.")

    if dst_cfg.exists():
        raise SystemExit(f"Target config {dst_cfg} already exists; aborting to avoid overwrite.")

    # Ensure the destination directory exists (create configs/bots if needed)
    dst_cfg.parent.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(src_cfg, dst_cfg)
    print(f"Created bot config: {dst_cfg}")
    print("Please edit this file to customize pricing, features, and channel IDs.")
    print()
    print("Suggested environment variables:")
    print(f"  TELEGRAM_TOKEN={args.token}")
    print(f"  BOT_ID={args.bot_id}")
    print(f"  DB_PATH=/app/data/{args.bot_id}.sqlite")


if __name__ == "__main__":
    main()
