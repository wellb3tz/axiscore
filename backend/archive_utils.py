import os
import subprocess
import tempfile
import uuid
import shutil
from pathlib import Path
import traceback

# Configuration flag - set to False to use Python implementations only
USE_COMMAND_LINE_TOOLS = False  # Disable command-line tools completely

# Import Python-based archive libraries as fallback
try:
    import rarfile
    import py7zr
    import zipfile
    import patoolib
    PYTHON_ARCHIVE_AVAILABLE = True
except ImportError:
    PYTHON_ARCHIVE_AVAILABLE = False
    print("Warning: Python archive libraries not available, falling back to command-line tools only")

def extract_archive(file_path):
    """
    Extract a RAR, ZIP, or 7z archive to a temporary directory and return the path.
    
    Args:
        file_path (str): Path to the archive file
        
    Returns:
        dict: {
            'success': bool,
            'extract_path': str or None,
            'error': str or None,
            'files': list of files found
        }
    """
    # Generate a unique directory for extraction
    extract_id = str(uuid.uuid4())
    extract_path = os.path.join(tempfile.gettempdir(), f"axiscore_extract_{extract_id}")
    
    # Create extraction directory
    os.makedirs(extract_path, exist_ok=True)
    
    # Get the file extension
    file_ext = Path(file_path).suffix.lower()
    
    # Initialize result
    result = {
        'success': False,
        'extract_path': extract_path,
        'error': None,
        'files': []
    }
    
    try:
        print(f"Starting extraction of {file_path}, file size: {os.path.getsize(file_path)} bytes")
        
        # Check if file exists and is readable
        if not os.path.exists(file_path):
            raise Exception(f"File does not exist: {file_path}")
        
        if not os.access(file_path, os.R_OK):
            raise Exception(f"File is not readable: {file_path}")
        
        # Try Python-based extraction first
        if PYTHON_ARCHIVE_AVAILABLE:
            print("Attempting Python-based extraction methods...")
            extraction_successful = try_python_extraction(file_path, extract_path, result, file_ext.lstrip('.'))
            if extraction_successful:
                print("Python-based extraction succeeded")
                return result
            else:
                print("All Python-based extraction methods failed")
        else:
            print("Python archive libraries not available")
                
        # Try command-line tools if enabled and Python extraction failed
        if USE_COMMAND_LINE_TOOLS:
            # Command-line extraction code...
            # (This code is not shown here since we disabled command-line tools)
            pass
        
        # If we get here, all extraction methods failed
        if not result['success']:
            raise Exception("All extraction methods failed")
        
    except Exception as e:
        # If anything fails, clean up and return error
        result['success'] = False
        result['error'] = str(e)
        print(f"Extraction failed with error: {str(e)}")
        print(traceback.format_exc())  # Print traceback for debugging
        try:
            # Clean up extraction directory on failure
            shutil.rmtree(extract_path)
            result['extract_path'] = None
        except Exception as cleanup_error:
            print(f"Error during cleanup: {cleanup_error}")
    
    return result

