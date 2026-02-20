from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from datetime import timedelta
import random

from .models import User, OTPCode, AuditLog, Notification
from .serializers import RegisterSerializer, LoginSerializer, UserSerializer, ReviewSerializer
from apps.bookings.models import Review


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            AuditLog.log(user, 'register', request=request)
            return Response({
                'user': UserSerializer(user).data,
                'tokens': {'access': str(refresh.access_token), 'refresh': str(refresh)}
            }, status=201)
        return Response(serializer.errors, status=400)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)
            AuditLog.log(user, 'login', request=request)
            return Response({
                'user': UserSerializer(user).data,
                'tokens': {'access': str(refresh.access_token), 'refresh': str(refresh)}
            })
        return Response(serializer.errors, status=400)


class VerifyOTPView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        code = request.data.get('code')
        if not code:
            return Response({'error': 'OTP code required'}, status=400)
        expiry = timezone.now() - timedelta(minutes=10)
        otp = OTPCode.objects.filter(
            user=request.user, code=code, is_used=False, created_at__gte=expiry
        ).first()
        if not otp:
            return Response({'error': 'Invalid or expired OTP'}, status=400)
        otp.is_used = True
        otp.save()
        request.user.is_verified = True
        request.user.save()
        return Response({'message': 'Email verified successfully'})


class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


class ReviewListCreateView(generics.ListCreateAPIView):
    serializer_class = ReviewSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        qs = Review.objects.select_related('reviewer').order_by('-created_at')
        prop_id = self.request.query_params.get('property') or self.request.query_params.get('prop')
        if prop_id:
            qs = qs.filter(prop_id=prop_id)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


