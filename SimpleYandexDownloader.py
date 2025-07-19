import requests
import os
import sys
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import glob
import signal
import time
import threading
import itertools

# Set the full path to ffmpeg
FFMPEG_PATH = r"C:\Users\veesa\Downloads\ffmpeg-2025-07-17-git-bc8d06d541-full_build\bin\ffmpeg"

# Global flag for cancellation
cancelled = False
cancellation_lock = threading.Lock()

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global cancelled
    with cancellation_lock:
        cancelled = True
    print("\n\n⚠️  Cancellation requested! Stopping download...")
    print("🛑 Download cancelled by user!")
    # Force exit after a short delay to allow message to display
    time.sleep(0.5)
    sys.exit(0)

# Register signal handler for Ctrl+C
signal.signal(signal.SIGINT, signal_handler)

def get_default_downloads_folder():
    """Get the default downloads folder based on the user's OS."""
    if os.name == 'nt':  # Windows
        import winreg
        sub_key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders'
        downloads_guid = '{374DE290-123F-4565-9164-39C4925E467B}'
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
                location = winreg.QueryValueEx(key, downloads_guid)[0]
                return location
        except:
            # Fallback for Windows
            return os.path.join(os.path.expanduser('~'), 'Downloads')
    else:  # macOS, Linux, etc.
        return os.path.join(os.path.expanduser('~'), 'Downloads')

def get_next_filename(output_path):
    """Get the next available filename in sequence (downloaded_001.mp4, downloaded_002.mp4, etc.)"""
    pattern = os.path.join(output_path, "downloaded_*.mp4")
    existing_files = glob.glob(pattern)
    
    if not existing_files:
        return "downloaded_001.mp4"
    
    # Extract numbers from existing filenames
    numbers = []
    for file in existing_files:
        filename = os.path.basename(file)
        match = re.search(r'downloaded_(\d+)\.mp4', filename)
        if match:
            numbers.append(int(match.group(1)))
    
    if not numbers:
        return "downloaded_001.mp4"
    
    # Find the next number
    next_num = max(numbers) + 1
    return f"downloaded_{next_num:03d}.mp4"

def print_progress_bar(current, total, prefix="Progress", suffix="Complete", length=50, fill="█"):
    """Print a modern progress bar like pip installations with color"""
    # ANSI color codes
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'
    
    if total == 0:
        percent = "0.0"
        filled_length = 0
    else:
        percent = f"{100 * (current / float(total)):.1f}"
        filled_length = int(length * current // total)
    
    # Colorful progress bar
    progress_color = GREEN if filled_length > length * 0.7 else BLUE if filled_length > length * 0.3 else YELLOW
    bar = progress_color + fill * filled_length + RESET + '-' * (length - filled_length)
    
    # Format the output with colors
    print(f'\r{CYAN}{prefix}{RESET} |{bar}| {CYAN}{percent}%{RESET} {suffix}', end='', flush=True)
    
    if current == total:
        print()

def detect_segment_count(base_url, session, max_limit=None):
    """Detect how many segments are actually available using a super conservative approach"""
    print("🔍 Detecting available segments...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'cross-site',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
        'Referer': 'https://disk.yandex.com/'  # Important for Yandex
    }
    
    # Spinner animation - use simpler characters that work better in GUI
    spinner = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
    found_segments = 0
    
    # First verify segment 0 exists
    segment_url = base_url
    try:
        print(f"\r{next(spinner)} 🔍 Verifying first segment...", end="", flush=True)
        response = session.get(segment_url, headers=headers, timeout=10, stream=True)
        if response.status_code != 200:
            print(f"\r{' ' * 80}")
            print("❌ First segment not found! URL may be invalid.")
            return 0
        
        # Read a small part to verify it's a valid segment
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                break
            
    except Exception as e:
        print(f"\r{' ' * 80}")
        print(f"❌ Error accessing first segment: {str(e)}")
        return 0
    
    # Start with a very conservative approach - check each segment one by one
    # Only go up to 30 max for initial detection (most videos have fewer segments)
    max_to_check = 30 if max_limit is None or max_limit > 30 else max_limit
    
    # Check segments sequentially
    for i in range(max_to_check):
        segment_url = base_url.replace("0.ts", f"{i}.ts")
        try:
            print(f"\r{next(spinner)} 🔍 Checking segment {i}...", end="", flush=True)
            
            # Use GET instead of HEAD to be more accurate (some servers respond differently)
            response = session.get(segment_url, headers=headers, timeout=5, stream=True)
            
            if response.status_code == 200:
                # Verify it's actually a valid segment by reading a small part
                is_valid = False
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        is_valid = True
                        break
                
                if is_valid:
                    found_segments = i + 1
                else:
                    # We found a response but it's not a valid segment
                    break
            else:
                # We found the end
                break
                
            # Don't hammer the server
            time.sleep(0.1)
            
        except Exception as e:
            # Error means we've likely reached the end
            break
    
    # Clear the spinner line and print a newline for cleaner output
    print(f"\r{' ' * 80}")
    print(f"✅ Found {found_segments} segments available")
    return found_segments

def download_segment_with_retry(args):
    """Download a single segment with retry logic"""
    global cancelled
    
    # Check if cancelled
    with cancellation_lock:
        if cancelled:
            return None
        
    index, url, temp_dir, session = args
    filename = f"segment_{index:05d}.ts"
    filepath = os.path.join(temp_dir, filename)
    
    # Skip if already downloaded and has content
    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        return filepath
    
    # Retry logic
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        # Check cancellation before each attempt
        with cancellation_lock:
            if cancelled:
                return None
        
        try:
            # Use the same headers as the browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'cross-site',
                'Pragma': 'no-cache',
                'Cache-Control': 'no-cache'
            }
            
            response = session.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        
            # Check if file is valid
            if os.path.getsize(filepath) < 1000:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return None
                
            return filepath
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 524:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    return None
            elif e.response.status_code == 404:
                return None
            else:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return None
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            return None
    
    return None

