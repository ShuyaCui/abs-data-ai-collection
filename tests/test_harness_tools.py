from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).parents[1]
PLUGIN = ROOT / "harness" / "dsh" / "npl-document-tools.mjs"
PATCH = ROOT / "harness" / "dsh" / "npl-document-tools.patch.yml"


def test_dsh_document_plugin_registers_only_bounded_tools() -> None:
    script = """
const plugin = (await import(process.argv[1])).default;
const definitions = [];
plugin.apply({ tools: { register(definition) { definitions.push(definition); } } }, {
  python: process.execPath,
  worker: '/unused/worker.py',
});
console.log(JSON.stringify(definitions.map(({ name, parameters, output }) => ({ name, parameters, output }))));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script, str(PLUGIN)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    definitions = json.loads(result.stdout)
    assert [definition["name"] for definition in definitions] == [
        "retrieve_evidence",
        "get_page",
        "get_table",
        "extract_field_facts",
        "validate_facts",
        "request_review",
    ]
    assert all(definition["output"]["schema"]["type"] == "object" for definition in definitions)
    assert definitions[0]["parameters"]["required"] == ["document_sha256", "scope", "evidence_id"]


def test_dsh_document_plugin_loads_from_patch(tmp_path: Path) -> None:
    package_dir = tmp_path / "dsh" / "profiles" / "headless" / "node_modules"
    package_dir.mkdir(parents=True)
    (package_dir / "npl-document-tools").symlink_to(ROOT / "harness" / "dsh", target_is_directory=True)
    result = subprocess.run(
        [ROOT / "node_modules/.bin/dsh", "--profile", "headless", "--patch", PATCH, "--dump-config"],
        cwd=ROOT,
        env={**os.environ, "DSH_HOME": str(tmp_path / "dsh")},
        check=True,
        capture_output=True,
        text=True,
    )

    assert "id: npl-document-tools" in result.stdout


def test_dsh_blocks_text_egress_without_a_deployment_grant() -> None:
    script = """
const plugin = (await import(process.argv[1])).default;
const definitions = [];
plugin.apply({ tools: { register(definition) { definitions.push(definition); } } }, { python: process.execPath, worker: '/unused/worker.py' });
try {
  await definitions[0].execute({ document_sha256: 'a'.repeat(64), scope: 'pypdf-all', evidence_id: 'p001:b001' }, { signal: new AbortController().signal });
} catch (error) {
  console.log(error.message);
}
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script, str(PLUGIN)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "document text egress is disabled by deployment policy"
