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
        "NPL_PPSTRUCTURE_MEMORY:-6g",
        "--memory \"$memory\"",
        "--pids-limit 256",
        "--cap-drop ALL",
        "no-new-privileges",
        "readonly",
        "--user \"$uid:$gid\"",
        "PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT=False",
        "src=$staging,dst=/output",
        "refusing to overwrite",
    ):
        assert required in source
    assert "src=$output,dst=/output" not in source


def test_restricted_ppstructure_launcher_requires_a_positive_physical_page(tmp_path: Path) -> None:
    source = tmp_path / "input.png"
    source.write_bytes(b"image")

    result = subprocess.run(["sh", "docker/run-ppstructure-smoke.sh", str(source), str(tmp_path / "output"), "0"], capture_output=True, text=True)

    assert result.returncode == 2
    assert "physical page" in result.stderr
