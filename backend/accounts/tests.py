import json

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import Client, TestCase
from rest_framework.test import APIClient

from accounts.authentication import ACCESS_TOKEN_MAX_AGE
from accounts.models import User
from config.exceptions import api_exception_handler
from config.runtime import validate_runtime_settings
from series.models import Series


class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient(HTTP_HOST='localhost')
        self.password = 'haslo-testowe'
        self.admin = User.objects.create_user(username='admin', password=self.password)

    def login(self, data=None, **extra):
        payload = {'username': 'admin', 'password': self.password} if data is None else data
        return self.client.post('/api/auth/login', payload, format='json', **extra)

    def test_login_returns_bearer_token(self):
        response = self.login()

        self.assertEqual(response.status_code, 200)
        self.assertIn('application/json', response['Content-Type'])
        body = response.json()
        self.assertEqual(set(body), {'accessToken', 'tokenType', 'expiresIn'})
        self.assertIsInstance(body['accessToken'], str)
        self.assertTrue(body['accessToken'])
        self.assertEqual(body['tokenType'], 'Bearer')
        self.assertEqual(body['expiresIn'], ACCESS_TOKEN_MAX_AGE)
        self.assertNotIn(self.password, response.content.decode())
        self.assertNotIn(self.admin.password, response.content.decode())

        created = self.client.post(
            '/api/series',
            {'name': 'Temperatura', 'minValue': 0, 'maxValue': 10, 'color': '#1f77b4'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {body["accessToken"]}',
        )
        self.assertEqual(created.status_code, 201)

    def test_wrong_password_and_unknown_user_look_the_same(self):
        wrong = self.login({'username': 'admin', 'password': 'zle-haslo-1'})
        missing = self.login({'username': 'nikt', 'password': 'zle-haslo-1'})

        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(missing.status_code, 401)
        self.assertIn('application/problem+json', wrong['Content-Type'])
        self.assertEqual(wrong.json()['title'], 'Brak autoryzacji')
        self.assertEqual(wrong.json()['status'], 401)
        self.assertEqual(wrong.json(), missing.json())
        self.assertNotIn('admin', wrong.content.decode())
        self.assertNotIn(self.password, wrong.content.decode())
        self.assertTrue(User.objects.filter(username='admin').exists())

    def test_inactive_user_is_rejected_like_a_bad_password(self):
        self.admin.is_active = False
        self.admin.save(update_fields=['is_active'])
        inactive = self.login()
        wrong = self.login({'username': 'admin', 'password': 'zle-haslo-1'})

        self.assertEqual(inactive.status_code, 401)
        self.assertEqual(inactive.json()['detail'], wrong.json()['detail'])

    def test_missing_fields_and_wrong_types_return_400(self):
        missing = self.login({'username': 'admin'})
        typed = self.login({'username': 1, 'password': True})

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.json()['status'], 400)
        self.assertIn('password', [item['field'] for item in missing.json()['errors']])
        self.assertEqual(typed.status_code, 400)
        self.assertEqual(User.objects.count(), 1)

    def test_invalid_json_and_plain_text_do_not_leak_tracebacks(self):
        broken = self.client.post(
            '/api/auth/login',
            '{"username":',
            content_type='application/json',
        )
        plain = self.client.post(
            '/api/auth/login',
            'username=admin',
            content_type='text/plain',
        )

        self.assertEqual(broken.status_code, 400)
        self.assertEqual(plain.status_code, 415)
        self.assertNotIn(b'Traceback', broken.content)
        self.assertNotIn(b'Traceback', plain.content)

    def test_logout_invalidates_only_the_presented_token(self):
        first = self.login().json()['accessToken']
        second = self.login().json()['accessToken']
        response = self.client.post(
            '/api/auth/logout',
            HTTP_AUTHORIZATION=f'Bearer {first}',
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b'')
        blocked = self.client.post(
            '/api/series',
            {'name': 'Temperatura', 'minValue': 0, 'maxValue': 10, 'color': '#1f77b4'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {first}',
        )
        allowed = self.client.get('/api/sensors', HTTP_AUTHORIZATION=f'Bearer {second}')
        self.assertEqual(blocked.status_code, 401)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(Series.objects.count(), 0)

    def test_logout_without_token_returns_401(self):
        response = self.client.post('/api/auth/logout')

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['status'], 401)

    def test_password_change_replaces_the_password(self):
        token = self.login().json()['accessToken']
        response = self.client.put(
            '/api/auth/password',
            {'currentPassword': self.password, 'newPassword': 'nowe-haslo-9'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b'')
        self.assertNotIn(self.password, response.content.decode())
        self.assertNotIn('nowe-haslo-9', response.content.decode())
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.check_password(self.password))
        self.assertTrue(self.admin.check_password('nowe-haslo-9'))
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(
            self.login({'username': 'admin', 'password': 'nowe-haslo-9'}).status_code,
            200,
        )

    def test_wrong_current_password_returns_403_without_change(self):
        token = self.login().json()['accessToken']
        response = self.client.put(
            '/api/auth/password',
            {'currentPassword': 'zle-haslo-1', 'newPassword': 'nowe-haslo-9'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn('application/problem+json', response['Content-Type'])
        self.assertEqual(response.json()['status'], 403)
        self.assertNotIn('zle-haslo-1', response.content.decode())
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password(self.password))

    def test_short_new_password_returns_422_without_change(self):
        token = self.login().json()['accessToken']
        response = self.client.put(
            '/api/auth/password',
            {'currentPassword': self.password, 'newPassword': 'krotkie'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['status'], 422)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password(self.password))

    def test_password_change_without_token_returns_401(self):
        response = self.client.put(
            '/api/auth/password',
            {'currentPassword': self.password, 'newPassword': 'nowe-haslo-9'},
            format='json',
        )

        self.assertEqual(response.status_code, 401)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password(self.password))

    def test_public_reads_stay_public_and_admin_routes_stay_protected(self):
        series = self.client.get('/api/series')
        measurements = self.client.get('/api/measurements')
        sensors = self.client.get('/api/sensors')

        self.assertEqual(series.status_code, 200)
        self.assertEqual(measurements.status_code, 200)
        self.assertEqual(sensors.status_code, 401)

    def test_login_does_not_require_csrf_cookie(self):
        client = Client(enforce_csrf_checks=True, HTTP_HOST='localhost')
        response = client.post(
            '/api/auth/login',
            data=json.dumps({'username': 'admin', 'password': self.password}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.cookies.keys(), set())


class SecurityConfigTests(TestCase):
    def setUp(self):
        self.client = APIClient(HTTP_HOST='localhost')

    def test_api_sends_nosniff_and_limits_cors(self):
        origin = settings.CORS_ALLOWED_ORIGINS[0]
        allowed = self.client.get('/api/series', HTTP_ORIGIN=origin)
        blocked = self.client.get('/api/series', HTTP_ORIGIN='https://evil.example')

        self.assertEqual(allowed['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(allowed['Access-Control-Allow-Origin'], origin)
        self.assertNotEqual(blocked.get('Access-Control-Allow-Origin'), 'https://evil.example')
        self.assertNotEqual(blocked.get('Access-Control-Allow-Origin'), '*')
        self.assertNotEqual(
            (blocked.get('Access-Control-Allow-Credentials') or '').lower(),
            'true',
        )

    def test_local_https_redirect_stays_off(self):
        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)
        self.assertFalse(settings.CORS_ALLOW_ALL_ORIGINS)
        self.assertNotIn('*', settings.ALLOWED_HOSTS)
        self.assertFalse(getattr(settings, 'SECURE_SSL_REDIRECT', False))

    def test_production_rejects_the_insecure_secret(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_runtime_settings(debug=False, secret_key='django-insecure-example')
        validate_runtime_settings(debug=True, secret_key='django-insecure-example')
        validate_runtime_settings(debug=False, secret_key='osobny-klucz-produkcyjny')

    def test_unhandled_exception_hides_internals(self):
        from rest_framework.renderers import JSONRenderer

        response = api_exception_handler(RuntimeError('secret-db-path'), {})
        response.accepted_renderer = JSONRenderer()
        response.accepted_media_type = 'application/json'
        response.renderer_context = {}
        response.render()

        self.assertEqual(response.status_code, 500)
        self.assertIn('application/problem+json', response['Content-Type'])
        text = response.content.decode()
        self.assertNotIn('secret-db-path', text)
        self.assertNotIn('Traceback', text)
        self.assertEqual(response.data['status'], 500)
        self.assertTrue(response.data['title'])
