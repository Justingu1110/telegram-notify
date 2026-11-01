import time

import pytest
from fake_servers import FakeServer, closed_port_url
from telegram_notify.fetcher import FetchError, HttpFetcher

PAGE = "<html><body>永寿 四十克 罐 ¥9,140.00 库存: 8有库存</body></html>"


@pytest.fixture
def shop():
    servers = []

    def start(respond):
        server = FakeServer(respond)
        servers.append(server)
        return server

    yield start
    for server in servers:
        server.close()


def html(body, content_type="text/html; charset=UTF-8"):
    return lambda request: (200, body.encode("utf-8"), content_type)


def test_a_page_is_fetched_and_returned_as_text(shop):
    server = shop(html(PAGE))

    assert HttpFetcher()(server.url + "/category") == PAGE


@pytest.mark.parametrize("status", [403, 404, 503])
def test_a_page_that_is_not_ok_fails_the_fetch_and_names_the_status(shop, status):
    server = shop(lambda request: (status, b"nope", "text/html"))

    with pytest.raises(FetchError) as caught:
        HttpFetcher()(server.url + "/category")

    assert str(status) in str(caught.value)


def test_an_unreachable_site_fails_the_fetch():
    with pytest.raises(FetchError):
        HttpFetcher(timeout=2)(closed_port_url() + "/category")


def test_a_site_that_does_not_answer_in_time_fails_the_fetch_quickly(shop):
    def slow(request):
        time.sleep(2)
        return 200, b"late", "text/html; charset=UTF-8"

    server = shop(slow)
    started = time.monotonic()

    with pytest.raises(FetchError):
        HttpFetcher(timeout=0.3)(server.url + "/category")

    assert time.monotonic() - started < 1.5


def test_requests_are_spaced_out_but_the_first_one_is_not_delayed(shop):
    server = shop(html(PAGE))
    pauses = []
    fetch = HttpFetcher(delay=1.5, sleep=pauses.append)

    for _ in range(3):
        fetch(server.url + "/category")

    assert pauses == [1.5, 1.5]


def test_chinese_text_survives_when_the_site_does_not_declare_a_charset(shop):
    server = shop(html(PAGE, content_type="text/html"))

    assert HttpFetcher()(server.url + "/category") == PAGE


def test_the_requests_say_which_tool_is_asking(shop):
    server = shop(html(PAGE))

    HttpFetcher()(server.url + "/category")

    assert "telegram-notify" in server.requests[0]["headers"]["User-Agent"]
