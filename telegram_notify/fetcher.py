import time

import requests

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) telegram-notify"


class FetchError(Exception):
    pass


class HttpFetcher:
    def __init__(self, timeout=20, delay=1.0, sleep=time.sleep):
        self._timeout = timeout
        self._delay = delay
        self._sleep = sleep
        self._made_a_request = False

    def __call__(self, url):
        if self._made_a_request:
            self._sleep(self._delay)
        self._made_a_request = True
        try:
            response = requests.get(url, timeout=self._timeout, headers={"User-Agent": USER_AGENT})
        except requests.RequestException as error:
            raise FetchError(f"could not fetch {url} ({type(error).__name__})") from None
        if response.status_code != 200:
            raise FetchError(f"{url} returned HTTP {response.status_code}")
        if "charset" not in response.headers.get("Content-Type", "").lower():
            response.encoding = "utf-8"
        return response.text
