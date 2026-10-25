# Discord Bot 設定步驟

> **已經照舊版步驟邀請過 bot 的話：** 這一版多了 **Add Reactions** 權限。請重新做一次「5-1 產生邀請連結」（這次勾四個權限），再貼到瀏覽器授權一次，權限就會更新。

這份文件帶你做四件事：

1. 在 Discord Developer Portal 建立 application 和 bot
2. 打開 Message Content Intent
3. 拿到 bot token
4. 把 bot 邀進你自己的 Server

> 開始前請先做完 `docs/discord-server-setup.md`（你要有自己的 Server 和 `CHANNEL_ID`）。
>
> Developer Portal 只有英文介面，下面的按鈕名稱直接照英文找。

---

## ⚠️ 先看這個：bot token 的規則

**bot token 是 bot 的登入密碼。誰拿到這串文字，誰就能完全冒充你的 bot。**

| 絕對不可以 | 原因 |
|---|---|
| 貼給任何人（包含同學、朋友） | 對方可以操控你的 bot |
| **貼進這個對話（Claude Code 的對話框）** | 對話內容可能被記錄；也會變成日後被轉貼的風險 |
| 貼在 Discord 的任何頻道 | Discord 會自動偵測並使它失效，而且別人也看得到 |
| **commit 進 git、推上 GitHub** | 公開後幾分鐘內就會被機器人掃走 |
| 截圖時露出來 | 同上 |
| 寫進程式碼或 docs 裡的文件 | 同上 |

**token 只能存在一個地方：你電腦上專案資料夾裡的 `.env` 檔**（本文件最後一節教你建立）。`.env` 已經被 `.gitignore` 擋住，不會被 commit。

**如果不小心貼出去了：** 馬上回到 Developer Portal 的 Bot 頁面按 **Reset Token**（步驟 3），舊的 token 立刻失效。這個動作是免費的，寧可多按。

---

## 一、建立 application 和 bot

**application** 是 Discord 裡的一個「應用程式」資料夾；**bot** 是這個應用程式底下、真正能在 Server 裡發言的機器人帳號。

1. 打開瀏覽器，進入 **https://discord.com/developers/applications**。
2. 用你平常的 Discord 帳號登入（會自動帶入）。
3. 右上角按 **New Application**。
4. **Name** 欄位輸入名字，例如 `食譜機器人`。這會是 bot 在 Server 裡顯示的名字。
5. 勾選同意條款（Discord Developer Terms of Service 和 Developer Policy）。
6. 按 **Create**。

接著會進到這個 application 的設定頁，**左邊有一排選單**（General Information、Installation、OAuth2、Bot……）。

7. 點左邊選單的 **Bot**。
   - 新的 application 通常已經自動有一個 bot。如果頁面上出現 **Add Bot** 之類的按鈕，按它並確認。

---

## 二、打開 Message Content Intent

### 這是什麼、為什麼一定要打開

**Intent**（權限開關）是 Discord 規定的：bot 要事先聲明「我想收到哪一類資訊」，沒聲明就收不到。

**Message Content Intent** 的意思是「bot 可以看到別人訊息的內容」。

Discord 對這個開關特別嚴格，沒打開時，bot 雖然會收到「有人傳了訊息」的通知，但**訊息的文字、附件（也就是食材照片）都是空的**。我們的 agent 靠的就是附件裡的照片，所以**一定要打開**，否則 bot 看起來上線了，卻什麼照片都收不到。

> 在少於 100 個 Server 的 bot，可以直接打開，不需要審核。你的 bot 只在你自己的 Server，沒問題。

### 步驟

1. 在左邊選單點 **Bot**。
2. 往下捲，找到 **Privileged Gateway Intents** 這一區。
3. 找到 **Message Content Intent**，把右邊的開關**打開**（變成藍色／綠色）。
4. 其他兩個（Presence Intent、Server Members Intent）**不用開**。
5. 頁面下方會跳出一條「Careful — you have unsaved changes!」的提示，按 **Save Changes**。

> 沒存檔的話，開關會跳回去。存完後可以重新整理頁面，確認開關還是打開的。

