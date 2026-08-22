from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sys

from npl_extract.parsers import PypdfNativeParser


def main() -> int:
    _limit_resources()
    pages = PypdfNativeParser().parse(Path(sys.argv[1]))
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
