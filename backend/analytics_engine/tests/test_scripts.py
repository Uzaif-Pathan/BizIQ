"""The helper scripts must keep working: sample check passes, and the generator reproduces the committed samples."""
import filecmp
import shutil
import subprocess
import sys

from conftest import SAMPLES

ROOT = SAMPLES.parents[1]


def test_check_samples_script_passes():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_samples.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.count("PASS") == 4


def test_generator_reproduces_committed_samples(tmp_path):
    (tmp_path / "scripts").mkdir()
    shutil.copy(ROOT / "scripts" / "generate_demo_data.py", tmp_path / "scripts")
    subprocess.run([sys.executable, str(tmp_path / "scripts" / "generate_demo_data.py")], check=True, capture_output=True)
    out = tmp_path / "data" / "samples"
    for f in out.rglob("*.csv"):
        assert filecmp.cmp(f, SAMPLES / f.relative_to(out), shallow=False), f.name
    assert (out / "businesses.json").read_text() == (SAMPLES / "businesses.json").read_text()
