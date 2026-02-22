from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from decimal import Decimal
from .models import Booking, Wishlist
from .serializers import BookingSerializer
from apps.core.models import AuditLog, Notification
import random
import string
import traceback


def _get_network(currency):
    networks = {
        "btc": "Bitcoin Network", "eth": "Ethereum (ERC-20)",
        "usdt": "Tron (TRC-20)", "ltc": "Litecoin Network",
        "bnb": "BNB Smart Chain (BEP-20)", "sol": "Solana Network",
        "doge": "Dogecoin Network",
    }
    return networks.get(currency, currency.upper())


def _make_address(currency):
    r = random.choices
    d = "abcdefghijklmnopqrstuvwxyz0123456789"
    h = "abcdef0123456789"
    m = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    addresses = {
        "btc":  "bc1q" + "".join(r(d, k=38)),
        "eth":  "0x" + "".join(r(h, k=40)),
        "usdt": "T" + "".join(r(m, k=33)),
        "ltc":  "L" + "".join(r(d, k=33)),
        "bnb":  "bnb1" + "".join(r(d, k=38)),
        "sol":  "".join(r(m, k=44)),
        "doge": "D" + "".join(r(d, k=33)),
    }
    return addresses.get(currency, addresses["btc"])


class BookingCreateView(generics.CreateAPIView):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_create(self, serializer):
        from apps.payments.models import Transaction
        booking = serializer.save()
        user = self.request.user
        if user.wallet_balance < booking.total_price:
            booking.delete()
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Insufficient wallet balance.")
        user.wallet_balance -= Decimal(str(booking.total_price))
        user.save(update_fields=["wallet_balance"])
        booking.status = "confirmed"
        booking.save()
        Transaction.objects.create(
            user=user, booking=booking, amount=-booking.total_price,
            transaction_type="booking_payment",
            description="Payment for " + booking.listing.title,
            status="completed"
        )
        AuditLog.log(user, "booking_created", {"booking_id": booking.id, "amount": str(booking.total_price)})


class BookingInitiateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from apps.payments.views import PendingCryptoPayment
        from apps.properties.models import Property
        from datetime import date

        listing_id   = request.data.get("listing")
        check_in     = request.data.get("check_in")
        check_out    = request.data.get("check_out")
        guests_count = request.data.get("guests_count", 1)
        currency     = str(request.data.get("currency", "btc")).lower()

        if not listing_id or not check_in or not check_out:
            return Response({"error": "listing, check_in, check_out are required"}, status=400)

        try:
            prop = Property.objects.get(id=int(listing_id), is_active=True)
        except (Property.DoesNotExist, ValueError, TypeError):
            return Response({"error": "Property not found"}, status=404)

        try:
            ci = date.fromisoformat(str(check_in))
            co = date.fromisoformat(str(check_out))
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=400)

        if ci >= co:
            return Response({"error": "Check-out must be after check-in"}, status=400)

        if Booking.has_conflict(prop, ci, co):
            return Response({"error": "Selected dates are not available"}, status=400)

        nights     = (co - ci).days
        total      = float(prop.price_per_night) * nights
        rates      = {"btc": 0.0000156, "eth": 0.000285, "usdt": 1.0,
                      "ltc": 0.0112, "bnb": 0.00174, "sol": 0.00617, "doge": 6.82}
        pay_amount  = round(total * rates.get(currency, 1.0), 8)
        pay_address = _make_address(currency)
        payment_id  = "pay_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=16))

        PendingCryptoPayment.objects.create(
            user=request.user, payment_id=payment_id, amount_usd=total,
            currency=currency, status="waiting",
            meta={"listing_id": int(listing_id), "check_in": str(check_in),
                  "check_out": str(check_out), "guests_count": int(guests_count),
                  "type": "booking", "pay_address": pay_address, "pay_amount": pay_amount}
        )
        return Response({
            "payment_id": payment_id, "pay_address": pay_address,
            "pay_amount": pay_amount, "pay_currency": currency.upper(),
            "amount_usd": total, "nights": nights, "property": prop.title,
            "status": "waiting", "network": _get_network(currency), "expires_in": 3600,
        })


class BookingPaymentStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, payment_id):
        from apps.payments.views import PendingCryptoPayment
        try:
            pending = PendingCryptoPayment.objects.get(payment_id=payment_id, user=request.user)
        except PendingCryptoPayment.DoesNotExist:
            return Response({"error": "Payment not found"}, status=404)
        return Response({"status": pending.status, "booking_created": pending.status == "finished"})

    def post(self, request, payment_id):
        from apps.payments.views import PendingCryptoPayment
        from apps.properties.models import Property
        from apps.payments.models import Transaction
        from datetime import date

        try:
            pending = PendingCryptoPayment.objects.get(payment_id=payment_id, user=request.user)
        except PendingCryptoPayment.DoesNotExist:
            return Response({"error": "Payment not found"}, status=404)

        if pending.status == "finished":
            return Response({"error": "Already processed"}, status=400)

        meta = pending.meta or {}

        # ── Step 1: get property & dates ──────────────────────────
        try:
            prop = Property.objects.get(id=meta["listing_id"])
        except (Property.DoesNotExist, KeyError):
            return Response({"error": "Property not found"}, status=404)

        try:
            ci = date.fromisoformat(meta["check_in"])
            co = date.fromisoformat(meta["check_out"])
        except (KeyError, ValueError) as e:
            return Response({"error": "Invalid date in payment record: " + str(e)}, status=400)

        if Booking.has_conflict(prop, ci, co):
            return Response({"error": "Dates became unavailable."}, status=400)

        # ── Step 2: create booking ─────────────────────────────────
        try:
            booking = Booking.objects.create(
                guest=request.user, listing=prop, check_in=ci, check_out=co,
                guests_count=meta.get("guests_count", 1),
                total_price=Decimal(str(pending.amount_usd)),
                status="confirmed"
            )
        except Exception as e:
            return Response({"error": "Booking creation failed: " + str(e)}, status=500)

        # ── Step 3: guest transaction ──────────────────────────────
        try:
            Transaction.objects.create(
                user=request.user, booking=booking,
                amount=-Decimal(str(pending.amount_usd)),
                transaction_type="booking_payment",
                description="Crypto (" + pending.currency.upper() + ") for " + prop.title,
                status="completed"
            )
        except Exception:
            pass  # non-fatal

        # ── Step 4: host payout 97% ────────────────────────────────
        points_earned = 0
        try:
            payout = round(float(pending.amount_usd) * 0.97, 2)
            host   = prop.host
            # Use F() expression to avoid float/Decimal type conflict
            from django.db.models import F
            Property.objects.filter(pk=prop.pk)  # just keep import happy
            from apps.core.models import User as CoreUser
            CoreUser.objects.filter(pk=host.pk).update(
                wallet_balance=F("wallet_balance") + Decimal(str(payout))
            )
            host.refresh_from_db()

            Transaction.objects.create(
                user=host, booking=booking,
                amount=Decimal(str(payout)),
                transaction_type="host_payout",
                description="Instant payout for " + prop.title,
                status="completed"
            )

            # Notify host
            guest_name = request.user.get_full_name().strip() or request.user.username
            Notification.objects.create(
                user=host,
                title="New Booking + Payout! ",
                message=(guest_name + " booked " + prop.title + " from " + str(ci) +
                         " to " + str(co) + ". $" + str(payout) + " (97%) added to your wallet instantly!"),
                notif_type="booking", link="/my-listings"
            )
        except Exception:
            pass  # host payout failure is non-fatal to booking

        # ── Step 5: loyalty points ─────────────────────────────────
        try:
            points_earned = int(float(pending.amount_usd))
            from apps.core.models import User as CoreUser
            CoreUser.objects.filter(pk=request.user.pk).update(
                loyalty_points=F("loyalty_points") + points_earned
            )
        except Exception:
            points_earned = 0  # non-fatal

        # ── Step 6: finalise ───────────────────────────────────────
        try:
            AuditLog.log(request.user, "booking_created_crypto",
                         {"booking_id": booking.id, "payment_id": payment_id,
                          "amount": str(pending.amount_usd)})
        except Exception:
            pass

        pending.status = "finished"
        pending.save()

        return Response({
            "status": "finished", "booking_created": True,
            "booking_id": booking.id, "property": prop.title,
            "amount": str(pending.amount_usd), "points_earned": points_earned,
        })


class BookingListView(generics.ListAPIView):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.filter(guest=self.request.user).select_related("listing").order_by("-created_at")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
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
        from django.db.models import F

        try:
            booking = Booking.objects.get(pk=pk, guest=request.user)
        except Booking.DoesNotExist:
            return Response({"error": "Booking not found"}, status=404)

        if booking.status not in ["pending", "confirmed"]:
            return Response({"error": "Cannot cancel this booking"}, status=400)

        booking.status = "cancelled"
        booking.save()

        # Refund guest using F() to avoid type issues
        from apps.core.models import User as CoreUser
        CoreUser.objects.filter(pk=request.user.pk).update(
            wallet_balance=F("wallet_balance") + booking.total_price
        )

        try:
            Transaction.objects.create(
                user=request.user, booking=booking, amount=booking.total_price,
                transaction_type="refund",
                description="Refund for cancelled " + booking.listing.title,
                status="completed"
            )
        except Exception:
            pass

        # Claw back host payout
        try:
            payout = Decimal(str(round(float(booking.total_price) * 0.97, 2)))
            host   = booking.listing.host
            CoreUser.objects.filter(pk=host.pk).update(
                wallet_balance=F("wallet_balance") - payout
            )
            Transaction.objects.create(
                user=host, booking=booking, amount=-payout,
                transaction_type="payout_reversal",
                description="Reversed — booking cancelled for " + booking.listing.title,
                status="completed"
            )
            user_name = request.user.get_full_name() or request.user.username
            Notification.objects.create(
                user=host, title="Booking Cancelled",
                message=(user_name + " cancelled their booking for " + booking.listing.title +
                         ". $" + str(payout) + " reversed from your wallet."),
                notif_type="cancellation", link="/my-listings"
            )
        except Exception:
            pass

        AuditLog.log(request.user, "booking_cancelled", {"booking_id": booking.id})
        return Response({"message": "Booking cancelled and refunded successfully"})


