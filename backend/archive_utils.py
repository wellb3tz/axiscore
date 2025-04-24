import os
import subprocess
import tempfile
import uuid
import shutil
from pathlib import Path

# Configuration flag - set to False to use Python implementations only
USE_COMMAND_LINE_TOOLS = True

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
        # Try different extraction commands based on file extension
        if file_ext in ['.rar']:
            # Try Python-based extraction first if command line tools are disabled
            if not USE_COMMAND_LINE_TOOLS and PYTHON_ARCHIVE_AVAILABLE:
                extraction_successful = try_python_extraction(file_path, extract_path, result, 'rar')
                if extraction_successful:
                    return result
                    
            # Try with 7z first as it's often more robust with RAR files
            if USE_COMMAND_LINE_TOOLS:
                try:
                    print(f"Trying 7z for RAR extraction: {file_path}")
                    process = subprocess.run(
                        ['7z', 'x', file_path, f'-o{extract_path}'],
                        capture_output=True,
                        check=True
                    )
                    result['success'] = True
                    print(f"Extracted RAR file using 7z: {file_path}")
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    print(f"7z extraction for RAR failed: {str(e)}")
                    
                    # Try with unrar-free next
                    try:
                        process = subprocess.run(
                            ['unrar-free', 'x', file_path, extract_path],
                            capture_output=True,
                            check=True
                        )
                        result['success'] = True
                        print(f"Extracted RAR file using unrar-free: {file_path}")
                    except (subprocess.CalledProcessError, FileNotFoundError) as e:
                        print(f"unrar-free extraction failed: {str(e)}")
                        
                        # Fallback to standard unrar if available
                        try:
                            # Try unrar with proper error handling
                            print(f"Trying unrar for extraction: {file_path}")
                            # Add timeout and safer handling
                            process = subprocess.run(
                                ['unrar', 'x', '-y', file_path, extract_path],
                                capture_output=True,
                                check=False,  # Don't raise exception, handle errors manually
                                timeout=300   # 5 minute timeout
                            )
                            # Check return code manually
                            if process.returncode == 0:
                                result['success'] = True
                                print(f"Extracted RAR file using unrar: {file_path}")
                            else:
                                error_output = process.stderr.decode('utf-8', errors='ignore') if process.stderr else "Unknown error"
                                print(f"unrar extraction failed with code {process.returncode}: {error_output}")
                                raise Exception(f"unrar command failed: {error_output}")
                        except (subprocess.SubprocessError, FileNotFoundError, Exception) as e:
                            print(f"unrar extraction failed: {str(e)}")
                            
                            # Try Python-based extraction as fallback
                            if PYTHON_ARCHIVE_AVAILABLE:
                                extraction_successful = try_python_extraction(file_path, extract_path, result, 'rar')
                                if not extraction_successful:
                                    raise Exception("All RAR extraction methods failed")
                            else:
                                raise Exception("Failed to extract RAR file, both command-line and Python methods unavailable")
            else:
                # If command line tools are disabled, but we've reached here, it means the Python extraction failed
                raise Exception("Python-based RAR extraction failed and command-line tools are disabled")
                
        elif file_ext in ['.zip']:
            # Try Python-based extraction first if command line tools are disabled
            if not USE_COMMAND_LINE_TOOLS and PYTHON_ARCHIVE_AVAILABLE:
                extraction_successful = try_python_extraction(file_path, extract_path, result, 'zip')
                if extraction_successful:
                    return result
                    
            # Try with unzip first
            if USE_COMMAND_LINE_TOOLS:
                try:
                    process = subprocess.run(
                        ['unzip', file_path, '-d', extract_path],
                        capture_output=True,
                        check=True
                    )
                    result['success'] = True
                    print(f"Extracted ZIP file using unzip: {file_path}")
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    print(f"unzip extraction failed: {str(e)}")
                    
                    # Try with 7z
                    try:
                        process = subprocess.run(
                            ['7z', 'x', file_path, f'-o{extract_path}'],
                            capture_output=True,
                            check=True
                        )
                        result['success'] = True
                        print(f"Extracted ZIP file using 7z: {file_path}")
                    except (subprocess.CalledProcessError, FileNotFoundError) as e:
                        print(f"7z extraction for ZIP failed: {str(e)}")
                    
                        # Fallback to Python-based extraction for ZIP
                        if PYTHON_ARCHIVE_AVAILABLE:
                            extraction_successful = try_python_extraction(file_path, extract_path, result, 'zip')
                            if not extraction_successful:
                                raise Exception("All ZIP extraction methods failed")
                        else:
                            raise Exception("Failed to extract ZIP file, both command-line and Python methods unavailable")
            else:
                # If command line tools are disabled, but we've reached here, it means the Python extraction failed
                raise Exception("Python-based ZIP extraction failed and command-line tools are disabled")
        
        elif file_ext in ['.7z']:
            # Try Python-based extraction first if command line tools are disabled
            if not USE_COMMAND_LINE_TOOLS and PYTHON_ARCHIVE_AVAILABLE:
                extraction_successful = try_python_extraction(file_path, extract_path, result, '7z')
                if extraction_successful:
                    return result
                    
            # Try with 7z
            if USE_COMMAND_LINE_TOOLS:
                try:
                    process = subprocess.run(
                        ['7z', 'x', file_path, f'-o{extract_path}'],
                        capture_output=True,
                        check=True
                    )
                    result['success'] = True
                    print(f"Extracted 7z file using 7z command: {file_path}")
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    print(f"7z extraction failed: {str(e)}")
                    
                    # Fallback to Python-based extraction for 7z
                    if PYTHON_ARCHIVE_AVAILABLE:
                        extraction_successful = try_python_extraction(file_path, extract_path, result, '7z')
                        if not extraction_successful:
                            raise Exception("All 7z extraction methods failed")
                    else:
                        raise Exception("Failed to extract 7z file, both command-line and Python methods unavailable")
            else:
                # If command line tools are disabled, but we've reached here, it means the Python extraction failed
                raise Exception("Python-based 7z extraction failed and command-line tools are disabled")
                
        # Fallback to 7z for any format if still not successful
        if not result['success'] and USE_COMMAND_LINE_TOOLS:
            try:
                process = subprocess.run(
                    ['7z', 'x', file_path, f'-o{extract_path}'],
                    capture_output=True,
                    check=True
                )
                result['success'] = True
                print(f"Extracted archive using 7z fallback: {file_path}")
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                print(f"7z fallback extraction failed: {str(e)}")
                
                # Last resort - try patool if available
                if PYTHON_ARCHIVE_AVAILABLE:
                    try:
                        patoolib.extract_archive(file_path, outdir=extract_path)
                        result['success'] = True
                        print(f"Extracted archive using patool fallback: {file_path}")
                    except Exception as e:
                        print(f"patool fallback extraction failed: {str(e)}")
                        raise Exception(f"All extraction methods failed: {str(e)}")
                else:
                    raise Exception("All extraction methods failed, and Python fallbacks not available")
        
        # If extraction succeeded but no files were found, it may be a false positive
        if result['success']:
            file_list = list_files_recursive(extract_path)
            if not file_list:
                print("Warning: Extraction reported success but no files were found")
                result['success'] = False
                result['error'] = "Extraction appeared to succeed but no files were found"
            else:
                result['files'] = file_list
                print(f"Successfully extracted {len(file_list)} files")
            
    except Exception as e:
        # If anything fails, clean up and return error
        result['success'] = False
        result['error'] = str(e)
        try:
            # Clean up extraction directory on failure
            shutil.rmtree(extract_path)
            result['extract_path'] = None
        except:
            pass
    
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
        return False
        
    try:
        if archive_type == 'rar':
            print("Trying Python rarfile library")
            # Configure rarfile for better handling
            rarfile.UNRAR_TOOL = None  # Use internal implementation if possible
            rarfile.PATH_SEP = '/'
            # Attempt to open with more lenient error checking
            with rarfile.RarFile(file_path, errors='ignore') as rf:
                rf.extractall(path=extract_path)
            result['success'] = True
            print(f"Extracted RAR file using Python rarfile: {file_path}")
            return True
        elif archive_type == 'zip':
            print("Trying Python zipfile library")
            with zipfile.ZipFile(file_path, 'r') as z:
                z.extractall(path=extract_path)
            result['success'] = True
            print(f"Extracted ZIP file using Python zipfile: {file_path}")
            return True
        elif archive_type == '7z':
            print("Trying Python py7zr library")
            with py7zr.SevenZipFile(file_path, mode='r') as z:
                z.extractall(path=extract_path)
            result['success'] = True
            print(f"Extracted 7z file using Python py7zr: {file_path}")
            return True
            
        # If we get here, try patoolib as last resort
        print("Trying Python patoolib library")
        patoolib.extract_archive(file_path, outdir=extract_path, verbosity=-1)
        result['success'] = True
        print(f"Extracted file using Python patoolib: {file_path}")
        return True
        
    except Exception as e:
        print(f"Python extraction failed: {str(e)}")
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