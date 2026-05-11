#!/usr/bin/env python3
"""Compatibility entrypoint for ``python3 report_formatter.py``."""

from deepalpha.report_formatter import *  # noqa: F401,F403
from deepalpha.report_formatter import main


if __name__ == "__main__":
    main()
