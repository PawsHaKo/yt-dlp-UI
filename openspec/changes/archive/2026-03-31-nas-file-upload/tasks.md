## 1. Server 端 NAS 設定與模組

- [x] 1.1 在 server.py 新增 NAS 環境變數讀取（NAS connection is configured via environment variables），啟動時偵測是否設定完整並 log 警告
- [x] 1.2 實作 Synology FileStation API 模組（使用 Synology FileStation API 上傳）：登入取得 sid、multipart 上傳檔案、登出釋放 session

## 2. Server 端 API Endpoint

- [x] 2.1 Server 端新增 `POST /nas/upload` endpoint（使用環境變數管理 NAS 連線設定），接收 JSON body `{ "file_name": "xxx.mp3" }`，驗證檔案存在後呼叫 FileStation 上傳
- [x] 2.2 實作上傳結果的 JSON 回應（Upload endpoint provides clear error feedback）：成功、404 檔案不存在、501 NAS 未設定、502 NAS 驗證或上傳失敗
- [x] 2.3 新增 `GET /nas/status` endpoint 回傳 NAS 是否已設定，供前端判斷是否顯示按鈕

## 3. 前端 UI

- [x] 3.1 頁面載入時呼叫 `/nas/status`，判斷是否顯示上傳按鈕（UI hides upload button when NAS is not configured）
- [x] 3.2 在 index.html 檔案列表每個項目新增「傳到 NAS」按鈕（Users can upload files to Synology NAS from the file list），含 loading 狀態與成功/失敗回饋（前端按鈕與狀態回饋）
