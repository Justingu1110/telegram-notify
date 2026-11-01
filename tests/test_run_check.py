import json
import re

import pytest

from pages import (
    MARUKYU_LIST_URL,
    detail_page_saying,
    detail_url,
    page_without_any_product,
    page_without_first_products,
    real_detail_page,
    real_list_page,
)
from telegram_notify import Watch, load_watches, run_check

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
        self._saved = "{}"

    @property
    def state(self):
        return json.loads(self._saved)

    def load(self):
        return json.loads(self._saved)

    def save(self, state):
        self._saved = json.dumps(state, ensure_ascii=False)


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


def run_after_baseline(baseline_page, later_page, notifier=None):
    watch = load_watches()[0]
    store = MemoryStore()
    notifier = notifier or RecordingNotifier()
    run_check([watch], fetch=FakeSite({watch.url: baseline_page}), notify=RecordingNotifier(), store=store)
    run_check([watch], fetch=FakeSite({watch.url: later_page}), notify=notifier, store=store)
    return notifier


def test_new_product_after_baseline_is_notified_once_with_its_details():
    full_page = real_list_page()

    notifier = run_after_baseline(page_without_first_products(full_page), full_page)

    assert len(notifier.sent) == 1
    notification = notifier.sent[0]
    assert "新品上架通知" in notification
    assert "永寿 四十克 罐 （Matcha Eiju 40g can）" in notification
    assert "¥9,140.00" in notification
    assert f"{MARUKYU_LIST_URL}/pid/8835" in notification
    assert "⚠️" in notification
    assert "仅配送中国地区，不包含台湾香港澳门" in notification


def test_a_product_notified_once_is_not_notified_again():
    full_page = real_list_page()
    watch = load_watches()[0]
    store = MemoryStore()
    run_check([watch], fetch=FakeSite({watch.url: page_without_first_products(full_page)}), notify=RecordingNotifier(), store=store)
    run_check([watch], fetch=FakeSite({watch.url: full_page}), notify=RecordingNotifier(), store=store)
    notifier = RecordingNotifier()

    run_check([watch], fetch=FakeSite({watch.url: full_page}), notify=notifier, store=store)

    assert notifier.sent == []


def test_each_of_several_new_products_gets_its_own_notification_in_page_order():
    full_page = real_list_page()

    notifier = run_after_baseline(page_without_first_products(full_page, 2), full_page)

    assert len(notifier.sent) == 2
    assert f"{MARUKYU_LIST_URL}/pid/8835" in notifier.sent[0]
    assert f"{MARUKYU_LIST_URL}/pid/8794" in notifier.sent[1]


def test_special_characters_in_a_product_name_are_escaped_for_telegram_html():
    full_page = real_list_page().replace("永寿 四十克 罐 （Matcha Eiju 40g can）", "A &amp; B &lt;x&gt;")

    notifier = run_after_baseline(page_without_first_products(full_page), full_page)

    assert "A &amp; B &lt;x&gt;" in notifier.sent[0]
    assert "<x>" not in notifier.sent[0]


def test_a_new_product_without_a_shipping_note_has_no_warning_line():
    full_page = re.sub(r'<div class="text">.*?</div>', "", real_list_page(), count=1, flags=re.S)

    notifier = run_after_baseline(page_without_first_products(full_page), full_page)

    assert len(notifier.sent) == 1
    assert "⚠️" not in notifier.sent[0]


class FailsOnSecondSend:
    def __init__(self):
        self.sent = []

    def __call__(self, text):
        if len(self.sent) == 1:
            raise RuntimeError("telegram is down")
        self.sent.append(text)


