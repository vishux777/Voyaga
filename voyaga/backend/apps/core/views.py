from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import User, OTPCode, AuditLog
from .serializers import RegisterSerializer, LoginSerializer, UserSerializer, ReviewSerializer
from apps.bookings.models import Review


def get_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {'access': str(refresh.access_token), 'refresh': str(refresh)}


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        s = RegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.save()
        otp = OTPCode.generate(user)
        AuditLog.log(user, 'register', {'email': user.email}, request)
        return Response({
            'message': f'Account created! Your OTP is: {otp.code} (dev mode)',
            'user': UserSerializer(user).data,
            'tokens': get_tokens(user)
        }, status=201)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.validated_data['user']
        AuditLog.log(user, 'login', {}, request)
        return Response({'user': UserSerializer(user).data, 'tokens': get_tokens(user)})


class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('code')
        try:
            user = User.objects.get(email=email)
            cutoff = timezone.now() - timedelta(minutes=10)
            otp = OTPCode.objects.filter(
                user=user, code=code, is_used=False, created_at__gte=cutoff
            ).last()
            if not otp:
                return Response({'error': 'Invalid or expired OTP'}, status=400)
            otp.is_used = True
            otp.save()
            user.is_verified = True
            user.save()
            return Response({'message': 'Email verified successfully'})
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ReviewListCreateView(generics.ListCreateAPIView):
    serializer_class = ReviewSerializer

    def get_queryset(self):
        qs = Review.objects.select_related('reviewer', 'prop')
        prop_id = self.request.query_params.get('property')
        if prop_id:
            qs = qs.filter(prop_id=prop_id)
        return qs

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

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

        if settings.OPENAI_API_KEY:
            try:
                from openai import OpenAI
                from apps.properties.models import Property
                client = OpenAI(api_key=settings.OPENAI_API_KEY)
                props = Property.objects.filter(is_active=True).values(
                    'title', 'city', 'price_per_night', 'property_type'
                )[:5]
                prop_context = "\n".join([
                    f"- {p['title']} in {p['city']}: ${p['price_per_night']}/night ({p['property_type']})"
                    for p in props
                ])
                resp = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": f"You are Voya, a helpful AI travel assistant for Voyaga. Be concise. Available listings:\n{prop_context}"},
                        {"role": "user", "content": message}
                    ],
                    max_tokens=300
                )
                reply = resp.choices[0].message.content
            except Exception:
                reply = _smart_reply(message)
        else:
            reply = _smart_reply(message)

        return Response({'reply': reply})


def _smart_reply(message):
    msg = message.lower()
    if any(w in msg for w in ['hello', 'hi', 'hey']):
        return "Hello! I'm Voya, your AI travel assistant. I can help you find the perfect stay, answer questions about bookings, and suggest destinations. What are you looking for?"
    if any(w in msg for w in ['cheap', 'budget', 'affordable']):
        return "For budget-friendly stays, filter by price under $80/night. Our studios and apartments offer excellent value!"
    if any(w in msg for w in ['luxury', 'premium', 'fancy']):
        return "Our luxury villas and penthouses start from $200/night with stunning amenities. Check out our top-rated properties!"
    if any(w in msg for w in ['beach', 'ocean', 'sea', 'maldives', 'bali']):
        return "We have stunning coastal properties! Popular picks: Maldives Overwater Bungalow, Santorini Cliffside Villa, and Ubud Jungle Retreat."
    if any(w in msg for w in ['book', 'reserve', 'booking']):
        return "Booking is easy — find a property, pick your dates, and click Reserve. Payment comes from your wallet balance instantly."
    if any(w in msg for w in ['cancel', 'refund']):
        return "Cancellations are instant with a full wallet refund. Just visit My Bookings and hit Cancel."
    if any(w in msg for w in ['payment', 'pay', 'wallet']):
        return "Voyaga uses a simulated wallet. You start with $500 free. Top up anytime from your dashboard!"
    if any(w in msg for w in ['review', 'rating']):
        return "Only guests who completed a stay can leave reviews — keeping ratings 100% authentic."
    return "I'm Voya, your travel assistant! Ask me about destinations, prices, or how to book. How can I help?"