"""The storage folder every dumped source file lands in.

Each test of this suite owns one file in ``storage/``: the test dumps the
file's content before it runs, and the file stays on disk after the run,
so the exact document a test fed the library can be opened and read. The
folder holds generated output only — its contents stay out of git.
"""

from pathlib import Path

STORAGE_DIR = Path(__file__).resolve().parent / "storage"


def prepare_storage_dir() -> None:
    """Create the storage folder (a test calls this before dumping its file)."""
    STORAGE_DIR.mkdir(exist_ok=True)
