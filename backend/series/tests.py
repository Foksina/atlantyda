from datetime import datetime, timezone

from django.test import SimpleTestCase, TestCase
from django.urls import resolve, reverse
from rest_framework.test import APIClient

from accounts.authentication import issue_access_token
from accounts.models import User
from measurements.models import Measurement
from sensors.models import Sensor
from series.models import Series
from series.serializers import SeriesSerializer


class SeriesApiStructureTests(SimpleTestCase):
    def test_list_url_resolves(self):
        match = resolve('/api/series')
        self.assertEqual(match.url_name, 'series-list')

    def test_detail_url_resolves(self):
        match = resolve('/api/series/12')
        self.assertEqual(match.url_name, 'series-detail')
        self.assertEqual(match.kwargs['series_id'], '12')

    def test_list_url_reverses_without_trailing_slash(self):
        self.assertEqual(reverse('series-list'), '/api/series')

    def test_detail_url_reverses_without_trailing_slash(self):
        self.assertEqual(reverse('series-detail', kwargs={'series_id': '12'}), '/api/series/12')

    def test_serializer_exposes_contract_fields(self):
        self.assertEqual(
            list(SeriesSerializer().fields),
            ['id', 'name', 'minValue', 'maxValue', 'color', 'icon', 'unit'],
        )


class SeriesReadApiTests(TestCase):
    def setUp(self):
        self.client = APIClient(HTTP_HOST='localhost')
        self.temperature = Series.objects.create(
            name='Temperatura',
            unit='°C',
            min_value=0,
            max_value=40,
            color='#1f77b4',
            icon='thermometer',
        )
        self.pressure = Series.objects.create(
            name='Ciśnienie',
            min_value=900,
            max_value=1100,
            color='#ff7f0e',
        )

    def test_list_returns_every_series(self):
        response = self.client.get('/api/series', HTTP_ACCEPT='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertIn('application/json', response['Content-Type'])
        self.assertEqual(
            response.json(),
            [
                {
                    'id': self.temperature.id,
                    'name': 'Temperatura',
                    'minValue': 0,
                    'maxValue': 40,
                    'color': '#1f77b4',
                    'icon': 'thermometer',
                    'unit': '°C',
                },
                {
                    'id': self.pressure.id,
                    'name': 'Ciśnienie',
                    'minValue': 900,
                    'maxValue': 1100,
                    'color': '#ff7f0e',
                    'icon': None,
                    'unit': None,
                },
            ],
        )

    def test_list_is_empty_array_without_series(self):
        Series.objects.all().delete()

        response = self.client.get('/api/series')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_detail_returns_one_series(self):
        response = self.client.get(f'/api/series/{self.temperature.id}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], self.temperature.id)
        self.assertEqual(response.json()['name'], 'Temperatura')
        self.assertEqual(response.json()['minValue'], 0)
        self.assertEqual(response.json()['maxValue'], 40)
        self.assertEqual(response.json()['color'], '#1f77b4')

    def test_missing_series_returns_problem_details(self):
        response = self.client.get('/api/series/999999999')

        self.assertEqual(response.status_code, 404)
        self.assertIn('application/problem+json', response['Content-Type'])
        body = response.json()
        self.assertEqual(body['status'], 404)
        self.assertIsInstance(body['title'], str)
        self.assertTrue(body['title'])

    def test_non_numeric_id_returns_404(self):
        response = self.client.get('/api/series/brak')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['status'], 404)

    def test_unsupported_accept_header_returns_406(self):
        response = self.client.get('/api/series', HTTP_ACCEPT='application/xml')

        self.assertEqual(response.status_code, 406)

    def test_list_stays_public_with_invalid_token(self):
        response = self.client.get('/api/series', HTTP_AUTHORIZATION='Bearer nie-token')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)


