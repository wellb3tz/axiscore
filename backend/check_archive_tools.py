#!/usr/bin/env python3
"""
Check which archive extraction tools are available on the system.
"""

import os
import sys
import shutil
import subprocess

def check_command(command):
    """Check if a command is available in PATH."""
    path = shutil.which(command)
    if path:
        print(f"✅ {command}: Available at {path}")
        # Try running the command to check version
        try:
            if command == "unrar":
                proc = subprocess.run([command], capture_output=True, text=True)
                output = proc.stdout if proc.stdout else proc.stderr
                # Extract version info if available
                if output:
                    lines = output.split("\n")
                    for line in lines:
                        if "UNRAR" in line or "Copyright" in line:
                            print(f"   {line.strip()}")
                            break
            elif command == "7z":
                proc = subprocess.run([command], capture_output=True, text=True)
                output = proc.stdout if proc.stdout else proc.stderr
                if output:
                    lines = output.split("\n")
                    for line in lines:
                        if "7-Zip" in line:
                            print(f"   {line.strip()}")
                            break
            elif command == "unzip":
                proc = subprocess.run([command, "-v"], capture_output=True, text=True)
                if proc.stdout:
                    lines = proc.stdout.split("\n")
                    for line in lines:
                        if "UnZip" in line:
                            print(f"   {line.strip()}")
                            break
        except Exception as e:
            print(f"   Could not get version info: {e}")
        return True
    else:
        print(f"❌ {command}: Not found")
        return False

def check_python_modules():
    """Check if Python archive modules are available."""
    modules = {
        "rarfile": "RAR file extraction (Python)",
        "py7zr": "7z file extraction (Python)",
        "zipfile": "ZIP file extraction (Python)",
        "patoolib": "Universal archive extraction (Python)"
    }
    
    for module, description in modules.items():
        try:
            __import__(module)
            print(f"✅ {module}: Available ({description})")
        except ImportError:
            print(f"❌ {module}: Not found ({description})")

def main():
    """Main function."""
    print("Checking archive extraction tools...\n")
    
    # Check command-line tools
    commands = ["unrar", "unrar-free", "7z", "unzip", "rar"]
    available_commands = []
    
    print("Command-line tools:")
    print("-----------------")
    for command in commands:
        if check_command(command):
            available_commands.append(command)
    
    if not available_commands:
        print("\n⚠️ No command-line extraction tools found!")
        print("You should install at least one of: 7-Zip, unrar, or unzip.")
    
    # Check Python modules
    print("\nPython modules:")
    print("--------------")
    check_python_modules()
    
    # Recommend missing tools
    print("\nRecommendations:")
    print("--------------")
    
    if "7z" not in available_commands:
        print("- Install 7-Zip (recommended for best compatibility)")
        if sys.platform == "win32":
            print("  Download from: https://www.7-zip.org/download.html")
        elif sys.platform == "linux":
            print("  Run: sudo apt-get install p7zip-full")
        elif sys.platform == "darwin":
            print("  Run: brew install p7zip")
    
    if "unrar" not in available_commands:
        print("- Install unrar for RAR file support")
        if sys.platform == "win32":
            print("  Download from: https://www.rarlab.com/rar_add.htm")
        elif sys.platform == "linux":
            print("  Run: sudo apt-get install unrar")
        elif sys.platform == "darwin":
            print("  Run: brew install unrar")
    
    if "unzip" not in available_commands:
        print("- Install unzip for ZIP file support")
        if sys.platform.startswith(("linux", "darwin")):
            print("  Run: sudo apt-get install unzip")

if __name__ == "__main__":
    main() 