## Why

使用者下載音訊檔案後，常需要將檔案手動傳送到 Synology NAS 進行備份或歸檔。目前沒有內建的傳送機制，使用者必須自己透過 Finder 或其他工具操作。整合 Synology FileStation REST API，讓使用者可以直接從檔案列表一鍵傳送到 NAS。

## What Changes

- 新增 NAS 連線設定（透過環境變數：`NAS_HOST`、`NAS_PORT`、`NAS_USER`、`NAS_PASSWORD`、`NAS_UPLOAD_PATH`）
- Server 端新增 Synology FileStation API 整合模組（登入 → 上傳 → 登出）
- Server 端新增 `POST /nas/upload` API endpoint
- 首頁檔案列表 (`index.html`) 每個檔案項目新增「傳送到 NAS」按鈕
- 上傳過程中顯示狀態回饋（進行中、成功、失敗）

## Non-Goals (optional)

- 不支援從 NAS 下載或同步檔案回本機
- 不支援在 UI 中設定或變更 NAS 連線參數（透過環境變數管理）
- 不支援自動傳送（僅手動觸發）
- 不支援 Synology 以外的 NAS 品牌

## Capabilities

### New Capabilities

- `nas-file-upload`: 透過 Synology FileStation API 將本機下載的檔案上傳到 NAS 指定路徑

### Modified Capabilities

（無）

## Impact

- 受影響的程式碼：`server.py`（新增 endpoint 與 NAS 模組）、`index.html`（新增上傳按鈕與狀態顯示）
- 新增依賴：無（使用 Python 標準庫 `urllib` / `http.client` 呼叫 REST API）
- 環境變數：新增 5 個 NAS 相關環境變數