def test_a_failed_send_does_not_cause_already_notified_products_to_be_notified_again():
    full_page = real_list_page()
    watch = load_watches()[0]
    store = MemoryStore()
    run_check([watch], fetch=FakeSite({watch.url: page_without_first_products(full_page, 2)}), notify=RecordingNotifier(), store=store)
    with pytest.raises(RuntimeError):
        run_check([watch], fetch=FakeSite({watch.url: full_page}), notify=FailsOnSecondSend(), store=store)
    notifier = RecordingNotifier()

    run_check([watch], fetch=FakeSite({watch.url: full_page}), notify=notifier, store=store)

    assert len(notifier.sent) == 1
    assert f"{MARUKYU_LIST_URL}/pid/8794" in notifier.sent[0]


class AlwaysFails:
    def __call__(self, text):
        raise RuntimeError("telegram is down")


def test_a_failed_startup_summary_is_sent_again_on_the_next_run():
    watch = load_watches()[0]
    site = FakeSite({watch.url: real_list_page()})
    store = MemoryStore()
    with pytest.raises(RuntimeError):
        run_check([watch], fetch=site, notify=AlwaysFails(), store=store)
    notifier = RecordingNotifier()

    run_check([watch], fetch=site, notify=notifier, store=store)

    assert len(notifier.sent) == 1
    assert "監控已啟動" in notifier.sent[0]


def test_special_characters_in_a_watch_name_are_escaped_in_the_startup_summary():
    watch = Watch(name="A&B <c>", url=load_watches()[0].url, parser="marukyu")
    notifier = RecordingNotifier()

    run_check([watch], fetch=FakeSite({watch.url: real_list_page()}), notify=notifier, store=MemoryStore())

    assert "A&amp;B &lt;c&gt;" in notifier.sent[0]


def test_special_characters_in_the_price_and_shipping_note_are_escaped_too():
    full_page = real_list_page().replace("¥9,140.00", "&lt;b&gt;9,140").replace("请注意，仅配送中国地区", "请注意&amp;仅配送中国地区")

    notifier = run_after_baseline(page_without_first_products(full_page), full_page)

    assert "&lt;b&gt;9,140" in notifier.sent[0]
    assert "请注意&amp;仅配送中国地区" in notifier.sent[0]
    assert "<b>" not in notifier.sent[0]


class FlakySite:
    def __init__(self, pages):
        self.pages = pages
        self.down = set()

    def __call__(self, url):
        if url in self.down:
            raise ConnectionError("site is down")
        return self.pages[url]


def check(watch, site, store, notifier):
    run_check([watch], fetch=site, notify=notifier, store=store)


def baselined_watch():
    watch = load_watches()[0]
    site = FlakySite({watch.url: real_list_page()})
    store = MemoryStore()
    check(watch, site, store, RecordingNotifier())
    return watch, site, store


def test_one_or_two_failed_checks_send_no_warning():
    watch, site, store = baselined_watch()
    notifier = RecordingNotifier()
    site.down.add(watch.url)

    for _ in range(2):
        check(watch, site, store, notifier)

    assert notifier.sent == []


def test_the_third_failed_check_in_a_row_sends_one_warning_naming_the_watch():
    watch, site, store = baselined_watch()
    notifier = RecordingNotifier()
    site.down.add(watch.url)

    for _ in range(3):
        check(watch, site, store, notifier)

    assert len(notifier.sent) == 1
    assert watch.name in notifier.sent[0]


def test_further_failures_after_the_third_do_not_repeat_the_warning():
    watch, site, store = baselined_watch()
    notifier = RecordingNotifier()
    site.down.add(watch.url)

    for _ in range(6):
        check(watch, site, store, notifier)

    assert len(notifier.sent) == 1


def test_one_success_resets_the_count_so_three_more_failures_are_needed():
    watch, site, store = baselined_watch()
    notifier = RecordingNotifier()
    for _ in range(2):
        site.down.add(watch.url)
        check(watch, site, store, notifier)
    site.down.clear()
    check(watch, site, store, notifier)
    site.down.add(watch.url)
    for _ in range(2):
        check(watch, site, store, notifier)
    assert notifier.sent == []

    check(watch, site, store, notifier)

    assert len(notifier.sent) == 1


