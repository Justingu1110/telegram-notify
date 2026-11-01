from pathlib import Path

import pytest

from telegram_notify import Watch, load_watches, run_check

FIXTURES = Path(__file__).parent / "fixtures" / "marukyu"
MARUKYU_LIST_URL = "https://www.marukyu-koyamaen.net/category/select/cid/312"

# What the real list page shows for each product (the shop itself truncates two names).
SHOWN_ON_LIST_PAGE = {
    "8835": ("永寿 四十克 罐 （Matcha Eiju 40g can）", "¥9,140.00"),
    "8794": ("秋季限定 壶切抹茶 四十克 罐 （Matcha Tsubok...", "¥7,140.00"),
    "8778": ("雲鹤 四十克 罐 （Matcha Unkaku 40g ca...", "¥7,140.00"),
}
SHIPPING_SENTENCE = {
    "8835": "仅配送中国地区，不包含台湾香港澳门",
    "8794": "仅寄送中国地区，不包含台湾香港澳门",
    "8778": "不包含 台灣,香港 澳門地區",
}


class FakeSite:
    def __init__(self, pages):
        self._pages = pages

    def __call__(self, url):
        return self._pages[url]


class RecordingNotifier:
    def __init__(self):
        self.sent = []

    def __call__(self, text):
        self.sent.append(text)


class MemoryStore:
    def __init__(self):
        self.state = {}

    def load(self):
        return self.state

    def save(self, state):
        self.state = state


def real_list_page():
    return (FIXTURES / "list.html").read_text(encoding="utf-8")


def test_first_run_sends_one_startup_summary_with_product_count():
    notifier = RecordingNotifier()

    run_check(
        load_watches(),
        fetch=FakeSite({MARUKYU_LIST_URL: real_list_page()}),
        notify=notifier,
        store=MemoryStore(),
    )

    assert len(notifier.sent) == 1
    assert "監控已啟動" in notifier.sent[0]
    assert "目前記錄 3 件商品" in notifier.sent[0]


def record_after_first_run(pid):
    watch = load_watches()[0]
    store = MemoryStore()
    run_check(
        [watch],
        fetch=FakeSite({watch.url: real_list_page()}),
        notify=RecordingNotifier(),
        store=store,
    )
    return store.state[watch.name]["products"][pid]


@pytest.mark.parametrize("pid", SHOWN_ON_LIST_PAGE)
def test_first_run_records_name_price_and_detail_page_url(pid):
    name, price = SHOWN_ON_LIST_PAGE[pid]

    record = record_after_first_run(pid)

    assert record["name"] == name
    assert record["price"] == price
    assert record["url"] == f"{MARUKYU_LIST_URL}/pid/{pid}"


@pytest.mark.parametrize("pid", SHIPPING_SENTENCE)
def test_first_run_records_shipping_note_as_plain_text(pid):
    shipping = record_after_first_run(pid)["shipping"]

    assert SHIPPING_SENTENCE[pid] in shipping
    assert "<" not in shipping


def test_running_again_on_unchanged_pages_sends_nothing_more():
    watch = load_watches()[0]
    site = FakeSite({watch.url: real_list_page()})
    notifier = RecordingNotifier()
    store = MemoryStore()
    run_check([watch], fetch=site, notify=notifier, store=store)
    sent_after_first_run = list(notifier.sent)

    run_check([watch], fetch=site, notify=notifier, store=store)

    assert notifier.sent == sent_after_first_run


def two_watches():
    first = load_watches()[0]
    second = Watch(name="第二個監控項目", url=first.url + "?second=1", parser=first.parser)
    return first, second


def test_each_watch_gets_its_own_startup_summary():
    first, second = two_watches()
    notifier = RecordingNotifier()

    run_check(
        [first, second],
        fetch=FakeSite({first.url: real_list_page(), second.url: real_list_page()}),
        notify=notifier,
        store=MemoryStore(),
    )

    assert len(notifier.sent) == 2
    assert first.name in notifier.sent[0]
    assert second.name in notifier.sent[1]


def test_adding_a_watch_later_sends_a_summary_only_for_the_new_watch():
    first, second = two_watches()
    site = FakeSite({first.url: real_list_page(), second.url: real_list_page()})
    notifier = RecordingNotifier()
    store = MemoryStore()
    run_check([first], fetch=site, notify=notifier, store=store)
    notifier.sent.clear()

    run_check([first, second], fetch=site, notify=notifier, store=store)

    assert len(notifier.sent) == 1
    assert second.name in notifier.sent[0]


def test_every_watch_listed_in_the_config_file_is_checked_in_order(tmp_path):
    config = tmp_path / "watches.toml"
    config.write_text(
        '[[watch]]\nname = "甲"\nurl = "https://example.test/a"\nparser = "marukyu"\n\n'
        '[[watch]]\nname = "乙"\nurl = "https://example.test/b"\nparser = "marukyu"\n',
        encoding="utf-8",
    )
    notifier = RecordingNotifier()

    run_check(
        load_watches(config),
        fetch=FakeSite({"https://example.test/a": real_list_page(), "https://example.test/b": real_list_page()}),
        notify=notifier,
        store=MemoryStore(),
    )

    assert len(notifier.sent) == 2
    assert "甲" in notifier.sent[0]
    assert "乙" in notifier.sent[1]


def test_first_run_records_html_entities_in_name_price_and_note_as_plain_characters():
    page = real_list_page()
    page = page.replace("永寿 四十克 罐 （Matcha Eiju 40g can）", "永寿 &amp; 罐 &lt;40g&gt;")
    page = page.replace("¥9,140.00", "&yen;9,140.00")
    page = page.replace("请注意，仅配送中国地区", "请注意&amp;仅配送中国地区")
    watch = load_watches()[0]
    store = MemoryStore()

    run_check([watch], fetch=FakeSite({watch.url: page}), notify=RecordingNotifier(), store=store)

    record = store.state[watch.name]["products"]["8835"]
    assert record["name"] == "永寿 & 罐 <40g>"
    assert record["price"] == "¥9,140.00"
    assert "请注意&仅配送中国地区" in record["shipping"]
