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
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                }
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
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                }
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
            user=request.user,
            code=code,
            is_used=False,
            created_at__gte=expiry
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
        if not message:
            return Response({'error': 'Message required'}, status=400)

        reply = self._smart_reply(message.lower())
        return Response({'reply': reply})

    def _smart_reply(self, msg):
        import random

        if any(w in msg for w in ['hello', 'hi', 'hey', 'greet', 'good morning', 'good evening']):
            return random.choice([
                "Hello! I'm **Voya**, your AI travel companion on Voyaga! 🌍 I can help you discover luxury villas, budget studios, beachfront stays, and more — all bookable with crypto. Where would you like to go?",
                "Hey there, traveller! 👋 I'm Voya, your personal AI concierge. Tell me your dream destination and I'll find the perfect stay for you!",
            ])

        if any(w in msg for w in ['luxury', 'villa', 'penthouse', 'premium', 'high end', 'upscale']):
            return "🏛️ **Luxury Collection on Voyaga:**\n\nOur finest properties include:\n• **Santorini Cliffside Villa** — $420/night, infinity pool + caldera views\n• **Maldives Overwater Bungalow** — $650/night, glass floor, private lagoon\n• **Swiss Alps Chalet** — $380/night, ski-in/ski-out\n• **Bali Jungle Retreat** — $280/night, private pool + yoga pavilion\n\nAll accept crypto. Want me to refine by destination or budget?"

        if any(w in msg for w in ['budget', 'cheap', 'affordable', 'cheap', 'low cost', 'inexpensive']):
            return "💰 **Budget-Friendly Stays on Voyaga:**\n\nGreat value options starting from:\n• **Tokyo Studio** — $85/night, city center, fast wifi\n• **Copenhagen Apartment** — $95/night, design district\n• **Bali Studio** — $75/night, rice field views\n• **New York Apartment** — $110/night, Manhattan\n\nAll include free cancellation. Which city interests you?"

        if any(w in msg for w in ['beach', 'ocean', 'sea', 'coastal', 'maldives', 'santorini', 'bali']):
            return "🌊 **Beach & Coastal Properties:**\n\n• **Maldives** — Overwater bungalows from $450/night\n• **Santorini, Greece** — Cliffside villas from $320/night\n• **Bali, Indonesia** — Beachfront villas from $150/night\n• **Amalfi Coast** — Sea-view apartments from $180/night\n\nCrystal waters, private pools, and full crypto payment support. Interested in any of these?"

        if any(w in msg for w in ['book', 'booking', 'reserve', 'how to book', 'how do i book']):
            return "📋 **How to Book on Voyaga:**\n\n1. Browse properties on the **Stays** page\n2. Select your dates and guest count\n3. Choose your cryptocurrency (BTC, ETH, USDT, SOL, and more)\n4. Send payment to the generated wallet address\n5. Confirm payment — booking is instantly confirmed ✅\n\nNo banks, no credit cards. Pure crypto. Need help with anything specific?"

        if any(w in msg for w in ['cancel', 'refund', 'cancellation']):
            return "✅ **Voyaga Cancellation Policy:**\n\nWe offer **instant full refunds** on all cancellations:\n• Cancel any confirmed booking from your dashboard\n• Refund goes immediately to your Voyaga wallet\n• No fees, no waiting period\n• Wallet balance can be withdrawn to any crypto address\n\nSimple, fair, and instant — that's how it should be."

        if any(w in msg for w in ['crypto', 'bitcoin', 'ethereum', 'payment', 'pay', 'currency']):
            return "₿ **Crypto Payments on Voyaga:**\n\nWe accept 7 cryptocurrencies:\n• **Bitcoin (BTC)** — Most trusted\n• **Ethereum (ETH)** — Fast & popular\n• **USDT (TRC-20)** — Stable, no volatility\n• **Solana (SOL)** — Ultra-fast, low fees\n• **Litecoin (LTC)** — Quick settlement\n• **BNB** — BNB Smart Chain\n• **Dogecoin (DOGE)** — Community favourite\n\nAll transactions verified on-chain. Zero hidden fees."

        if any(w in msg for w in ['host', 'list', 'listing', 'rent out', 'my property', 'become a host']):
            return "🏠 **Become a Host on Voyaga:**\n\n1. Click **Host** in the navigation bar\n2. Fill in your property details and photos\n3. Your listing goes live instantly\n4. Earn **97% of every booking** — direct to your wallet\n\nAny authenticated user can list — no approval needed. Start earning crypto from your property today!"

        if any(w in msg for w in ['paris', 'france']):
            return "🗼 **Paris, France:**\n\nVoyaga has curated Haussmann apartments in Le Marais, studios near the Eiffel Tower, and loft-style penthouses in Saint-Germain. Prices from $120/night. Perfect for romantic getaways or solo exploration. Shall I show you available dates?"

        if any(w in msg for w in ['tokyo', 'japan']):
            return "🗾 **Tokyo, Japan:**\n\nChoose from minimalist studios in Shinjuku, traditional machiya homes in Yanaka, or modern apartments in Shibuya. From $85/night. Best visited March–May (cherry blossoms) or Oct–Nov. Interested?"

        if any(w in msg for w in ['review', 'rating', 'trust', 'verified']):
            return "⭐ **Verified Reviews on Voyaga:**\n\nEvery review is from a real guest who completed a verified stay. No fake reviews, no paid placements — ever. Guests can also upload photos with their reviews for extra authenticity.\n\nOur average rating across all properties is 4.7/5 ⭐"

        if any(w in msg for w in ['carbon', 'environment', 'eco', 'green', 'sustainable', 'footprint']):
            return "🌱 **Carbon Footprint Tracking:**\n\nEvery Voyaga booking shows your environmental impact:\n• ✈️ **Travel emissions** — CO₂ per stay\n• ⚡ **Energy usage** — kWh per night\n• 💧 **Water consumption** — litres per night\n\nWe calculate this based on property type, location, and amenities. Choose lower-impact properties and travel more consciously!"

        if any(w in msg for w in ['security', 'safe', 'secure', 'trust']):
            return "🔐 **Voyaga Security Standards:**\n\n• **JWT Authentication** — Short-lived tokens, auto-refresh\n• **On-chain verification** — Every payment verified on blockchain\n• **Full audit logs** — Every action timestamped and logged\n• **OTP email verification** — Account security on signup\n• **Role-based access** — Guests, hosts, and admins fully separated\n• **Encrypted passwords** — PBKDF2 hashing, never plaintext\n\nYour data and funds are always protected."

        if any(w in msg for w in ['recommend', 'suggest', 'best', 'top', 'popular']):
            return "✨ **Top Picks Right Now:**\n\n🏝️ **Maldives Overwater Bungalow** — $650/night · Glass floor, private lagoon\n🏛️ **Santorini Cliffside Villa** — $420/night · Infinity pool, caldera views\n🌿 **Bali Jungle Retreat** — $280/night · Private pool, yoga pavilion\n🗼 **Paris Le Marais Loft** — $195/night · 5-min walk to the Louvre\n\nAll bookable instantly with crypto. Want details on any of these?"

        if any(w in msg for w in ['thank', 'thanks', 'bye', 'goodbye', 'great', 'awesome', 'perfect']):
            return random.choice([
                "You're so welcome! 🌟 Have an amazing trip — Voyaga will be here whenever you're ready to explore again. Safe travels! ✈️",
                "Happy to help! 😊 Whenever you're ready to book your next adventure, just ask. Bon voyage! 🌍",
            ])

        if any(w in msg for w in ['withdraw', 'wallet', 'balance', 'payout']):
            return "💸 **Voyaga Wallet & Withdrawals:**\n\nYour Voyaga wallet holds your balance from refunds and host payouts. You can withdraw anytime:\n• Minimum withdrawal: $10\n• Supported: BTC, ETH, USDT, LTC, BNB, SOL, DOGE\n• Processing time: within 24 hours\n\nGo to **Profile → Withdraw** to cash out."

        return random.choice([
            "Great question! 🌍 Tell me more — are you looking for a specific destination, property type, or budget range? I'll find the perfect match for you.",
            "I'd love to help you plan that trip! Could you share a destination or travel dates? Voyaga has incredible properties worldwide. 🗺️",
            "Hmm, let me think about that! 🤔 For best results, tell me: **Where** do you want to go, **when**, and what's your **budget**?",
        ])


class NotificationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        notifs = Notification.objects.filter(user=request.user)[:30]
        data = [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'type': n.notif_type,
            'link': n.link,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat(),
        } for n in notifs]
        unread = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({'results': data, 'unread': unread})

    def post(self, request):
        # Mark all as read
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'message': 'All marked as read'})


class NotificationReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        Notification.objects.filter(id=pk, user=request.user).update(is_read=True)
        return Response({'message': 'Marked as read'})