def test_a_page_with_no_products_counts_as_a_failure_and_keeps_the_known_products():
    watch, site, store = baselined_watch()
    site.pages[watch.url] = page_without_any_product(real_list_page())
    notifier = RecordingNotifier()

    for _ in range(3):
        check(watch, site, store, notifier)

    assert len(notifier.sent) == 1
    assert watch.name in notifier.sent[0]
    assert set(store.state[watch.name]["products"]) == set(SHOWN_ON_LIST_PAGE)


def test_a_page_with_no_products_is_not_recorded_as_a_baseline():
    watch = load_watches()[0]
    site = FlakySite({watch.url: page_without_any_product(real_list_page())})
    store = MemoryStore()
    notifier = RecordingNotifier()
    check(watch, site, store, notifier)
    assert notifier.sent == []

    site.pages[watch.url] = real_list_page()
    check(watch, site, store, notifier)

    assert len(notifier.sent) == 1
    assert "目前記錄 3 件商品" in notifier.sent[0]


def test_a_page_whose_markup_the_parser_cannot_read_counts_as_a_failure():
    watch, site, store = baselined_watch()
    site.pages[watch.url] = real_list_page().replace('<div class="price">', '<div class="amount">', 1)
    notifier = RecordingNotifier()

    for _ in range(3):
        check(watch, site, store, notifier)

    assert len(notifier.sent) == 1
    assert watch.name in notifier.sent[0]


def test_products_already_known_are_not_announced_as_new_when_the_site_recovers():
    watch, site, store = baselined_watch()
    notifier = RecordingNotifier()
    site.down.add(watch.url)
    for _ in range(3):
        check(watch, site, store, notifier)
    warnings_sent = list(notifier.sent)
    site.down.clear()

    check(watch, site, store, notifier)

    assert notifier.sent == warnings_sent


def test_failures_before_the_first_baseline_are_counted_too():
    watch = load_watches()[0]
    site = FlakySite({watch.url: real_list_page()})
    site.down.add(watch.url)
    store = MemoryStore()
    notifier = RecordingNotifier()

    for _ in range(3):
        check(watch, site, store, notifier)

    assert len(notifier.sent) == 1
    assert watch.name in notifier.sent[0]


def test_a_watch_that_keeps_failing_does_not_stop_another_watch_from_being_checked():
    first = load_watches()[0]
    second = Watch(name="第二個監控項目", url=first.url + "?second=1", parser=first.parser)
    full_page = real_list_page()
    site = FlakySite({first.url: full_page, second.url: page_without_first_products(full_page)})
    store = MemoryStore()
    run_check([first, second], fetch=site, notify=RecordingNotifier(), store=store)
    site.pages[second.url] = full_page
    site.down.add(first.url)
    notifier = RecordingNotifier()

    for _ in range(3):
        run_check([first, second], fetch=site, notify=notifier, store=store)

    assert len(notifier.sent) == 2
    assert f"{MARUKYU_LIST_URL}/pid/8835" in notifier.sent[0]
    assert first.name in notifier.sent[1]
    assert second.name not in notifier.sent[1]


def test_the_warning_says_why_when_the_site_could_not_be_reached():
    watch, site, store = baselined_watch()
    site.down.add(watch.url)
    notifier = RecordingNotifier()

    for _ in range(3):
        check(watch, site, store, notifier)

    assert "site is down" in notifier.sent[0]


def test_the_warning_says_why_when_no_products_could_be_read():
    watch, site, store = baselined_watch()
    site.pages[watch.url] = page_without_any_product(real_list_page())
    notifier = RecordingNotifier()

    for _ in range(3):
        check(watch, site, store, notifier)

    assert "解析不到任何商品" in notifier.sent[0]


def test_a_warning_that_could_not_be_sent_is_sent_on_the_next_failed_check():
    watch, site, store = baselined_watch()
    site.down.add(watch.url)
    for _ in range(2):
        check(watch, site, store, RecordingNotifier())
    with pytest.raises(RuntimeError):
        check(watch, site, store, AlwaysFails())
    notifier = RecordingNotifier()

    check(watch, site, store, notifier)

    assert len(notifier.sent) == 1
    assert watch.name in notifier.sent[0]


