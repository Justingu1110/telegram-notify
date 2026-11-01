# telegram-notify

通用的網頁監控工具：定時檢查網頁上列出的商品，一有新品上架或補貨，就用 Telegram 通知你。目前監控的是丸久小山園的抹茶頁面（https://www.marukyu-koyamaen.net/category/select/cid/312），之後可以加其他網站。

用詞（Watch、Product、Baseline、Event 等）的定義在 [`GLOSSARY.md`](GLOSSARY.md)，重要決定記在 [`docs/adr/`](docs/adr/)。

## 運作方式

- 每 15 分鐘，一個外部定時器呼叫 GitHub Actions 的工作流程 `check.yml`，它執行 `python -m telegram_notify`（細節見「定時執行」）。
- 程式依序檢查 `watches.toml` 裡的每個 **Watch**（監控項目）：讀列表頁，再讀每件 **Product**（商品）的詳細頁取得庫存。
- 新增一個 Watch 後的第一次檢查只建立 **Baseline**（基準線），發一則「監控已啟動，目前記錄 N 件商品」，不逐件通知。
- 之後偵測兩種 **Event**（事件），各發一則 **Notification**（通知）：
  - **New Product**（新品上架）：出現從沒見過的商品。
  - **Restock**（補貨）：商品從缺貨變成有庫存（從列表消失後回來，或庫存文字從缺貨用語變回「有库存」）。
- 網頁連不上、讀不出來或解析不到任何商品，算一次 **Failure**（失敗），不會動到已記錄的商品；連續失敗 3 次發一則 **Warning**（警告），成功一次就歸零。
- 沒看過的庫存文字不產生任何 Event，也不改變原本的狀態，只記錄原文。
- 已知商品的紀錄存在本 repo 的 `state` 分支（`state.json`），不放 `main`，所以每次執行都從上次的狀態接續。

## 第一次設定

### 1. Telegram

1. 在 Telegram 找 **@BotFather**，傳 `/newbot` 建立一個 Bot，記下它給的 **token**。
2. 對你新建的 Bot 按 Start 並傳一句話（沒做這步，Bot 之後無法傳訊息給你）。
3. 查你的 **Chat ID**：把 token 帶進 `https://api.telegram.org/bot<token>/getUpdates`，在結果裡找 `"chat":{"id":` 後面的數字。也可以用 Telegram 上的 @userinfobot。
4. 先驗證能不能傳訊息：`https://api.telegram.org/bot<token>/sendMessage?chat_id=<Chat ID>&text=hi`，看到 `"ok":true` 並且收到「hi」就對了。

token 是密碼，不要貼到任何對話、issue 或檔案裡。

### 2. GitHub Actions Secrets

到 repo 的 Settings → Secrets and variables → Actions → **New repository secret**，新增兩個（名稱要一字不差）：

- `TELEGRAM_BOT_TOKEN`：上面的 token
- `TELEGRAM_CHAT_ID`：上面的 Chat ID

GitHub 會把它們在日誌裡遮成 `***`，存進去之後也沒有任何方式再讀出內容。

## 定時執行

GitHub 自己的排程（`schedule`）在這個 repo 實測沒有觸發過，所以改由一個外部的免費定時服務（Cloudflare Workers 的 Cron Trigger）每 15 分鐘呼叫一次工作流程的「手動觸發」。GitHub 的排程仍保留當備援，重複觸發不會重複通知（見 [`docs/adr/0002-trigger-from-an-external-timer.md`](docs/adr/0002-trigger-from-an-external-timer.md)）。

定時器送出的請求：

- 網址：`https://api.github.com/repos/Justingu1110/telegram-notify/actions/workflows/check.yml/dispatches`
- 方法：`POST`，內容：`{"ref":"main"}`，成功的回應是 HTTP 204
- 標頭：`Authorization: Bearer <權杖>`、`Accept: application/vnd.github+json`、`User-Agent`（GitHub 要求一定要有）
- 權杖：fine-grained，只選這個 repo，權限只要 **Actions: Read and write**，90 天到期。**到期前要建立新的，並更新 Cloudflare Worker 的 `GITHUB_TOKEN` Secret**，否則檢查會悄悄停止（目前這一個約在 2027-01-30 到期）。

