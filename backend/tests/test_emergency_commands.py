import unittest
import sys
import os
import json
from unittest.mock import patch, MagicMock

# Add parent directory to path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the Flask app
import app

class TestEmergencyCommands(unittest.TestCase):

    def setUp(self):
        """Set up test client and other test variables"""
        self.app = app.app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Reset global state variables
        app.PROCESSING_FILES = set()
        app.PROCESSING_TIMES = {}
        app.IGNORE_ALL_ARCHIVES = False
        app.LAST_RESET_TIME = 0
    
    @patch('app.send_message')
    @patch('app.db')
    def test_911_command(self, mock_db, mock_send_message):
        """Test that the /911 command correctly sets the emergency flag"""
        # Configure mocks
        mock_db.ensure_connection.return_value = True
        mock_db.execute.return_value = None
        mock_db.commit.return_value = None
        
        # Add a file to processing
        app.PROCESSING_FILES.add('test_file_id')
        app.PROCESSING_TIMES['test_file_id'] = 12345
        
        # Create a test request payload
        payload = {
            'message': {
                'text': '/911',
                'chat': {
                    'id': 12345
                }
            }
        }
        
        # Call the webhook endpoint
        response = self.client.post('/webhook', json=payload)
        response_data = json.loads(response.data)
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data['status'], 'ok')
        self.assertEqual(response_data['message'], 'Emergency stop executed')
        
        # Verify the IGNORE_ALL_ARCHIVES flag was set to True
        self.assertTrue(app.IGNORE_ALL_ARCHIVES)
        
        # Verify the processing files was cleared
        self.assertEqual(len(app.PROCESSING_FILES), 0)
        
        # Verify send_message was called
        mock_send_message.assert_called_once()
    
    @patch('app.send_message')
    def test_disable_command(self, mock_send_message):
        """Test the /disable command sets the emergency flag"""
        # Create a test request payload
        payload = {
            'message': {
                'text': '/disable',
                'chat': {
                    'id': 12345
                }
            }
        }
        
        # Call the webhook endpoint
        response = self.client.post('/webhook', json=payload)
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        
        # Verify the IGNORE_ALL_ARCHIVES flag was set to True
        self.assertTrue(app.IGNORE_ALL_ARCHIVES)
        
        # Verify send_message was called with correct message
        mock_send_message.assert_called_once()
        call_args = mock_send_message.call_args[0]
        self.assertEqual(call_args[0], 12345)
        self.assertEqual(call_args[1], "Processing has been disabled (circuit breaker active).")
    
    @patch('app.send_message')
    def test_enable_command(self, mock_send_message):
        """Test the /enable command clears the emergency flag"""
        # Set the emergency flag first
        app.IGNORE_ALL_ARCHIVES = True
        
        # Create a test request payload
        payload = {
            'message': {
                'text': '/enable',
                'chat': {
                    'id': 12345
                }
            }
        }
        
        # Call the webhook endpoint
        response = self.client.post('/webhook', json=payload)
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        
        # Verify the IGNORE_ALL_ARCHIVES flag was cleared
        self.assertFalse(app.IGNORE_ALL_ARCHIVES)
        
        # Verify send_message was called with correct message
        mock_send_message.assert_called_once()
        call_args = mock_send_message.call_args[0]
        self.assertEqual(call_args[0], 12345)
        self.assertEqual(call_args[1], "Processing has been re-enabled.")
    
    @patch('app.send_message')
    def test_emergency_flag_blocks_uploads(self, mock_send_message):
        """Test that when emergency flag is set, file uploads are blocked"""
        # Set the emergency flag
        app.IGNORE_ALL_ARCHIVES = True
        
        # Create a test request payload with a document
        payload = {
            'message': {
                'chat': {
                    'id': 12345
                },
                'document': {
                    'file_id': 'test_file_id',
                    'file_name': 'test.zip'
                }
            }
        }
        
        # Call the webhook endpoint
        response = self.client.post('/webhook', json=payload)
        response_data = json.loads(response.data)
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data['status'], 'stopped')
        
        # Verify send_message was called with the correct notification
        mock_send_message.assert_called_once()
        call_args = mock_send_message.call_args[0]
        self.assertEqual(call_args[0], 12345)
        self.assertIn("Processing is currently disabled", call_args[1])


if __name__ == '__main__':
    unittest.main() 