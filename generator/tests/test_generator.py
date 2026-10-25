import json
import os
import random
import unittest
from datetime import datetime, timedelta, timezone
from io import BytesIO
from urllib.error import HTTPError, URLError

from generator.cli import build_settings, settings_from_sources
from generator.client import (
    AUTH,
    CONNECTION,
    CREATED,
    MeasurementClient,
    SERVER,
    TIMEOUT,
    VALIDATION,
    redact,
)
from generator.clock import format_timestamp, historical_timestamp, is_too_far_in_future, parse_timestamp
from generator.runner import run_generator
from generator.values import ValueGenerator


SECRET = "super-secret-key"
STAMP = "2026-01-10T10:00:00Z"


class Response:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def http_error(url, code):
    return HTTPError(url, code, "error", hdrs=None, fp=BytesIO(b"{}"))


class ValueTests(unittest.TestCase):
    def test_first_value_is_the_start_and_later_values_stay_in_range(self):
        generator = ValueGenerator(3, minimum=0, maximum=10, step=4, rng=random.Random(1))

        values = [generator.next_value() for _ in range(30)]

        self.assertEqual(values[0], 3)
        self.assertTrue(all(0 <= value <= 10 for value in values))
        self.assertTrue(any(value != 3 for value in values[1:]))

    def test_zero_step_keeps_the_clamped_start(self):
        generator = ValueGenerator(50, minimum=0, maximum=10, step=0)

        self.assertEqual(generator.next_value(), 10)
        self.assertEqual(generator.next_value(), 10)

    def test_inverted_range_is_rejected(self):
        with self.assertRaises(ValueError):
            ValueGenerator(1, minimum=10, maximum=0, step=0.1)


class ClockTests(unittest.TestCase):
    def test_formats_utc_timestamp_with_z(self):
        moment = datetime(2026, 1, 10, 11, 0, tzinfo=timezone(timedelta(hours=1)))

        self.assertEqual(format_timestamp(moment), STAMP)

    def test_naive_timestamp_is_rejected(self):
        with self.assertRaises(ValueError):
            format_timestamp(datetime(2026, 1, 10, 10, 0))

    def test_historical_timestamps_keep_order(self):
        start = parse_timestamp(STAMP)

        stamps = [format_timestamp(historical_timestamp(start, index, 60)) for index in range(3)]

        self.assertEqual(
            stamps,
            ["2026-01-10T10:00:00Z", "2026-01-10T10:01:00Z", "2026-01-10T10:02:00Z"],
        )

    def test_future_limit_is_five_minutes(self):
        now = parse_timestamp("2026-06-01T12:00:00Z")

        self.assertFalse(is_too_far_in_future(now + timedelta(minutes=5), now))
        self.assertTrue(is_too_far_in_future(now + timedelta(minutes=5, seconds=1), now))


