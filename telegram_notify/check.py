from dataclasses import asdict
from html import escape

from .parsers import get_parser


def run_check(watches, fetch, notify, store):
    state = store.load()
    try:
        for watch in watches:
            products = get_parser(watch.parser)(fetch(watch.url))
            if watch.name not in state:
                notify(f"監控已啟動：{escape(watch.name)}\n目前記錄 {len(products)} 件商品")
                state[watch.name] = {"products": {p.id: _record(p) for p in products}}
                continue
            known = state[watch.name]["products"]
            for product in products:
                if product.id not in known:
                    notify(_new_product_message(product))
                    known[product.id] = _record(product)
    finally:
        store.save(state)


def _record(product):
    return {k: v for k, v in asdict(product).items() if k != "id"}


def _new_product_message(product):
    lines = ["🆕 新品上架通知", "", escape(product.name), f"價格: {escape(product.price)}"]
    if product.shipping:
        lines.append(f"⚠️ {escape(product.shipping)}")
    lines.append(escape(product.url))
    return "\n".join(lines)
