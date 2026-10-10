"""Runs the chart script as a subprocess on the labelled synthetic fixture,
writing into tmp_path; results/ is never touched."""

import subprocess
import sys
from pathlib import Path

FIGURES = Path(__file__).resolve().parents[1]
SCRIPT = FIGURES / "exp3_duplicates.py"
FIXTURE = FIGURES / "tests" / "fixtures" / "exp3_summary_synthetic.csv"


def test_chart_from_synthetic_fixture(tmp_path: Path):
    output = tmp_path / "exp3_duplicates.svg"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--input", str(FIXTURE), "--output", str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert output.exists()
    svg = output.read_text(encoding="utf-8")
    assert svg.startswith("<?xml") and "<svg" in svg
    # placeholder title, all three stacks, and the printed values (including 0)
    assert "TITLE: author to write" in svg
    for stack in ("dotnet", "java", "python"):
        assert stack in svg
    for value in ("98.0", "99.0", "97.0", "497.0", "498.0", "496.0"):
        assert value in svg
    assert svg.count(">0.0<") >= 6  # every keyed bar prints its zero
