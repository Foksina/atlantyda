from datetime import datetime, timezone

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.authentication import issue_access_token
from accounts.models import User
from measurements.models import Measurement
from sensors.keys import hash_api_key
from sensors.models import Sensor
from series.models import Series


class SensorReadApiTests(TestCase):
    def setUp(self):
        self.client = APIClient(HTTP_HOST='localhost')
        self.admin = User.objects.create_user(username='admin', password='haslo-testowe')
        self.token = issue_access_token(self.admin)
        self.series = Series.objects.create(
            name='Temperatura',
            min_value=0,
            max_value=40,
            color='#1f77b4',
        )
        self.secret_hash = 'tajny-skrot-klucza-czujnika'
        self.sensor = Sensor.objects.create(
            name='Czujnik A',
            series=self.series,
            api_key_hash=self.secret_hash,
        )
        self.quiet = Sensor.objects.create(
            name='Czujnik B',
            series=self.series,
            api_key_hash='inny-skrot',
        )
        self.measured_at = datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc)
        Measurement.objects.create(
            sensor=self.sensor,
            value=21.5,
            timestamp=self.measured_at,
        )

    def auth(self, token=None):
        headers = {}
        if token is not None:
            headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        return headers

    def test_list_returns_sensors_without_secrets(self):
        response = self.client.get('/api/sensors', **self.auth(self.token))

        self.assertEqual(response.status_code, 200)
        self.assertIn('application/json', response['Content-Type'])
        body = response.json()
        self.assertEqual([item['id'] for item in body], [self.sensor.id, self.quiet.id])
        first = body[0]
        self.assertEqual(first['name'], 'Czujnik A')
        self.assertEqual(first['seriesId'], self.series.id)
        self.assertIsNotNone(first['createdAt'])
        self.assertEqual(
            datetime.fromisoformat(first['lastMeasurementAt'].replace('Z', '+00:00')),
            self.measured_at,
        )
        self.assertIsNone(body[1]['lastMeasurementAt'])
        self.assertNotIn('apiKey', first)
        self.assertNotIn('api_key_hash', first)
        self.assertNotIn('is_active', first)
        self.assertNotIn(self.secret_hash, response.content.decode())

    def test_detail_returns_one_sensor(self):
        response = self.client.get(f'/api/sensors/{self.sensor.id}', **self.auth(self.token))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['id'], self.sensor.id)
        self.assertEqual(body['name'], 'Czujnik A')
        self.assertEqual(body['seriesId'], self.series.id)
        self.assertNotIn(self.secret_hash, response.content.decode())

    def test_empty_list(self):
        Sensor.objects.all().delete()

        response = self.client.get('/api/sensors', **self.auth(self.token))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_missing_sensor_returns_problem_details(self):
        response = self.client.get('/api/sensors/999999999', **self.auth(self.token))

        self.assertEqual(response.status_code, 404)
        self.assertIn('application/problem+json', response['Content-Type'])
        body = response.json()
        self.assertEqual(body['status'], 404)
        self.assertTrue(body['title'])

    def test_non_numeric_id_returns_404(self):
        response = self.client.get('/api/sensors/brak', **self.auth(self.token))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['status'], 404)

    def test_missing_token_returns_401(self):
        response = self.client.get('/api/sensors')

        self.assertEqual(response.status_code, 401)
        self.assertIn('application/problem+json', response['Content-Type'])
        self.assertEqual(response.json()['status'], 401)

    def test_forged_token_returns_401(self):
        response = self.client.get(
            f'/api/sensors/{self.sensor.id}',
            **self.auth('eyJhbGciOiJub25lIn0.eyJzdWIiOiJhZG1pbiJ9.'),
        )

        self.assertEqual(response.status_code, 401)

    def test_unsupported_accept_header_returns_406(self):
        response = self.client.get(
            '/api/sensors',
            HTTP_ACCEPT='application/xml',
            **self.auth(self.token),
        )

        self.assertEqual(response.status_code, 406)

    def test_series_list_stays_public(self):
        response = self.client.get('/api/series')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]['name'], 'Temperatura')