class ClientTests(unittest.TestCase):
    def test_request_matches_the_contract_and_hides_the_key(self):
        captured = []

        def urlopen(request, timeout):
            captured.append((request, timeout))
            return Response(201, b'{"id": 7, "seriesId": 3, "value": 21.5}')

        client = MeasurementClient("http://127.0.0.1:8000/", SECRET, timeout=4, urlopen_func=urlopen)
        result = client.send(21.5, STAMP)

        request, timeout = captured[0]
        body = json.loads(request.data.decode("utf-8"))
        message = result.describe(21.5, STAMP)
        self.assertEqual(timeout, 4)
        self.assertEqual(request.full_url, "http://127.0.0.1:8000/api/measurements")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("X-api-key"), SECRET)
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(body, {"value": 21.5, "timestamp": STAMP})
        self.assertEqual(result.kind, CREATED)
        self.assertNotIn(SECRET, message)
        self.assertNotIn("api_key", message)

    def test_validation_auth_server_connection_and_timeout(self):
        cases = [
            (lambda request, timeout: (_ for _ in ()).throw(http_error(request.full_url, 422)), VALIDATION, 422),
            (lambda request, timeout: (_ for _ in ()).throw(http_error(request.full_url, 401)), AUTH, 401),
            (lambda request, timeout: (_ for _ in ()).throw(http_error(request.full_url, 500)), SERVER, 500),
            (lambda request, timeout: (_ for _ in ()).throw(URLError(SECRET)), CONNECTION, None),
            (lambda request, timeout: (_ for _ in ()).throw(TimeoutError()), TIMEOUT, None),
        ]
        for urlopen, kind, status in cases:
            with self.subTest(kind=kind):
                client = MeasurementClient("http://api.test", SECRET, urlopen_func=urlopen)
                result = client.send(1, STAMP)
                self.assertEqual(result.kind, kind)
                self.assertEqual(result.status, status)
                self.assertNotIn(SECRET, result.describe(1, STAMP))

    def test_series_lookup_uses_public_list_without_api_key(self):
        captured = []

        def urlopen(request, timeout):
            captured.append(request)
            payload = json.dumps([{"id": 3, "minValue": 0, "maxValue": 40}]).encode()
            return Response(200, payload)

        client = MeasurementClient("http://api.test", SECRET, urlopen_func=urlopen)

        self.assertEqual(client.series_bounds(3), (0.0, 40.0))
        self.assertIsNone(captured[0].get_header("X-api-key"))
        self.assertEqual(captured[0].full_url, "http://api.test/api/series")

    def test_redact_removes_the_key(self):
        self.assertEqual(redact(f"header {SECRET} tail", SECRET), "header [ukryto] tail")


class RunnerTests(unittest.TestCase):
    def _settings(self, **overrides):
        values = dict(
            api_url="http://api.test",
            api_key=SECRET,
            count=3,
            continuous=False,
            interval=0,
            start_value=1,
            minimum=0,
            maximum=10,
            step=0,
            series_id=None,
            history=False,
            history_from=None,
            history_step=60,
            timeout=10,
            seed=1,
        )
        values.update(overrides)
        return settings_from_sources(**values)

    def test_finite_mode_sends_the_requested_number(self):
        client = ScriptedClient([ok()] * 3)
        sleeps = []

        code = run_generator(
            self._settings(count=3, interval=5),
            client,
            ValueGenerator(1, step=0),
            sleep=sleeps.append,
            now=lambda: parse_timestamp(STAMP),
            output=lambda message: None,
        )

        self.assertEqual(code, 0)
        self.assertEqual(len(client.sent), 3)
        self.assertEqual(sleeps, [5, 5])

    def test_auth_failure_stops_without_another_request(self):
        client = ScriptedClient([fail(401, AUTH), ok()])
        lines = []

        code = run_generator(
            self._settings(count=5),
            client,
            ValueGenerator(1, step=0),
            sleep=lambda seconds: None,
            now=lambda: parse_timestamp(STAMP),
            output=lines.append,
        )

        self.assertEqual(code, 2)
        self.assertEqual(len(client.sent), 1)
        self.assertTrue(lines[0].startswith("Klucz API został odrzucony"))
        self.assertNotIn(SECRET, "\n".join(lines))

    def test_validation_error_stops_finite_mode(self):
        client = ScriptedClient([fail(422, VALIDATION), ok()])

        code = run_generator(
            self._settings(count=2),
            client,
            ValueGenerator(11, step=0),
            sleep=lambda seconds: None,
            now=lambda: parse_timestamp(STAMP),
            output=lambda message: None,
        )

        self.assertEqual(code, 2)
        self.assertEqual(len(client.sent), 1)

    def test_continuous_mode_continues_after_validation_error_and_can_stop(self):
        client = ScriptedClient([fail(422, VALIDATION), ok(), ok()])

        code = run_generator(
            self._settings(count=None, continuous=True, interval=0),
            client,
            ValueGenerator(1, step=0),
            sleep=lambda seconds: None,
            now=lambda: parse_timestamp(STAMP),
            stop_check=lambda: len(client.sent) >= 2,
            output=lambda message: None,
        )

        self.assertEqual(code, 0)
        self.assertEqual(len(client.sent), 2)

    def test_continuous_mode_stops_on_interrupt(self):
        client = ScriptedClient([ok()])
        lines = []

        def sleep(seconds):
            raise KeyboardInterrupt

        code = run_generator(
            self._settings(count=None, continuous=True, interval=10),
            client,
            ValueGenerator(1, step=0),
            sleep=sleep,
            now=lambda: parse_timestamp(STAMP),
            output=lines.append,
        )

        self.assertEqual(code, 0)
        self.assertEqual(lines[-1], "Zatrzymano generator.")
        self.assertNotIn(SECRET, "\n".join(lines))

    def test_history_is_explicit_and_ordered(self):
        with self.assertRaises(ValueError):
            self._settings(history_from=STAMP)
        client = ScriptedClient([ok(), ok(), ok()])

        code = run_generator(
            self._settings(count=3, history=True, history_from=STAMP, history_step=60),
            client,
            ValueGenerator(1, step=0),
            sleep=lambda seconds: None,
            now=lambda: parse_timestamp("2026-06-01T12:00:00Z"),
            output=lambda message: None,
        )

        self.assertEqual(code, 0)
        self.assertEqual(
            [timestamp for _, timestamp in client.sent],
            ["2026-01-10T10:00:00Z", "2026-01-10T10:01:00Z", "2026-01-10T10:02:00Z"],
        )

    def test_future_history_is_not_sent(self):
        client = ScriptedClient([ok()])
        now = parse_timestamp("2026-06-01T12:00:00Z")

        code = run_generator(
            self._settings(
                count=1,
                history=True,
                history_from="2026-06-01T12:06:00Z",
            ),
            client,
            ValueGenerator(1, step=0),
            sleep=lambda seconds: None,
            now=lambda: now,
            output=lambda message: None,
        )

        self.assertEqual(code, 2)
        self.assertEqual(client.sent, [])