def download_video_from_pattern(base_url, max_segments, output_filename=None):
    """Download video using the TS segment pattern with automatic detection"""
    global cancelled
    
    if output_filename is None:
        output_filename = "yandex_video.mp4"
    elif not output_filename.endswith('.mp4'):
        output_filename += '.mp4'
        
    output_path = get_default_downloads_folder()
    temp_dir = os.path.join(output_path, f"temp_{os.path.splitext(output_filename)[0]}")
    
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(output_path, exist_ok=True)
    
    # Create session
    session = requests.Session()
    
    # Detect actual number of segments (limit search based on user's max)
    actual_segments = detect_segment_count(base_url, session, max_segments)
    
    if actual_segments == 0:
        print("❌ No segments found! The URL may be invalid or expired.")
        return False
        
    # Just show the detected count
    print(f"✅ Found {actual_segments} segments available")
    
    # Use the smaller of detected segments or user's max
    num_segments = min(actual_segments, max_segments)
    
    print(f"📥 Downloading all {actual_segments} segments...")
    print("💡 Press Ctrl+C to cancel at any time")
    print()
    
    # Generate segment URLs
    segment_urls = []
    for i in range(num_segments):
        # Replace the segment number in the URL
        segment_url = base_url.replace("0.ts", f"{i}.ts")
        segment_urls.append(segment_url)
    
    # Download segments with modern progress tracking
    downloaded_files = []
    failed_segments = []
    completed = 0
    total_bytes = 0
    total_segments = len(segment_urls)
    
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(download_segment_with_retry, (i, url, temp_dir, session)): i 
                for i, url in enumerate(segment_urls)
            }
            
            # Process completed tasks
            for future in as_completed(future_to_index):
                # Check cancellation
                with cancellation_lock:
                    if cancelled:
                        print("\n🛑 Download cancelled by user!")
                        return False
                
                index = future_to_index[future]
                completed += 1
                
                try:
                    filepath = future.result()
                    if filepath:
                        downloaded_files.append(filepath)
                        # Track downloaded bytes
                        if os.path.exists(filepath):
                            total_bytes += os.path.getsize(filepath)
                    else:
                        failed_segments.append(index)
                except Exception as e:
                    failed_segments.append(index)
                
                # Update progress bar
                success_rate = len(downloaded_files) / completed * 100 if completed > 0 else 0
                mb_downloaded = total_bytes / (1024 * 1024)
                
                print_progress_bar(
                    completed, total_segments,
                    prefix=f"Downloading {num_segments} segments",
                    suffix=f"({completed}/{total_segments}, {mb_downloaded:.1f}MB, {success_rate:.1f}% success)"
                )
                
    except KeyboardInterrupt:
        print("\n🛑 Download cancelled by user!")
        return False
    
    # Calculate total size
    total_size_mb = sum(os.path.getsize(f) for f in downloaded_files) / (1024 * 1024) if downloaded_files else 0
    
    print(f"\n✅ Download completed!")
    print(f"📊 Results: {len(downloaded_files)}/{num_segments} segments downloaded successfully ({total_size_mb:.2f} MB)")
    
    if failed_segments:
        print(f"⚠️ {len(failed_segments)} segments failed to download")
    
    if len(downloaded_files) == 0:
        print("❌ No segments were downloaded successfully!")
        print("💡 Tip: Try getting a fresh URL from your browser's Network tab")
        return False
    
    # Check if cancelled before combining
    with cancellation_lock:
        if cancelled:
            print("🛑 Download cancelled before combining segments!")
            return False
    
    # Create segments file for ffmpeg
    segments_file = os.path.join(temp_dir, "segments.txt")
    with open(segments_file, 'w') as f:
        for filepath in sorted(downloaded_files):
            f.write(f"file '{filepath}'\n")
    
    # Combine with ffmpeg
    output_file = os.path.join(output_path, output_filename)
    print(f"🔧 Combining {len(downloaded_files)} segments into {output_filename}...")
    
    # Check ffmpeg
    try:
        subprocess.run([FFMPEG_PATH, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        print(f"❌ Error: ffmpeg not found at {FFMPEG_PATH}")
        return False
    
    # Use ffmpeg to combine
    ffmpeg_cmd = [
        FFMPEG_PATH,
        "-f", "concat",
        "-safe", "0",
        "-i", segments_file,
        "-c", "copy",
        "-bsf:a", "aac_adtstoasc",
        output_file
    ]
    
    try:
        process = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except KeyboardInterrupt:
        print("\n🛑 FFmpeg process cancelled!")
        return False
    
    if process.returncode == 0:
        print(f"✅ Video successfully saved to: {output_file}")
        if failed_segments:
            print(f"⚠️  Note: {len(failed_segments)} segments were missing, but video was created successfully")
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)
        return True
    else:
        print("❌ Error combining segments:")
        print(process.stderr.decode())
        return False

if __name__ == "__main__":
    print("🎬 Yandex Video Downloader")
    print("=" * 40)
    print("Instructions:")
    print("1. Open your browser's Network tab (F12)")
    print("2. Find a .ts segment URL (like 0.ts?vid=...)")
    print("3. Copy the full URL")
    print("4. Enter it below")
    print("💡 Press Ctrl+C anytime to cancel")
    print("🔍 Script will automatically detect available segments")
    print()
    
    try:
        # Get the base URL from user
        sample_url = input("📋 Paste a .ts segment URL: ").strip()
        
        if not sample_url:
            print("❌ No URL provided!")
            sys.exit(1)
        
        # Extract the pattern
        if "0.ts" in sample_url:
            base_url = sample_url
        else:
            # Try to find the pattern
            match = re.search(r'(https?://[^?]+)0\.ts([^?]*\?.*)', sample_url)
            if match:
                base_url = match.group(1) + "0.ts" + match.group(2)
            else:
                print("❌ Could not extract URL pattern. Please provide a URL containing '0.ts'")
                sys.exit(1)
        
        # Set a reasonable default maximum (we'll detect the actual number)
        max_segments = 200  # High enough to handle most videos  # Default
        
        # Auto-generate filename
        output_path = get_default_downloads_folder()
        output_filename = get_next_filename(output_path)
        
        print(f"\n🚀 Starting download...")
        print(f"🔗 Base URL: {base_url[:80]}...")
        print(f"📊 Maximum segments: {max_segments}")
        print(f"💾 Output: {output_filename}")
        print()
        
        success = download_video_from_pattern(base_url, max_segments, output_filename)
        
        if success:
            print("\n🎉 Download completed successfully!")
        else:
            with cancellation_lock:
                if cancelled:
                    print("\n❌ Download was cancelled.")
                else:
                    print("\n❌ Download failed. Check the error messages above.")
                
    except KeyboardInterrupt:
        print("\n\n🛑 Operation cancelled by user!")
        sys.exit(0)


#        py SimpleYandexDownloader.py  
#
 