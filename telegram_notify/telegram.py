import requests

TOKEN_VARIABLE = "TELEGRAM_BOT_TOKEN"
CHAT_VARIABLE = "TELEGRAM_CHAT_ID"


class TelegramError(Exception):
    pass


class MissingSettings(Exception):
    pass


class TelegramNotifier:
    def __init__(self, token, chat_id, api_base="https://api.telegram.org", timeout=15):
        self._token = token
        self._chat_id = chat_id
        self._api_base = api_base
        self._timeout = timeout

    @classmethod
    def from_env(cls, env, **options):
        missing = [name for name in (TOKEN_VARIABLE, CHAT_VARIABLE) if not env.get(name)]
        if missing:
            raise MissingSettings("missing environment variable(s): " + ", ".join(missing))
        return cls(env[TOKEN_VARIABLE], env[CHAT_VARIABLE], **options)

    def __call__(self, text):
        try:
            response = requests.post(
                f"{self._api_base}/bot{self._token}/sendMessage",
                data={"chat_id": self._chat_id, "text": text, "parse_mode": "HTML"},
                timeout=self._timeout,
            )
        except requests.RequestException as error:
            raise TelegramError(f"could not reach Telegram ({type(error).__name__})") from None
        if not response.ok:
            raise TelegramError(f"Telegram rejected the message (HTTP {response.status_code}): {_reason(response)}")


def _reason(response):
    try:
        return response.json().get("description", "")
    except ValueError:
        return ""
