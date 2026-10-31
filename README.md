# telegram-notify

抹茶商品新上架監控：定時抓取丸久小山園官網商品頁，比對是否有新商品，有的話透過 Telegram Bot 發通知（含商品名稱、價格、配送限制說明）。

監控網址：https://www.marukyu-koyamaen.net/category/select/cid/312

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
