from django.test import SimpleTestCase
from django.urls import resolve, reverse

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