def test_the_saved_record_stops_changing_once_the_warning_has_been_sent():
    watch, site, store = baselined_watch()
    site.down.add(watch.url)
    for _ in range(3):
        check(watch, site, store, RecordingNotifier())
    record_after_warning = store.state

    for _ in range(3):
        check(watch, site, store, RecordingNotifier())

    assert store.state == record_after_warning


class FailsWith:
    def __init__(self, reason):
        self.reason = reason

    def __call__(self, url):
        raise RuntimeError(self.reason)


def test_a_very_long_failure_reason_is_shortened_in_the_warning():
    watch, _site, store = baselined_watch()
    notifier = RecordingNotifier()

    for _ in range(3):
        check(watch, FailsWith("boom " * 2000), store, notifier)

    assert "boom" in notifier.sent[0]
    assert len(notifier.sent[0]) < 500


def full_site(list_page=None):
    watch = load_watches()[0]
    pages = {watch.url: list_page or real_list_page()}
    for pid in SHOWN_ON_LIST_PAGE:
        pages[detail_url(pid)] = real_detail_page(pid)
    return FlakySite(pages)


def test_the_baseline_records_each_products_stock_text_and_status():
    watch = load_watches()[0]
    store = MemoryStore()

    run_check([watch], fetch=full_site(), notify=RecordingNotifier(), store=store)

    products = store.state[watch.name]["products"]
    assert products["8835"]["stock_text"] == "8有库存"
    assert products["8794"]["stock_text"] == "10有库存"
    assert products["8778"]["stock_text"] == "10有库存"
    assert {p["stock_status"] for p in products.values()} == {"in_stock"}


def test_the_baseline_produces_no_event_beyond_the_startup_summary():
    watch = load_watches()[0]
    notifier = RecordingNotifier()

    run_check([watch], fetch=full_site(), notify=notifier, store=MemoryStore())

    assert len(notifier.sent) == 1
    assert "監控已啟動" in notifier.sent[0]


def baseline_with_8835_out_of_stock():
    watch = load_watches()[0]
    site = full_site()
    site.pages[detail_url("8835")] = detail_page_saying("8835", "无库存")
    store = MemoryStore()
    run_check([watch], fetch=site, notify=RecordingNotifier(), store=store)
    return watch, site, store


def test_a_product_that_stays_listed_but_goes_from_out_of_stock_to_in_stock_is_a_restock():
    watch, site, store = baseline_with_8835_out_of_stock()
    site.pages[detail_url("8835")] = real_detail_page("8835")
    notifier = RecordingNotifier()

    run_check([watch], fetch=site, notify=notifier, store=store)

    assert len(notifier.sent) == 1
    notification = notifier.sent[0]
    assert "補貨通知" in notification
    assert "新品上架" not in notification
    assert "永寿 四十克 罐 （Matcha Eiju 40g can）" in notification
    assert "¥9,140.00" in notification
    assert detail_url("8835") in notification
    assert "⚠️" in notification
    assert "仅配送中国地区，不包含台湾香港澳门" in notification


def baselined_site():
    watch = load_watches()[0]
    site = full_site()
    store = MemoryStore()
    run_check([watch], fetch=site, notify=RecordingNotifier(), store=store)
    return watch, site, store


def test_a_product_that_disappears_from_the_list_and_comes_back_in_stock_is_a_restock_not_a_new_product():
    watch, site, store = baselined_site()
    full_page = real_list_page()
    site.pages[watch.url] = page_without_first_products(full_page)
    notifier = RecordingNotifier()
    run_check([watch], fetch=site, notify=notifier, store=store)
    assert notifier.sent == []
    site.pages[watch.url] = full_page

    run_check([watch], fetch=site, notify=notifier, store=store)

    assert len(notifier.sent) == 1
    assert "補貨通知" in notifier.sent[0]
    assert "新品上架" not in notifier.sent[0]
    assert detail_url("8835") in notifier.sent[0]


