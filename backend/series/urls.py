from django.urls import path

from .views import SeriesDetailView, SeriesListView

urlpatterns = [
    path('series', SeriesListView.as_view(), name='series-list'),
    path('series/', SeriesListView.as_view()),
    path('series/<str:series_id>', SeriesDetailView.as_view(), name='series-detail'),
    path('series/<str:series_id>/', SeriesDetailView.as_view()),
]
