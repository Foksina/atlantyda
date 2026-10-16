from django.core.exceptions import ImproperlyConfigured


def validate_runtime_settings(*, debug, secret_key):
    if debug:
        return
    if not secret_key or secret_key.startswith('django-insecure-'):
        raise ImproperlyConfigured(
            'Ustaw DJANGO_SECRET_KEY, gdy DJANGO_DEBUG jest wyłączone.'
        )
