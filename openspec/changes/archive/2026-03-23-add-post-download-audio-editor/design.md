## Context

目前系統以下載任務為核心，完成後只提供檔案列表與下載連結。使用者若要刪除片段或調整音量，必須轉到外部軟體，造成操作中斷。此變更需跨前端頁面、後端 API、轉檔流程與暫存檔生命週期管理，屬於跨模組設計。

## Goals / Non-Goals

**Goals:**

- 在現有 UI 中新增「下載後剪輯」完整流程（進入編輯頁、預覽、提交）。
- 以後端 ffmpeg 產生預覽與最終輸出，確保結果一致性。
- 支援多段刪除與整檔音量調整。
- 提供另存與覆蓋兩種提交模式，覆蓋需可回復。
- 控制暫存檔成長，避免磁碟持續累積。

**Non-Goals:**

- 不實作 undo/redo 歷史堆疊。
- 不實作區段別音量 automation 或特效鏈。
- 不改造現有下載佇列架構。
- 不引入前端打包系統（維持靜態頁面架構）。

## Decisions

### 使用獨立編輯頁承載波形編輯流程
- Decision: 從檔案列表進入獨立編輯頁（例如 `/editor?file=...`）。
- Rationale: 波形、區塊清單、播放控制與提交操作需要較大版面；獨立頁可降低首頁複雜度並簡化狀態管理。
- Alternative considered: 首頁彈窗或內嵌展開；兩者都會使佇列頁面狀態管理與響應式排版明顯複雜。

### 前端使用 Wavesurfer.js，後端負責預覽與最終輸出
- Decision: 前端用 Wavesurfer.js（CDN）處理波形顯示、縮放與區塊標記；後端以 ffmpeg 產生預覽檔與最終檔。
- Rationale: 可快速獲得可用的波形互動，同時維持「預覽結果 = 最終輸出」一致性。
- Alternative considered: 前端 ffmpeg.wasm；在大檔案時記憶體與效能風險較高，且整合成本較大。

### 以預覽 ID 驅動提交，避免重複計算
- Decision: `POST /edits/preview` 產生 `preview_id`；`POST /edits/commit` 以 `preview_id` 直接提交。
- Rationale: 提交時不需再次計算相同 filter，降低等待時間並確保提交內容與預覽一致。
- Alternative considered: 提交時重算；雖可減少暫存檔管理，但會增加 CPU 使用與結果偏差風險。

### 覆蓋原檔採備份先行與同格式限制
- Decision: 覆蓋模式必須與原檔格式一致，且先產生 `.bak.<timestamp>` 再替換原檔。
- Rationale: 避免副檔名與實際編碼不一致，並保留回復能力。
- Alternative considered: 直接覆蓋不備份；風險高且無法回復。

### 暫存檔採雙層清理策略
- Decision: 使用者取消或提交後立即刪除預覽檔，另以背景清理器週期掃描過期暫存（例如 TTL 2 小時）。
- Rationale: 平衡即時清理與異常中斷場景，避免磁碟膨脹。
- Alternative considered: 僅定時清理；短時間可能堆積大量暫存。

## Risks / Trade-offs

- [ffmpeg filter 組裝複雜度] → 以區段正規化（排序、合併、越界檢查）與單元測試覆蓋核心路徑。
- [預覽檔殘留] → 預覽即時刪除 + TTL 清理 + 啟動時清理一次歷史檔。
- [音質「盡量沿用」仍需重編碼] → 使用 ffprobe 擷取來源 bitrate 作為輸出參考，缺值 fallback 192k。
- [CDN 依賴可用性] → 若 CDN 載入失敗，編輯頁顯示明確錯誤並禁止提交，避免產生不完整輸出。