---

## 三、拿到 bot token

1. 還在左邊選單的 **Bot** 頁面。
2. 找到 **Token** 這一區，按 **Reset Token**。
3. 跳出確認視窗，按 **Yes, do it!**。（如果你的帳號有開雙重驗證，會要你輸入驗證碼。）
4. 畫面上會出現一長串 token，旁邊有 **Copy** 按鈕。按 **Copy**。
5. **馬上**照本文件最後一節的做法，貼進 `.env`。先不要貼到別的地方。

> **token 只會顯示這一次。** 離開頁面後就看不到完整內容，要用只能再按 Reset Token 重新產生一個（舊的就失效）。所以複製後請立刻存好。
>
> 提醒：不要把它貼進 Claude 對話，不要截圖。

---

## 四、只讓你自己能邀請 bot（建議）

1. 還在 **Bot** 頁面，往下找 **Public Bot**。
2. 把它**關掉**。這樣只有你（application 的擁有者）能把 bot 邀進 Server，別人拿到邀請連結也加不了。
3. 找到 **Requires OAuth2 Code Grant**，確認它是**關閉**的（預設就是關）。
4. 按 **Save Changes**。

---

## 五、把 bot 邀進你的 Server

### 5-1 產生邀請連結

1. 左邊選單點 **OAuth2**。
2. 往下找到 **OAuth2 URL Generator**（OAuth2 網址產生器）。
3. **SCOPES**（範圍）這一區，只勾 **`bot`**。
   - 不要勾 `applications.commands`，這一版用不到。
4. 勾了 `bot` 之後，下面會出現 **BOT PERMISSIONS**（權限）這一區。只勾這四個：

   | 權限 | 為什麼需要 |
   |---|---|
   | **View Channels** | 讓 bot 看得到頻道 |
   | **Send Messages** | 讓 bot 能回覆「處理中」和食譜 |
   | **Read Message History** | 讓 bot 能「回覆」某則特定訊息（回覆原照片需要） |
   | **Add Reactions** | 讓 bot 能在收到的照片上加 ⏳ 表示排隊中，處理完再拿掉 |

   **其他全部不要勾**，尤其不要勾 **Administrator**（管理員）。bot 只做這三件事，給越少越安全。
   > bot 移除自己加的 ⏳ 反應，不需要額外權限。

5. 往下捲到最下面，**GENERATED URL** 會出現一串網址。按旁邊的 **Copy**。
   - 這是**邀請連結**，不是 token，可以放心使用，但不需要分享給別人。

### 5-2 邀請 bot 進 Server

1. 把剛才複製的網址貼到瀏覽器網址列，按 Enter。
2. 頁面會問你「要把這個 bot 加到哪個伺服器」。在下拉選單中選你自己的 Server（例如 `食譜機器人測試`）。
   - 如果下拉選單裡沒有你的 Server，代表你登入的 Discord 帳號不是那個 Server 的擁有者／管理員，請確認登入的是同一個帳號。
3. 按 **繼續**（Continue）。
4. 畫面列出 bot 會得到的權限（應該只有上面四個）。確認後按 **授權**（Authorize）。
5. 可能出現「我不是機器人」的驗證，照畫面完成。
6. 看到「已授權」（Authorized）就成功了。

### 5-3 確認 bot 進來了

1. 回到 Discord，打開你的 Server。
2. 右邊的成員清單（如果沒有看到，按右上角的「成員」圖示）會多出 `食譜機器人`，旁邊有個 **BOT** 標籤。
3. 此時它是**離線（灰色）**，這是正常的。要等你之後啟動 agent 程式，它才會變成上線。

### 5-4 只讓 bot 在 `#食譜` 發言（建議）

程式本身只會處理 `CHANNEL_ID` 那個頻道，但在 Discord 這邊也限制一次更保險：

