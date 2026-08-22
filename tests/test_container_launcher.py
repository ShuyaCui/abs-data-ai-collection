from pathlib import Path
import subprocess


def test_restricted_ppstructure_launcher_guards_its_boundary(tmp_path: Path) -> None:
    launcher = Path("docker/run-ppstructure-smoke.sh")
    result = subprocess.run(["sh", launcher, "relative.png", str(tmp_path)], capture_output=True, text=True)

    assert result.returncode == 2
    assert "absolute path" in result.stderr
    source = launcher.read_text()
    for required in (
        "--platform linux/amd64",
        "--network none",
        "--read-only",
        "--memory 4g",
        "--pids-limit 256",
        "--cap-drop ALL",
        "no-new-privileges",
        "readonly",
        "--user \"$uid:$gid\"",
        "src=$staging,dst=/output",
        "refusing to overwrite",
    ):
        assert required in source
    assert "src=$output,dst=/output" not in source
