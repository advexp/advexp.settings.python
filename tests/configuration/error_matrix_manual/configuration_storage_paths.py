"""The storage folder in which every dumped source file lands.

Each test of this suite owns one file in ``storage/``. The test dumps the
content of the file before it runs, and the file stays on disk after the
run, so the exact document that the test fed the library can be opened and
read. The folder holds generated output only, and its contents stay out of
git.
"""

from pathlib import Path

STORAGE_DIR = Path(__file__).resolve().parent / "storage"


def prepare_storage_dir() -> None:
    """Create the storage folder (a test calls this before dumping its file)."""
    STORAGE_DIR.mkdir(exist_ok=True)
