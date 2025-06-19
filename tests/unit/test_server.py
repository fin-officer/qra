"""Unit tests for the Flask server."""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from qra.server import create_app, auto_save_manager


@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app()
    app.config['TESTING'] = True
    return app


def test_auto_save_manager():
    """Test the AutoSaveManager functionality."""
    mock_processor = MagicMock()
    
    # Test starting the auto-save
    auto_save_manager.start(mock_processor)
    assert auto_save_manager.processor == mock_processor
    assert auto_save_manager.running is True
    
    # Test stopping the auto-save
    auto_save_manager.stop()
    assert auto_save_manager.running is False


def test_index_route(app, client):
    """Test the index route."""
    with app.test_client() as client:
        response = client.get('/')
        assert response.status_code == 200
        assert 'QRA Editor' in response.data.decode()


def test_preview_route(app, client):
    """Test the preview route."""
    with app.test_client() as client:
        response = client.get('/preview')
        assert response.status_code == 200


@patch('qra.server.MHTMLProcessor')
def test_api_files_route(mock_processor_class, app, client):
    """Test the /api/files route."""
    # Setup mock
    mock_processor = MagicMock()
    mock_processor.get_qra_files.return_value = [
        {'name': 'test.html', 'type': 'html', 'content': '<html>test</html>'}
    ]
    mock_processor_class.return_value = mock_processor
    
    with app.test_client() as client:
        response = client.get('/api/files')
        assert response.status_code == 200
        data = response.get_json()
        assert 'files' in data
        assert len(data['files']) == 1
        assert data['files'][0]['name'] == 'test.html'


@patch('qra.server.MHTMLProcessor')
def test_api_save_route(mock_processor_class, app, client):
    """Test the /api/save route."""
    # Setup mock
    mock_processor = MagicMock()
    mock_processor_class.return_value = mock_processor
    
    test_data = {
        'filename': 'test.html',
        'content': '<html>updated</html>'
    }
    
    with app.test_client() as client:
        response = client.post('/api/save', json=test_data)
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        
        # Verify the save method was called
        mock_processor.save_file_content.assert_called_once_with(
            'test.html',
            '<html>updated</html>'
        )


def test_404_error(app, client):
    """Test 404 error handling."""
    with app.test_client() as client:
        response = client.get('/nonexistent-route')
        assert response.status_code == 404
