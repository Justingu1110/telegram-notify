#!/usr/bin/env python3
import json
import os
import re
import sys
import requests

MONITOR_URLS = [
    "https://www.marukyu-koyamaen.net/category/select/cid/312",
]

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "matcha_monitor_state.json")

ITEM_PATTERN = re.compile(
    r'pid/(\d+)"[^>]*>\s*<img[^>]*/>\s*</a>\s*</div>\s*<div class="data clearfix">'
    r'.*?<h3><a href="([^"]*)">(.*?)</a></h3>.*?<div class="price">(.*?)</div>'
    r'(?:\s*<div class="text">(.*?)</div>)?',
    re.S,
)


def clean_shipping_text(raw):
    if not raw:
        return ""
    raw = re.sub(r"<[^>]*$", "", raw)  # drop a tag the site's own truncation left half-open
    text = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", text).strip()


def fetch_products(url):
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    products = {}
    for pid, link, name, price, shipping in ITEM_PATTERN.findall(resp.text):
        products[pid] = {
            "name": name.strip(),
            "price": price.strip(),
            "url": link.strip(),
            "shipping": clean_shipping_text(shipping),
        }
    return products


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_telegram_message(text):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=15,
    )
    resp.raise_for_status()


def main():
    state = load_state()
    state_changed = False

    for url in MONITOR_URLS:
        try:
            current = fetch_products(url)
        except requests.RequestException as e:
            print(f"[WARN] fetch failed for {url}: {e}", file=sys.stderr)
            continue

        if not current:
            print(f"[WARN] no products parsed for {url}, skipping (selector may be stale)", file=sys.stderr)
            continue

        previous_pids = set(state.get(url, {}).keys())
        current_pids = set(current.keys())
        new_pids = current_pids - previous_pids

        if url not in state:
            print(f"[INFO] first run for {url}, saving baseline of {len(current)} products, no notification sent")
        elif new_pids:
            for pid in new_pids:
                p = current[pid]
                lines = ["🆕 新品上架通知", "", p["name"], f"價格: {p['price']}"]
                if p["shipping"]:
                    lines.append(f"⚠️ {p['shipping']}")
                lines.append(p["url"])
                send_telegram_message("\n".join(lines))
                print(f"[INFO] notified new product {pid}: {p['name']}")

        state[url] = current
        state_changed = True

    if state_changed:
        save_state(state)


if __name__ == "__main__":
    main()
