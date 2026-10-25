from datetime import datetime, timezone

from .clock import format_timestamp, historical_timestamp, is_too_far_in_future
from .client import AUTH


def is_critical(result, continuous):
    if result.ok:
        return False
    if result.kind == AUTH:
        return True
    return not continuous


def run_generator(
    settings,
    client,
    values,
    *,
    sleep,
    now=None,
    stop_check=None,
    output=print,
):
    clock = now or (lambda: datetime.now(timezone.utc))
    sent = 0
    index = 0
    try:
        while True:
            if stop_check is not None and stop_check():
                return 0
            if not settings.continuous and sent >= settings.count:
                return 0
            moment = (
                historical_timestamp(settings.history_from, index, settings.history_step)
                if settings.history
                else clock()
            )
            timestamp = format_timestamp(moment)
            if settings.history and is_too_far_in_future(moment, clock()):
                output(
                    "Przerwano: znacznik czasu jest późniejszy niż 5 minut od czasu tego komputera."
                )
                return 2
            value = values.next_value()
            result = client.send(value, timestamp)
            output(result.describe(value, timestamp))
            index += 1
            if is_critical(result, settings.continuous):
                return 2
            if result.ok:
                sent += 1
                if not settings.continuous and sent >= settings.count:
                    return 0
            if settings.interval > 0 and (settings.continuous or sent < settings.count):
                sleep(settings.interval)
    except KeyboardInterrupt:
        output("Zatrzymano generator.")
        return 0
