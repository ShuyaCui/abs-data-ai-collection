from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).parents[1]
PATCH = ROOT / "harness" / "dsh" / "npl-headless.patch.yml"
DSH = ROOT / "node_modules" / ".bin" / "dsh"


def test_dsh_patch_disables_generic_agent_tools(tmp_path: Path) -> None:
    result = subprocess.run(
        [DSH, "--profile", "headless", "--patch", PATCH, "--dump-config"],
        cwd=ROOT,
        env={**os.environ, "DSH_HOME": str(tmp_path / "dsh"), "DSH_PERMISSION_MODE": "read-only"},
        check=True,
        capture_output=True,
        text=True,
    )

    for tool_id in ("tool-bash", "tool-fs", "tool-web", "tool-subagent", "tool-workflow"):
        entry = re.search(rf"- id: {tool_id}\n.*?(?=\n- id:|\Z)", result.stdout, re.DOTALL)
        assert entry and "disabled: true" in entry.group(0)
    assert "id: session-telemetry-otel" in result.stdout
    assert "mode: DISABLED" in result.stdout
