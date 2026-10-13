from django.test import SimpleTestCase, TestCase
from django.urls import resolve, reverse
from rest_framework.test import APIClient

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