def test_the_same_restock_is_not_announced_twice():
    watch, site, store = baseline_with_8835_out_of_stock()
    site.pages[detail_url("8835")] = real_detail_page("8835")
    run_check([watch], fetch=site, notify=RecordingNotifier(), store=store)
    notifier = RecordingNotifier()

    run_check([watch], fetch=site, notify=notifier, store=store)

    assert notifier.sent == []


def test_an_unfamiliar_stock_text_sends_nothing_keeps_the_known_status_and_is_recorded():
    watch, site, store = baselined_site()
    site.pages[detail_url("8835")] = detail_page_saying("8835", "特别说明")
    notifier = RecordingNotifier()

    run_check([watch], fetch=site, notify=notifier, store=store)

    assert notifier.sent == []
    record = store.state[watch.name]["products"]["8835"]
    assert record["stock_text"] == "特别说明"
    assert record["stock_status"] == "in_stock"


def test_coming_back_to_in_stock_after_an_unfamiliar_text_is_not_a_restock_when_it_was_in_stock_before():
    watch, site, store = baselined_site()
    site.pages[detail_url("8835")] = detail_page_saying("8835", "特别说明")
    run_check([watch], fetch=site, notify=RecordingNotifier(), store=store)
    site.pages[detail_url("8835")] = real_detail_page("8835")
    notifier = RecordingNotifier()

    run_check([watch], fetch=site, notify=notifier, store=store)

    assert notifier.sent == []


def test_an_unfamiliar_text_between_out_of_stock_and_in_stock_still_ends_in_one_restock():
    watch, site, store = baseline_with_8835_out_of_stock()
    site.pages[detail_url("8835")] = detail_page_saying("8835", "特别说明")
    notifier = RecordingNotifier()
    run_check([watch], fetch=site, notify=notifier, store=store)
    assert notifier.sent == []
    site.pages[detail_url("8835")] = real_detail_page("8835")

    run_check([watch], fetch=site, notify=notifier, store=store)

    assert len(notifier.sent) == 1
    assert "補貨通知" in notifier.sent[0]


def test_one_unreadable_detail_page_only_affects_that_product_and_is_not_a_watch_failure():
    watch = load_watches()[0]
    site = full_site()
    for pid in ("8835", "8794"):
        site.pages[detail_url(pid)] = detail_page_saying(pid, "无库存")
    store = MemoryStore()
    run_check([watch], fetch=site, notify=RecordingNotifier(), store=store)
    site.down.add(detail_url("8835"))
    site.pages[detail_url("8794")] = real_detail_page("8794")
    notifier = RecordingNotifier()

    for _ in range(3):
        run_check([watch], fetch=site, notify=notifier, store=store)

    assert len(notifier.sent) == 1
    assert detail_url("8794") in notifier.sent[0]
    assert "監控異常" not in notifier.sent[0]
    record = store.state[watch.name]["products"]["8835"]
    assert record["stock_text"] == "无库存"
    assert record["stock_status"] == "out_of_stock"

    site.down.clear()
    site.pages[detail_url("8835")] = real_detail_page("8835")
    run_check([watch], fetch=site, notify=notifier, store=store)

    assert len(notifier.sent) == 2
    assert detail_url("8835") in notifier.sent[1]


def test_a_failed_list_page_does_not_make_products_look_out_of_stock():
    watch, site, store = baselined_site()
    site.down.add(watch.url)
    notifier = RecordingNotifier()
    for _ in range(3):
        run_check([watch], fetch=site, notify=notifier, store=store)
    warnings_sent = list(notifier.sent)
    site.down.clear()

    run_check([watch], fetch=site, notify=notifier, store=store)

    assert notifier.sent == warnings_sent


