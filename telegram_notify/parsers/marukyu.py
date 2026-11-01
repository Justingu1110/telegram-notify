import html as html_lib
import re

from ..models import Product, Stock

_PID = re.compile(r"pid/(\d+)")
_TITLE = re.compile(r'<h3><a href="([^"]*)">(.*?)</a></h3>', re.S)
_PRICE = re.compile(r'<div class="price">(.*?)</div>', re.S)
_NOTE = re.compile(r'<div class="text">(.*?)</div>', re.S)
# No sold-out page has been seen yet, so these wordings are guesses; unrecognised texts count as unknown.
_OUT_OF_STOCK_WORDS = ("无库存", "没有库存", "缺货", "售罄", "售完")
_IN_STOCK = re.compile(r"\d*\s*有库存")
_STOCK = re.compile(r'<span class="data-name">\s*库存[:：]?\s*</span>\s*<span class="data-desc">(.*?)</span>', re.S)


def parse_list(html):
    products = []
    for block in html.split('<div class="item">')[1:]:
        url, name = _TITLE.search(block).groups()
        note = _NOTE.search(block)
        products.append(
            Product(
                id=_PID.search(block).group(1),
                name=html_lib.unescape(name).strip(),
                price=html_lib.unescape(_PRICE.search(block).group(1)).strip(),
                url=url.strip(),
                shipping=_plain_text(note.group(1)) if note else "",
            )
        )
    return products


def parse_stock(html):
    match = _STOCK.search(html)
    if not match:
        return None
    text = _plain_text(match.group(1))
    if any(word in text for word in _OUT_OF_STOCK_WORDS):
        return Stock(text=text, status="out_of_stock")
    if _IN_STOCK.fullmatch(text):
        return Stock(text=text, status="in_stock")
    return Stock(text=text, status="unknown")


def _plain_text(fragment):
    # The shop itself cuts this text off mid-tag (e.g. "<strong s..."), so drop a trailing half-open tag first.
    fragment = re.sub(r"<[^>]*$", "", fragment)
    text = html_lib.unescape(re.sub(r"<[^>]+>", " ", fragment))
    return re.sub(r"\s+", " ", text).strip()
