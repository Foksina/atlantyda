import hashlib
import hmac
import secrets

from django.conf import settings


def generate_api_key():
    return secrets.token_urlsafe(32)


def hash_api_key(api_key):
    return hmac.new(
        settings.SECRET_KEY.encode(),
        api_key.encode(),
        hashlib.sha256,
    ).hexdigest()
