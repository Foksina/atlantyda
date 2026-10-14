from django.core import signing
from rest_framework.authentication import BaseAuthentication

from .models import User

ACCESS_TOKEN_SALT = 'atlantyda.access-token'
ACCESS_TOKEN_MAX_AGE = 60 * 60


def issue_access_token(user):
    return signing.dumps({'uid': user.pk}, salt=ACCESS_TOKEN_SALT)


def user_from_access_token(token):
    try:
        payload = signing.loads(
            token,
            salt=ACCESS_TOKEN_SALT,
            max_age=ACCESS_TOKEN_MAX_AGE,
        )
    except signing.BadSignature:
        return None
    if not isinstance(payload, dict):
        return None
    user_id = payload.get('uid')
    if user_id is None:
        return None
    return User.objects.filter(pk=user_id, is_active=True).first()


class BearerAuthentication(BaseAuthentication):
    """Token administratora z nagłówka Authorization: Bearer."""

    def authenticate(self, request):
        header = request.headers.get('Authorization')
        if not header:
            return None
        scheme, _, credentials = header.partition(' ')
        token = credentials.strip()
        if scheme.lower() != 'bearer' or not token:
            return None
        user = user_from_access_token(token)
        if user is None:
            return None
        return (user, token)
