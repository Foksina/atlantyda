from django.urls import path

from .views import MeasurementCreateView

urlpatterns = [
    path('measurements', MeasurementCreateView.as_view(), name='measurement-list'),
    path('measurements/', MeasurementCreateView.as_view()),
]
