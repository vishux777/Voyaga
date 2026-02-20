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
        print(f'[CHAT] MISTRAL_API_KEY = "{settings.MISTRAL_API_KEY}"')
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
        history = request.data.get('history', [])

        if not message:
            return Response({'error': 'Message required'}, status=400)

        from apps.properties.models import Property
        props = Property.objects.filter(is_active=True).values(
            'title', 'city', 'country', 'price_per_night', 'property_type'
        )[:8]
        prop_context = "\n".join([
            f"- {p['title']} in {p['city']}, {p['country']}: ${p['price_per_night']}/night ({p['property_type']})"
            for p in props
        ])

        system_prompt = f"""You are Voya, an intelligent and friendly AI travel assistant for Voyaga — a luxury crypto-powered travel platform.

You help users find properties, plan trips, answer booking questions, and suggest destinations.
Be concise, warm, and helpful. Use emojis occasionally to keep things friendly.

Available listings on Voyaga right now:
{prop_context}

Key facts about Voyaga:
- Bookings are paid via cryptocurrency (BTC, ETH, USDT, SOL, etc.)
- Users can list their own properties
- Cancellations give instant refunds
- Reviews are only from verified guests"""

        if settings.MISTRAL_API_KEY:
            try:
                from mistralai import Mistral
                client = Mistral(api_key=settings.MISTRAL_API_KEY)

                messages = [{"role": "system", "content": system_prompt}]

                for h in history[-6:]:
                    if h.get('role') in ('user', 'assistant') and h.get('content'):
                        messages.append({"role": h['role'], "content": h['content']})

                messages.append({"role": "user", "content": message})

                resp = client.chat.complete(
                    model="mistral-small-latest",
                    messages=messages,
                    max_tokens=400
                )
                reply = resp.choices[0].message.content

            except Exception as e:
                import traceback
                traceback.print_exc()
                reply = _smart_reply(message)
        else:
            reply = _smart_reply(message)

        return Response({'reply': reply})

