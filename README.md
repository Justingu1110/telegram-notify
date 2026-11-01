# telegram-notify

抹茶商品新上架監控：定時抓取丸久小山園官網商品頁，比對是否有新商品，有的話透過 Telegram Bot 發通知（含商品名稱、價格、配送限制說明）。

監控網址：https://www.marukyu-koyamaen.net/category/select/cid/312

> 專案正在改寫成通用的網頁監控工具（規格見 issue #1）。下面的「開發」是新版，「檔案」以後的內容是舊版腳本，改寫完成後會整份更新。

## 開發

需要 Python 3.11 以上（設定檔用內建的 `tomllib` 讀取）。安裝相依套件並執行測試：

```bash
pip install -r requirements-dev.txt
python3 -m pytest
```

- 要監控的網頁寫在 `watches.toml`，每個 `[[watch]]` 是一個 Watch（名稱、網址、使用哪個網站解析程式）。
- 核心測試從「執行一次檢查」進行，網頁、Telegram、紀錄三處換成假的；網頁用 `tests/fixtures/marukyu/` 裡抓回來的真實原始網頁碼。真實的網頁取得、Telegram 發送、紀錄存取，則用本機的假伺服器與暫時的 git 儲存庫測試。

### 在本機執行一次檢查

```bash
export TELEGRAM_BOT_TOKEN='（BotFather 給的 token）'
export TELEGRAM_CHAT_ID='（要接收通知的 Chat ID）'
python3 -m telegram_notify
```

注意：這會**真的**向商店發請求、真的傳 Telegram 訊息，並把紀錄推到目前這個 repo 的 `origin` 的 `state` 分支（所以需要有寫入 `origin` 的權限）。只想試跑的話，請在一個暫時的 clone 裡執行，或改用另一個 Chat ID。缺少任何一個環境變數時會直接停止並說明缺哪個。token 只放在環境變數或 GitHub Actions Secrets，不要寫進任何檔案。

## 檔案

- `matcha_monitor.py` — 主程式。抓取商品頁、解析商品清單、比對狀態、發送 Telegram 通知。
- `matcha_monitor_state.json` — 執行時產生的狀態檔（記錄目前已知的商品清單），不納入版本控制，執行一次會自動建立。

## 執行環境需求

這個專案目前跑在 Claude Code 雲端環境裡，需要：

1. **環境變數**（Environment variables，不是 Network secrets）：
   - `TELEGRAM_BOT_TOKEN` — Telegram Bot 的 API token
   - `TELEGRAM_CHAT_ID` — 要發送通知的 chat id
2. **網路存取允許清單**（Network access / Allowed domains）需要包含：
   - `www.marukyu-koyamaen.net`
   - `api.telegram.org`
3. Python 套件：`pip install -r requirements.txt`（目前只需要 `requests`）

## 手動執行

```bash
python3 matcha_monitor.py
```

第一次執行只會建立 baseline（`matcha_monitor_state.json`），不會發通知。之後每次執行，若解析到的商品清單比對 state file 有新增的商品，才會發送 Telegram 通知。

## 目前的排程

有一個雲端排程（cron trigger）設定為每小時執行一次 `python3 /home/user/matcha_monitor.py`，trigger id `trig_01A8ghLoKfR3zt6tSNtopsSc`。

這個排程是綁定在特定 session 上執行的，不是跟著這個 repo走——在新 session 裡 clone 這個 repo 並不會自動恢復排程。如果要在新 session 接手，請先確認排程還在跑（用 `list_triggers` 或直接問 Claude「查一下排程狀態」），不需要重新設定；只有在排程被刪除或 session 失效時才需要重新建立。

## 新 session 接手開發的步驟

1. Attach 這個 repo
2. 確認 Environment 的環境變數和網路允許清單符合上面「執行環境需求」
3. 跑一次 `python3 matcha_monitor.py` 確認正常運作
4. 繼續開發（例如加監控其他商品頁網址、調整通知格式）
