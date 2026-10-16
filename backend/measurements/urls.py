from django.urls import path

from .views import MeasurementDetailView, MeasurementListView

urlpatterns = [
    path('measurements', MeasurementListView.as_view(), name='measurement-list'),
    path('measurements/', MeasurementListView.as_view()),
    path(
        'measurements/<str:measurement_id>',
        MeasurementDetailView.as_view(),
        name='measurement-detail',
    ),
    path('measurements/<str:measurement_id>/', MeasurementDetailView.as_view()),
]