class ScriptedClient:
    def __init__(self, results):
        self.results = list(results)
        self.sent = []

    def send(self, value, timestamp):
        self.sent.append((value, timestamp))
        return self.results.pop(0)


def ok():
    from generator.client import SendResult

    return SendResult(True, 201, CREATED)


def fail(status, kind):
    from generator.client import SendResult

    return SendResult(False, status, kind)


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.previous = os.environ.copy()
        for name in list(os.environ):
            if name.startswith("ATLANTYDA_"):
                del os.environ[name]

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.previous)

    def test_count_comes_from_the_environment(self):
        os.environ["ATLANTYDA_API_URL"] = "http://127.0.0.1:8000"
        os.environ["ATLANTYDA_API_KEY"] = SECRET
        os.environ["ATLANTYDA_COUNT"] = "4"
        args = build_args()

        settings = build_settings(args)

        self.assertEqual(settings.count, 4)
        self.assertFalse(settings.continuous)
        self.assertNotIn(SECRET, settings.api_url)

    def test_continuous_flag_ignores_count_from_the_environment(self):
        os.environ["ATLANTYDA_API_URL"] = "http://127.0.0.1:8000"
        os.environ["ATLANTYDA_API_KEY"] = SECRET
        os.environ["ATLANTYDA_COUNT"] = "4"

        settings = build_settings(build_args(continuous=True))

        self.assertTrue(settings.continuous)
        self.assertIsNone(settings.count)


def build_args(**overrides):
    from argparse import Namespace

    values = dict(
        env_file=None,
        api_url=None,
        api_key=None,
        count=None,
        continuous=False,
        interval=None,
        start_value=None,
        min_value=None,
        max_value=None,
        step=None,
        series_id=None,
        history=False,
        history_from=None,
        history_step=None,
        timeout=None,
        seed=None,
    )
    values.update(overrides)
    return Namespace(**values)


if __name__ == "__main__":
    unittest.main()