def test_a_product_whose_stock_was_unknown_at_the_baseline_is_not_announced_when_it_turns_up_in_stock():
    watch = load_watches()[0]
    site = full_site()
    site.pages[detail_url("8835")] = detail_page_saying("8835", "特别说明")
    store = MemoryStore()
    run_check([watch], fetch=site, notify=RecordingNotifier(), store=store)
    site.pages[detail_url("8835")] = real_detail_page("8835")
    notifier = RecordingNotifier()

    run_check([watch], fetch=site, notify=notifier, store=store)

    assert notifier.sent == []


def test_a_new_product_is_announced_once_and_its_stock_is_recorded():
    watch = load_watches()[0]
    full_page = real_list_page()
    site = full_site(page_without_first_products(full_page))
    store = MemoryStore()
    run_check([watch], fetch=site, notify=RecordingNotifier(), store=store)
    site.pages[watch.url] = full_page
    notifier = RecordingNotifier()

    run_check([watch], fetch=site, notify=notifier, store=store)

    assert len(notifier.sent) == 1
    assert "新品上架通知" in notifier.sent[0]
    record = store.state[watch.name]["products"]["8835"]
    assert record["stock_text"] == "8有库存"
    assert record["stock_status"] == "in_stock"


def test_a_detail_page_without_a_stock_line_leaves_the_recorded_stock_untouched():
    watch, site, store = baseline_with_8835_out_of_stock()
    site.pages[detail_url("8835")] = real_detail_page("8835").replace("库存:", "在庫:")
    notifier = RecordingNotifier()

    run_check([watch], fetch=site, notify=notifier, store=store)

    assert notifier.sent == []
    record = store.state[watch.name]["products"]["8835"]
    assert record["stock_text"] == "无库存"
    assert record["stock_status"] == "out_of_stock"


def test_a_restock_notification_that_could_not_be_sent_is_sent_on_the_next_run():
    watch, site, store = baseline_with_8835_out_of_stock()
    site.pages[detail_url("8835")] = real_detail_page("8835")
    with pytest.raises(RuntimeError):
        run_check([watch], fetch=site, notify=AlwaysFails(), store=store)
    notifier = RecordingNotifier()

    run_check([watch], fetch=site, notify=notifier, store=store)

    assert len(notifier.sent) == 1
    assert "補貨通知" in notifier.sent[0]


@pytest.mark.parametrize("sold_out_text", ["没有库存", "暂时没有库存"])
def test_a_text_saying_there_is_no_stock_is_not_read_as_in_stock(sold_out_text):
    watch = load_watches()[0]
    site = full_site()
    site.pages[detail_url("8835")] = detail_page_saying("8835", sold_out_text)
    store = MemoryStore()
    notifier = RecordingNotifier()
    run_check([watch], fetch=site, notify=notifier, store=store)
    assert len(notifier.sent) == 1
    site.pages[detail_url("8835")] = real_detail_page("8835")

    run_check([watch], fetch=site, notify=notifier, store=store)

    assert len(notifier.sent) == 2
    assert "補貨通知" in notifier.sent[1]


def test_a_list_page_that_lists_fewer_products_than_it_says_it_has_counts_as_a_failure():
    watch, site, store = baselined_site()
    site.pages[watch.url] = real_list_page().replace("3 件中", "5 件中")
    notifier = RecordingNotifier()

    for _ in range(3):
        run_check([watch], fetch=site, notify=notifier, store=store)

    assert len(notifier.sent) == 1
    assert "監控異常" in notifier.sent[0]
    assert "5" in notifier.sent[0]
    statuses = {p["stock_status"] for p in store.state[watch.name]["products"].values()}
    assert statuses == {"in_stock"}


def test_a_list_page_that_shows_no_total_is_still_read_normally():
    watch = load_watches()[0]
    page = real_list_page().replace("<dt>3 件中</dt>", "")
    notifier = RecordingNotifier()

    run_check([watch], fetch=full_site(page), notify=notifier, store=MemoryStore())

    assert len(notifier.sent) == 1
    assert "目前記錄 3 件商品" in notifier.sent[0]
