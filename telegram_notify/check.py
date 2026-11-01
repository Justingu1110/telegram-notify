from dataclasses import asdict
from html import escape

from .parsers import get_parser

FAILURES_BEFORE_WARNING = 3


def run_check(watches, fetch, notify, store):
    state = store.load()
    try:
        for watch in watches:
            entry = state.setdefault(watch.name, {})
            parse_list = get_parser(watch.parser)
            products, problem = _read_products(parse_list, fetch, watch.url)
            if problem:
                _count_failure(watch, entry, notify, problem)
                continue
            entry["failures"] = 0
            if "products" not in entry:
                notify(f"監控已啟動：{escape(watch.name)}\n目前記錄 {len(products)} 件商品")
                entry["products"] = {p.id: _record(p) for p in products}
                continue
            known = entry["products"]
            for product in products:
                if product.id not in known:
                    notify(_new_product_notification(product))
                    known[product.id] = _record(product)
    finally:
        store.save(state)


def _read_products(parse_list, fetch, url):
    try:
        products = parse_list(fetch(url))
    except Exception as error:
        return [], f"{type(error).__name__}: {error}"
    if not products:
        return [], "解析不到任何商品（網站可能改版）"
    return products, None


def _count_failure(watch, entry, notify, problem):
    failures = entry.get("failures", 0) + 1
    if failures == FAILURES_BEFORE_WARNING:
        notify(f"⚠️ 監控異常：{escape(watch.name)}\n已連續 {failures} 次檢查失敗\n原因：{escape(problem)}")
    entry["failures"] = failures


def _record(product):
    return {k: v for k, v in asdict(product).items() if k != "id"}


def _new_product_notification(product):
    lines = ["🆕 新品上架通知", "", escape(product.name), f"價格: {escape(product.price)}"]
    if product.shipping:
        lines.append(f"⚠️ {escape(product.shipping)}")
    lines.append(escape(product.url))
    return "\n".join(lines)
