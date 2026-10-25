from datetime import datetime, timedelta, timezone

FUTURE_LIMIT = timedelta(minutes=5)


def parse_timestamp(value):
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError(
            "Znacznik czasu musi zawierać strefę czasową, np. 2026-01-10T10:00:00Z."
        )
    return parsed.astimezone(timezone.utc)


def format_timestamp(moment):
    if moment.tzinfo is None:
        raise ValueError("Znacznik czasu musi mieć strefę czasową.")
    utc = moment.astimezone(timezone.utc).replace(microsecond=0)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def historical_timestamp(start, index, step_seconds):
    return start + timedelta(seconds=step_seconds * index)


def is_too_far_in_future(moment, now):
    return moment > now.astimezone(timezone.utc) + FUTURE_LIMIT