任何時候想立刻檢查一次：到 repo 的 Actions → **Check the watches** → **Run workflow** → 分支選 `main`。

## 新增一個 Watch

1. **同一個網站的另一個分類頁**：在 `watches.toml` 加一段，`parser` 沿用 `"marukyu"`：

   ```toml
   [[watch]]
   name = "丸久小山園 煎茶"
   url = "https://www.marukyu-koyamaen.net/category/select/cid/315"
   parser = "marukyu"
   ```

   `name` 要唯一，而且**改名會被當成全新的 Watch**（重新建立 Baseline、再發一次啟動通知）。上面的網址只是範例，其他分類頁的版面是否跟抹茶頁一樣沒有驗證過，新增後請先手動執行一次，確認「監控已啟動」的商品件數正確。

2. **另一個網站**：還要為它寫一個解析程式。在 `telegram_notify/parsers/` 新增一個檔案，提供兩個函式，並在 `telegram_notify/parsers/__init__.py` 的 `PARSERS` 登記：
   - `parse_list(html)`：回傳這一頁所有 Product（ID、品名、價格、詳細頁網址、配送說明）的清單。
   - `parse_stock(html)`：從商品詳細頁回傳庫存原文與狀態（有庫存、缺貨、不明）；讀不到就回傳 `None`。

3. **取得測試資料**：開發環境連不到商店，所以真實網頁要靠 GitHub Actions 抓。工作流程 **Capture Marukyu fixtures**（`.github/workflows/capture-fixtures.yml`，從 Actions 頁面手動觸發）會把網頁原始碼存進 `tests/fixtures/marukyu/`；它目前只會抓丸久小山園，新網站要複製 `scripts/capture_marukyu_fixtures.sh` 與那個工作流程，改成新的網址。

4. **寫測試**：測試只從「執行一次檢查」進去，網頁、Telegram、紀錄三處換成假的，用上一步抓回的真實網頁（可參考 `tests/test_run_check.py`）。

5. **觸發時間**：目前所有 Watch 共用同一個定時器（每 15 分鐘）。讓每個 Watch 各自設定觸發時間，另外規劃在 issue #12。

## 開發

需要 Python 3.11 以上（設定檔用內建的 `tomllib` 讀取）。安裝相依套件並執行測試：

```bash
pip install -r requirements-dev.txt
python3 -m pytest
```

核心測試從「執行一次檢查」進行；真實的網頁取得、Telegram 發送、紀錄存取，則用本機的假伺服器與暫時的 git 儲存庫測試。

### 在本機執行一次檢查

```bash
export TELEGRAM_BOT_TOKEN='（BotFather 給的 token）'
export TELEGRAM_CHAT_ID='（要接收通知的 Chat ID）'
python3 -m telegram_notify
```

注意：這會**真的**向商店發請求、真的傳 Telegram 訊息，並把紀錄推到目前這個 repo 的 `origin` 的 `state` 分支（所以需要有寫入 `origin` 的權限）。只想試跑的話，請在一個暫時的 clone 裡執行，或改用另一個 Chat ID。缺少任何一個環境變數時會直接停止並說明缺哪個。

## 檔案

- `watches.toml`：要監控的 Watch。
- `telegram_notify/`：程式。`check.py` 是「執行一次檢查」，`parsers/` 是各網站的解析程式，`fetcher.py`、`telegram.py`、`statestore.py` 分別負責網頁取得、Telegram 發送、紀錄存取。
- `tests/`：測試與真實網頁樣本（`tests/fixtures/`）。
- `.github/workflows/`：`check.yml`（定時檢查）、`capture-fixtures.yml`（抓測試用的網頁）。
- `docs/adr/`：重要決定的紀錄。