def try_python_extraction(file_path, extract_path, result, archive_type):
    """
    Try Python-based extraction methods.
    
    Args:
        file_path (str): Path to the archive file
        extract_path (str): Path to extract files to
        result (dict): Result dictionary to update
        archive_type (str): Type of archive ('rar', 'zip', or '7z')
        
    Returns:
        bool: True if extraction was successful
    """
    if not PYTHON_ARCHIVE_AVAILABLE:
        print("Python archive libraries not available")
        return False
        
    errors = []
    
    # Try patoolib first - it's a universal extractor
    try:
        print("Trying Python patoolib library")
        patoolib.extract_archive(file_path, outdir=extract_path, verbosity=2)  # Use verbosity=2 for more output
        result['success'] = True
        print(f"Extracted file using Python patoolib: {file_path}")
        file_list = list_files_recursive(extract_path)
        if file_list:
            result['files'] = file_list
            print(f"Found {len(file_list)} files using patoolib")
            return True
        else:
            print("Patoolib reported success but no files were found")
            errors.append("Patoolib: No files found after extraction")
    except Exception as e:
        error_msg = f"Python patoolib extraction failed: {str(e)}"
        print(error_msg)
        errors.append(error_msg)

    # Try type-specific extraction
    if archive_type == 'rar':
        try:
            print("Trying Python rarfile library")
            # Configure rarfile for better handling
            try:
                # Try to use internal implementation
                rarfile.UNRAR_TOOL = None
            except:
                pass
            rarfile.PATH_SEP = '/'
            # Attempt to open with more lenient error checking
            with rarfile.RarFile(file_path, errors='ignore') as rf:
                # First try to list the files to verify RAR is readable
                file_list = rf.namelist()
                print(f"RAR file contains {len(file_list)} files")
                
                # Then extract
                rf.extractall(path=extract_path)
            result['success'] = True
            print(f"Extracted RAR file using Python rarfile: {file_path}")
            
            file_list = list_files_recursive(extract_path)
            if file_list:
                result['files'] = file_list
                print(f"Found {len(file_list)} files using rarfile")
                return True
            else:
                print("Rarfile reported success but no files were found")
                errors.append("Rarfile: No files found after extraction")
        except Exception as e:
            error_msg = f"Python rarfile extraction failed: {str(e)}"
            print(error_msg)
            errors.append(error_msg)
    
    elif archive_type == 'zip':
        try:
            print("Trying Python zipfile library")
            with zipfile.ZipFile(file_path, 'r') as z:
                z.extractall(path=extract_path)
            result['success'] = True
            print(f"Extracted ZIP file using Python zipfile: {file_path}")
            
            file_list = list_files_recursive(extract_path)
            if file_list:
                result['files'] = file_list
                print(f"Found {len(file_list)} files using zipfile")
                return True
            else:
                print("Zipfile reported success but no files were found")
                errors.append("Zipfile: No files found after extraction")
        except Exception as e:
            error_msg = f"Python zipfile extraction failed: {str(e)}"
            print(error_msg)
            errors.append(error_msg)
    
    elif archive_type == '7z':
        try:
            print("Trying Python py7zr library")
            with py7zr.SevenZipFile(file_path, mode='r') as z:
                z.extractall(path=extract_path)
            result['success'] = True
            print(f"Extracted 7z file using Python py7zr: {file_path}")
            
            file_list = list_files_recursive(extract_path)
            if file_list:
                result['files'] = file_list
                print(f"Found {len(file_list)} files using py7zr")
                return True
            else:
                print("Py7zr reported success but no files were found")
                errors.append("Py7zr: No files found after extraction")
        except Exception as e:
            error_msg = f"Python py7zr extraction failed: {str(e)}"
            print(error_msg)
            errors.append(error_msg)
    
    if errors:
        error_summary = "\n".join(errors)
        print(f"All Python extraction methods failed with errors:\n{error_summary}")
    
    return False

def list_files_recursive(dir_path):
    """
    List all files in a directory recursively.
    
    Args:
        dir_path (str): Path to the directory
        
    Returns:
        list: List of dictionaries with file information
    """
    files = []
    
    try:
        for root, dirs, filenames in os.walk(dir_path):
            for filename in filenames:
                # Get the full path
                full_path = os.path.join(root, filename)
                
                # Get the relative path from the extraction directory
                rel_path = os.path.relpath(full_path, dir_path)
                
                # Handle non-UTF-8 filenames
                try:
                    # Try to encode/decode to validate
                    rel_path.encode('utf-8').decode('utf-8')
                except UnicodeEncodeError:
                    # If we can't encode, create a sanitized version
                    rel_path = f"renamed_file_{uuid.uuid4()}{os.path.splitext(filename)[1]}"
                    # Rename the actual file to match our sanitized name
                    new_full_path = os.path.join(os.path.dirname(full_path), rel_path)
                    try:
                        os.rename(full_path, new_full_path)
                        full_path = new_full_path
                    except:
                        # If renaming fails, just skip this file
                        continue
                
                files.append({
                    'path': rel_path,
                    'filename': os.path.basename(rel_path),
                    'extension': os.path.splitext(rel_path)[1].lower()
                })
    except Exception as e:
        print(f"Error listing files: {e}")
    
    return files

def find_3d_model_files(file_list):
    """
    Find 3D model files in a list of files.
    
    Args:
        file_list (list): List of file paths
        
    Returns:
        list: List of dictionaries with file info
    """
    model_extensions = ['.glb', '.gltf', '.fbx', '.obj']
    models = []
    
    for file_path in file_list:
        # Get file extension
        ext = Path(file_path).suffix.lower()
        
        if ext in model_extensions:
            models.append({
                'path': file_path,
                'extension': ext,
                'filename': os.path.basename(file_path)
            })
    
    return models

def cleanup_extraction(extract_path):
    """
    Clean up the extraction directory.
    
    Args:
        extract_path (str): Path to the extraction directory
    """
    if extract_path and os.path.exists(extract_path):
        try:
            shutil.rmtree(extract_path)
            return True
        except Exception as e:
            print(f"Failed to clean up extraction directory: {e}")
            return False
    return False 