class SeriesCreateApiTests(TestCase):
    def setUp(self):
        self.client = APIClient(HTTP_HOST='localhost')
        self.admin = User.objects.create_user(username='admin', password='haslo-testowe')
        self.token = issue_access_token(self.admin)
        self.valid = {
            'name': 'Zasolenie',
            'minValue': 30,
            'maxValue': 40,
            'color': '#1F77B4',
            'icon': 'drop',
            'unit': 'PSU',
        }

    def post(self, data, token=None, **extra):
        headers = {}
        if token is not None:
            headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        return self.client.post('/api/series', data, format='json', **headers, **extra)

    def test_admin_creates_series(self):
        response = self.post(self.valid, token=self.token)

        self.assertEqual(response.status_code, 201)
        self.assertIn('application/json', response['Content-Type'])
        body = response.json()
        self.assertEqual(response['Location'], f'/api/series/{body["id"]}')
        self.assertEqual(body['name'], 'Zasolenie')
        self.assertEqual(body['minValue'], 30)
        self.assertEqual(body['maxValue'], 40)
        self.assertEqual(body['color'], '#1F77B4')
        self.assertEqual(body['icon'], 'drop')
        self.assertEqual(body['unit'], 'PSU')
        detail = self.client.get(response['Location'])
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json(), body)

    def test_optional_fields_may_be_omitted(self):
        payload = {
            'name': 'Prąd',
            'minValue': -2.5,
            'maxValue': 2.5,
            'color': '#abcdef',
        }

        response = self.post(payload, token=self.token)

        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()['icon'])
        self.assertIsNone(response.json()['unit'])

    def test_same_name_can_be_created_twice(self):
        first = self.post(self.valid, token=self.token)
        second = self.post(self.valid, token=self.token)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(first.json()['id'], second.json()['id'])

    def test_missing_required_field_returns_400(self):
        payload = {'minValue': 0, 'maxValue': 1, 'color': '#000000'}

        response = self.post(payload, token=self.token)

        self.assertEqual(response.status_code, 400)
        self.assertIn('application/problem+json', response['Content-Type'])
        body = response.json()
        self.assertEqual(body['status'], 400)
        self.assertTrue(body['title'])
        self.assertIn('name', [item['field'] for item in body['errors']])
        self.assertEqual(Series.objects.count(), 0)

    def test_wrong_types_return_400(self):
        payload = {**self.valid, 'minValue': 'dużo', 'color': 112}

        response = self.post(payload, token=self.token)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 400)
        self.assertEqual(Series.objects.count(), 0)

    def test_boolean_value_is_rejected(self):
        response = self.post({**self.valid, 'maxValue': True}, token=self.token)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Series.objects.count(), 0)

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            '/api/series',
            '{"name":',
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 400)

    def test_equal_range_returns_422(self):
        response = self.post({**self.valid, 'minValue': 10, 'maxValue': 10}, token=self.token)

        self.assertEqual(response.status_code, 422)
        self.assertIn('application/problem+json', response['Content-Type'])
        self.assertEqual(response.json()['status'], 422)
        self.assertEqual(Series.objects.count(), 0)

    def test_reversed_range_returns_422(self):
        response = self.post({**self.valid, 'minValue': 8, 'maxValue': 3}, token=self.token)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(Series.objects.count(), 0)

    def test_invalid_color_returns_422(self):
        response = self.post({**self.valid, 'color': 'niebieski'}, token=self.token)

        self.assertEqual(response.status_code, 422)
        self.assertIn('color', [item['field'] for item in response.json()['errors']])
        self.assertEqual(Series.objects.count(), 0)

    def test_too_long_unit_returns_422(self):
        response = self.post({**self.valid, 'unit': 'x' * 21}, token=self.token)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(Series.objects.count(), 0)

    def test_plain_text_body_returns_415(self):
        response = self.client.post(
            '/api/series',
            'name=Zasolenie',
            content_type='text/plain',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )

        self.assertEqual(response.status_code, 415)
        self.assertIn('application/problem+json', response['Content-Type'])
        self.assertEqual(response.json()['status'], 415)

    def test_missing_token_returns_401(self):
        response = self.post(self.valid)

        self.assertEqual(response.status_code, 401)
        self.assertIn('application/problem+json', response['Content-Type'])
        self.assertEqual(response.json()['status'], 401)
        self.assertEqual(Series.objects.count(), 0)

    def test_forged_token_returns_401(self):
        response = self.post(self.valid, token='eyJhbGciOiJub25lIn0.eyJzdWIiOiJhZG1pbiJ9.')

        self.assertEqual(response.status_code, 401)
        self.assertEqual(Series.objects.count(), 0)

    def test_inactive_administrator_returns_401(self):
        self.admin.is_active = False
        self.admin.save(update_fields=['is_active'])

        response = self.post(self.valid, token=self.token)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(Series.objects.count(), 0)


