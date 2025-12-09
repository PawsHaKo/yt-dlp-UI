# yt-dlp Web UI

A simple, self-hosted web interface for downloading audio from YouTube using `yt-dlp`.

## Features

- **Simple Web Interface:** Clean and easy-to-use UI for downloading audio.
- **Bulk Downloads:** Paste multiple YouTube URLs to download them in a batch.
- **MP3 Conversion:** Automatically converts and saves audio in MP3 format.
- **Download Progress:** Real-time progress bars show the status of each download.
- **File Listing:** Displays a list of all downloaded audio files.

## Prerequisites

Before you begin, you need to have the following software installed on your system.

1.  **Python 3:** The web server is a Python script. You can download Python from [python.org](https://www.python.org/).

2.  **yt-dlp:** This is the core command-line tool used for the downloads.
    - You can find the installation instructions on the [official yt-dlp repository](https://github.com/yt-dlp/yt-dlp).

3.  **ffmpeg:** This is a required dependency for `yt-dlp` to convert video and audio streams, and is essential for creating MP3 files.
    - **On macOS (using Homebrew):**
      ```sh
      brew install ffmpeg
      ```
    - **On Windows (using Chocolatey or Scoop):**
      ```sh
      # Using Chocolatey
      choco install ffmpeg

      # Using Scoop
      scoop install ffmpeg
      ```
    - **On Debian/Ubuntu Linux:**
      ```sh
      sudo apt update && sudo apt install ffmpeg
      ```

## Setup

1.  **Download the project files.** You can do this by cloning the repository or downloading the files as a ZIP.

2.  **Place the `yt-dlp` executable:**
    - Place your `yt-dlp` executable file in the project directory. The server script expects to find it there.

## How to Run the Server

1.  **Navigate to the web UI directory:**
    Open your terminal or command prompt and change to the project directory.
    ```sh
    cd path/to/the/project
    ```

2.  **Run the Python server:**
    Execute the server script using Python 3.
    ```sh
    python3 server.py
    ```

3.  **Access the Web UI:**
    Once the server is running, you will see a message like `serving at port 8000`. Open your web browser and navigate to:
    [http://localhost:8000](http://localhost:8000)

## How to Use

- **Single or Bulk URLs:** Paste one or more YouTube URLs into the text area. You can separate them with new lines, spaces, or commas.
- **Start Processing:** Click the "Start Processing" button.
- **Monitor Progress:** The download progress for each URL will appear below the input form.
- **Access Files:** Successfully downloaded files will be listed at the bottom of the page and stored in the `downloads` directory.
