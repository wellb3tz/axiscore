import unittest
import sys
import os
import json
from unittest.mock import patch, MagicMock

# Add parent directory to path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_utils import (
    check_telegram_auth,
    send_message,
    download_telegram_file
)

class TestTelegramUtils(unittest.TestCase):
    
    def test_check_telegram_auth_valid(self):
        """Test valid Telegram authentication data"""
        # This is a simplified test - real implementation would use actual HMAC
        with patch('telegram_utils.hmac.new') as mock_hmac:
            mock_hash = MagicMock()
            mock_hash.hexdigest.return_value = "valid_hash"
            mock_hmac.return_value = mock_hash
            
            auth_data = {
                'id': '12345',
                'first_name': 'Test User',
                'hash': 'valid_hash'  # This should match what our mocked hmac returns
            }
            
            result = check_telegram_auth(auth_data.copy(), "test_secret")
            self.assertTrue(result)
    
    def test_check_telegram_auth_invalid(self):
        """Test invalid Telegram authentication data"""
        with patch('telegram_utils.hmac.new') as mock_hmac:
            mock_hash = MagicMock()
            mock_hash.hexdigest.return_value = "valid_hash"
            mock_hmac.return_value = mock_hash
            
            auth_data = {
                'id': '12345',
                'first_name': 'Test User',
                'hash': 'invalid_hash'  # This won't match our mocked hmac
            }
            
            result = check_telegram_auth(auth_data.copy(), "test_secret")
            self.assertFalse(result)
    
    @patch('telegram_utils.requests.post')
    def test_send_message(self, mock_post):
        """Test sending a message via Telegram API"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response
        
        # Call the function
        result = send_message('123456', 'Test message', 'test_bot_token')
        
        # Verify the correct API was called
        mock_post.assert_called_once()
        call_args = mock_post.call_args[0][0]
        self.assertEqual(call_args, 'https://api.telegram.org/bottest_bot_token/sendMessage')
        
        # Verify correct payload was sent
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['chat_id'], '123456')
        self.assertEqual(payload['text'], 'Test message')
    
    @patch('telegram_utils.requests.get')
    def test_download_telegram_file(self, mock_get):
        """Test downloading a file from Telegram"""
        # Setup first mock response for getFile
        file_info_response = MagicMock()
        file_info_response.json.return_value = {
            "ok": True,
            "result": {
                "file_id": "test_file_id",
                "file_path": "documents/test_file.zip",
                "file_size": 1024
            }
        }
        
        # Setup second mock response for the download
        file_download_response = MagicMock()
        file_download_response.status_code = 200
        file_download_response.content = b'test file content'
        
        # Configure the mock to return different responses for different URLs
        def get_side_effect(url, *args, **kwargs):
            if 'getFile' in url:
                return file_info_response
            else:
                return file_download_response
            
        mock_get.side_effect = get_side_effect
        
        # Test with emergency flag set to False
        result = download_telegram_file('test_file_id', 'test_bot_token', False)
        
        # Verify we got the correct result
        self.assertIsNotNone(result)
        self.assertEqual(result['filename'], 'test_file_id_test_file.zip')
        self.assertEqual(result['size'], len(b'test file content'))
        
        # Test with emergency flag set to True
        result = download_telegram_file('test_file_id', 'test_bot_token', True)
        
        # Should return None because emergency flag is active
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main() 