class SeriesUpdateApiTests(TestCase):
    def setUp(self):
        self.client = APIClient(HTTP_HOST='localhost')
        self.admin = User.objects.create_user(username='admin', password='haslo-testowe')
        self.token = issue_access_token(self.admin)
        self.series = Series.objects.create(
            name='Temperatura',
            min_value=10,
            max_value=30,
            color='#1f77b4',
            icon='thermometer',
            unit='°C',
        )
        self.sensor = Sensor.objects.create(
            name='Czujnik A',
            series=self.series,
            api_key_hash='klucz-a',
        )
        self.measured_at = datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc)
        self.measurement = Measurement.objects.create(
            sensor=self.sensor,
            value=28,
            timestamp=self.measured_at,
        )

    def payload(self, **overrides):
        data = {
            'name': 'Temperatura',
            'minValue': 10,
            'maxValue': 30,
            'color': '#1f77b4',
            'icon': 'thermometer',
            'unit': '°C',
        }
        data.update(overrides)
        return data

    def put(self, data, series_id=None, token=None):
        headers = {}
        if token is not None:
            headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        target = self.series.id if series_id is None else series_id
        return self.client.put(f'/api/series/{target}', data, format='json', **headers)

    def assert_series_unchanged(self):
        self.series.refresh_from_db()
        self.assertEqual(self.series.name, 'Temperatura')
        self.assertEqual(self.series.min_value, 10)
        self.assertEqual(self.series.max_value, 30)
        self.assertEqual(self.series.color, '#1f77b4')
        self.assertEqual(self.series.icon, 'thermometer')
        self.assertEqual(self.series.unit, '°C')

    def assert_measurement_unchanged(self):
        self.measurement.refresh_from_db()
        self.assertEqual(self.measurement.value, 28)
        self.assertEqual(self.measurement.timestamp, self.measured_at)
        self.assertEqual(Measurement.objects.count(), 1)
        self.assertEqual(Sensor.objects.count(), 1)

    def test_admin_updates_series(self):
        response = self.put(
            self.payload(name='Temperatura wody', color='#ff7f0e', icon='wave', unit='K'),
            token=self.token,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                'id': self.series.id,
                'name': 'Temperatura wody',
                'minValue': 10,
                'maxValue': 30,
                'color': '#ff7f0e',
                'icon': 'wave',
                'unit': 'K',
            },
        )
        detail = self.client.get(f'/api/series/{self.series.id}')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json(), response.json())
        self.assert_measurement_unchanged()

    def test_update_without_optional_fields_clears_them(self):
        response = self.put(
            {
                'name': 'Temperatura',
                'minValue': 10,
                'maxValue': 30,
                'color': '#1f77b4',
            },
            token=self.token,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['icon'])
        self.assertIsNone(response.json()['unit'])

    def test_range_update_keeps_fitting_measurements(self):
        response = self.put(self.payload(minValue=20, maxValue=28), token=self.token)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['minValue'], 20)
        self.assertEqual(response.json()['maxValue'], 28)
        self.assert_measurement_unchanged()

    def test_missing_series_returns_404(self):
        response = self.put(self.payload(), series_id=999999999, token=self.token)

        self.assertEqual(response.status_code, 404)
        self.assertIn('application/problem+json', response['Content-Type'])
        self.assertEqual(response.json()['status'], 404)
        self.assertTrue(response.json()['title'])
        self.assert_series_unchanged()

    def test_non_numeric_id_returns_404(self):
        response = self.put(self.payload(), series_id='brak', token=self.token)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['status'], 404)

    def test_missing_required_field_returns_400(self):
        payload = self.payload()
        del payload['name']

        response = self.put(payload, token=self.token)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 400)
        self.assertIn('name', [item['field'] for item in response.json()['errors']])
        self.assert_series_unchanged()

    def test_wrong_type_returns_400(self):
        response = self.put(self.payload(minValue='ciepło'), token=self.token)

        self.assertEqual(response.status_code, 400)
        self.assert_series_unchanged()
        self.assert_measurement_unchanged()

    def test_invalid_range_returns_422(self):
        response = self.put(self.payload(minValue=30, maxValue=10), token=self.token)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['status'], 422)
        self.assert_series_unchanged()

    def test_measurement_above_new_maximum_returns_409(self):
        response = self.put(self.payload(minValue=10, maxValue=25), token=self.token)

        self.assertEqual(response.status_code, 409)
        self.assertIn('application/problem+json', response['Content-Type'])
        self.assertEqual(response.json()['status'], 409)
        self.assertTrue(response.json()['title'])
        self.assert_series_unchanged()
        self.assert_measurement_unchanged()

    def test_measurement_below_new_minimum_returns_409(self):
        response = self.put(self.payload(minValue=29, maxValue=40), token=self.token)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['status'], 409)
        self.assert_series_unchanged()
        self.assert_measurement_unchanged()

    def test_other_series_measurement_does_not_cause_conflict(self):
        other = Series.objects.create(
            name='Ciśnienie',
            min_value=0,
            max_value=200,
            color='#aabbcc',
        )
        other_sensor = Sensor.objects.create(
            name='Czujnik B',
            series=other,
            api_key_hash='klucz-b',
        )
        Measurement.objects.create(
            sensor=other_sensor,
            value=180,
            timestamp=self.measured_at,
        )

        response = self.put(self.payload(minValue=20, maxValue=28), token=self.token)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Measurement.objects.get(pk=self.measurement.pk).value, 28)
        self.assertEqual(Measurement.objects.get(sensor=other_sensor).value, 180)

    def test_missing_token_returns_401(self):
        response = self.put(self.payload(name='Inna nazwa'))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['status'], 401)
        self.assert_series_unchanged()

    def test_get_stays_public_after_update_rules(self):
        response = self.client.get(f'/api/series/{self.series.id}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['name'], 'Temperatura')


class SeriesDeleteApiTests(TestCase):
    def setUp(self):
        self.client = APIClient(HTTP_HOST='localhost')
        self.admin = User.objects.create_user(username='admin', password='haslo-testowe')
        self.token = issue_access_token(self.admin)
        self.measured_at = datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc)
        self.series = self.make_series('Temperatura', 'klucz-a', 28)
        self.other = self.make_series('Ciśnienie', 'klucz-b', 180, color='#aabbcc')

    def make_series(self, name, key, value, color='#1f77b4'):
        series = Series.objects.create(
            name=name,
            min_value=0,
            max_value=200,
            color=color,
        )
        sensor = Sensor.objects.create(name=f'Czujnik {name}', series=series, api_key_hash=key)
        measurement = Measurement.objects.create(
            sensor=sensor,
            value=value,
            timestamp=self.measured_at,
        )
        series.sensor = sensor
        series.measurement = measurement
        return series

    def delete(self, series_id=None, token=None):
        headers = {}
        if token is not None:
            headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        target = self.series.id if series_id is None else series_id
        return self.client.delete(f'/api/series/{target}', **headers)

    def test_admin_deletes_series_and_related_records(self):
        response = self.delete(token=self.token)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b'')
        self.assertFalse(Series.objects.filter(pk=self.series.id).exists())
        self.assertFalse(Sensor.objects.filter(pk=self.series.sensor.id).exists())
        self.assertFalse(Measurement.objects.filter(pk=self.series.measurement.id).exists())
        detail = self.client.get(f'/api/series/{self.series.id}')
        self.assertEqual(detail.status_code, 404)

    def test_other_series_stays_intact(self):
        response = self.delete(token=self.token)

        self.assertEqual(response.status_code, 204)
        self.other.refresh_from_db()
        self.assertEqual(self.other.name, 'Ciśnienie')
        self.assertTrue(Sensor.objects.filter(pk=self.other.sensor.id).exists())
        self.assertEqual(Measurement.objects.get(pk=self.other.measurement.id).value, 180)
        listed = self.client.get('/api/series')
        self.assertEqual([item['id'] for item in listed.json()], [self.other.id])

    def test_missing_series_returns_404(self):
        response = self.delete(series_id=999999999, token=self.token)

        self.assertEqual(response.status_code, 404)
        self.assertIn('application/problem+json', response['Content-Type'])
        self.assertEqual(response.json()['status'], 404)
        self.assertTrue(response.json()['title'])
        self.assertTrue(Series.objects.filter(pk=self.series.id).exists())

    def test_non_numeric_id_returns_404(self):
        response = self.delete(series_id='brak', token=self.token)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['status'], 404)
        self.assertEqual(Series.objects.count(), 2)

    def test_second_delete_returns_404(self):
        first = self.delete(token=self.token)
        second = self.delete(token=self.token)

        self.assertEqual(first.status_code, 204)
        self.assertEqual(second.status_code, 404)

    def test_missing_token_returns_401(self):
        response = self.delete()

        self.assertEqual(response.status_code, 401)
        self.assertIn('application/problem+json', response['Content-Type'])
        self.assertEqual(response.json()['status'], 401)
        self.assertTrue(Series.objects.filter(pk=self.series.id).exists())
        self.assertTrue(Measurement.objects.filter(pk=self.series.measurement.id).exists())

    def test_forged_token_returns_401(self):
        response = self.delete(token='eyJhbGciOiJub25lIn0.eyJzdWIiOiJhZG1pbiJ9.')

        self.assertEqual(response.status_code, 401)
        self.assertEqual(Series.objects.count(), 2)
        self.assertEqual(Measurement.objects.count(), 2)
