import os
import sys
import archive_utils

def test_archive_extraction(file_path):
    """
    Test the extraction of an archive file.
    
    Args:
        file_path (str): Path to the archive file
    """
    print(f"Testing extraction of: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return
    
    print(f"File size: {os.path.getsize(file_path)} bytes")
    print(f"File extension: {os.path.splitext(file_path)[1]}")
    
    # Try extraction
    result = archive_utils.extract_archive(file_path)
    
    if result['success']:
        print(f"Extraction successful!")
        print(f"Extracted to: {result['extract_path']}")
        print(f"Found {len(result['files'])} files")
        
        # List the first 10 files
        if result['files']:
            print("\nSample of extracted files:")
            for i, file_info in enumerate(result['files'][:10]):
                print(f"  - {file_info['filename']} ({file_info['extension']})")
            
            if len(result['files']) > 10:
                print(f"  ... and {len(result['files']) - 10} more files")
        
        # Check for 3D model files
        model_files = archive_utils.find_3d_model_files(result['files'])
        if model_files:
            print(f"\nFound {len(model_files)} 3D model files:")
            for model in model_files:
                print(f"  - {model['filename']} ({model['extension']})")
        else:
            print("\nNo 3D model files found in the archive")
        
        # Cleanup
        print("\nCleaning up extraction directory...")
        archive_utils.cleanup_extraction(result['extract_path'])
        print("Cleanup complete")
    else:
        print(f"Extraction failed!")
        print(f"Error: {result['error']}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_archive.py <path_to_archive_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    test_archive_extraction(file_path) 