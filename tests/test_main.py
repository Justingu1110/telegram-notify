import pytest
from fake_servers import FakeServer
from git_helpers import git, make_checkout, make_remote
from pages import (
    detail_page_saying,
    real_detail_page,
    real_list_page,
    page_without_first_products,
)
from telegram_notify.__main__ import main
from telegram_notify.fetcher import HttpFetcher
from telegram_notify.telegram import TelegramError

SHOP = "https://www.marukyu-koyamaen.net"
TOKEN = "123456789:SECRET-TOKEN-VALUE"
ENV = {"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_CHAT_ID": "8607183589"}
OK = (200, b'{"ok": true, "result": {}}', "application/json")


class World:
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        self.remote = make_remote(tmp_path)
        self.list_page = real_list_page()
        self.detail_pages = {pid: real_detail_page(pid) for pid in ("8835", "8794", "8778")}
        self.telegram_answer = OK
        self.shop_down = False
        self.shop = FakeServer(self._serve_shop)
        self.telegram = FakeServer(lambda request: self.telegram_answer)
        self.watches = tmp_path / "watches.toml"
        self.watches.write_text(
            f'[[watch]]\nname = "丸久小山園 抹茶"\nurl = "{self.shop.url}/category/select/cid/312"\nparser = "marukyu"\n',
            encoding="utf-8",
        )
        self.runs = 0

    def _serve_shop(self, request):
        if self.shop_down:
            return 503, b"maintenance", "text/html"
        path = request["path"]
        if path == "/category/select/cid/312":
            page = self.list_page.replace(SHOP, self.shop.url)
        else:
            page = self.detail_pages[path.rsplit("/", 1)[1]]
        return 200, page.encode("utf-8"), "text/html; charset=UTF-8"

    def run(self, env=ENV):
        self.runs += 1
        checkout = make_checkout(self.tmp_path, self.remote, f"run{self.runs}")
        return main(
            env=env,
            watches_path=self.watches,
            repo_dir=checkout,
            telegram_api_base=self.telegram.url,
            fetch=HttpFetcher(delay=0),
        )

    def notifications_sent(self):
        return [request["form"]["text"] for request in self.telegram.requests]

    def commits_on_state_branch(self):
        return int(git("rev-list", "--count", "refs/heads/state", cwd=self.remote))

    def close(self):
        self.shop.close()
        self.telegram.close()


@pytest.fixture
def world(tmp_path):
    world = World(tmp_path)
    yield world
    world.close()


def test_missing_settings_stop_the_run_with_a_message_naming_them(world, capsys):
    exit_code = main(env={"TELEGRAM_CHAT_ID": "1"}, watches_path=world.watches, repo_dir=world.tmp_path)

    assert exit_code != 0
    assert "TELEGRAM_BOT_TOKEN" in capsys.readouterr().err
    assert world.shop.requests == []


def test_the_first_real_run_announces_itself_and_saves_the_record_on_the_state_branch(world):
    assert world.run() == 0

    assert len(world.notifications_sent()) == 1
    assert "監控已啟動" in world.notifications_sent()[0]
    assert "目前記錄 3 件商品" in world.notifications_sent()[0]
    saved = git("show", "refs/heads/state:state.json", cwd=world.remote)
    assert "8835" in saved
    assert "8有库存" in saved


def test_a_second_run_in_a_fresh_checkout_with_nothing_new_sends_nothing_and_adds_no_commit(world):
    world.run()

    assert world.run() == 0

    assert len(world.notifications_sent()) == 1
    assert world.commits_on_state_branch() == 1


def test_a_sale_changes_the_saved_stock_text_without_any_notification(world):
    world.run()
    world.detail_pages["8835"] = detail_page_saying("8835", "7有库存")

    assert world.run() == 0

    assert len(world.notifications_sent()) == 1
    assert world.commits_on_state_branch() == 2
    assert "7有库存" in git("show", "refs/heads/state:state.json", cwd=world.remote)


def test_a_restock_reaches_telegram_as_an_html_notification(world):
    world.detail_pages["8835"] = detail_page_saying("8835", "无库存")
    world.run()
    world.detail_pages["8835"] = real_detail_page("8835")

    world.run()

    restock = world.telegram.requests[-1]
    assert len(world.telegram.requests) == 2
    assert "補貨通知" in restock["form"]["text"]
    assert restock["form"]["parse_mode"] == "HTML"
    assert restock["form"]["chat_id"] == "8607183589"


def test_when_telegram_refuses_the_run_fails_without_the_token_and_the_next_run_delivers(world, capsys):
    full_page = world.list_page
    world.list_page = page_without_first_products(full_page)
    world.run()
    world.list_page = full_page
    world.telegram_answer = (500, b'{"ok": false, "description": "Internal Server Error"}', "application/json")

    with pytest.raises(TelegramError) as caught:
        world.run()

    assert TOKEN not in str(caught.value)
    captured = capsys.readouterr()
    assert TOKEN not in captured.out + captured.err
    sent_before = len(world.telegram.requests)
    world.telegram_answer = OK

    assert world.run() == 0

    assert "新品上架通知" in world.telegram.requests[-1]["form"]["text"]
    assert len(world.telegram.requests) == sent_before + 1


def test_a_shop_that_keeps_failing_ends_in_exactly_one_warning(world):
    world.run()
    world.shop_down = True

    for _ in range(5):
        assert world.run() == 0

    warnings = [text for text in world.notifications_sent() if "監控異常" in text]
    assert len(warnings) == 1
    assert "丸久小山園 抹茶" in warnings[0]
