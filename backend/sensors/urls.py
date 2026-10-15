from django.urls import path

from .views import SensorDetailView, SensorListView

urlpatterns = [
    path('sensors', SensorListView.as_view(), name='sensor-list'),
    path('sensors/', SensorListView.as_view()),
    path('sensors/<str:sensor_id>', SensorDetailView.as_view(), name='sensor-detail'),
    path('sensors/<str:sensor_id>/', SensorDetailView.as_view()),
]
