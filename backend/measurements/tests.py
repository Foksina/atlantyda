from datetime import datetime, timedelta, timezone as datetime_timezone
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.authentication import issue_access_token
from accounts.models import User
from measurements.models import Measurement
from sensors.keys import hash_api_key
from sensors.models import Sensor
from series.models import Series


def isoformat_z(value):
    return value.astimezone(datetime_timezone.utc).isoformat().replace('+00:00', 'Z')


class MeasurementCreateApiTests(TestCase):
    def setUp(self):
        self.client = APIClient(HTTP_HOST='localhost')
        self.admin = User.objects.create_user(username='admin', password='haslo-testowe')
        self.token = issue_access_token(self.admin)
        self.series = Series.objects.create(
            name='Temperatura',
            min_value=0,
            max_value=10,
            color='#1f77b4',
        )
        self.other_series = Series.objects.create(
            name='Ciśnienie',
            min_value=0,
            max_value=200,
            color='#aabbcc',
        )
        self.api_key = 'a' * 40
        self.other_key = 'b' * 40
        self.sensor = Sensor.objects.create(
            name='Czujnik A',
            series=self.series,
            api_key_hash=hash_api_key(self.api_key),
        )
        self.other = Sensor.objects.create(
            name='Czujnik B',
            series=self.other_series,
            api_key_hash=hash_api_key(self.other_key),
        )
        self.measured_at = datetime(2026, 1, 10, 10, 0, tzinfo=datetime_timezone.utc)

    def post(self, data, key=None, omit_key=False, **extra):
        headers = {}
        if not omit_key:
            headers['HTTP_X_API_KEY'] = self.api_key if key is None else key
        return self.client.post('/api/measurements', data, format='json', **headers, **extra)

    def test_value_inside_range_is_stored_for_the_sensor(self):
        response = self.post({'value': 4.5, 'timestamp': '2026-01-10T10:00:00Z'})

        self.assertEqual(response.status_code, 201)
        self.assertIn('application/json', response['Content-Type'])
        body = response.json()
        self.assertEqual(response['Location'], f'/api/measurements/{body["id"]}')
        self.assertEqual(body['value'], 4.5)
        self.assertEqual(body['seriesId'], self.series.id)
        self.assertEqual(body['sensorId'], self.sensor.id)
        self.assertEqual(
            datetime.fromisoformat(body['timestamp'].replace('Z', '+00:00')),
            self.measured_at,
        )
        self.assertNotIn('apiKey', body)
        self.assertNotIn('api_key_hash', body)
        stored = Measurement.objects.get(pk=body['id'])
        self.assertEqual(stored.sensor_id, self.sensor.id)
        self.assertEqual(stored.value, 4.5)
        self.assertEqual(stored.timestamp, self.measured_at)
        self.assertNotIn(self.api_key, response.content.decode())
        self.assertNotIn(self.sensor.api_key_hash, response.content.decode())

        detail = self.client.get(
            f'/api/sensors/{self.sensor.id}',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(
            datetime.fromisoformat(detail.json()['lastMeasurementAt'].replace('Z', '+00:00')),
            self.measured_at,
        )

    def test_client_cannot_choose_another_sensor(self):
        response = self.post(
            {
                'value': 3,
                'timestamp': '2026-01-10T10:00:00Z',
                'sensorId': self.other.id,
                'seriesId': self.other_series.id,
            }
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body['sensorId'], self.sensor.id)
        self.assertEqual(body['seriesId'], self.series.id)
        self.assertEqual(Measurement.objects.get(pk=body['id']).sensor_id, self.sensor.id)
        self.assertFalse(Measurement.objects.filter(sensor=self.other).exists())

    def test_boundary_values_are_accepted(self):
        low = self.post({'value': 0, 'timestamp': '2026-01-10T10:00:00Z'})
        high = self.post({'value': 10, 'timestamp': '2026-01-10T11:00:00Z'})

        self.assertEqual(low.status_code, 201)
        self.assertEqual(high.status_code, 201)
        self.assertEqual(low.json()['value'], 0)
        self.assertEqual(high.json()['value'], 10)
        self.assertEqual(Measurement.objects.count(), 2)

    def test_omitted_timestamp_uses_server_time(self):
        fixed = datetime(2026, 6, 1, 12, 0, tzinfo=datetime_timezone.utc)
        with patch('measurements.views.timezone.now', return_value=fixed):
            response = self.post({'value': 1})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            datetime.fromisoformat(response.json()['timestamp'].replace('Z', '+00:00')),
            fixed,
        )
        self.assertEqual(Measurement.objects.get().timestamp, fixed)

    def test_past_timestamp_is_accepted(self):
        response = self.post({'value': 1, 'timestamp': '2020-01-01T00:00:00Z'})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Measurement.objects.count(), 1)

    def test_timestamp_within_five_minutes_is_accepted(self):
        fixed = datetime(2026, 6, 1, 12, 0, tzinfo=datetime_timezone.utc)
        limit = fixed + timedelta(minutes=5)
        with patch('measurements.views.timezone.now', return_value=fixed):
            response = self.post({'value': 1, 'timestamp': isoformat_z(limit)})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Measurement.objects.get().timestamp, limit)

    def test_timestamp_beyond_five_minutes_returns_422_without_saving(self):
        fixed = datetime(2026, 6, 1, 12, 0, tzinfo=datetime_timezone.utc)
        future = fixed + timedelta(hours=1)
        with patch('measurements.views.timezone.now', return_value=fixed):
            response = self.post({'value': 1, 'timestamp': isoformat_z(future)})

        self.assertEqual(response.status_code, 422)
        self.assertIn('application/problem+json', response['Content-Type'])
        body = response.json()
        self.assertEqual(body['type'], 'about:blank')
        self.assertEqual(body['title'], 'Nie można przetworzyć danych')
        self.assertEqual(body['status'], 422)
        self.assertIn('timestamp', [item['field'] for item in body['errors']])
        self.assertEqual(Measurement.objects.count(), 0)
        self.assertNotIn(self.api_key, response.content.decode())

    def test_value_outside_range_returns_422_without_saving(self):
        response = self.post({'value': 11, 'timestamp': '2026-01-10T10:00:00Z'})

        self.assertEqual(response.status_code, 422)
        self.assertIn('application/problem+json', response['Content-Type'])
        body = response.json()
        self.assertEqual(body['status'], 422)
        self.assertTrue(body['title'])
        self.assertIn('value', [item['field'] for item in body['errors']])
        self.assertEqual(Measurement.objects.count(), 0)
        self.series.refresh_from_db()
        self.assertEqual(self.series.min_value, 0)
        self.assertEqual(self.series.max_value, 10)

    def test_missing_api_key_returns_401(self):
        response = self.post({'value': 1, 'timestamp': '2026-01-10T10:00:00Z'}, omit_key=True)

        self.assertEqual(response.status_code, 401)
        self.assertIn('application/problem+json', response['Content-Type'])
        body = response.json()
        self.assertEqual(body['title'], 'Brak autoryzacji')
        self.assertEqual(body['status'], 401)
        self.assertEqual(Measurement.objects.count(), 0)

    def test_invalid_api_key_returns_401(self):
        response = self.post(
            {'value': 1, 'timestamp': '2026-01-10T10:00:00Z'},
            key='x' * 40,
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['status'], 401)
        self.assertNotIn('x' * 40, response.content.decode())
        self.assertEqual(Measurement.objects.count(), 0)

    def test_inactive_sensor_key_returns_401(self):
        self.sensor.is_active = False
        self.sensor.save(update_fields=['is_active'])

        response = self.post({'value': 1, 'timestamp': '2026-01-10T10:00:00Z'})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(Measurement.objects.count(), 0)
        self.assertNotIn(self.api_key, response.content.decode())
        self.assertNotIn(self.sensor.api_key_hash, response.content.decode())

    def test_unregistered_sensor_key_returns_401(self):
        deleted = self.client.delete(
            f'/api/sensors/{self.sensor.id}',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(deleted.status_code, 204)

        response = self.post({'value': 1, 'timestamp': '2026-01-10T10:00:00Z'})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(Measurement.objects.count(), 0)

    def test_admin_token_without_api_key_returns_401(self):
        response = self.post(
            {'value': 1, 'timestamp': '2026-01-10T10:00:00Z'},
            omit_key=True,
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(Measurement.objects.count(), 0)

    def test_admin_token_does_not_replace_api_key(self):
        response = self.post(
            {'value': 2, 'timestamp': '2026-01-10T10:00:00Z'},
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['sensorId'], self.sensor.id)

    def test_missing_value_returns_400(self):
        response = self.post({'timestamp': '2026-01-10T10:00:00Z'})

        self.assertEqual(response.status_code, 400)
        self.assertIn('application/problem+json', response['Content-Type'])
        body = response.json()
        self.assertEqual(body['status'], 400)
        self.assertEqual(body['title'], 'Niepoprawne żądanie')
        self.assertIn('value', [item['field'] for item in body['errors']])
        self.assertEqual(Measurement.objects.count(), 0)

    def test_wrong_types_return_400(self):
        for payload in (
            {'value': 'abc', 'timestamp': '2026-01-10T10:00:00Z'},
            {'value': True, 'timestamp': '2026-01-10T10:00:00Z'},
        ):
            with self.subTest(payload=payload):
                response = self.post(payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['status'], 400)
                self.assertNotIn(b'Traceback', response.content)
        self.assertEqual(Measurement.objects.count(), 0)

    def test_invalid_timestamp_returns_400(self):
        response = self.post({'value': 1, 'timestamp': 'wczoraj'})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 400)
        self.assertIn('timestamp', [item['field'] for item in response.json()['errors']])
        self.assertEqual(Measurement.objects.count(), 0)

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            '/api/measurements',
            '{"value":',
            content_type='application/json',
            HTTP_X_API_KEY=self.api_key,
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn(b'Traceback', response.content)
        self.assertEqual(Measurement.objects.count(), 0)

    def test_plain_text_body_returns_415(self):
        response = self.client.post(
            '/api/measurements',
            'value=1',
            content_type='text/plain',
            HTTP_X_API_KEY=self.api_key,
        )

        self.assertEqual(response.status_code, 415)
        self.assertIn('application/problem+json', response['Content-Type'])
        self.assertEqual(response.json()['status'], 415)
        self.assertEqual(Measurement.objects.count(), 0)

    def test_existing_series_list_stays_public(self):
        self.post({'value': 1, 'timestamp': '2026-01-10T10:00:00Z'})

        response = self.client.get('/api/series')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]['name'], 'Temperatura')
