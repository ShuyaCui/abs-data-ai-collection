from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from npl_extract.parsers import DoclingNativeParser, PypdfNativeParser


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parser", choices=["docling", "docling-ocr", "pypdf"], required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--page-start", type=int, default=1)
    parser.add_argument("--page-end", type=int)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.page_start < 1 or args.page_end is not None and args.page_end < args.page_start:
        parser.error("page range must be positive and ascending")
    try:
        _limit_resources()
        if args.expected_sha256 and sha256(args.path.read_bytes()).hexdigest() != args.expected_sha256:
            raise RuntimeError("PARSER_INPUT_CHANGED: staged PDF hash does not match intake")
        parser_class = {"docling": DoclingNativeParser, "docling-ocr": lambda: DoclingNativeParser(ocr=True), "pypdf": PypdfNativeParser}[args.parser]
        parser_instance = parser_class()
        pages = parser_instance.parse(args.path, (args.page_start, args.page_end or 2**63 - 1))
    except Exception as error:
        message = str(error)
        if message.startswith("PARSER_INPUT_CHANGED:") or message.startswith("PARSER_PLATFORM_UNSUPPORTED:"):
            code, _, message = message.partition(": ")
        else:
            code = "PARSER_EXTRA_MISSING" if isinstance(error, RuntimeError) and "install npl-extract" in message else "PARSER_FAILED"
        print(json.dumps({"error": {"code": code, "message": message}}))
        return 2
    print(json.dumps([asdict(page) for page in pages], ensure_ascii=False))
    return 0


def _limit_resources() -> None:
    try:
        import resource
    except ImportError as error:
        raise RuntimeError("PARSER_PLATFORM_UNSUPPORTED: POSIX resource limits are unavailable") from error
    for limit, value in ((resource.RLIMIT_CPU, 120), (resource.RLIMIT_FSIZE, 64 * 1024**2)):
        _, maximum = resource.getrlimit(limit)
        if maximum < value:
            raise RuntimeError("PARSER_PLATFORM_UNSUPPORTED: parser resource limit is below the required minimum")
        resource.setrlimit(limit, (value, maximum))


if __name__ == "__main__":
    raise SystemExit(main())
