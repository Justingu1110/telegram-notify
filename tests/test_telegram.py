import time
import traceback

import pytest
from fake_servers import FakeServer, closed_port_url
from telegram_notify.telegram import MissingSettings, TelegramError, TelegramNotifier

TOKEN = "123456789:SECRET-TOKEN-VALUE"
OK = (200, b'{"ok": true, "result": {}}', "application/json")


@pytest.fixture
def telegram():
    servers = []

    def start(respond):
        server = FakeServer(respond)
        servers.append(server)
        return server

    yield start
    for server in servers:
        server.close()


def test_a_notification_is_posted_to_the_bot_api_as_html_for_the_configured_chat(telegram):
    server = telegram(lambda request: OK)

    TelegramNotifier(TOKEN, "8607183589", api_base=server.url)("A &amp; B")

    request = server.requests[0]
    assert request["method"] == "POST"
    assert request["path"] == f"/bot{TOKEN}/sendMessage"
    assert request["form"] == {"chat_id": "8607183589", "text": "A &amp; B", "parse_mode": "HTML"}


def everything_printed_about(error):
    return str(error) + "".join(traceback.format_exception(error))


def test_a_message_telegram_rejects_fails_the_call_and_says_why_without_the_token(telegram):
    rejected = (400, b'{"ok": false, "description": "Bad Request: message is too long"}', "application/json")
    server = telegram(lambda request: rejected)

    with pytest.raises(TelegramError) as caught:
        TelegramNotifier(TOKEN, "1", api_base=server.url)("hello")

    assert "400" in str(caught.value)
    assert "message is too long" in str(caught.value)
    assert TOKEN not in everything_printed_about(caught.value)


def test_a_rejection_without_a_json_body_still_fails_the_call(telegram):
    server = telegram(lambda request: (502, b"<html>Bad Gateway</html>", "text/html"))

    with pytest.raises(TelegramError) as caught:
        TelegramNotifier(TOKEN, "1", api_base=server.url)("hello")

    assert "502" in str(caught.value)
    assert TOKEN not in everything_printed_about(caught.value)


def test_an_unreachable_telegram_fails_the_call_without_leaking_the_token():
    with pytest.raises(TelegramError) as caught:
        TelegramNotifier(TOKEN, "1", api_base=closed_port_url(), timeout=2)("hello")

    assert "could not reach Telegram" in str(caught.value)
    assert TOKEN not in everything_printed_about(caught.value)


def test_a_telegram_that_does_not_answer_in_time_fails_the_call_quickly_without_leaking_the_token(telegram):
    def slow(request):
        time.sleep(2)
        return OK

    server = telegram(slow)
    started = time.monotonic()

    with pytest.raises(TelegramError) as caught:
        TelegramNotifier(TOKEN, "1", api_base=server.url, timeout=0.3)("hello")

    assert time.monotonic() - started < 1.5
    assert TOKEN not in everything_printed_about(caught.value)


def test_missing_environment_variables_are_named_without_printing_any_value():
    with pytest.raises(MissingSettings) as caught:
        TelegramNotifier.from_env({"TELEGRAM_CHAT_ID": "8607183589"})

    assert "TELEGRAM_BOT_TOKEN" in str(caught.value)
    assert "TELEGRAM_CHAT_ID" not in str(caught.value)
    assert "8607183589" not in str(caught.value)


def test_both_missing_variables_are_named():
    with pytest.raises(MissingSettings) as caught:
        TelegramNotifier.from_env({})

    assert "TELEGRAM_BOT_TOKEN" in str(caught.value)
    assert "TELEGRAM_CHAT_ID" in str(caught.value)


def test_an_empty_variable_counts_as_missing():
    with pytest.raises(MissingSettings):
        TelegramNotifier.from_env({"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": "1"})


def test_a_notifier_built_from_the_environment_sends_with_those_settings(telegram):
    server = telegram(lambda request: OK)
    env = {"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_CHAT_ID": "8607183589"}

    TelegramNotifier.from_env(env, api_base=server.url)("hi")

    assert server.requests[0]["path"] == f"/bot{TOKEN}/sendMessage"
    assert server.requests[0]["form"]["chat_id"] == "8607183589"
