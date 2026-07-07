#!/usr/bin/env python3
"""
DevKit — Portable Project Ops Toolkit
Usage:
  python devkit.py            → launches GUI
  python devkit.py --cli      → interactive CLI
  python devkit.py run script.dk    → execute script file
  python devkit.py preview script.dk → preview only
  python devkit.py --help     → show manual
"""
import sys
import os

# Make devkit_core importable regardless of where we're called from
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from devkit_core.cli import run_cli
from devkit_core.manual import print_manual


def main():
    args = sys.argv[1:]

    if not args:
        # No args = launch GUI
        try:
            from devkit_core.gui import launch_gui
            launch_gui()
        except ImportError as e:
            print(f"GUI unavailable ({e}). Falling back to CLI.")
            run_cli([])
        return

    if args[0] in ("-h", "--help", "help", "manual"):
        print_manual()
        return

    run_cli(args)


if __name__ == "__main__":
    main()
