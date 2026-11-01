"""Wgrywa dane przykładowe wymagane przez test F11.

Hasło administratora i klucz czujnika nie są wpisane w tym pliku.
Klucz wraca z API tylko przy tworzeniu czujnika i jest przekazywany generatorowi w zmiennej środowiska.

Uruchomienie z katalogu głównego repozytorium:

    ATLANTYDA_API_URL=https://atlantyda.onrender.com
    ATLANTYDA_ADMIN_USER=...
    ATLANTYDA_ADMIN_PASSWORD=...
    python -m generator.seed

Ponowne uruchomienie doda kolejne trzy serie.
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

SERIES = [
    {
        "body": {
            "name": "Temperatura wody",
            "minValue": 4,
            "maxValue": 28,
            "color": "#1f77b4",
            "icon": "thermometer",
            "unit": "°C",
        },
        "sensor": "Czujnik temperatury komory A",
        "start": 12,
        "step": 0.4,
    },
    {
        "body": {
            "name": "Ciśnienie hydrostatyczne",
            "minValue": 1,
            "maxValue": 20,
            "color": "#2ca02c",
            "icon": "gauge",
            "unit": "bar",
        },
        "sensor": "Czujnik ciśnienia komory A",
        "start": 8,
        "step": 0.3,
    },
    {
        "body": {
            "name": "Zasolenie",
            "minValue": 30,
            "maxValue": 40,
            "color": "#ff7f0e",
            "icon": "drop",
            "unit": "PSU",
        },
        "sensor": "Czujnik zasolenia komory A",
        "start": 35,
        "step": 0.2,
    },
]

MEASUREMENT_COUNT = 16


def request(base, method, path, body=None, token=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    call = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(call, timeout=60) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise SystemExit(f"{method} {path} -> {error.code}\n{detail}") from error


def required_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Ustaw zmienną {name}.")
    return value


def send_measurements(base, api_key, series_id, start, step, history_from):
    env = os.environ.copy()
    env["ATLANTYDA_API_KEY"] = api_key
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "generator",
            "--api-url",
            base,
            "--count",
            str(MEASUREMENT_COUNT),
            "--interval",
            "0",
            "--series-id",
            str(series_id),
            "--start-value",
            str(start),
            "--step",
            str(step),
            "--history",
            "--from",
            history_from,
            "--history-step",
            "60",
            "--seed",
            "7",
        ],
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(f"Generator zakończył się kodem {completed.returncode}.")


def main():
    base = required_env("ATLANTYDA_API_URL").rstrip("/")
    login = request(
        base,
        "POST",
        "/api/auth/login",
        {
            "username": required_env("ATLANTYDA_ADMIN_USER"),
            "password": required_env("ATLANTYDA_ADMIN_PASSWORD"),
        },
    )
    token = login["accessToken"]
    history_from = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

    for spec in SERIES:
        series = request(base, "POST", "/api/series", spec["body"], token=token)
        sensor = request(
            base,
            "POST",
            "/api/sensors",
            {"name": spec["sensor"], "seriesId": series["id"]},
            token=token,
        )
        send_measurements(base, sensor["apiKey"], series["id"], spec["start"], spec["step"], history_from)
        print(f"{series['name']}: wysłano {MEASUREMENT_COUNT} pomiarów")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
