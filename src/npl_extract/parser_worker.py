from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from npl_extract.parsers import DoclingNativeParser, PypdfNativeParser


def main() -> int:
    _limit_resources()
    parser = argparse.ArgumentParser()
    parser.add_argument("--parser", choices=["docling", "pypdf"], required=True)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        pages = {"docling": DoclingNativeParser, "pypdf": PypdfNativeParser}[args.parser]().parse(args.path)
    except RuntimeError as error:
        code = "PARSER_EXTRA_MISSING" if "install npl-extract" in str(error) else "PARSER_FAILED"
        print(json.dumps({"error": {"code": code, "message": str(error)}}))
        return 2
    print(json.dumps([asdict(page) for page in pages], ensure_ascii=False))
    return 0


def _limit_resources() -> None:
    try:
        import resource
    except ImportError as error:
        raise RuntimeError("parser resource limits are unavailable") from error
    for limit, value in ((resource.RLIMIT_CPU, 120), (resource.RLIMIT_FSIZE, 64 * 1024**2)):
        _, maximum = resource.getrlimit(limit)
        if maximum < value:
            raise RuntimeError("parser resource limit is below the required minimum")
        resource.setrlimit(limit, (value, maximum))


if __name__ == "__main__":
    raise SystemExit(main())