class HostBookingsView(generics.ListAPIView):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.filter(
            listing__host=self.request.user
        ).select_related("listing", "guest").order_by("-created_at")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class CompleteBookingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            booking = Booking.objects.get(pk=pk)
            if booking.listing.host != request.user:
                return Response({"error": "Unauthorized"}, status=403)
        except Booking.DoesNotExist:
            return Response({"error": "Not found"}, status=404)
        booking.status = "completed"
        booking.save()
        return Response({"message": "Booking marked as completed."})


class PropertyAvailabilityView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        from apps.properties.models import Property
        from datetime import timedelta
        try:
            prop = Property.objects.get(pk=pk)
        except Property.DoesNotExist:
            return Response({"error": "Not found"}, status=404)

        bookings = Booking.objects.filter(
            listing=prop, status__in=["confirmed", "pending"]
        ).values("check_in", "check_out")

        blocked = []
        for b in bookings:
            d = b["check_in"]
            while d < b["check_out"]:
                blocked.append(d.isoformat())
                from datetime import timedelta as td
                d = d.__class__(d.year, d.month, d.day) + td(days=1)
                d = (b["check_in"].__class__)(d.year, d.month, d.day)
                # safer loop
                break
        # redo blocked dates properly
        blocked = []
        for b in bookings:
            from datetime import timedelta as td
            start = b["check_in"]
            end   = b["check_out"]
            cur   = start
            while cur < end:
                blocked.append(cur.isoformat())
                import datetime
                cur = cur + td(days=1)

        return Response({"blocked_dates": blocked})


class WishlistView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.properties.serializers import PropertyListSerializer
        items      = Wishlist.objects.filter(user=request.user).select_related("property")
        properties = [item.property for item in items]
        data       = PropertyListSerializer(properties, many=True, context={"request": request}).data
        return Response({"results": data, "count": len(data)})

    def post(self, request):
        from apps.properties.models import Property
        prop_id = request.data.get("property")
        if not prop_id:
            return Response({"error": "property id required"}, status=400)
        try:
            prop = Property.objects.get(id=prop_id)
        except Property.DoesNotExist:
            return Response({"error": "Property not found"}, status=404)
        obj, created = Wishlist.objects.get_or_create(user=request.user, property=prop)
        if created:
            return Response({"message": "Added to wishlist", "wishlisted": True}, status=201)
        obj.delete()
        return Response({"message": "Removed from wishlist", "wishlisted": False})


class WishlistCheckView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        wishlisted = Wishlist.objects.filter(user=request.user, property_id=pk).exists()
        return Response({"wishlisted": wishlisted})


class HostAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.properties.models import Property
        from datetime import date

        props     = Property.objects.filter(host=request.user)
        prop_ids  = list(props.values_list("id", flat=True))
        all_b     = Booking.objects.filter(listing_id__in=prop_ids)
        confirmed = all_b.filter(status__in=["confirmed", "completed"])

        total_revenue  = confirmed.aggregate(s=Sum("total_price"))["s"] or 0
        total_earnings = round(float(total_revenue) * 0.97, 2)

        today       = date.today()
        month_start = today.replace(day=1)
        month_b     = confirmed.filter(created_at__date__gte=month_start)
        month_rev   = month_b.aggregate(s=Sum("total_price"))["s"] or 0

        monthly = []
        for i in range(5, -1, -1):
            m = today.month - i
            y = today.year
            if m <= 0:
                m += 12
                y -= 1
            rev = confirmed.filter(created_at__year=y, created_at__month=m
                                   ).aggregate(s=Sum("total_price"))["s"] or 0
            cnt = confirmed.filter(created_at__year=y, created_at__month=m).count()
            monthly.append({
                "month": date(y, m, 1).strftime("%b"),
                "earnings": round(float(rev) * 0.97, 2),
                "bookings": cnt,
            })

        prop_stats = []
        for p in props:
            b   = confirmed.filter(listing=p)
            rev = b.aggregate(s=Sum("total_price"))["s"] or 0
            prop_stats.append({
                "id": p.id, "title": p.title, "city": p.city,
                "bookings": b.count(),
                "earnings": round(float(rev) * 0.97, 2),
                "avg_rating": p.avg_rating,
                "is_active": p.is_active,
            })

        avg_r = props.aggregate(r=Avg("reviews__rating"))["r"]

        return Response({
            "total_earnings":  total_earnings,
            "total_bookings":  confirmed.count(),
            "month_earnings":  round(float(month_rev) * 0.97, 2),
            "month_bookings":  month_b.count(),
            "total_listings":  props.count(),
            "active_listings": props.filter(is_active=True).count(),
            "monthly":         monthly,
            "properties":      prop_stats,
            "avg_rating":      round(avg_r, 1) if avg_r else None,
        })