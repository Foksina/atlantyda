import hmac

from sensors.keys import hash_api_key
from sensors.models import Sensor


def sensor_from_api_key(api_key):
    if not isinstance(api_key, str) or not api_key or api_key.strip() != api_key:
        return None
    digest = hash_api_key(api_key)
    sensor = (
        Sensor.objects.select_related('series')
        .filter(api_key_hash=digest, is_active=True)
        .first()
    )
    if sensor is None or len(sensor.api_key_hash) != len(digest):
        return None
    if not hmac.compare_digest(sensor.api_key_hash, digest):
        return None
    return sensor
