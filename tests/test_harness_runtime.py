from __future__ import annotations

import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).parents[1]
VERIFY = ROOT / "harness" / "dsh" / "verify-runtime.mjs"


def test_fixed_dsh_runtime_identity_is_verified() -> None:
    result = subprocess.run(
        ["node", VERIFY], cwd=ROOT, check=True, capture_output=True, text=True
    )

    identity = json.loads(result.stdout)
    assert identity["version"] == "0.1.0-rc.8"
    assert identity["integrity"].startswith("sha512-")
