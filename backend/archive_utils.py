import os
import subprocess
import tempfile
import uuid
import shutil
from pathlib import Path

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
            # Try with unrar
            try:
                process = subprocess.run(
                    ['unrar', 'x', file_path, extract_path],
                    capture_output=True,
                    text=True,
                    check=True
                )
                result['success'] = True
                print(f"Extracted RAR file using unrar: {file_path}")
            except subprocess.CalledProcessError as e:
                print(f"unrar extraction failed: {e.stderr}")
                raise Exception(f"Failed to extract RAR with unrar: {e.stderr}")
                
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
            except subprocess.CalledProcessError as e:
                print(f"unzip extraction failed: {e.stderr}")
                raise Exception(f"Failed to extract ZIP with unzip: {e.stderr}")
                
        # Fallback to 7z for any format
        if not result['success']:
            try:
                process = subprocess.run(
                    ['7z', 'x', file_path, f'-o{extract_path}'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                result['success'] = True
                print(f"Extracted archive using 7z: {file_path}")
            except subprocess.CalledProcessError as e:
                print(f"7z extraction failed: {e.stderr}")
                raise Exception(f"Failed to extract archive with 7z: {e.stderr}")
        
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