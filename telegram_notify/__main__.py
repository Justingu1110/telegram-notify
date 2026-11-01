import os
import sys

from .check import run_check
from .fetcher import HttpFetcher
from .statestore import GitStateStore
from .telegram import MissingSettings, TelegramNotifier
from .watches import DEFAULT_WATCHES_PATH, load_watches


def main(
    env=None,
    watches_path=DEFAULT_WATCHES_PATH,
    repo_dir=".",
    telegram_api_base="https://api.telegram.org",
    fetch=None,
):
    env = os.environ if env is None else env
    try:
        notify = TelegramNotifier.from_env(env, api_base=telegram_api_base)
    except MissingSettings as error:
        print(f"telegram-notify: {error}", file=sys.stderr)
        return 2
    run_check(
        load_watches(watches_path),
        fetch=fetch or HttpFetcher(),
        notify=notify,
        store=GitStateStore(repo_dir),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
