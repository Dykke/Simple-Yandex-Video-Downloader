import os
import sys
import subprocess
import shutil
import platform
import time

def check_pyinstaller():
    """Check if PyInstaller is installed."""
    try:
        import PyInstaller
        return True
    except ImportError:
        return False

def install_pyinstaller():
    """Install PyInstaller using pip."""
    print("Installing PyInstaller...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

def build_executable():
    """Build the executable using PyInstaller."""
    print("Building executable...")
    
    # Delete any existing build/dist directories
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")
        
    # Get system info for naming
    system = platform.system().lower()
    
    # Create icon file path
    icon_param = []
    
    # Build command
    cmd = [
        "pyinstaller",
        "--onefile",  # Create a single executable
        "--noconsole",  # No console window
        "--name", "YandexVideoDownloader",
        "--add-data", "README.md" + os.pathsep + ".",  # Add README
    ] + icon_param + ["SimpleYandexDownloaderGUI.py"]
    
    # Run PyInstaller
    subprocess.run(cmd, check=True)
    
    print("\nExecutable built successfully!")
    print(f"You can find it in the 'dist' folder as YandexVideoDownloader{'exe' if system == 'windows' else ''}")

if __name__ == "__main__":
    print("===== Building Yandex Video Downloader Executable =====")
    
    # Check and install PyInstaller if needed
    if not check_pyinstaller():
        print("PyInstaller not found.")
        install_pyinstaller()
    
    # Build the executable
    build_executable()
    
    print("\nBuild process completed!")
    print("Note: Make sure to distribute FFmpeg along with your executable, or instruct users to install it separately.")
    
    # Wait to exit
    time.sleep(1) 