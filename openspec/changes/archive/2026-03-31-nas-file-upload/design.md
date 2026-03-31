## Context

目前系統架構為單一 Python HTTP server (`server.py`)，提供下載管理與音訊編輯功能。下載的檔案儲存在本機 `downloads/` 目錄。前端為純 HTML + vanilla JS（`index.html` 與 `editor.html`）。

使用者希望能從檔案列表直接將檔案傳送到 Synology NAS，透過 FileStation REST API 實現。

## Goals / Non-Goals

**Goals:**

- 透過環境變數管理 NAS 連線設定，不需修改程式碼即可配置
- 在 server 端封裝 Synology FileStation API 的登入、上傳、登出流程
- 提供 `POST /nas/upload` endpoint 供前端呼叫
- 在首頁檔案列表提供「傳到 NAS」按鈕與狀態回饋

**Non-Goals:**

- 不支援 NAS → 本機的反向同步
- 不支援在 UI 中修改 NAS 設定
- 不支援自動觸發上傳
- 不支援 Synology 以外的 NAS

## Decisions

### 使用環境變數管理 NAS 連線設定

NAS 帳密屬於敏感資訊，透過環境變數（`NAS_HOST`、`NAS_PORT`、`NAS_USER`、`NAS_PASSWORD`、`NAS_UPLOAD_PATH`）管理，避免寫入程式碼或設定檔後意外 commit。

**替代方案**：JSON 設定檔 — 方便但有洩漏風險；寫死在 server.py — 不靈活。

### 使用 Synology FileStation API 上傳

透過 FileStation `SYNO.FileStation.Upload` API 進行檔案上傳。流程：

1. 呼叫 `SYNO.API.Auth` 取得 session ID (`sid`)
2. 使用 `sid` 呼叫 `SYNO.FileStation.Upload` 上傳檔案（multipart/form-data）
3. 呼叫 `SYNO.API.Auth` 登出釋放 session

每次上傳獨立建立 session，避免 session 過期問題。使用 Python 標準庫（`urllib.request` + `http.client`）實作，不需額外依賴。

**替代方案**：SMB 掛載 — 需預先掛載且限同網段；rsync — 需 SSH 設定。

### Server 端新增 `POST /nas/upload` endpoint

接收 JSON body `{ "file_name": "xxx.mp3" }` 後：
1. 檢查環境變數是否已設定
2. 驗證檔案存在於 `downloads/` 目錄
3. 執行 FileStation API 上傳流程
4. 回傳 JSON 結果（成功或錯誤訊息）

### 前端按鈕與狀態回饋

在 `index.html` 每個檔案項目旁新增「傳到 NAS」按鈕。按下後：
- 按鈕顯示 loading 狀態（disabled + 文字變更）
- 成功後短暫顯示 ✓ 標記
- 失敗時顯示錯誤訊息

NAS 未設定時（endpoint 回傳 501），按鈕隱藏或 disabled。

## Risks / Trade-offs

- [NAS 連線失敗] → 上傳 API 回傳明確錯誤訊息，前端顯示給使用者
- [Session 過期] → 每次上傳獨立建立 session，不快取 sid
- [大檔案上傳耗時] → 前端顯示 loading 狀態，server 端同步上傳（目前不需非同步，檔案通常為音訊大小）
- [環境變數未設定] → server 啟動時偵測並 log 警告，API 回傳 501 Not Configured
