# recipe

一支跑在本機的 Discord agent：指定頻道裡有人傳食材照片，就用 `claude -p` 辨識食材、推薦料理與食譜，建檔到 Excel、存照片，並回覆上傳者。

設計說明在 [`docs/architecture.md`](docs/architecture.md)，需求在 [`docs/requirements.md`](docs/requirements.md)。

## 第一次使用

1. 照 [`docs/discord-server-setup.md`](docs/discord-server-setup.md) 建好 Server 和頻道。
2. 照 [`docs/discord-bot-setup.md`](docs/discord-bot-setup.md) 建好 bot、打開 Message Content Intent、授權 **Add Reactions** 等權限，並建立 `.env`。
3. 安裝套件：

   ```
   uv sync
   ```

## 啟動 agent

在專案資料夾（`recipe`）打開終端機：

```
uv run python -m recipe_agent
```

- 看到頻道出現「食譜機器人上線了！」就是成功。
- 要關掉：在終端機按 `Ctrl + C`，頻道會出現「食譜機器人下線了。」
- agent 開著才會處理照片；關掉期間傳的照片開機後**不會**補處理。
- Excel 若正被你打開，agent 會在終端機印出 `[警告]` 並重試；仍寫不進去時，該筆紀錄先存在 `DATA_DIR\pending_records.jsonl`，下次寫入時補寫。

## 看 log（處理過程的紀錄）

處理每一件工作時，終端機會即時印出進度，同樣的內容也寫進 `DATA_DIR\logs\agent.log`（超過約 2 MB 會自動換檔，保留最近 3 份）。一件成功的工作大致長這樣：

```
收到照片訊息，已排隊｜上傳者=小明 (123…)｜照片=1 張｜前面還有 0 件
開始處理｜上傳者=小明 (123…)｜照片=1 張
下載完成｜可用照片=1 張｜略過=0 張
啟動 claude -p（1 張照片，模型=sonnet）
claude -p 完成｜花了 8.9 秒
分析完成｜是否為食材=是｜辨識到=番茄｜料理=番茄炒蛋
照片已存檔｜2026-10-25 14-03-39 番茄.jpg
已回覆上傳者｜共 1 則訊息
已寫入 Excel｜recipes.xlsx
處理結束｜結果=成功｜上傳者=小明 (123…)｜花了 9.0 秒
```

失敗、被擋掉的訊息（不支援的附件、同一個人連傳）、Excel 寫不進去，也都會留下一行。log 裡不會出現 token，也不會寫出完整食譜內容。

## 跑測試

```
uv run pytest
```

## 資料放哪裡

`.env` 的 `DATA_DIR` 指向的資料夾（這個資料夾**不要**放進 git）：

```
<DATA_DIR>\
├─ recipes.xlsx           紀錄（一直往下加）
├─ pending_records.jsonl  Excel 寫不進去時的暫存（平常不存在）
├─ photos\                存下來的照片，檔名「YYYY-MM-DD hh-mm-ss 主要食材簡稱.jpg」
└─ logs\agent.log         錯誤與警告細節
```

## 四段安全防護在哪裡

每一段都用這樣的註解框起來，**一開始全部開啟**：

```
# ==== 防護 N：<說明>　開始 ====
...
# ==== 防護 N 結束 ====
```

要「關掉」某一段，把兩個標記之間的內容整段註解掉就好，程式仍能執行。搜尋 `防護 N：` 就能找到。

| 防護 | 檔案 | 約在第幾行 | 做什麼 |
|---|---|---|---|
| 防護 1：claude -p 的檔案範圍隔離 | `src/recipe_agent/claude_runner.py` | 72～76 | 把 `claude -p` 的工作目錄限制在「只有這一件照片」的暫存資料夾，只給它讀檔工具，不把 `DISCORD_TOKEN` 交給它 |
| 防護 2：上傳者打的字只當資料 | `src/recipe_agent/claude_runner.py` | 52～54 | 丟掉上傳者打的字，給 `claude -p` 的提示詞只用固定範本 |
| 防護 3：主要食材簡稱清洗 | `src/recipe_agent/photo_store.py` | 53～65 | 檔名前先清掉 `/`、`\`、`..`、冒號等會讓路徑亂跑的字，並檢查最後落點仍在照片資料夾裡 |
| 防護 4：Excel 文字轉純文字 | `src/recipe_agent/record_store.py` | 159～163 | 儲存格文字以 `=`、`+`、`-`、`@` 開頭時，處理成純文字，避免被當成公式 |

行號是寫這份 README 當下的位置，改過程式後可能偏移幾行，以搜尋為準。

關掉某一段之後，跑 `uv run pytest` 會看到對應那段的測試開始失敗，可以用來對照效果。

## 不可以 commit 的東西

- `.env`（內含 `DISCORD_TOKEN`）
- `DATA_DIR` 裡的照片、Excel、log

這些已經寫在 `.gitignore`。commit 前先看一下 `git status`。
