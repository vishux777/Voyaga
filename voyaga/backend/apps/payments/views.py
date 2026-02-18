from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import serializers
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


class WalletTopupView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            amount = float(request.data.get('amount', 0))
        except (TypeError, ValueError):
            return Response({'error': 'Invalid amount'}, status=400)

        if amount <= 0 or amount > 10000:
            return Response({'error': 'Amount must be between $1 and $10,000'}, status=400)

        user = request.user
        user.wallet_balance += amount
        user.save()

        Transaction.objects.create(
            user=user,
            amount=amount,
            transaction_type='wallet_topup',
            description=f"Wallet top-up (simulated)",
            status='completed'
        )
        AuditLog.log(user, 'wallet_topup', {'amount': amount})
        return Response({'message': f'${amount:.2f} added to wallet', 'new_balance': float(user.wallet_balance)})


class WalletBalanceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({'balance': float(request.user.wallet_balance)})
