import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import threading
import os
import sys
import re
import io
from contextlib import redirect_stdout
import SimpleYandexDownloader as downloader
import itertools
import time

class RedirectText:
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.buffer = ""
        self.current_line = ""
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        self.last_line_index = None
        
    def write(self, string):
        # Strip ANSI color codes
        string = self.ansi_escape.sub('', string)
        
        self.text_widget.configure(state="normal")
        
        # Handle carriage returns properly
        if '\r' in string and not '\n' in string:
            # This is an update to the current line (like a progress bar)
            if self.last_line_index:
                # Delete the current line
                self.text_widget.delete(self.last_line_index, f"{self.last_line_index.split('.')[0]}.end")
                
            # Write the new content
            clean_string = string.replace('\r', '')
            self.text_widget.insert(self.last_line_index or tk.END, clean_string)
            
            # Save where this line starts
            if not self.last_line_index:
                self.last_line_index = self.text_widget.index(tk.INSERT)
        else:
            # If we have a newline, reset our line tracking
            if '\n' in string:
                self.last_line_index = None
            
            # Clean progress bar characters for better display
            clean_string = string
            if '[' in string and ']' in string and ('-' in string or '=' in string or '█' in string):
                # This is likely a progress bar - simplify it
                parts = string.split('[')
                if len(parts) > 1:
                    prefix = parts[0]
                    rest = '['.join(parts[1:])
                    bar_parts = rest.split(']')
                    if len(bar_parts) > 1:
                        # Extract text after the progress bar
                        suffix = ']'.join(bar_parts[1:])
                        # Just show the text parts without the bar itself
                        clean_string = f"{prefix} {suffix}"
            
            # Insert the cleaned text
            self.text_widget.insert(tk.END, clean_string)
        
        # Keep scroll at the bottom
        self.text_widget.see(tk.END)
        self.text_widget.configure(state="disabled")
        
    def flush(self):
        pass

class YandexDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Yandex Video Downloader")
        self.root.geometry("800x600")
        self.root.minsize(600, 500)
        
        # Version and copyright info
        self.version = "1.0.0"
        self.copyright = "© 2025 Dykke"
        
        # Set theme
        style = ttk.Style()
        try:
            self.root.tk.call("source", "azure.tcl")
            style.theme_use("azure")
            self.theme_available = True
        except:
            self.theme_available = False
        
        # Create frame for input
        input_frame = ttk.LabelFrame(root, text="URL Input")
        input_frame.pack(padx=10, pady=10, fill=tk.X)
        
        # URL input
        ttk.Label(input_frame, text="Paste .ts segment URL:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.url_entry = ttk.Entry(input_frame, width=70)
        self.url_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W+tk.E)
        
        # Output file selection
        ttk.Label(input_frame, text="Output folder:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.output_var = tk.StringVar(value=downloader.get_default_downloads_folder())
        self.output_entry = ttk.Entry(input_frame, textvariable=self.output_var, width=70)
        self.output_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W+tk.E)
        self.browse_btn = ttk.Button(input_frame, text="Browse", command=self.browse_folder)
        self.browse_btn.grid(row=1, column=2, padx=5, pady=5)
        
        # FFMPEG path
        ttk.Label(input_frame, text="FFmpeg path:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        self.ffmpeg_var = tk.StringVar(value=downloader.FFMPEG_PATH)
        self.ffmpeg_entry = ttk.Entry(input_frame, textvariable=self.ffmpeg_var, width=70)
        self.ffmpeg_entry.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W+tk.E)
        self.browse_ffmpeg_btn = ttk.Button(input_frame, text="Browse", command=self.browse_ffmpeg)
        self.browse_ffmpeg_btn.grid(row=2, column=2, padx=5, pady=5)
        
        # Button to start download
        button_frame = ttk.Frame(root)
        button_frame.pack(padx=10, pady=5, fill=tk.X)
        
        self.download_btn = ttk.Button(button_frame, text="Start Download", command=self.start_download)
        self.download_btn.pack(side=tk.LEFT, padx=5)
        
        self.cancel_btn = ttk.Button(button_frame, text="Cancel", command=self.cancel_download, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # Progress bar
        progress_frame = ttk.LabelFrame(root, text="Progress")
        progress_frame.pack(padx=10, pady=10, fill=tk.X)
        
        self.progress = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=100, mode="determinate")
        self.progress.pack(padx=10, pady=10, fill=tk.X)
        
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(progress_frame, textvariable=self.status_var)
        self.status_label.pack(padx=5, pady=5)
        
        # Output log
        log_frame = ttk.LabelFrame(root, text="Log")
        log_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10)
        self.log_text.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        self.log_text.configure(state="disabled")
        
        # Credits footer
        footer_frame = ttk.Frame(root)
        footer_frame.pack(padx=10, pady=5, fill=tk.X)
        
        credit_text = f"Simple Yandex Video Downloader v{self.version} | {self.copyright} | MIT License"
        credit_label = ttk.Label(footer_frame, text=credit_text, foreground="gray")
        credit_label.pack(side=tk.RIGHT, padx=5, pady=2)
        
        # Initialize variables
        self.download_thread = None
        self.redirect = RedirectText(self.log_text)
        
        # Instructions
        self.add_to_log("🎬 Yandex Video Downloader GUI\n")
        self.add_to_log("Instructions:\n")
        self.add_to_log("1. Open your browser's Network tab (F12)\n")
        self.add_to_log("2. Find/Filter a .ts segment URL (like 0.ts?vid=...)\n")
        self.add_to_log("3. Copy the full URL\n")
        self.add_to_log("4. Paste it in the URL field above\n")
        self.add_to_log("5. Click 'Start Download'\n\n")
        self.add_to_log("The application will automatically detect segments and download them.\n")
        
        # Set up close protocol
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def add_to_log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, message)
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")
        
    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_var.set(folder)
            
    def browse_ffmpeg(self):
        if os.name == 'nt':  # Windows
            ffmpeg = filedialog.askopenfilename(filetypes=[("FFmpeg", "ffmpeg.exe"), ("All files", "*.*")])
        else:
            ffmpeg = filedialog.askopenfilename(filetypes=[("FFmpeg", "ffmpeg"), ("All files", "*.*")])
        if ffmpeg:
            self.ffmpeg_var.set(ffmpeg)
            
    def update_progress(self, value, maximum, status_text):
        if maximum > 0:
            percentage = int((value / maximum) * 100)
            self.progress["value"] = percentage
        else:
            self.progress["value"] = 0
        self.status_var.set(status_text)
        
    def start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            self.add_to_log("❌ No URL provided! Please paste a .ts segment URL.\n")
            return
            
        # Update FFmpeg path in downloader module
        downloader.FFMPEG_PATH = self.ffmpeg_var.get()
        
        # Disable controls
        self.download_btn.configure(state=tk.DISABLED)
        self.cancel_btn.configure(state=tk.NORMAL)
        self.url_entry.configure(state=tk.DISABLED)
        self.output_entry.configure(state=tk.DISABLED)
        self.ffmpeg_entry.configure(state=tk.DISABLED)
        self.browse_btn.configure(state=tk.DISABLED)
        self.browse_ffmpeg_btn.configure(state=tk.DISABLED)
        
        # Reset progress
        self.progress["value"] = 0
        self.status_var.set("Starting download...")
        self.log_text.configure(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state="disabled")
        
        # Extract the pattern
        if "0.ts" in url:
            base_url = url
        else:
            # Try to find the pattern
            match = re.search(r'(https?://[^?]+)0\.ts([^?]*\?.*)', url)
            if match:
                base_url = match.group(1) + "0.ts" + match.group(2)
            else:
                self.add_to_log("❌ Could not extract URL pattern. Please provide a URL containing '0.ts'\n")
                self.reset_ui()
                return
                
        # Set a reasonable default maximum (we'll detect the actual number)
        max_segments = 200  # High enough to handle most videos
        
        # Auto-generate filename
        output_path = self.output_var.get()
        output_filename = downloader.get_next_filename(output_path)
        
        # Redirect stdout to our log
        sys.stdout = self.redirect
        
        # Create a thread for downloading
        self.download_thread = threading.Thread(
            target=self.download_thread_func,
            args=(base_url, max_segments, output_filename)
        )
        self.download_thread.daemon = True
        self.download_thread.start()
        
    def download_thread_func(self, base_url, max_segments, output_filename):
        try:
            # Override the progress bar function
            original_print_progress = downloader.print_progress_bar
            
            def custom_progress_bar(current, total, prefix="Progress", suffix="Complete", length=50, fill="█"):
                # Update GUI progress bar directly instead of using console output
                if total > 0:
                    percentage = int((current / total) * 100)
                    self.root.after(0, lambda: self.update_progress(
                        current, total, 
                        f"{prefix}: {current}/{total} ({percentage}% {suffix})"
                    ))
                
                # Create a simplified version for the log that won't show the bar
                log_msg = f"\rDownloading: {current}/{total} - {suffix}"
                print(log_msg, end="")
                
                # If we're done, print a newline
                if current == total:
                    print()
            
            # Replace the progress function
            downloader.print_progress_bar = custom_progress_bar
            
            # Create a custom spinner function for better GUI display
            original_spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
            spinner_index = [0]  # Use list to allow modification in nested function
            
            def custom_spinner():
                # Get next character and increment index
                char = original_spinner_chars[spinner_index[0]]
                spinner_index[0] = (spinner_index[0] + 1) % len(original_spinner_chars)
                # Force GUI update and small delay for animation
                self.root.update_idletasks()
                time.sleep(0.1)
                return char
            
            # Override the spinner generation in the downloader module
            def patched_detect_segment_count(base_url, session, max_limit=None):
                """Detect segments with custom spinner for GUI"""
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
                    'Referer': 'https://disk.yandex.com/'
                }
                
                found_segments = 0
                
                # First verify segment 0 exists
                segment_url = base_url
                try:
                    # Use a clean line for segment checking
                    print("\n🔍 Checking segment availability...\n")
                    print(f"{custom_spinner()} Verifying first segment...", end="", flush=True)
                    response = session.get(segment_url, headers=headers, timeout=10, stream=True)
                    if response.status_code != 200:
                        print("\n❌ First segment not found! URL may be invalid.")
                        return 0
                    
                    # Read a small part to verify it's a valid segment
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            break
                        
                except Exception as e:
                    print(f"\n❌ Error accessing first segment: {str(e)}")
                    return 0
                
                # Start with a conservative approach
                max_to_check = 30 if max_limit is None or max_limit > 30 else max_limit
                
                # Initialize progress tracking
                print("\nScanning for available segments:")
                print("----------------------------")
                
                # Check segments sequentially
                for i in range(max_to_check):
                    segment_url = base_url.replace("0.ts", f"{i}.ts")
                    try:
                        # Only update every 5 segments to reduce log noise
                        if i % 5 == 0 or i == max_to_check - 1:
                            print(f"Checking segments {i}-{min(i+4, max_to_check-1)}...")
                        
                        response = session.get(segment_url, headers=headers, timeout=5, stream=True)
                        
                        if response.status_code == 200:
                            # Verify it's actually a valid segment
                            is_valid = False
                            for chunk in response.iter_content(chunk_size=1024):
                                if chunk:
                                    is_valid = True
                                    break
                            
                            if is_valid:
                                found_segments = i + 1
                            else:
                                break
                        else:
                            break
                            
                        time.sleep(0.1)
                        
                    except Exception as e:
                        break
                
                print("\n----------------------------")
                print(f"✅ Found {found_segments} segments available")
                return found_segments
            
            # Use our custom detection function
            original_detect = downloader.detect_segment_count
            downloader.detect_segment_count = patched_detect_segment_count
            
            # Start download
            success = downloader.download_video_from_pattern(base_url, max_segments, output_filename)
            
            # Reset the functions
            downloader.print_progress_bar = original_print_progress
            downloader.detect_segment_count = original_detect
            
            # Update UI from main thread
            self.root.after(0, lambda: self.download_finished(success))
            
        except Exception as e:
            # Handle exceptions
            print(f"\n❌ Error: {str(e)}")
            self.root.after(0, self.reset_ui)
        finally:
            # Reset stdout
            sys.stdout = sys.__stdout__
            
    def download_finished(self, success):
        if success:
            self.status_var.set("Download completed successfully!")
        else:
            if downloader.cancelled:
                self.status_var.set("Download cancelled")
            else:
                self.status_var.set("Download failed")
                
        self.reset_ui()
        
    def cancel_download(self):
        if self.download_thread and self.download_thread.is_alive():
            # Set the cancellation flag in the downloader
            with downloader.cancellation_lock:
                downloader.cancelled = True
            self.status_var.set("Cancelling download...")
            self.cancel_btn.configure(state=tk.DISABLED)
            
    def reset_ui(self):
        self.download_btn.configure(state=tk.NORMAL)
        self.cancel_btn.configure(state=tk.DISABLED)
        self.url_entry.configure(state=tk.NORMAL)
        self.output_entry.configure(state=tk.NORMAL)
        self.ffmpeg_entry.configure(state=tk.NORMAL)
        self.browse_btn.configure(state=tk.NORMAL)
        self.browse_ffmpeg_btn.configure(state=tk.NORMAL)
        # Reset cancellation flag
        with downloader.cancellation_lock:
            downloader.cancelled = False
            
    def on_closing(self):
        # Cancel any running downloads
        self.cancel_download()
        # Wait a moment for the download to stop
        self.root.after(100, self.root.destroy)

if __name__ == "__main__":
    root = tk.Tk()
    app = YandexDownloaderGUI(root)
    root.mainloop() 