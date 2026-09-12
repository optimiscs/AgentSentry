import json
import hashlib
import platform
from datetime import datetime, timezone
from pathlib import Path
import pytest
from agentsentry.config import Settings
from agentsentry.demo import seed
from agentsentry.gateway.runtime import Runtime

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings(tmp_path):
    policy = tmp_path / "default.aspolicy"
    policy.write_text((ROOT / "policies/default.aspolicy").read_text())
    s = Settings(tmp_path / "state", tmp_path / "state/workspace", policy)
    seed(s)
    return s


@pytest.fixture
def rt(settings):
    r = Runtime(settings)
    yield r
    r.close()


def pytest_configure(config):
    config.case_results = []


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        item.config.case_results.append(
            {
                "test": item.nodeid,
                "outcome": report.outcome,
                "duration_seconds": report.duration,
                "cases": [m.args[0] for m in item.iter_markers("case")],
            }
        )


def pytest_sessionfinish(session, exitstatus):
    target = ROOT / "artifacts/test-results.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "exitstatus": exitstatus,
                "tests": session.config.case_results,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "python": platform.python_version(),
                "platform": platform.platform(),
                "source_files": {
                    str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for folder, pattern in [
                        ("src", "*.py"),
                        ("policies", "*.aspolicy"),
                        ("tests", "*.py"),
                        ("dashboard/src", "*"),
                    ]
                    for p in sorted((ROOT / folder).rglob(pattern))
                    if p.is_file()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
