import contextlib
import os
import subprocess
from pathlib import Path
from shutil import rmtree

import pytest

site_dir = Path(__file__).absolute().parent.parent / "site"


@pytest.fixture(scope="function", autouse=True)
def cleanup_folders():
    with contextlib.suppress(OSError):
        rmtree(str(site_dir))
    yield
    with contextlib.suppress(OSError):
        rmtree(str(site_dir))


def test_docs_build():
    subprocess.run(f"hatch run docs:build -d {site_dir}", shell=True, env=os.environ, check=True)
    assert site_dir.is_dir()
    assert (site_dir / "index.html").is_file()
