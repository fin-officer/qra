"""Pytest configuration and fixtures."""
import os
import tempfile
import pytest
from pathlib import Path

from qra.core import MHTMLProcessor


@pytest.fixture
temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
test_mhtml_file():
    """Create a simple MHTML test file."""
    content = """MIME-Version: 1.0
Content-Type: multipart/related; boundary="----=_NextPart_000_0000_01D9A1B2.12345678"

------=_NextPart_000_0000_01D9A1B2.12345678
Content-Type: text/html; charset=utf-8
Content-Transfer-Encoding: quoted-printable
Content-Location: test.html

<!DOCTYPE html><html><head><title>Test</title></head><body>Test Content</body></html>
------=_NextPart_000_0000_01D9A1B2.12345678--
"""
    with tempfile.NamedTemporaryFile(suffix='.mhtml', delete=False) as f:
        f.write(content.encode('utf-8'))
        f.flush()
        yield Path(f.name)
    if os.path.exists(f.name):
        os.unlink(f.name)


@pytest.fixture
test_md_file():
    """Create a simple Markdown test file."""
    content = "# Test Markdown\n\nThis is a test markdown file.\n\n- Item 1\n- Item 2"
    with tempfile.NamedTemporaryFile(suffix='.md', delete=False) as f:
        f.write(content.encode('utf-8'))
        f.flush()
        yield Path(f.name)
    if os.path.exists(f.name):
        os.unlink(f.name)
