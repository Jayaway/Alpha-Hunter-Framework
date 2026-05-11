#!/usr/bin/env python3
"""Export runtime graph JSON into a static web asset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_INPUT = Path("graph_data/关系图谱.json")
DEFAULT_OUTPUT = Path("web/graph-data.js")


def export_graph(input_path: Path, output_path: Path) -> None:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    output_path.write_text(f"window.DEEPALPHA_GRAPH = {payload};\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export DeepAlpha graph data for the static web UI.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    export_graph(args.input, args.output)
    print(f"exported {args.input} -> {args.output}")


if __name__ == "__main__":
    main()
