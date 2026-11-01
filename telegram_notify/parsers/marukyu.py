import re

from ..models import Product

_PID = re.compile(r"pid/(\d+)")
_TITLE = re.compile(r'<h3><a href="([^"]*)">(.*?)</a></h3>', re.S)
_PRICE = re.compile(r'<div class="price">(.*?)</div>', re.S)
_NOTE = re.compile(r'<div class="text">(.*?)</div>', re.S)


def parse_list(html):
    products = []
    for block in html.split('<div class="item">')[1:]:
        url, name = _TITLE.search(block).groups()
        note = _NOTE.search(block)
        products.append(
            Product(
                id=_PID.search(block).group(1),
                name=name.strip(),
                price=_PRICE.search(block).group(1).strip(),
                url=url.strip(),
                shipping=_plain_text(note.group(1)) if note else "",
            )
        )
    return products


def _plain_text(fragment):
    # The shop itself cuts this text off mid-tag (e.g. "<strong s..."), so drop a trailing half-open tag first.
    fragment = re.sub(r"<[^>]*$", "", fragment)
    text = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", text).strip()
