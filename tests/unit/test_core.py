"""Unit tests for the core MHTML processing functionality."""
import os
import pytest
from pathlib import Path

from qra.core import MHTMLProcessor


def test_mhtml_processor_initialization():
    """Test MHTMLProcessor initialization."""
    processor = MHTMLProcessor()
    assert processor.filepath is None
    assert processor.qra_dir.name == '.qra'
    assert isinstance(processor.components, dict)


def test_extract_to_qra_folder(test_mhtml_file, temp_dir):
    """Test extracting MHTML to .qra folder."""
    processor = MHTMLProcessor(test_mhtml_file)
    
    # Change to temp directory for testing
    original_dir = os.getcwd()
    os.chdir(temp_dir)
    
    try:
        count = processor.extract_to_qra_folder()
        
        # Verify files were extracted
        assert count > 0
        assert (temp_dir / '.qra').exists()
        assert (temp_dir / '.qra' / 'metadata.json').exists()
        
        # Clean up
        if (temp_dir / '.qra').exists():
            import shutil
            shutil.rmtree(temp_dir / '.qra')
    finally:
        os.chdir(original_dir)


def test_create_empty_mhtml(temp_dir):
    """Test creating an empty MHTML file."""
    output_file = temp_dir / 'empty.mhtml'
    processor = MHTMLProcessor()
    
    processor.create_empty_mhtml(output_file)
    
    assert output_file.exists()
    assert output_file.stat().st_size > 0


def test_markdown_to_mhtml(test_md_file, temp_dir):
    """Test converting Markdown to MHTML."""
    output_file = temp_dir / 'output.mhtml'
    processor = MHTMLProcessor()
    
    processor.markdown_to_mhtml(test_md_file, output_file)
    
    assert output_file.exists()
    assert output_file.stat().st_size > 0
    
    # Verify it's a valid MHTML file
    with open(output_file, 'rb') as f:
        content = f.read().decode('utf-8', errors='ignore')
        assert 'MIME-Version: 1.0' in content
        assert 'Content-Type: multipart/related' in content


def test_mhtml_to_markdown(test_mhtml_file, temp_dir):
    """Test converting MHTML to Markdown."""
    output_file = temp_dir / 'output.md'
    processor = MHTMLProcessor(test_mhtml_file)
    
    processor.mhtml_to_markdown(output_file)
    
    assert output_file.exists()
    assert output_file.stat().st_size > 0


def test_search_files(test_mhtml_file, temp_dir):
    """Test searching through MHTML files."""
    # Copy test file to temp directory
    import shutil
    test_file = temp_dir / 'test.mhtml'
    shutil.copy2(test_mhtml_file, test_file)
    
    processor = MHTMLProcessor()
    results = processor.search_files(['Test', 'Content'], str(temp_dir))
    
    assert str(test_file) in results
    assert len(results[str(test_file)]) > 0
