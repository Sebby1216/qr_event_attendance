import os
import tempfile
from pathlib import Path

_test_dir = tempfile.mkdtemp(prefix="ssit-test-")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + (Path(_test_dir) / "test.db").as_posix()
