from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from .models import Booking
from .serializers import BookingSerializer
from apps.core.models import AuditLog
import time
import random
import string


def _get_network(currency):
    networks = {
        'btc': 'Bitcoin Network',
        'eth': 'Ethereum (ERC-20)',
        'usdt': 'Tron (TRC-20)',
        'ltc': 'Litecoin Network',
        'bnb': 'BNB Smart Chain (BEP-20)',
        'sol': 'Solana Network',
        'doge': 'Dogecoin Network',
    }
    return networks.get(currency, currency.upper())


def _make_address(currency):
    r = random.choices
    d = 'abcdefghijklmnopqrstuvwxyz0123456789'
    h = 'abcdef0123456789'
    m = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    addresses = {
        'btc':  'bc1q' + ''.join(r(d, k=38)),
        'eth':  '0x'   + ''.join(r(h, k=40)),
        'usdt': 'T'    + ''.join(r(m, k=33)),
        'ltc':  'L'    + ''.join(r(d, k=33)),
        'bnb':  'bnb1' + ''.join(r(d, k=38)),
        'sol':  ''.join(r(m, k=44)),
        'doge': 'D'    + ''.join(r(d, k=33)),
    }
    return addresses.get(currency, addresses['btc'])


class BookingCreateView(generics.CreateAPIView):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def perform_create(self, serializer):
        from apps.payments.models import Transaction
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
        AuditLog.log(user, 'booking_created', {
            'booking_id': booking.id,
            'amount': str(booking.total_price)
        })


class BookingInitiateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from apps.properties.models import Property
        from apps.payments.views import PendingCryptoPayment
        from datetime import date

        listing_id = request.data.get('listing')
        check_in   = request.data.get('check_in')
        check_out  = request.data.get('check_out')
        guests_count = request.data.get('guests_count', 1)
        currency   = str(request.data.get('currency', 'btc')).lower()

        if not listing_id or not check_in or not check_out:
            return Response({
                'error': f'Missing: listing={listing_id}, check_in={check_in}, check_out={check_out}'
            }, status=400)

        try:
            prop = Property.objects.get(id=int(listing_id), is_active=True)
        except (Property.DoesNotExist, ValueError, TypeError):
            return Response({'error': 'Property not found'}, status=404)

        try:
            ci = date.fromisoformat(str(check_in))
            co = date.fromisoformat(str(check_out))
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

        if ci >= co:
            return Response({'error': 'Check-out must be after check-in'}, status=400)

        if Booking.has_conflict(prop, ci, co):
            return Response({'error': 'Selected dates are not available'}, status=400)

        nights    = (co - ci).days
        total     = float(prop.price_per_night) * nights

        rates = {
            'btc': 0.0000156, 'eth': 0.000285, 'usdt': 1.0,
            'ltc': 0.0112,    'bnb': 0.00174,  'sol':  0.00617,
            'doge': 6.82
        }
        rate        = rates.get(currency, 1.0)
        pay_amount  = round(total * rate, 8)
        pay_address = _make_address(currency)
        payment_id  = 'pay_' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))

        PendingCryptoPayment.objects.create(
            user=request.user,
            payment_id=payment_id,
            amount_usd=total,
            currency=currency,
            status='waiting',
            meta={
                'listing_id': int(listing_id),
                'check_in':   str(check_in),
                'check_out':  str(check_out),
                'guests_count': int(guests_count),
                'type': 'booking',
                'pay_address': pay_address,
                'pay_amount':  pay_amount,
            }
        )

        return Response({
            'payment_id':  payment_id,
            'pay_address': pay_address,
            'pay_amount':  pay_amount,
            'pay_currency': currency.upper(),
            'amount_usd':  total,
            'nights':      nights,
            'property':    prop.title,
            'status':      'waiting',
            'network':     _get_network(currency),
            'expires_in':  3600,
        })


class BookingPaymentStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, payment_id):
        from apps.payments.views import PendingCryptoPayment

        try:
            pending = PendingCryptoPayment.objects.get(
                payment_id=payment_id, user=request.user
            )
        except PendingCryptoPayment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=404)

        return Response({
            'status': pending.status,
            'booking_created': pending.status == 'finished',
        })

    def post(self, request, payment_id):
        from apps.payments.views import PendingCryptoPayment
        from apps.properties.models import Property
        from apps.payments.models import Transaction
        from datetime import date

        try:
            pending = PendingCryptoPayment.objects.get(
                payment_id=payment_id, user=request.user
            )
        except PendingCryptoPayment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=404)

        if pending.status == 'finished':
            return Response({'error': 'Already processed'}, status=400)

        meta = pending.meta or {}

        try:
            prop = Property.objects.get(id=meta['listing_id'])
            ci   = date.fromisoformat(meta['check_in'])
            co   = date.fromisoformat(meta['check_out'])

            if Booking.has_conflict(prop, ci, co):
                return Response({'error': 'Dates became unavailable.'}, status=400)

            booking = Booking.objects.create(
                guest=request.user,
                listing=prop,
                check_in=ci,
                check_out=co,
                guests_count=meta.get('guests_count', 1),
                total_price=pending.amount_usd,
                status='confirmed'
            )

            Transaction.objects.create(
                user=request.user,
                booking=booking,
                amount=-pending.amount_usd,
                transaction_type='booking_payment',
                description=f'Crypto ({pending.currency.upper()}) — {prop.title}',
                status='completed'
            )

            AuditLog.log(request.user, 'booking_created_crypto', {
                'booking_id': booking.id,
                'payment_id': payment_id,
                'amount':     pending.amount_usd
            })

            pending.status = 'finished'
            pending.save()

            return Response({
                'status':         'finished',
                'booking_created': True,
                'booking_id':     booking.id,
                'property':       prop.title,
                'amount':         pending.amount_usd
            })

        except Exception as e:
            return Response({'error': str(e)}, status=500)


class BookingListView(generics.ListAPIView):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.filter(
            guest=self.request.user
        ).select_related('listing').order_by('-created_at')

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
        from apps.payments.models import Transaction

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
        return Response({'message': 'Booking cancelled and refunded to wallet successfully'})


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
        from apps.payments.models import Transaction

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
            return Response({'message': 'Booking completed. 97% payout sent to wallet.'})
        return Response({'error': 'Check-out date has not passed yet'}, status=400)