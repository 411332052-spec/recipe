# CLAUDE.md

一支跑在本機的 Discord agent：指定頻道裡有人傳食材照片，就用 `claude -p` 辨識食材、推薦料理與食譜，建檔到 Excel、存照片，並回覆上傳者。

## 開始任何工作前

先讀 `docs/architecture.md`（架構與設計決定），需求在 `docs/requirements.md`。兩份文件有出入時，以 `docs/architecture.md` 為準，並告訴使用者。

使用者不是寫程式的人：說明用繁體中文、白話，專有名詞第一次出現時用一句話解釋。

## 四段防護

`docs/architecture.md` 第 12 節定義了四段防護。規則：

- 每一段都放在**獨立的函式**裡，並用固定格式的註解標出開始與結束：

  ```python
  # ===== 防護 N 開始：<一句話說明> =====
  ...
  # ===== 防護 N 結束 =====
  ```

- 四段是：防護 1（`claude -p` 看不到 `DATA_DIR`）、防護 2（上傳者的文字只當資料）、防護 3（檔名清洗）、防護 4（Excel 文字轉純文字）。
- **一開始全部開啟。** 不要做成 `.env` 或參數開關；上課時才會手動逐段關掉對照。
- 沒有使用者明確要求，不要關掉、弱化或移除任何一段，也不要為了讓測試通過而繞過它。

## 不可以 commit 的東西

- 不可以把 `.env` commit 進 git（內含 `DISCORD_TOKEN`）。repo 裡只放 `.env.example`，且不含真實值。
- `DATA_DIR` 裡的照片、Excel（`*.xlsx`）、log、`pending_records.jsonl` 也不要 commit。
- 不要把 token 寫進程式碼、文件、log 或對話。
- commit 前先看 `git status`，確認沒有上述檔案。
