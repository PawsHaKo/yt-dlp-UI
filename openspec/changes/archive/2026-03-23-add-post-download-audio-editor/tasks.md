## 1. 前端編輯入口與畫面骨架

- [x] 1.1 實作「Users can enter an audio editor from downloaded files」：在下載檔案列表加入編輯入口並導向獨立頁（對應設計：使用獨立編輯頁承載波形編輯流程）
- [x] 1.2 建立 editor 頁面結構與狀態容器，含檔案載入、控制列、區塊清單與提交區

## 2. 波形互動與操作模型

- [x] 2.1 實作「Editor SHALL support waveform-based multi-range deletion and gain control」：整合 Wavesurfer.js 波形、時間軸與縮放（對應設計：前端使用 Wavesurfer.js，後端負責預覽與最終輸出）
- [x] 2.2 完成多段刪除區塊新增/移除/清空與整檔音量滑桿（-20dB 到 +20dB）

## 3. 預覽 API 與後端轉檔

- [x] 3.1 實作「System SHALL generate preview audio on demand」：新增 `POST /edits/preview` 與 `GET /edits/previews/{preview_id}`
- [x] 3.2 以 ffmpeg 建立多段刪除 + 音量 filter pipeline，並以 ffprobe 擷取來源音質參數
- [x] 3.3 以 preview_id 維護暫存預覽中繼資料與檔案映射（對應設計：以預覽 ID 驅動提交，避免重複計算）

## 4. 提交流程與覆蓋安全

- [x] 4.1 實作「System SHALL support save-as and overwrite commit modes」：新增 `POST /edits/commit` 與 save_as/overwrite 分流
- [x] 4.2 實作覆蓋前備份、同格式限制與預設另存命名（對應設計：覆蓋原檔採備份先行與同格式限制）

## 5. 暫存清理與測試

- [x] 5.1 實作「System SHALL manage preview temp lifecycle」：新增 `DELETE /edits/previews/{preview_id}` 並在取消/提交時即刪
- [x] 5.2 建立背景清理機制與 TTL 設定，清理過期暫存（對應設計：暫存檔採雙層清理策略）
- [x] 5.3 補齊單元與 API 測試，覆蓋區段正規化、預覽建立、提交模式、格式限制與清理行為
