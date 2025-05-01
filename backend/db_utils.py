import os
import psycopg2
import re
import socket
from datetime import datetime
import traceback
from flask import jsonify

class DatabaseManager:
    """
    Database connection and utility manager for the application.
    Handles initialization, connection maintenance, and basic operations.
    """
    
    def __init__(self, database_url=None):
        """
        Initialize the database manager.
        
        Args:
            database_url: The database connection URL
        """
        self.conn = None
        self.cursor = None
        self.database_url = database_url or os.getenv('DATABASE_URL')
        self.resolve_ip_from_hostname()
        self.initialized = self.initialize_db()
    
    def resolve_ip_from_hostname(self):
        """
        Extract host from DATABASE_URL and resolve to IPv4 address.
        This helps avoid DNS resolution issues in some environments.
        """
        if self.database_url:
            host_match = re.search(r'@([^:]+):', self.database_url)
            if host_match:
                hostname = host_match.group(1)
                try:
                    # Get the IPv4 address
                    host_ip = socket.gethostbyname(hostname)
                    # Replace the hostname with the IP address
                    self.database_url = self.database_url.replace('@' + hostname + ':', '@' + host_ip + ':')
                    print(f"Resolved hostname {hostname} to IP {host_ip}")
                except socket.gaierror:
                    print(f"Could not resolve hostname {hostname}")
    
    def initialize_db(self):
        """
        Initialize database connection and create required tables.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.conn = psycopg2.connect(self.database_url, sslmode='require')
            self.cursor = self.conn.cursor()

            # Create models table if it doesn't exist
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS models (
                    id SERIAL PRIMARY KEY,
                    telegram_id TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    model_url TEXT NOT NULL,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create users table if it doesn't exist
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    telegram_id TEXT NOT NULL UNIQUE,
                    username TEXT,
                    password TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create model_content table if it doesn't exist
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS model_content (
                    model_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create failed_archives table to track failed archive processing
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS failed_archives (
                    id SERIAL PRIMARY KEY,
                    file_id TEXT NOT NULL UNIQUE,
                    filename TEXT NOT NULL,
                    error TEXT NOT NULL,
                    telegram_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            self.conn.commit()
            print("Successfully connected to database and initialized tables")
            return True
        except psycopg2.OperationalError as e:
            print(f"Error connecting to database: {e}")
            # If in development, raise the error; in production, continue with limited functionality
            if os.getenv('FLASK_ENV') == 'development':
                raise
            else:
                self.conn = None
                self.cursor = None
                print("Running with limited functionality - database features will be unavailable")
                return False
    
    def ensure_connection(self):
        """
        Ensure database connection is active, reconnect if needed.
        
        Returns:
            bool: True if connection is established, False otherwise
        """
        try:
            # Check if connection is closed or cursor is None
            if self.conn is None or self.cursor is None or self.conn.closed:
                print("Database connection lost, reconnecting...")
                # Reconnect to database
                self.conn = psycopg2.connect(self.database_url, sslmode='require')
                self.cursor = self.conn.cursor()
                print("Successfully reconnected to database")
            
            # Test connection with a simple query
            self.cursor.execute("SELECT 1")
            self.cursor.fetchone()
            return True
        except Exception as e:
            print(f"Failed to ensure database connection: {e}")
            try:
                # If connection exists but is broken, close it to avoid leaks
                if self.conn and not self.conn.closed:
                    self.conn.close()
            except:
                pass
            
            try:
                # Attempt to reconnect one more time
                self.conn = psycopg2.connect(self.database_url, sslmode='require')
                self.cursor = self.conn.cursor()
                print("Successfully reconnected to database after error")
                return True
            except Exception as reconnect_error:
                print(f"Failed to reconnect to database: {reconnect_error}")
                self.conn = None
                self.cursor = None
                return False
    
    def execute(self, query, params=None, fetch=None):
        """
        Execute a database query with error handling and connection checking.
        
        Args:
            query: SQL query to execute
            params: Parameters for the query
            fetch: 'one', 'all', or None to determine what to return
            
        Returns:
            Query results or None if failed
        """
        if not self.ensure_connection():
            print("Database connection unavailable")
            return None
            
        try:
            self.cursor.execute(query, params or ())
            
            if fetch == 'one':
                return self.cursor.fetchone()
            elif fetch == 'all':
                return self.cursor.fetchall()
            return True
        except Exception as e:
            print(f"Database query error: {e}")
            return None
    
    def commit(self):
        """Commit current transaction"""
        if self.conn:
            self.conn.commit()
    
    def rollback(self):
        """Rollback current transaction"""
        if self.conn:
            self.conn.rollback()
    
    def begin_transaction(self):
        """Begin a new transaction"""
        return self.execute("BEGIN")
    
    def check_table_exists(self, table_name):
        """Check if a table exists in the database"""
        return self.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = %s
            )
            """,
            (table_name,),
            fetch='one'
        )
        
    def check_column_exists(self, table_name, column_name):
        """Check if a column exists in a table"""
        return self.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = %s AND column_name = %s
            )
            """,
            (table_name, column_name),
            fetch='one'
        )
    
    def save_model(self, file_data, base_url):
        """
        Save a 3D model to storage and return a unique URL.
        For large models (>1MB), only store the model ID and not the content.
        
        Args:
            file_data: Dictionary containing model data
            base_url: Base URL for generating model access URLs
            
        Returns:
            str: Path to the saved model or None if failed
        """
        try:
            # Check if valid base64 content
            if not file_data.get('content'):
                print("❌ Missing content in file data")
                return None
                
            # Ensure database connection
            if not self.ensure_connection():
                print("❌ Database connection unavailable, cannot save model")
                return None
                
            # Generate a unique ID for the model
            import uuid
            model_id = str(uuid.uuid4())
            
            # Get the original filename and preserve its extension
            original_filename = file_data.get('filename', file_data.get('name', ''))
            
            # If no filename provided or invalid, determine extension from mime_type or use default
            if not original_filename or '.' not in original_filename:
                # Try to get extension from mime type
                mime_type = file_data.get('mime_type', '').lower()
                if 'fbx' in mime_type:
                    filename = f"model.fbx"
                else:
                    # Default to GLB if no better information
                    filename = f"model.glb"
            else:
                # Use the original filename
                filename = original_filename
                
            print(f"📌 Saving model with ID: {model_id}, filename: {filename}")
            
            # Extract file extension for later use
            file_extension = os.path.splitext(filename)[1].lower()
            
            # Check size of content
            content_size = file_data.get('size', len(file_data['content']))
            print(f"📊 Content size: {content_size} bytes, File type: {file_extension}")
            
            # Begin a transaction
            self.begin_transaction()
            
            # First, check if the model_content table exists
            if not self.check_table_exists('model_content')[0]:
                # Create model_content table if it doesn't exist
                print("📋 Creating model_content table")
                self.cursor.execute('''
                    CREATE TABLE model_content (
                        model_id TEXT PRIMARY KEY,
                        content TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            
            # Check if content_size column exists in models table
            if not self.check_column_exists('models', 'content_size')[0]:
                # Add content_size column if it doesn't exist
                print("📋 Adding content_size column to models table")
                self.execute("ALTER TABLE models ADD COLUMN content_size BIGINT")
                
            # Extract proper telegram_id with fallback to avoid 'unknown'
            telegram_id = file_data.get('telegram_id')
            if not telegram_id or telegram_id == 'unknown':
                telegram_id = '591646476'  # Use a default ID if unknown
                
            # Generate consistent URL for the model that will be accessible
            model_path = f"/models/{model_id}/{filename}"
            model_url = f"{base_url}{model_path}"
            
            print(f"🔗 Generated URL: {model_url}")
            
            # Always store content in model_content table
            try:
                self.execute(
                    "INSERT INTO model_content (model_id, content) VALUES (%s, %s)",
                    (model_id, file_data['content'])
                )
                print(f"✅ Content stored in model_content table with ID: {model_id}")
            except Exception as e:
                print(f"❌ Error storing in model_content: {e}")
                # Try legacy table name as fallback for compatibility
                try:
                    self.execute(
                        "INSERT INTO large_model_content (model_id, content) VALUES (%s, %s)",
                        (model_id, file_data['content'])
                    )
                    print(f"✅ Content stored in legacy large_model_content table with ID: {model_id}")
                except Exception as e2:
                    print(f"❌ Error storing in legacy table: {e2}")
                    raise e  # Re-raise the original error if both attempts fail
            
            # Store only metadata in the models table (no content)
            try:
                self.execute(
                    "INSERT INTO models (telegram_id, model_name, model_url, content_size, created_at) VALUES (%s, %s, %s, %s, %s)",
                    (telegram_id, filename, model_url, content_size, datetime.now())
                )
                print(f"✅ Model metadata stored in models table")
            except psycopg2.Error as e:
                # Check if error is due to missing column
                if "column" in str(e) and "does not exist" in str(e):
                    print(f"⚠️ Column error: {e}, trying with available columns")
                    # Try with just the essential columns
                    self.execute(
                        "INSERT INTO models (telegram_id, model_name, model_url) VALUES (%s, %s, %s)",
                        (telegram_id, filename, model_url)
                    )
                else:
                    raise
            
            # Commit the transaction
            self.commit()
            print(f"✅ Successfully saved model {model_id} to database")
            
            # For debugging, try to verify the content was stored
            try:
                result = self.execute(
                    "SELECT model_id FROM model_content WHERE model_id = %s",
                    (model_id,),
                    fetch='one'
                )
                if result:
                    print(f"✅ Verified: Content exists in model_content table")
                else:
                    print(f"⚠️ Warning: Content not found in model_content table")
            except Exception as verify_err:
                print(f"⚠️ Error verifying content: {verify_err}")
            
            # Return the path portion for the model
            return model_path
            
        except Exception as e:
            # Rollback in case of error
            self.rollback()
            print(f"❌ Error saving model to storage: {e}")
            print(traceback.format_exc())
            return None

    def get_user(self, telegram_id):
        """
        Get user information from the database.
        
        Args:
            telegram_id: The Telegram ID of the user
            
        Returns:
            User data or None if not found
        """
        return self.execute(
            "SELECT * FROM users WHERE telegram_id = %s",
            (telegram_id,),
            fetch='one'
        )

    def create_user(self, telegram_id, username, password=''):
        """
        Create a new user in the database.
        
        Args:
            telegram_id: The Telegram ID of the user
            username: The username
            password: Optional password
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.execute(
                "INSERT INTO users (telegram_id, username, password) VALUES (%s, %s, %s)",
                (telegram_id, username, password)
            )
            self.commit()
            return True
        except Exception as e:
            print(f"Error creating user: {e}")
            self.rollback()
            return False
    
    def get_models_for_user(self, telegram_id):
        """
        Get all models for a specific user.
        
        Args:
            telegram_id: The Telegram ID of the user
            
        Returns:
            List of models or empty list if none found
        """
        result = self.execute(
            "SELECT id, model_name, model_url, created_at FROM models WHERE telegram_id = %s",
            (telegram_id,),
            fetch='all'
        )
        
        if not result:
            return []
            
        model_list = []
        for model in result:
            model_list.append({
                "id": model[0],
                "name": model[1],
                "url": model[2],
                "created_at": model[3].isoformat() if model[3] else None
            })
            
        return model_list
    
    def add_model_for_user(self, telegram_id, model_name, model_url):
        """
        Add a model reference for a user.
        
        Args:
            telegram_id: The Telegram ID of the user
            model_name: The name of the model
            model_url: The URL to the model
            
        Returns:
            Model ID or None if failed
        """
        try:
            result = self.execute(
                "INSERT INTO models (telegram_id, model_name, model_url) VALUES (%s, %s, %s) RETURNING id",
                (telegram_id, model_name, model_url),
                fetch='one'
            )
            self.commit()
            
            if result:
                return result[0]
            return None
        except Exception as e:
            print(f"Error adding model for user: {e}")
            self.rollback()
            return None

