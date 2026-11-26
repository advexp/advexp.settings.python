"""The samples guard: every sample runs clean, and the abort print of the
shared-declarations sample names the failed members.

The samples are the living review of the public API: the project promises
that they run without errors after any change to it. Nothing else in the
suite executes them, so this module does — each sample runs as a console
command of the project interpreter, and a sample that exits nonzero fails
the suite.

The owner keeps personal experiment drafts beside the samples under names
carrying ``my_`` (``my_sample.py``, a future ``some_my.py``); the guard
skips every such file.
"""

import subprocess
import sys
from pathlib import Path
from typing import List

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# every sample of the three sets, minus the owner's personal drafts
SAMPLES: List[Path] = sorted(
    path
    for path in REPO_ROOT.glob("samples/*/*.py")
    if not path.name.startswith("my_") and not path.name.endswith("_my.py")
)

SHARED_DECLARATIONS = REPO_ROOT / "samples" / "both_packages" / "shared_declarations.py"


def run_sample(sample: Path) -> subprocess.CompletedProcess:
    """Run one sample the way its docstring tells the reader to run it."""
    return subprocess.run(
        [sys.executable, str(sample)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda path: str(path.relative_to(REPO_ROOT)))
def test_every_sample_runs_clean(sample: Path) -> None:
    run = run_sample(sample)
    assert run.returncode == 0, (
        f"the sample exited with {run.returncode}:\n{run.stdout}\n{run.stderr}"
    )


def test_shared_declarations_names_the_failed_members() -> None:
    """The abort print carries the member entries, not the bare header line."""
    run = run_sample(SHARED_DECLARATIONS)
    refused = [line for line in run.stdout.splitlines() if "refused:" in line]
    assert len(refused) == 2, run.stdout
    assert all("'api_token'" in line for line in refused), run.stdout
