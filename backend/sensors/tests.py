from datetime import datetime, timezone

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.authentication import issue_access_token
from accounts.models import User
from measurements.models import Measurement
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
