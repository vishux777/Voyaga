from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view()),
    path('login/', views.LoginView.as_view()),
    path('token/refresh/', TokenRefreshView.as_view()),
    path('verify-otp/', views.VerifyOTPView.as_view()),
    path('profile/', views.ProfileView.as_view()),
    path('reviews/', views.ReviewListCreateView.as_view()),
    path('chat/', views.AIChatView.as_view()),
    path('notifications/', views.NotificationListView.as_view()),
    path('notifications/<int:pk>/read/', views.NotificationReadView.as_view()),
]