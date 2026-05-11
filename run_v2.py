#!/usr/bin/env python3
"""Compatibility entrypoint for ``python3 run_v2.py``."""

from deepalpha.run_v2 import *  # noqa: F401,F403
from deepalpha.run_v2 import main


if __name__ == "__main__":
    main()
