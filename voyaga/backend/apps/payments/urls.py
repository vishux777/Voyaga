from django.urls import path
from . import views

urlpatterns = [
    path('transactions/', views.TransactionListView.as_view()),
    path('wallet/', views.WalletBalanceView.as_view()),
    path('wallet/topup/', views.WalletTopupView.as_view()),
    path('nowpayments/create/', views.NOWPaymentsCreateView.as_view()),
    path('nowpayments/status/<str:payment_id>/', views.NOWPaymentsStatusView.as_view()),
    path('nowpayments/currencies/', views.NOWPaymentsCurrenciesView.as_view()),
    path('withdraw/', views.WithdrawView.as_view()),
]