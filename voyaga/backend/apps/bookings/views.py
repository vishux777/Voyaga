from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from .models import Booking
from .serializers import BookingSerializer
from apps.payments.models import Transaction
from apps.core.models import AuditLog


class BookingCreateView(generics.CreateAPIView):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def perform_create(self, serializer):
        booking = serializer.save()
        user = self.request.user

        if user.wallet_balance < booking.total_price:
            booking.delete()
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Insufficient wallet balance.")

        user.wallet_balance -= booking.total_price
        user.save()
        booking.status = 'confirmed'
        booking.save()

        Transaction.objects.create(
            user=user,
            booking=booking,
            amount=-booking.total_price,
            transaction_type='booking_payment',
            description=f"Payment for {booking.listing.title}",
            status='completed'
        )
        AuditLog.log(user, 'booking_created', {'booking_id': booking.id, 'amount': str(booking.total_price)})


class BookingListView(generics.ListAPIView):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.filter(guest=self.request.user).select_related('listing').order_by('-created_at')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


class BookingDetailView(generics.RetrieveAPIView):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.filter(guest=self.request.user)


class BookingCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            booking = Booking.objects.get(pk=pk, guest=request.user)
        except Booking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=404)

        if booking.status not in ['pending', 'confirmed']:
            return Response({'error': 'Cannot cancel this booking'}, status=400)

        booking.status = 'cancelled'
        booking.save()

        user = request.user
        user.wallet_balance += booking.total_price
        user.save()

        Transaction.objects.create(
            user=user,
            booking=booking,
            amount=booking.total_price,
            transaction_type='refund',
            description=f"Refund for cancelled {booking.listing.title}",
            status='completed'
        )
        AuditLog.log(user, 'booking_cancelled', {'booking_id': booking.id})
        return Response({'message': 'Booking cancelled and refunded successfully'})


class HostBookingsView(generics.ListAPIView):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.filter(
            listing__host=self.request.user
        ).select_related('listing', 'guest').order_by('-created_at')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


class CompleteBookingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            booking = Booking.objects.get(pk=pk)
            if booking.listing.host != request.user:
                return Response({'error': 'Unauthorized'}, status=403)
        except Booking.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        if booking.check_out <= timezone.now().date():
            booking.status = 'completed'
            booking.save()
            host = request.user
            payout = booking.total_price * 97 / 100
            host.wallet_balance += payout
            host.save()
            Transaction.objects.create(
                user=host,
                booking=booking,
                amount=payout,
                transaction_type='host_payout',
                description=f"Payout for {booking.listing.title}",
                status='completed'
            )
            return Response({'message': 'Booking completed. 97% payout sent to your wallet.'})
        return Response({'error': 'Booking check-out date has not passed yet'}, status=400)