1. 在 Server 的頻道清單，對 `#食譜` 按**滑鼠右鍵** → **編輯頻道**（Edit Channel）。
2. 左邊選 **權限**（Permissions）。
3. 確認 `食譜機器人`（或它自動產生的身分組，名字跟 bot 相同）在清單中，且 **查看頻道**、**傳送訊息**、**讀取訊息歷史**、**新增反應** 都是綠色勾。
4. 其他頻道不用特別設定，因為我們沒有給 bot 任何在別處做事的理由；如果想更嚴格，可以在其他頻道把這個身分組的「查看頻道」設為禁止。

---

## 六、把設定寫進 `.env`

`.env` 是放在專案資料夾（`C:\Users\Penny\recipe`）裡的一個純文字檔，程式啟動時會讀它。**它是 token 唯一應該存在的地方。**

### 6-1 先建立資料夾（放照片和 Excel 的地方）

1. 打開檔案總管。
2. 到 `C:\Users\Penny\`，在空白處按右鍵 → **新增** → **資料夾**。
3. 取名 `recipe-data`。

這個資料夾放在 `recipe` 專案**外面**，這樣不會被誤 commit。

### 6-2 建立 `.env` 檔

> **小心：** 記事本存檔時，很容易自己加上 `.txt`，變成 `.env.txt`，程式就讀不到。請照下面步驟存。

1. 按 Windows 的**開始**，搜尋 **記事本**，打開。
2. 貼上這四行，然後把右邊換成你自己的值：

   ```
   DISCORD_TOKEN=貼上剛才複製的 token
   CHANNEL_ID=貼上你複製的頻道 ID 數字
   CLAUDE_MODEL=sonnet
   DATA_DIR=C:\Users\Penny\recipe-data
   ```

   規則：
   - `=` 兩邊**不要有空格**。
   - 值**不要加引號**。
   - `CLAUDE_MODEL` 先填 `sonnet`，之後可改。
3. 按 `Ctrl + S` 存檔。
4. 在存檔視窗：
   - 位置選 `C:\Users\Penny\recipe`。
   - **存檔類型**（Save as type）選 **「所有檔案」**（All Files）。
   - **檔案名稱**輸入 `.env`（前面有個點，沒有其他字）。
   - 按 **存檔**。
5. 關掉記事本。

### 6-3 確認 `.env` 沒有被 git 追蹤

1. 在 `C:\Users\Penny\recipe` 資料夾上方按右鍵 → 在終端機開啟（或在 Claude Code 裡輸入 `! git status`）。
2. 輸入 `git status`。
3. 輸出裡**不應該**出現 `.env`。（`.gitignore` 已經擋掉了。）如果出現了，**不要 commit**，先告訴我。

---

## 七、做完後確認

- [ ] Developer Portal 有你的 application，Bot 頁面存在。
- [ ] **Message Content Intent 是開著的**，而且已按 Save Changes。
- [ ] Public Bot 是關閉的。
- [ ] 邀請連結只勾了 `bot`，權限只有 View Channels、Send Messages、Read Message History、Add Reactions。
- [ ] Server 成員清單看得到 `食譜機器人`（BOT 標籤，離線是正常的）。
- [ ] `C:\Users\Penny\recipe\.env` 有四項設定，且檔名是 `.env`（不是 `.env.txt`）。
- [ ] `git status` 看不到 `.env`。
- [ ] token 沒有貼在任何其他地方（對話、截圖、Discord 頻道、文件）。

## 常見問題

| 狀況 | 原因與處理 |
|---|---|
| 下拉選單找不到我的 Server | 登入的 Discord 帳號不是 Server 擁有者／管理員。換成建立 Server 的那個帳號。 |
| 之後 bot 上線了，但傳照片沒反應 | 先回去檢查 **Message Content Intent** 是不是真的打開並存檔。這是最常見的原因。 |
| 之後 bot 看得到頻道卻不能回覆 | 檢查 `#食譜` 的權限，bot 的「傳送訊息」和「讀取訊息歷史」要是允許。 |
| token 貼錯、不見了、或貼到別處 | 回 **Bot** 頁面按 **Reset Token**，產生新的，舊的立即失效；再更新 `.env`。 |
| `.env` 存成了 `.env.txt` | 在檔案總管上方 **檢視** → 勾選 **副檔名**，看到後把 `.txt` 刪掉重新命名。 |