class AIChatView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        message = request.data.get('message', '').strip()
        history = request.data.get('history', [])
        if not message:
            return Response({'error': 'Message required'}, status=400)

        # Try Anthropic API first
        try:
            reply = self._claude_reply(message, history, request.user)
            return Response({'reply': reply})
        except Exception:
            pass

        # Fallback to smart replies
        reply = self._smart_reply(message.lower(), request.user)
        return Response({'reply': reply})

    def _claude_reply(self, message, history, user):
        """Use Anthropic Claude API for intelligent responses"""
        import anthropic
        from apps.properties.models import Property
        from apps.bookings.models import Booking, Review as ReviewModel

        # Gather live context from DB
        props = Property.objects.filter(is_active=True).prefetch_related('reviews')[:12]
        prop_context = []
        for p in props:
            avg = p.avg_rating
            prop_context.append(
                f"- {p.title} | {p.city}, {p.country} | ${p.price_per_night}/night | "
                f"{p.property_type} | {p.max_guests} guests | Rating: {avg or 'New'}"
            )

        # Recent reviews for context
        recent_reviews = ReviewModel.objects.select_related('prop', 'reviewer').order_by('-created_at')[:8]
        review_context = [
            f"- {r.reviewer.first_name or r.reviewer.username} gave {r.prop.title} "
            f"{r.rating}★: \"{r.comment[:80]}\"" for r in recent_reviews
        ]

        # User context
        user_bookings = Booking.objects.filter(guest=user).select_related('listing').order_by('-created_at')[:3]
        user_context = f"User: {user.get_full_name() or user.username}, Role: {user.role}, " \
                       f"Loyalty: {getattr(user, 'loyalty_tier', 'Explorer')} " \
                       f"({getattr(user, 'loyalty_points', 0)} pts)"
        if user_bookings:
            past = [b.listing.title for b in user_bookings]
            user_context += f", Past bookings: {', '.join(past)}"

        system_prompt = f"""You are Voya, the friendly and knowledgeable AI travel concierge for Voyaga — a luxury travel platform where properties are booked with cryptocurrency.

PLATFORM FACTS:
- Accepts: Bitcoin, Ethereum, USDT, Solana, Litecoin, BNB, Dogecoin
- Instant full refunds on cancellation
- Hosts earn 97% of every booking, paid instantly on confirmation
- Anyone can list their property — auto-promoted to host
- Carbon footprint tracker shows CO₂, energy, water per booking
- Loyalty program: Explorer → Silver (500pts) → Gold (2000pts) → Platinum (5000pts)
- 1 loyalty point per $1 spent. Points = discounts on future bookings
- Verified reviews only — guests who completed a stay
- Help email: help@voyaga.com

CURRENT PROPERTIES ON VOYAGA:
{chr(10).join(prop_context) if prop_context else 'No properties listed yet.'}

RECENT GUEST REVIEWS:
{chr(10).join(review_context) if review_context else 'No reviews yet.'}

CURRENT USER:
{user_context}

Be conversational, warm, and helpful. Give specific property recommendations when asked. 
Format responses with **bold** for emphasis and use relevant emojis. Keep replies concise but informative (under 200 words).
If asked about a specific property, give real details from the list above.
If asked about reviews, reference actual reviews above."""

        # Build message history for Claude
        messages = []
        for h in history[-8:]:  # last 8 exchanges
            if h.get('role') in ('user', 'assistant') and h.get('content'):
                messages.append({'role': h['role'], 'content': h['content']})
        messages.append({'role': 'user', 'content': message})

        client = anthropic.Anthropic(
            api_key=self._get_api_key()
        )
        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=400,
            system=system_prompt,
            messages=messages
        )
        return response.content[0].text

    def _get_api_key(self):
        import os
        from django.conf import settings
        key = getattr(settings, 'ANTHROPIC_API_KEY', None) or os.environ.get('ANTHROPIC_API_KEY', '')
        if not key:
            raise ValueError('No Anthropic API key configured')
        return key

    def _smart_reply(self, msg, user=None):
        """Fallback smart reply when API is unavailable"""
        from apps.properties.models import Property

        props = Property.objects.filter(is_active=True)[:6]
        prop_names = [f"{p.title} in {p.city} (${p.price_per_night}/night)" for p in props]
        prop_list  = '\n'.join([f'• {n}' for n in prop_names]) if prop_names else '• No listings yet'

        user_name = user.first_name or 'traveller' if user else 'traveller'
        tier = getattr(user, 'loyalty_tier', 'Explorer') if user else 'Explorer'
        pts  = getattr(user, 'loyalty_points', 0) if user else 0

        if any(w in msg for w in ['hello', 'hi', 'hey']):
            return (f"Hello {user_name}! 👋 I'm **Voya**, your AI travel concierge. "
                    f"You're a **{tier}** member with **{pts} loyalty points**! "
                    f"How can I help you plan your next adventure? ✈️")

        if any(w in msg for w in ['luxury', 'villa', 'penthouse', 'premium']):
            return f"🏛️ **Luxury options on Voyaga:**\n\n{prop_list}\n\nAll bookable with crypto. Want to explore any of these?"

        if any(w in msg for w in ['loyalty', 'points', 'tier', 'rewards']):
            return (f"🏆 **Your Loyalty Status:**\n\n"
                    f"Tier: **{tier}** | Points: **{pts}**\n\n"
                    f"• Explorer: 0 pts\n• Silver: 500 pts (5% off)\n"
                    f"• Gold: 2,000 pts (7% off)\n• Platinum: 5,000 pts (10% off)\n\n"
                    f"You earn **1 point per $1** spent on bookings!")

        if any(w in msg for w in ['wishlist', 'saved', 'favourite', 'favorite']):
            return "❤️ **Wishlist Feature:**\n\nHeart any property to save it! Access your saved properties from your profile. Perfect for planning future trips."

        if any(w in msg for w in ['carbon', 'environment', 'eco', 'green']):
            return ("🌱 **Carbon Footprint Tracking:**\n\n"
                    "Every booking shows your environmental impact:\n"
                    "• ✈️ CO₂ emissions per stay\n• ⚡ Energy usage (kWh)\n• 💧 Water consumption (L)\n\n"
                    "Choose greener properties and travel consciously!")

        if any(w in msg for w in ['cancel', 'refund']):
            return "✅ **Instant refunds** on all cancellations — money back to your wallet immediately. No fees, no waiting."

        if any(w in msg for w in ['book', 'how', 'payment', 'crypto']):
            return ("₿ **How to book:**\n\n1. Pick dates & guests\n2. Choose crypto (BTC/ETH/USDT/SOL...)\n"
                    "3. Send to generated address\n4. Confirm — instantly booked! ✅\n\n"
                    "Host gets 97% payout immediately on confirmation.")

        if any(w in msg for w in ['host', 'list', 'earn']):
            return ("🏠 **Become a host:**\n\n• List your property in minutes\n"
                    "• Earn **97% of every booking** — paid instantly\n"
                    "• No approval needed\n• Crypto payouts directly to your wallet")

        if any(w in msg for w in ['available', 'properties', 'stays', 'show']):
            return f"🌍 **Current listings on Voyaga:**\n\n{prop_list}"

        return (f"I'd love to help! Tell me your **destination**, **dates**, or **budget** "
                f"and I'll find the perfect stay. 🗺️\n\nOr ask me about:\n"
                f"• 🏆 Your loyalty points\n• ₿ Crypto payments\n• 🌱 Carbon footprint\n• ❤️ Wishlist")


class NotificationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        notifs = Notification.objects.filter(user=request.user)[:30]
        data = [{
            'id': n.id, 'title': n.title, 'message': n.message,
            'type': n.notif_type, 'link': n.link,
            'is_read': n.is_read, 'created_at': n.created_at.isoformat(),
        } for n in notifs]
        unread = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({'results': data, 'unread': unread})

    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'message': 'All marked as read'})


class NotificationReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        Notification.objects.filter(id=pk, user=request.user).update(is_read=True)
        return Response({'message': 'Marked as read'})