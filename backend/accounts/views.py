from django.contrib.auth.hashers import check_password, make_password
from rest_framework.exceptions import NotAuthenticated, ParseError, UnsupportedMediaType
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import (
    ACCESS_TOKEN_MAX_AGE,
    BearerAuthentication,
    issue_access_token,
    revoke_access_token,
)
from .models import User
from .serializers import LoginSerializer, PasswordChangeSerializer

SYNTAX_ERROR_CODES = {'required', 'invalid', 'null', 'blank'}
DUMMY_PASSWORD_HASH = make_password('atlantyda-dummy-password')


def problem_response(status_code, title, *, detail=None, instance=None, errors=None):
    payload = {
        'type': 'about:blank',
        'title': title,
        'status': status_code,
    }
    if detail:
        payload['detail'] = detail
    if instance:
        payload['instance'] = instance
    if errors:
        payload['errors'] = errors
    return Response(
        payload,
        status=status_code,
        content_type='application/problem+json',
    )


def field_errors(serializer_errors):
    items = []
    for field, messages in serializer_errors.items():
        for message in messages:
            items.append({'field': field, 'message': str(message)})
    return items


def validation_status(serializer_errors):
    for messages in serializer_errors.values():
        for message in messages:
            if getattr(message, 'code', None) in SYNTAX_ERROR_CODES:
                return 400
    return 422


def invalid_body(serializer, request, detail):
    status_code = validation_status(serializer.errors)
    title = 'Niepoprawne żądanie' if status_code == 400 else 'Nie można przetworzyć danych'
    return problem_response(
        status_code,
        title,
        detail=detail,
        instance=request.path,
        errors=field_errors(serializer.errors),
    )


def unauthorized(request, detail):
    return problem_response(
        401,
        'Brak autoryzacji',
        detail=detail,
        instance=request.path,
    )


def credentials_match(user, password):
    if user is None:
        check_password(password, DUMMY_PASSWORD_HASH)
        return False
    return user.is_active and user.check_password(password)


class AuthProblemMixin:
    def handle_exception(self, exc):
        if isinstance(exc, NotAuthenticated):
            return unauthorized(self.request, 'Wymagany jest token administratora.')
        if isinstance(exc, ParseError):
            return problem_response(
                400,
                'Niepoprawne żądanie',
                detail='Treść nie jest poprawnym JSON.',
                instance=self.request.path,
            )
        if isinstance(exc, UnsupportedMediaType):
            return problem_response(
                415,
                'Nieobsługiwany format',
                detail='Treść żądania musi mieć format JSON.',
                instance=self.request.path,
            )
        return super().handle_exception(exc)


class LoginView(AuthProblemMixin, APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return invalid_body(serializer, request, 'Dane logowania są niepoprawne.')
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        user = User.objects.filter(username=username).first()
        if not credentials_match(user, password):
            return unauthorized(request, 'Nieprawidłowa nazwa użytkownika lub hasło.')
        return Response(
            {
                'accessToken': issue_access_token(user),
                'tokenType': 'Bearer',
                'expiresIn': ACCESS_TOKEN_MAX_AGE,
            }
        )


class LogoutView(AuthProblemMixin, APIView):
    authentication_classes = [BearerAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        revoke_access_token(request.auth)
        return Response(status=204)


class PasswordChangeView(AuthProblemMixin, APIView):
    authentication_classes = [BearerAuthentication]
    permission_classes = [IsAuthenticated]

    def put(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        if not serializer.is_valid():
            return invalid_body(serializer, request, 'Dane zmiany hasła są niepoprawne.')
        current_password = serializer.validated_data['currentPassword']
        new_password = serializer.validated_data['newPassword']
        if not request.user.check_password(current_password):
            return problem_response(
                403,
                'Brak uprawnień',
                detail='Podane bieżące hasło jest niepoprawne.',
                instance=request.path,
            )
        request.user.set_password(new_password)
        request.user.save(update_fields=['password'])
        return Response(status=204)
