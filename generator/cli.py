import argparse
import os
import time
from dataclasses import dataclass
from datetime import datetime

from .client import MeasurementClient
from .clock import parse_timestamp
from .runner import run_generator
from .values import ValueGenerator


@dataclass(frozen=True)
class Settings:
    api_url: str
    api_key: str
    count: int | None
    continuous: bool
    interval: float
    start_value: float
    minimum: float | None
    maximum: float | None
    step: float
    series_id: str | None
    history: bool
    history_from: datetime | None
    history_step: float
    timeout: float
    seed: int | None


def load_env_file(path):
    with open(path, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _optional_float(value):
    if value is None or str(value).strip() == "":
        return None
    return float(value)


def _env(name):
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return None
    return value.strip()


def settings_from_sources(
    *,
    api_url,
    api_key,
    count,
    continuous,
    interval,
    start_value,
    minimum,
    maximum,
    step,
    series_id,
    history,
    history_from,
    history_step,
    timeout,
    seed,
):
    if not api_url:
        raise ValueError("Podaj adres API przez --api-url albo ATLANTYDA_API_URL.")
    if not api_key:
        raise ValueError("Podaj klucz API przez --api-key albo ATLANTYDA_API_KEY.")
    if continuous and count is not None:
        raise ValueError("Podaj albo --count, albo --continuous.")
    if not continuous and count is None:
        raise ValueError("Podaj liczbę pomiarów (--count) albo tryb ciągły (--continuous).")
    if count is not None and count < 1:
        raise ValueError("Liczba pomiarów musi być większa od zera.")
    if interval < 0:
        raise ValueError("Odstęp czasu nie może być ujemny.")
    if timeout <= 0:
        raise ValueError("Limit czasu oczekiwania musi być większy od zera.")
    if history and history_from is None:
        raise ValueError("Tryb historyczny wymaga --from albo ATLANTYDA_HISTORY_FROM.")
    if history_from is not None and not history:
        raise ValueError("Dane historyczne wymagają jawnego --history albo ATLANTYDA_HISTORY=true.")
    parsed_from = parse_timestamp(history_from) if history_from else None
    if history_step < 0:
        raise ValueError("Odstęp znaczników czasu nie może być ujemny.")
    parsed_seed = None if seed is None else int(seed)
    return Settings(
        api_url=api_url.rstrip("/"),
        api_key=api_key,
        count=count,
        continuous=continuous,
        interval=interval,
        start_value=start_value,
        minimum=minimum,
        maximum=maximum,
        step=step,
        series_id=series_id,
        history=history,
        history_from=parsed_from,
        history_step=history_step,
        timeout=timeout,
        seed=parsed_seed,
    )


def _parser():
    parser = argparse.ArgumentParser(
        prog="python -m generator",
        description="Wysyła symulowane pomiary czujnika przez POST /api/measurements.",
    )
    parser.add_argument("--env-file", help="Plik KEY=VALUE. Nie nadpisuje już ustawionych zmiennych.")
    parser.add_argument("--api-url", help="Adres serwera, np. http://127.0.0.1:8000")
    parser.add_argument("--api-key", help="Klucz API czujnika. Lepiej podać go w ATLANTYDA_API_KEY.")
    parser.add_argument("--count", type=int, help="Liczba pomiarów w trybie ograniczonym.")
    parser.add_argument("--continuous", action="store_true", help="Wysyłaj pomiary aż do przerwania.")
    parser.add_argument("--interval", type=float, help="Sekundy między kolejnymi wysyłkami.")
    parser.add_argument("--start-value", type=float, help="Pierwsza wartość pomiaru.")
    parser.add_argument("--min-value", type=float, help="Dolne ograniczenie wartości.")
    parser.add_argument("--max-value", type=float, help="Górne ograniczenie wartości.")
    parser.add_argument("--step", type=float, help="Maksymalna zmiana między pomiarami.")
    parser.add_argument("--series-id", help="Id serii. Generator odczyta jej minValue i maxValue.")
    parser.add_argument("--history", action="store_true", help="Wysyłaj pomiary historyczne.")
    parser.add_argument("--from", dest="history_from", help="Początek historii, ISO 8601 ze strefą.")
    parser.add_argument(
        "--history-step",
        type=float,
        help="Sekundy między znacznikami czasu w trybie historycznym.",
    )
    parser.add_argument("--timeout", type=float, help="Sekundy oczekiwania na odpowiedź HTTP.")
    parser.add_argument("--seed", type=int, help="Ziarno generatora losowego.")
    return parser


def _flag(args, name, env_name):
    if getattr(args, name):
        return True
    return (_env(env_name) or "").lower() in {"1", "true", "yes", "on"}


def _mode(args):
    env_continuous = (_env("ATLANTYDA_CONTINUOUS") or "").lower() in {"1", "true", "yes", "on"}
    env_count = _env("ATLANTYDA_COUNT")
    if args.continuous and args.count is not None:
        raise ValueError("Podaj albo --count, albo --continuous.")
    if args.continuous:
        return None, True
    if args.count is not None:
        return args.count, False
    if env_continuous and env_count is not None:
        raise ValueError("Ustaw albo ATLANTYDA_COUNT, albo ATLANTYDA_CONTINUOUS.")
    if env_continuous:
        return None, True
    if env_count is not None:
        return int(env_count), False
    return None, False


def build_settings(args):
    count, continuous = _mode(args)
    interval = args.interval
    if interval is None:
        interval = float(_env("ATLANTYDA_INTERVAL") or "10")
    start_value = args.start_value
    if start_value is None:
        start_value = float(_env("ATLANTYDA_START_VALUE") or "0")
    step = args.step
    if step is None:
        step = float(_env("ATLANTYDA_STEP") or "0.5")
    timeout = args.timeout
    if timeout is None:
        timeout = float(_env("ATLANTYDA_TIMEOUT") or "10")
    history_step = args.history_step
    if history_step is None:
        raw_step = _env("ATLANTYDA_HISTORY_STEP")
        history_step = float(raw_step) if raw_step is not None else 60.0
    minimum = args.min_value if args.min_value is not None else _optional_float(_env("ATLANTYDA_MIN_VALUE"))
    maximum = args.max_value if args.max_value is not None else _optional_float(_env("ATLANTYDA_MAX_VALUE"))
    return settings_from_sources(
        api_url=args.api_url or _env("ATLANTYDA_API_URL"),
        api_key=args.api_key or _env("ATLANTYDA_API_KEY"),
        count=count,
        continuous=continuous,
        interval=interval,
        start_value=start_value,
        minimum=minimum,
        maximum=maximum,
        step=step,
        series_id=args.series_id or _env("ATLANTYDA_SERIES_ID"),
        history=_flag(args, "history", "ATLANTYDA_HISTORY"),
        history_from=args.history_from or _env("ATLANTYDA_HISTORY_FROM"),
        history_step=history_step,
        timeout=timeout,
        seed=args.seed if args.seed is not None else _optional_float(_env("ATLANTYDA_SEED")),
    )


def apply_series_bounds(settings, client):
    if not settings.series_id:
        return settings
    fetched_min, fetched_max = client.series_bounds(settings.series_id)
    return Settings(
        **{
            **settings.__dict__,
            "minimum": settings.minimum if settings.minimum is not None else fetched_min,
            "maximum": settings.maximum if settings.maximum is not None else fetched_max,
        }
    )


def main(argv=None):
    parser = _parser()
    preliminary, _ = parser.parse_known_args(argv)
    if preliminary.env_file:
        load_env_file(preliminary.env_file)
    args = parser.parse_args(argv)
    try:
        settings = build_settings(args)
    except ValueError as error:
        parser.error(str(error))
    client = MeasurementClient(settings.api_url, settings.api_key, timeout=settings.timeout)
    try:
        settings = apply_series_bounds(settings, client)
    except (LookupError, RuntimeError) as error:
        print(error)
        return 2
    import random

    values = ValueGenerator(
        start=settings.start_value,
        minimum=settings.minimum,
        maximum=settings.maximum,
        step=settings.step,
        rng=random.Random(settings.seed) if settings.seed is not None else None,
    )
    return run_generator(settings, client, values, sleep=time.sleep)
