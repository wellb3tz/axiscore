import os
import traceback
from flask import jsonify, request
import psycopg2

def log_error(error, context=""):
    """Standardized error logging function"""
    error_type = type(error).__name__
    error_msg = str(error)
    error_trace = traceback.format_exc()
    
    # Always log to console
    print(f"❌ ERROR [{error_type}] {context}: {error_msg}")
    if error_trace:
        print(f"Stack trace:\n{error_trace}")
    
    return {
        "type": error_type,
        "message": error_msg,
        "trace": error_trace,
        "context": context
    }

def api_error(error, status_code=500, context=""):
    """Standardized API error response generator"""
    error_details = log_error(error, context)
    
    # Only include stack trace in development environment
    if os.getenv('FLASK_ENV') != 'development':
        error_details.pop('trace', None)
    
    return jsonify({
        "error": error_details['type'],
        "message": error_details['message'],
        "context": context,
        "status": "error",
        "path": request.path,
        "method": request.method
    }), status_code

def db_transaction(conn, cursor, ensure_db_connection):
    """
    Factory function that creates a database transaction decorator.
    
    Args:
        conn: The database connection object
        cursor: The database cursor object
        ensure_db_connection: Function to ensure DB connection is established
        
    Returns:
        A decorator function for database transactions
    """
    def decorator(func):
        """
        Decorator for database transactions that handles connection errors,
        commits on success, and rolls back on exception
        """
        def wrapper(*args, **kwargs):
            if not ensure_db_connection():
                return jsonify({"error": "Database unavailable", "status": "error"}), 503
            
            try:
                # Reset any previous transaction state
                conn.rollback()
                
                # Execute the function
                result = func(*args, **kwargs)
                
                # Commit if no exception occurred
                conn.commit()
                return result
            except psycopg2.Error as db_error:
                # Rollback on database errors
                try:
                    conn.rollback()
                except:
                    pass
                
                # Log and return standardized error response
                return api_error(db_error, 500, f"Database error in {func.__name__}")
            except Exception as e:
                # Rollback on any other exception
                try:
                    conn.rollback()
                except:
                    pass
                
                # Log and return standardized error response
                return api_error(e, 500, f"Error in {func.__name__}")
        
        # Preserve the function's metadata
        wrapper.__name__ = func.__name__
        return wrapper
    
    return decorator 