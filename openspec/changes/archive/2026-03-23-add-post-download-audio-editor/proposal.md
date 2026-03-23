## Why

目前系統只支援下載音訊，使用者若要裁切段落或調整音量，必須另開外部工具，流程中斷且成本高。新增「下載後直接剪輯」能力可把下載、預覽、提交整合在同一個介面，縮短完成素材的時間。

## What Changes

- 在下載檔案列表新增「編輯」入口，進入獨立音訊編輯頁。
- 編輯頁提供波形、時間軸、縮放、多段刪除區塊標記、整檔音量調整。
- 新增伺服器端預覽流程：使用者按下更新預覽後，由後端產生暫存預覽檔供播放。
- 新增提交流程：可選擇另存新檔或覆蓋原檔。
- 覆蓋原檔前先產生備份檔，且覆蓋模式必須與原檔格式一致。
- 支援輸出格式 `mp3` 與 `m4a`，並盡量沿用原檔音質參數。
- 新增暫存預覽檔生命週期管理（取消/提交即刪除，並定時清理殘留檔案）。

## Capabilities

### New Capabilities

- `post-download-audio-editing`: 下載完成後，使用者可在內建編輯器進行多段刪除、音量調整、預覽與輸出提交。

### Modified Capabilities

- (none)

## Impact

- Affected specs: `post-download-audio-editing`
- Affected code: `index.html`, `server.py`, `tests/test_server_api.py`, `tests/test_server_jobs.py`, 新增編輯頁與其測試檔。
- Affected APIs: 新增 `/edits/preview`、`/edits/previews/{preview_id}`、`/edits/commit`、`/edits/previews/{preview_id}`(DELETE)
- Dependencies: 前端引入 Wavesurfer.js（CDN）；後端持續依賴 ffmpeg/ffprobe。
