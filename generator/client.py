import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CREATED = "created"
VALIDATION = "validation"
AUTH = "auth"
SERVER = "server"
CONNECTION = "connection"
TIMEOUT = "timeout"
UNEXPECTED = "unexpected"


@dataclass(frozen=True)
class SendResult:
    ok: bool
    status: int | None
    kind: str

    def describe(self, value, timestamp):
        if self.ok:
            return (
                f"Zapisano pomiar value={value} timestamp={timestamp} status={self.status}."
            )
        labels = {
            VALIDATION: "Walidacja odrzuciła pomiar",
            AUTH: "Klucz API został odrzucony",
            SERVER: "Błąd serwera",
            CONNECTION: "Brak połączenia z API",
            TIMEOUT: "Przekroczono czas oczekiwania na API",
            UNEXPECTED: "Nieoczekiwana odpowiedź API",
        }
        status = f" status={self.status}" if self.status is not None else ""
        return f"{labels[self.kind]} value={value} timestamp={timestamp}{status}."


def redact(text, secret):
    if not secret or not text:
        return text
    return text.replace(secret, "[ukryto]")


def _kind_for_status(status):
    if status == 201:
        return CREATED
    if status in (400, 415, 422):
        return VALIDATION
    if status == 401:
        return AUTH
    if 500 <= status <= 599:
        return SERVER
    return UNEXPECTED


class MeasurementClient:
    """Wysyła pojedynczy pomiar przez POST /api/measurements. Nie ponawia żądania."""

    def __init__(self, api_url, api_key, timeout=10, urlopen_func=None):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._urlopen = urlopen_func or urlopen

    def send(self, value, timestamp):
        payload = json.dumps(
            {"value": value, "timestamp": timestamp},
            allow_nan=False,
        ).encode("utf-8")
        request = Request(
            f"{self.api_url}/api/measurements",
            data=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-API-Key": self.api_key,
            },
            method="POST",
        )
        try:
            with self._urlopen(request, timeout=self.timeout) as response:
                response.read()
                status = getattr(response, "status", 200)
        except TimeoutError:
            return SendResult(False, None, TIMEOUT)
        except HTTPError as error:
            try:
                error.read()
            finally:
                error.close()
            return SendResult(False, error.code, _kind_for_status(error.code))
        except URLError:
            return SendResult(False, None, CONNECTION)
        return SendResult(status == 201, status, _kind_for_status(status))

    def series_bounds(self, series_id):
        request = Request(
            f"{self.api_url}/api/series",
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            with self._urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (TimeoutError, HTTPError, URLError, json.JSONDecodeError) as error:
            raise RuntimeError("Nie udało się odczytać listy serii.") from error
        wanted = str(series_id)
        for item in payload:
            if str(item.get("id")) == wanted:
                return float(item["minValue"]), float(item["maxValue"])
        raise LookupError(f"Seria {wanted} nie występuje na liście publicznych serii.")
