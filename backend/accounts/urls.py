from django.urls import path

from .views import LoginView, LogoutView, PasswordChangeView

urlpatterns = [
    path('auth/login', LoginView.as_view(), name='auth-login'),
    path('auth/login/', LoginView.as_view()),
    path('auth/logout', LogoutView.as_view(), name='auth-logout'),
    path('auth/logout/', LogoutView.as_view()),
    path('auth/password', PasswordChangeView.as_view(), name='auth-password'),
    path('auth/password/', PasswordChangeView.as_view()),
]