# Create a function to get a transaction decorator
def create_transaction_decorator(db_manager):
    """
    Create a transaction decorator using the database manager.
    
    Args:
        db_manager: The DatabaseManager instance
        
    Returns:
        A decorator function for database transactions
    """
    def decorator(func):
        """
        Decorator for database transactions that handles connection errors,
        commits on success, and rolls back on exception
        """
        def wrapper(*args, **kwargs):
            if not db_manager.ensure_connection():
                return jsonify({"error": "Database unavailable", "status": "error"}), 503
            
            try:
                # Reset any previous transaction state
                db_manager.rollback()
                
                # Execute the function
                result = func(*args, **kwargs)
                
                # Commit if no exception occurred
                db_manager.commit()
                return result
            except psycopg2.Error as db_error:
                # Rollback on database errors
                db_manager.rollback()
                
                # Return standardized error response
                return jsonify({
                    "error": str(db_error), 
                    "status": "error",
                    "type": "DatabaseError"
                }), 500
            except Exception as e:
                # Rollback on any other exception
                db_manager.rollback()
                
                # Return standardized error response
                return jsonify({
                    "error": str(e), 
                    "status": "error",
                    "type": "ServerError"
                }), 500
        
        # Preserve the function's metadata
        wrapper.__name__ = func.__name__
        return wrapper
    
    return decorator 