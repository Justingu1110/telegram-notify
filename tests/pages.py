from pathlib import Path
import re

FIXTURES = Path(__file__).parent / "fixtures" / "marukyu"
MARUKYU_LIST_URL = "https://www.marukyu-koyamaen.net/category/select/cid/312"
ITEM_MARKER = '<div class="item">'


def real_list_page():
    return (FIXTURES / "list.html").read_text(encoding="utf-8")


def real_detail_page(pid):
    return (FIXTURES / "detail" / f"{pid}.html").read_text(encoding="utf-8")


def detail_url(pid):
    return f"{MARUKYU_LIST_URL}/pid/{pid}"


def detail_page_saying(pid, stock_text):
    return re.sub(
        r'(库存:</span>\s*<span class="data-desc">).*?(</span>)',
        lambda m: m.group(1) + stock_text + m.group(2),
        real_detail_page(pid),
        count=1,
        flags=re.S,
    )


def page_without_first_products(page, count=1):
    head, *blocks = page.split(ITEM_MARKER)
    remaining = len(blocks) - count
    return ITEM_MARKER.join([head, *blocks[count:]]).replace(f"{len(blocks)} 件中", f"{remaining} 件中")


def page_without_any_product(page):
    return page.split(ITEM_MARKER)[0].replace("3 件中", "0 件中")