class SensorCreateApiTests(TestCase):
    def setUp(self):
        self.client = APIClient(HTTP_HOST='localhost')
        self.admin = User.objects.create_user(username='admin', password='haslo-testowe')
        self.token = issue_access_token(self.admin)
        self.series = Series.objects.create(
            name='Temperatura',
            min_value=0,
            max_value=40,
            color='#1f77b4',
        )

    def post(self, data, token=None, **extra):
        headers = {}
        if token is not None:
            headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        return self.client.post('/api/sensors', data, format='json', **headers, **extra)

    def test_admin_creates_sensor_with_api_key(self):
        response = self.post(
            {'name': 'Czujnik głębokości', 'seriesId': self.series.id},
            token=self.token,
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn('application/json', response['Content-Type'])
        body = response.json()
        self.assertEqual(response['Location'], f'/api/sensors/{body["id"]}')
        self.assertEqual(body['name'], 'Czujnik głębokości')
        self.assertEqual(body['seriesId'], self.series.id)
        self.assertIsNotNone(body['createdAt'])
        self.assertIsNone(body['lastMeasurementAt'])
        self.assertGreaterEqual(len(body['apiKey']), 32)
        stored = Sensor.objects.get(pk=body['id'])
        self.assertEqual(stored.api_key_hash, hash_api_key(body['apiKey']))
        self.assertNotEqual(stored.api_key_hash, body['apiKey'])
        self.assertNotIn(body['apiKey'], stored.api_key_hash)

        detail = self.client.get(response['Location'], HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(detail.status_code, 200)
        self.assertNotIn('apiKey', detail.json())
        self.assertNotIn(body['apiKey'], detail.content.decode())
        self.assertNotIn(stored.api_key_hash, detail.content.decode())

        listed = self.client.get('/api/sensors', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertNotIn(body['apiKey'], listed.content.decode())
        self.assertNotIn(stored.api_key_hash, listed.content.decode())

    def test_string_series_id_is_accepted(self):
        response = self.post(
            {'name': 'Czujnik', 'seriesId': str(self.series.id)},
            token=self.token,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['seriesId'], self.series.id)

    def test_two_sensors_receive_different_keys(self):
        first = self.post({'name': 'A', 'seriesId': self.series.id}, token=self.token)
        second = self.post({'name': 'B', 'seriesId': self.series.id}, token=self.token)

        self.assertNotEqual(first.json()['apiKey'], second.json()['apiKey'])
        hashes = set(Sensor.objects.values_list('api_key_hash', flat=True))
        self.assertEqual(len(hashes), 2)

    def test_client_cannot_set_internal_fields(self):
        response = self.post(
            {
                'name': 'Czujnik',
                'seriesId': self.series.id,
                'id': 999,
                'api_key_hash': 'klient-podal-hash',
                'is_active': False,
            },
            token=self.token,
        )

        self.assertEqual(response.status_code, 201)
        stored = Sensor.objects.get(pk=response.json()['id'])
        self.assertNotEqual(stored.pk, 999)
        self.assertNotEqual(stored.api_key_hash, 'klient-podal-hash')
        self.assertTrue(stored.is_active)
        self.assertEqual(stored.api_key_hash, hash_api_key(response.json()['apiKey']))

    def test_missing_series_returns_422(self):
        response = self.post({'name': 'Czujnik', 'seriesId': 999999999}, token=self.token)

        self.assertEqual(response.status_code, 422)
        self.assertIn('application/problem+json', response['Content-Type'])
        self.assertEqual(response.json()['status'], 422)
        self.assertIn('seriesId', [item['field'] for item in response.json()['errors']])
        self.assertEqual(Sensor.objects.count(), 0)

    def test_missing_name_returns_400(self):
        response = self.post({'seriesId': self.series.id}, token=self.token)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 400)
        self.assertIn('name', [item['field'] for item in response.json()['errors']])
        self.assertEqual(Sensor.objects.count(), 0)

    def test_wrong_types_return_400(self):
        response = self.post({'name': 12, 'seriesId': True}, token=self.token)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Sensor.objects.count(), 0)

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            '/api/sensors',
            '{"name":',
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn(b'Traceback', response.content)

    def test_plain_text_body_returns_415(self):
        response = self.client.post(
            '/api/sensors',
            'name=Czujnik',
            content_type='text/plain',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )

        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.json()['status'], 415)

    def test_missing_token_returns_401(self):
        response = self.post({'name': 'Czujnik', 'seriesId': self.series.id})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['status'], 401)
        self.assertEqual(Sensor.objects.count(), 0)

    def test_forged_token_returns_401(self):
        response = self.post(
            {'name': 'Czujnik', 'seriesId': self.series.id},
            token='eyJhbGciOiJub25lIn0.eyJzdWIiOiJhZG1pbiJ9.',
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(Sensor.objects.count(), 0)

    def test_existing_get_still_hides_hash(self):
        created = self.post({'name': 'Czujnik', 'seriesId': self.series.id}, token=self.token)
        listed = self.client.get('/api/sensors', HTTP_AUTHORIZATION=f'Bearer {self.token}')

        self.assertEqual(listed.status_code, 200)
        self.assertNotIn('apiKey', listed.json()[0])
        self.assertNotIn(created.json()['apiKey'], listed.content.decode())
