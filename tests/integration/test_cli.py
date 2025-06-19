"""Integration tests for the CLI interface."""
import os
import pytest
import subprocess
from pathlib import Path


def test_cli_help():
    """Test the CLI help command."""
    result = subprocess.run(
        ["poetry", "run", "qra", "--help"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "QRA - MHTML Editor and Processor" in result.stdout


def test_cli_create_command(temp_dir):
    """Test the create command."""
    test_file = temp_dir / "test.mhtml"
    result = subprocess.run(
        ["poetry", "run", "qra", "create", str(test_file)],
        capture_output=True,
        text=True,
        cwd=temp_dir
    )
    
    assert result.returncode == 0
    assert test_file.exists()
    assert "Utworzono nowy plik MHTML" in result.stdout


def test_cli_edit_command(test_mhtml_file, temp_dir):
    """Test the edit command (basic test, doesn't test the full editor)."""
    result = subprocess.run(
        ["poetry", "run", "qra", "edit", str(test_mhtml_file)],
        capture_output=True,
        text=True,
        timeout=5  # Short timeout since we don't want to run the server
    )
    
    # The command should try to start the server
    assert "Uruchamianie edytora" in result.stdout


def test_cli_md_command(test_md_file, temp_dir):
    """Test the markdown to MHTML conversion."""
    output_file = temp_dir / "output.mhtml"
    result = subprocess.run(
        ["poetry", "run", "qra", "html", str(test_md_file), str(output_file)],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert output_file.exists()
    assert "Skonwertowano" in result.stdout


def test_cli_search_command(test_mhtml_file, temp_dir):
    """Test the search command."""
    result = subprocess.run(
        ["poetry", "run", "qra", "search", "Test", "--path", str(temp_dir)],
        capture_output=True,
        text=True
    )
    
    # The search should find our test file
    assert result.returncode == 0
    assert "Znaleziono" in result.stdout or "nie znaleziono" in result.stdout.lower()
