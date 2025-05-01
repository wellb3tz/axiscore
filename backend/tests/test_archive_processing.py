import unittest
import sys
import os
import json
import base64
from unittest.mock import patch, MagicMock, mock_open

# Add parent directory to path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the Flask app
import app
from archive_utils import extract_archive, find_3d_model_files

class TestArchiveProcessing(unittest.TestCase):
    
    def setUp(self):
        """Set up test client and other test variables"""
        self.app = app.app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Reset global state variables
        app.PROCESSING_FILES = set()
        app.PROCESSING_TIMES = {}
        app.IGNORE_ALL_ARCHIVES = False
    
    @patch('app.download_telegram_file')
    @patch('app.send_message')
    @patch('app.db')
    @patch('app.extract_archive')
    @patch('app.find_3d_model_files')
    @patch('app.open', new_callable=mock_open, read_data=b'model_file_content')
    @patch('app.os.remove')  # Mock os.remove to avoid file not found errors
    @patch('app.cleanup_extraction')  # Mock cleanup function
    def test_successful_archive_processing(self, mock_cleanup, 
                                           mock_remove, mock_open_file, mock_find_models, 
                                           mock_extract, mock_db, mock_send_message, mock_download):
        """Test successful archive processing workflow"""
        # Configure mocks
        mock_db.ensure_connection.return_value = True
        mock_db.execute.return_value = None
        mock_db.commit.return_value = None
        mock_db.save_model.return_value = '/models/123/model.glb'
        
        # Create a valid base64 string for testing
        valid_base64 = base64.b64encode(b'test archive content').decode('utf-8')
        
        # Mock the download to return a file with proper base64 content
        mock_download.return_value = {
            'filename': 'test_archive.zip',
            'content': valid_base64,
            'size': 1024
        }
        
        # Mock extract archive to indicate success
        extract_path = '/temp/extract_path'
        mock_extract.return_value = {
            'success': True, 
            'extract_path': extract_path,
            'files': ['file1.txt', 'model.glb', 'model.obj']
        }
        
        # Mock finding 3D models
        mock_find_models.return_value = [
            {'filename': 'model.glb', 'path': 'model.glb', 'extension': '.glb'}
        ]
        
        # Create a test request payload with an archive document
        payload = {
            'message': {
                'chat': {
                    'id': 12345
                },
                'document': {
                    'file_id': 'test_archive_id',
                    'file_name': 'test_archive.zip',
                    'mime_type': 'application/zip'
                }
            }
        }
        
        # Call the webhook endpoint
        response = self.client.post('/webhook', json=payload)
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        
        # Verify download_telegram_file was called with correct args
        mock_download.assert_called_once_with('test_archive_id', app.TELEGRAM_BOT_TOKEN, False)
        
        # Verify extract_archive was called
        mock_extract.assert_called_once()
        
        # Verify find_3d_model_files was called
        mock_find_models.assert_called_once()
        
        # Verify send_message was called at least once
        mock_send_message.assert_called()
    
    @patch('app.download_telegram_file')
    @patch('app.send_message')
    @patch('app.db')
    def test_no_3d_models_found(self, mock_db, mock_send_message, mock_download):
        """Test handling of archives with no 3D models"""
        # Configure mocks
        mock_db.ensure_connection.return_value = True
        mock_db.execute.return_value = None
        
        # Mock the download to return None (download failure)
        mock_download.return_value = None
        
        # Create a test request payload with an archive document
        payload = {
            'message': {
                'chat': {
                    'id': 12345
                },
                'document': {
                    'file_id': 'test_archive_id',
                    'file_name': 'test_archive.zip', 
                    'mime_type': 'application/zip'
                }
            }
        }
        
        # Call the webhook endpoint
        response = self.client.post('/webhook', json=payload)
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        
        # Verify download_telegram_file was called
        mock_download.assert_called_once()
        
        # Verify send_message was called with error message
        mock_send_message.assert_called()
        
        # Verify we recorded the failure in database
        mock_db.execute.assert_called()
    
    @patch('app.send_message')
    @patch('app.db')
    def test_already_processing_file(self, mock_db, mock_send_message):
        """Test handling of duplicate file processing attempts"""
        # Configure the mock to return data for failed archives
        mock_db.execute.return_value = MagicMock()
        mock_db.execute.return_value.__getitem__.return_value = "Previous error"
        
        # Add a file to processing set
        file_id = 'already_processing_id'
        app.PROCESSING_FILES.add(file_id)
        app.PROCESSING_TIMES[file_id] = 12345
        
        # Create a test request payload with same file_id
        payload = {
            'message': {
                'chat': {
                    'id': 12345
                },
                'document': {
                    'file_id': file_id,
                    'file_name': 'test_archive.zip',
                    'mime_type': 'application/zip'
                }
            }
        }
        
        # Call the webhook endpoint
        response = self.client.post('/webhook', json=payload)
        
        # Verify the response is 200
        self.assertEqual(response.status_code, 200)
        
        # Check response JSON
        response_data = json.loads(response.data)
        self.assertEqual(response_data['status'], 'error')
        self.assertEqual(response_data['msg'], 'Archive previously failed')


if __name__ == '__main__':
    unittest.main() 