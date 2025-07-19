# Simple Yandex Video Downloader

A Python script for downloading videos from Yandex Disk by extracting and combining video segments.

## Author

Created by Veesa

[![GitHub](https://img.shields.io/github/license/Dykke/Simple-Yandex-Video-Downloader)](https://github.com/Dykke/Simple-Yandex-Video-Downloader/blob/main/LICENSE)

## Requirements

- Python 3.6 or higher
- FFmpeg (the script is configured to look for FFmpeg at `C:\Users\<Your Name>\Downloads\ffmpeg-2025-07-17-git-bc8d06d541-full_build\bin\ffmpeg`)
- Python packages:
  - `requests`
  - `tkinter` (included with Python, required for GUI version)

## Setup

1. Clone this repository or download the script
2. Install required Python packages:
```
pip install requests
```
3. Make sure FFmpeg is installed and update the `FFMPEG_PATH` in the script to your FFmpeg location

## How to Use

### Command Line Version

1. Run the script:
```
py SimpleYandexDownloader.py
```

### GUI Version

1. Run the GUI version:
```
py SimpleYandexDownloaderGUI.py
```

### Executable Version

1. Build the executable (Windows, macOS, Linux):
```
py build_exe.py
```
2. Run the generated executable from the `dist` folder

**Note:** When using the executable version, you may see a command prompt window briefly appear during the download process or when combining files. This is normal and happens when FFmpeg is being called to combine the video segments. The window will close automatically when the process is complete.

2. Follow the on-screen instructions:
   - Open your browser's Network tab (F12)
   - Find/Filter a .ts segment URL (like 0.ts?vid=...)
   - Copy the full URL
   - Paste it when prompted

3. The script will:
   - Automatically detect available video segments
   - Download all segments in parallel
   - Combine them into a single MP4 file
   - Save the result to your Downloads folder

## Features

- Automatic segment detection
- Progress bar with download statistics
- Multi-threaded downloading
- Graceful cancellation with Ctrl+C
- Automatic naming of downloaded videos

## Notes

- The script requires a direct .ts segment URL, which you can find using your browser's developer tools
- Downloaded videos are saved to your default Downloads folder
- You can cancel the download at any time by pressing Ctrl+C

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 