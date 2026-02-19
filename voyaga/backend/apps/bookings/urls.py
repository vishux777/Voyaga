from django.urls import path
from . import views

urlpatterns = [
    path('', views.BookingListView.as_view()),
    path('create/', views.BookingCreateView.as_view()),
    path('initiate/', views.BookingInitiateView.as_view()),
    path('payment-status/<str:payment_id>/', views.BookingPaymentStatusView.as_view()),
    path('host/', views.HostBookingsView.as_view()),
    path('<int:pk>/', views.BookingDetailView.as_view()),
    path('<int:pk>/cancel/', views.BookingCancelView.as_view()),
    path('<int:pk>/complete/', views.CompleteBookingView.as_view()),
]