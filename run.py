#!/usr/bin/env python3
"""Compatibility entrypoint for ``python3 run.py``."""

from deepalpha.run import *  # noqa: F401,F403
from deepalpha.run import main


if __name__ == "__main__":
    main()
