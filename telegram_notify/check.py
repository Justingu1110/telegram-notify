from dataclasses import asdict

from .parsers import get_parser


def run_check(watches, fetch, notify, store):
    state = store.load()
    for watch in watches:
        products = get_parser(watch.parser)(fetch(watch.url))
        if watch.name not in state:
            state[watch.name] = {
                "products": {p.id: {k: v for k, v in asdict(p).items() if k != "id"} for p in products}
            }
            notify(f"監控已啟動：{watch.name}\n目前記錄 {len(products)} 件商品")
    store.save(state)
