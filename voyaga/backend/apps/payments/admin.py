from django.contrib import admin
from .models import Transaction
from .views import PendingCryptoPayment


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'transaction_type', 'amount', 'status', 'created_at']
    list_filter = ['transaction_type', 'status']


@admin.register(PendingCryptoPayment)
class PendingCryptoPaymentAdmin(admin.ModelAdmin):
    list_display = ['user', 'payment_id', 'currency', 'amount_usd', 'status', 'created_at']
    list_filter = ['status', 'currency']