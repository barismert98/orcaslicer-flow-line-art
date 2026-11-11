"""What the published package carries."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LICENSE_START = "GNU GENERAL PUBLIC LICENSE"


def test_the_license_is_in_the_repo_and_inside_the_package():
    repo_license = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert LICENSE_START in repo_license[:200]
    assert (ROOT / "src" / "flow_line_art" / "LICENSE").read_text(encoding="utf-8") == repo_license
