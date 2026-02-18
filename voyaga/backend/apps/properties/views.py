from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Q
from .models import Property, PropertyImage
from .serializers import (PropertyListSerializer, PropertyDetailSerializer,
                           PropertyCreateSerializer, PropertyImageSerializer)


class PropertyListView(generics.ListAPIView):
    serializer_class = PropertyListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Property.objects.filter(is_active=True).prefetch_related('images', 'reviews')
        q = self.request.query_params
        if q.get('city'):
            qs = qs.filter(city__icontains=q['city'])
        if q.get('country'):
            qs = qs.filter(country__icontains=q['country'])
        if q.get('type'):
            qs = qs.filter(property_type=q['type'])
        if q.get('min_price'):
            qs = qs.filter(price_per_night__gte=q['min_price'])
        if q.get('max_price'):
            qs = qs.filter(price_per_night__lte=q['max_price'])
        if q.get('guests'):
            qs = qs.filter(max_guests__gte=q['guests'])
        if q.get('search'):
            qs = qs.filter(
                Q(title__icontains=q['search']) |
                Q(city__icontains=q['search']) |
                Q(description__icontains=q['search'])
            )
        sort = q.get('sort', '-created_at')
        if sort in ['-created_at', 'price_per_night', '-price_per_night', 'title']:
            qs = qs.order_by(sort)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


class PropertyDetailView(generics.RetrieveAPIView):
    queryset = Property.objects.filter(is_active=True).prefetch_related('images', 'reviews__reviewer')
    serializer_class = PropertyDetailSerializer
    permission_classes = [permissions.AllowAny]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


class PropertyCreateView(generics.CreateAPIView):
    serializer_class = PropertyCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def perform_create(self, serializer):
        if self.request.user.role != 'host':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only hosts can create listings.")
        serializer.save()


class PropertyUpdateView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PropertyCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Property.objects.filter(host=self.request.user)


class MyPropertiesView(generics.ListAPIView):
    serializer_class = PropertyListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Property.objects.filter(host=self.request.user).prefetch_related('images', 'reviews')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


class PropertyImageUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        try:
            prop = Property.objects.get(pk=pk, host=request.user)
        except Property.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        images = request.FILES.getlist('images')
        if not images:
            return Response({'error': 'No images provided'}, status=400)

        created = []
        for i, img in enumerate(images):
            is_primary = i == 0 and not prop.images.filter(is_primary=True).exists()
            pi = PropertyImage.objects.create(property=prop, image=img, is_primary=is_primary)
            created.append(PropertyImageSerializer(pi, context={'request': request}).data)

        return Response(created, status=201)


class RecommendationsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        user = request.user if request.user.is_authenticated else None

        if user:
            from apps.bookings.models import Booking
            booked_ids = list(Booking.objects.filter(guest=user).values_list('listing_id', flat=True))

            if booked_ids:
                last_prop = Property.objects.filter(id__in=booked_ids).last()
                if last_prop:
                    similar = Property.objects.filter(
                        is_active=True,
                        city=last_prop.city
                    ).exclude(id__in=booked_ids).order_by('-created_at')[:6]

                    if similar.count() >= 3:
                        s = PropertyListSerializer(similar, many=True, context={'request': request})
                        return Response({'type': 'personalized', 'properties': s.data})

        top = Property.objects.filter(is_active=True).prefetch_related('reviews', 'images').order_by('-created_at')[:8]
        s = PropertyListSerializer(top, many=True, context={'request': request})
        return Response({'type': 'popular', 'properties': s.data})