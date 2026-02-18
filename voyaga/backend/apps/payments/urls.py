from django.urls import path
from . import views

urlpatterns = [
    path('transactions/', views.TransactionListView.as_view()),
    path('wallet/', views.WalletBalanceView.as_view()),
    path('wallet/topup/', views.WalletTopupView.as_view()),
]
