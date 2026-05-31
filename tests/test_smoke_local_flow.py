from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from smoke_local_flow import run_smoke


def test_local_smoke_flow_completes_approval_and_blocks_high_risk(tmp_path):
    result = run_smoke(Path("."), tmp_path)
    assert result["medium_status"] == "completed"
    assert result["high_status"] == "blocked"
    assert result["events_recorded"] > 0
