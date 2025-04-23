import os
import subprocess
import tempfile
import uuid
import shutil
from pathlib import Path

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
            # Try with unrar-free first
            try:
                process = subprocess.run(
                    ['unrar-free', 'x', file_path, extract_path],
                    capture_output=True,
                    text=True,
                    check=True
                )
                result['success'] = True
                print(f"Extracted RAR file using unrar-free: {file_path}")
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                print(f"unrar-free extraction failed: {str(e)}")
                
                # Fallback to standard unrar if available
                try:
                    process = subprocess.run(
                        ['unrar', 'x', file_path, extract_path],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    result['success'] = True
                    print(f"Extracted RAR file using unrar: {file_path}")
                except (subprocess.CalledProcessError, FileNotFoundError) as e:
                    print(f"unrar extraction also failed: {str(e)}")
                    
                    # Fallback to Python-based extraction
                    if PYTHON_ARCHIVE_AVAILABLE:
                        try:
                            # Try rarfile
                            rarfile.UNRAR_TOOL = None  # Use bundled Python implementation if possible
                            with rarfile.RarFile(file_path) as rf:
                                rf.extractall(extract_path)
                            result['success'] = True
                            print(f"Extracted RAR file using Python rarfile: {file_path}")
                        except Exception as e:
                            print(f"Python rarfile extraction failed: {str(e)}")
                            
                            # Last attempt with patool
                            try:
                                patoolib.extract_archive(file_path, outdir=extract_path)
                                result['success'] = True
                                print(f"Extracted RAR file using patool: {file_path}")
                            except Exception as e:
                                print(f"patool extraction failed: {str(e)}")
                                raise Exception(f"All RAR extraction methods failed: {str(e)}")
                    else:
                        raise Exception("Failed to extract RAR file, both command-line and Python methods unavailable")
                
        elif file_ext in ['.zip']:
            # Try with unzip
            try:
                process = subprocess.run(
                    ['unzip', file_path, '-d', extract_path],
                    capture_output=True,
                    text=True,
                    check=True
                )
                result['success'] = True
                print(f"Extracted ZIP file using unzip: {file_path}")
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                print(f"unzip extraction failed: {str(e)}")
                
                # Fallback to Python-based extraction for ZIP
                if PYTHON_ARCHIVE_AVAILABLE:
                    try:
                        with zipfile.ZipFile(file_path, 'r') as zip_ref:
                            zip_ref.extractall(extract_path)
                        result['success'] = True
                        print(f"Extracted ZIP file using Python zipfile: {file_path}")
                    except Exception as e:
                        print(f"Python zipfile extraction failed: {str(e)}")
                        raise Exception(f"Failed to extract ZIP file: {str(e)}")
                else:
                    raise Exception("Failed to extract ZIP file, both command-line and Python methods unavailable")
        
        elif file_ext in ['.7z']:
            # Try with 7z
            try:
                process = subprocess.run(
                    ['7z', 'x', file_path, f'-o{extract_path}'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                result['success'] = True
                print(f"Extracted 7z file using 7z command: {file_path}")
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                print(f"7z extraction failed: {str(e)}")
                
                # Fallback to Python-based extraction for 7z
                if PYTHON_ARCHIVE_AVAILABLE:
                    try:
                        with py7zr.SevenZipFile(file_path, mode='r') as z:
                            z.extractall(path=extract_path)
                        result['success'] = True
                        print(f"Extracted 7z file using Python py7zr: {file_path}")
                    except Exception as e:
                        print(f"Python py7zr extraction failed: {str(e)}")
                        raise Exception(f"Failed to extract 7z file: {str(e)}")
                else:
                    raise Exception("Failed to extract 7z file, both command-line and Python methods unavailable")
                
        # Fallback to 7z for any format if still not successful
        if not result['success']:
            try:
                process = subprocess.run(
                    ['7z', 'x', file_path, f'-o{extract_path}'],
                    capture_output=True,
                    text=True,
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
        
        # If extraction succeeded, list the files
        if result['success']:
            result['files'] = list_files_recursive(extract_path)
            
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

def list_files_recursive(directory):
    """
    List all files in a directory and its subdirectories.
    
    Args:
        directory (str): Path to directory
        
    Returns:
        list: List of file paths relative to the directory
    """
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            file_path = os.path.join(root, filename)
            rel_path = os.path.relpath(file_path, directory)
            files.append(rel_path)
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