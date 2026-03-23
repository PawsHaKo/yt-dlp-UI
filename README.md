# yt-dlp Web UI

A self-hosted web interface for downloading YouTube audio as MP3 by using `yt-dlp`.

## Features

- **Queue-first workflow:** Submit multiple URLs in one shot, then monitor a live job queue.
- **Parallel workers:** Up to 3 downloads run at the same time, while the rest stay queued.
- **Real progress updates:** UI shows actual `yt-dlp` status (`queued / downloading / postprocessing / completed / failed`).
- **Retry failed jobs:** Failed entries can be retried without pasting URLs again.
- **Downloaded file list:** Completed files are listed and can be opened directly.

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

4.  **(Optional) YouTube cookies file for restricted videos**
    - If some public-looking videos fail with `This video is not available`, provide a Netscape-format cookie file.
    - Default file name in project root: `www.youtube.com_cookies.txt`
    - Or set env var explicitly:
      ```sh
      export YTDLP_COOKIES_FILE=/absolute/path/to/cookies.txt
      ```
    - The server will pass this file to `yt-dlp --cookies` automatically (no keychain access needed).

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

- Paste one or more YouTube URLs into the input area (newlines, spaces, and commas are supported).
- Click **加入佇列** to create jobs.
- Watch the queue for each job status:
  - `排隊中` (`queued`)
  - `下載中` (`downloading`)
  - `後處理中` (`postprocessing`)
  - `完成` (`completed`)
  - `失敗` (`failed`)
- Click **重試** on failed jobs.
- Completed audio files are shown in **已下載檔案** and stored in the `downloads/` directory.

## API Endpoints

- `POST /jobs`
  - Body: `{ "urls": ["https://...", "..."] }`
  - Behavior: trims and deduplicates URLs, validates `http/https`, then creates queued jobs.
- `GET /jobs`
  - Returns all jobs in creation order.
  - Optional query: `?ids=<id1>,<id2>`.
- `POST /jobs/{id}/retry`
  - Retries only failed jobs by creating a new queued job with the same URL.
- `GET /files`
  - Returns downloaded file names from `downloads/`.
