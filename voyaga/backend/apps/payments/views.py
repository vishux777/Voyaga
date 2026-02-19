from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import serializers
from django.conf import settings
from django.db import models as db_models
import urllib.request
import urllib.error
import json
import time
from .models import Transaction
from apps.core.models import AuditLog


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'amount', 'transaction_type', 'description', 'status', 'booking', 'created_at']


class TransactionListView(generics.ListAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)


class WalletBalanceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({'balance': float(request.user.wallet_balance)})


class WalletTopupView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            amount = float(request.data.get('amount', 0))
        except (TypeError, ValueError):
            return Response({'error': 'Invalid amount'}, status=400)

        if amount <= 0 or amount > 100000:
            return Response({'error': 'Amount must be between $1 and $100,000'}, status=400)

        user = request.user
        user.wallet_balance += amount
        user.save()

        Transaction.objects.create(
            user=user,
            amount=amount,
            transaction_type='wallet_topup',
            description='Wallet top-up (simulated)',
            status='completed'
        )
        AuditLog.log(user, 'wallet_topup', {'amount': amount})
        return Response({
            'message': f'${amount:.2f} added to wallet',
            'new_balance': float(user.wallet_balance)
        })


def nowpayments_request(endpoint, method='GET', data=None):
    api_key = settings.NOWPAYMENTS_API_KEY
    if not api_key:
        raise ValueError('NOWPAYMENTS_API_KEY not set in .env')

    import requests
    url = f'https://api.sandbox.nowpayments.io/v1/{endpoint}'
    headers = {
        'x-api-key': api_key,
        'Content-Type': 'application/json'
    }

    try:
        if method == 'POST':
            resp = requests.post(url, json=data, headers=headers, timeout=15)
        else:
            resp = requests.get(url, headers=headers, timeout=15)

        print(f'[NOWPayments] {method} {url} → {resp.status_code}')

        if not resp.ok:
            print(f'[NOWPayments] Error body: {resp.text}')
            try:
                msg = resp.json().get('message') or resp.text
            except Exception:
                msg = resp.text
            raise ValueError(f'NOWPayments error: {msg}')

        return resp.json()

    except requests.exceptions.ConnectionError as e:
        print(f'[NOWPayments] Connection error: {e}')
        raise ValueError(f'Cannot connect to NOWPayments. Check your internet connection.')
    except requests.exceptions.Timeout:
        raise ValueError('NOWPayments request timed out.')
    except requests.exceptions.RequestException as e:
        raise ValueError(f'Request error: {str(e)}')
    
class PendingCryptoPayment(db_models.Model):
    user = db_models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=db_models.CASCADE,
        related_name='crypto_payments'
    )
    payment_id = db_models.CharField(max_length=100, unique=True)
    amount_usd = db_models.FloatField()
    currency = db_models.CharField(max_length=20)
    status = db_models.CharField(max_length=30, default='waiting')
    meta = db_models.JSONField(default=dict)
    created_at = db_models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'payments'

    def __str__(self):
        return f'{self.user.email} | {self.currency} | ${self.amount_usd} | {self.status}'


class NOWPaymentsCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            amount = float(request.data.get('amount', 0))
            currency = request.data.get('currency', 'btc').lower()
        except (TypeError, ValueError):
            return Response({'error': 'Invalid amount'}, status=400)

        if amount <= 0:
            return Response({'error': 'Amount must be greater than 0'}, status=400)

        if not settings.NOWPAYMENTS_API_KEY:
            return Response({'error': 'NOWPayments API key not configured'}, status=500)

        try:
            payment = nowpayments_request('payment', method='POST', data={
                'price_amount': amount,
                'price_currency': 'usd',
                'pay_currency': currency,
                'order_id': f'voyaga-wallet-{request.user.id}-{int(time.time())}',
                'order_description': f'Voyaga wallet topup for {request.user.email}',
            })

            PendingCryptoPayment.objects.create(
                user=request.user,
                payment_id=payment['payment_id'],
                amount_usd=amount,
                currency=currency,
                status='waiting',
                meta={}
            )

            return Response({
                'payment_id': payment['payment_id'],
                'pay_address': payment.get('pay_address'),
                'pay_amount': payment.get('pay_amount'),
                'pay_currency': payment.get('pay_currency'),
                'amount_usd': amount,
                'status': payment.get('payment_status'),
                'expiry': payment.get('expiration_estimate_date'),
            })

        except ValueError as e:
            return Response({'error': str(e)}, status=400)


class NOWPaymentsStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, payment_id):
        if not settings.NOWPAYMENTS_API_KEY:
            return Response({'error': 'NOWPayments not configured'}, status=500)

        try:
            pending = PendingCryptoPayment.objects.filter(
                payment_id=payment_id,
                user=request.user
            ).first()

            if not pending:
                return Response({'error': 'Payment not found'}, status=404)

            payment = nowpayments_request(f'payment/{payment_id}')
            status = payment.get('payment_status')

            if status in ('finished', 'confirmed') and pending.status not in ('finished', 'confirmed'):
                pending.status = status
                pending.save()

                user = request.user
                user.wallet_balance += pending.amount_usd
                user.save()

                Transaction.objects.create(
                    user=user,
                    amount=pending.amount_usd,
                    transaction_type='wallet_topup',
                    description=f'Crypto topup ({pending.currency.upper()}) — {payment_id}',
                    status='completed'
                )
                AuditLog.log(user, 'nowpayments_topup', {
                    'payment_id': payment_id,
                    'amount': pending.amount_usd,
                    'currency': pending.currency
                })

                return Response({
                    'status': status,
                    'credited': True,
                    'amount': pending.amount_usd,
                    'new_balance': float(user.wallet_balance)
                })

            pending.status = status
            pending.save()

            return Response({
                'status': status,
                'credited': False,
                'pay_address': payment.get('pay_address'),
                'pay_amount': payment.get('pay_amount'),
                'pay_currency': payment.get('pay_currency'),
                'actually_paid': payment.get('actually_paid', 0),
            })

        except ValueError as e:
            return Response({'error': str(e)}, status=400)


class NOWPaymentsCurrenciesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not settings.NOWPAYMENTS_API_KEY:
            return Response({'currencies': ['btc', 'eth', 'usdt', 'ltc', 'bnb', 'sol', 'doge']})
        try:
            data = nowpayments_request('currencies')
            currencies = data.get('currencies', [])[:30]
            return Response({'currencies': currencies})
        except ValueError:
            return Response({'currencies': ['btc', 'eth', 'usdt', 'ltc', 'bnb', 'sol', 'doge']})