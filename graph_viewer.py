#!/usr/bin/env python3
"""Compatibility entrypoint for ``python3 graph_viewer.py``."""

import runpy


if __name__ == "__main__":
    runpy.run_module("deepalpha.graph_viewer", run_name="__main__")
