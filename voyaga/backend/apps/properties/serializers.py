from rest_framework import serializers
from .models import Property, PropertyImage
from apps.core.serializers import UserSerializer


class PropertyImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = PropertyImage
        fields = ['id', 'image', 'image_url', 'is_primary']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        elif obj.image:
            return obj.image.url
        return None


class PropertyListSerializer(serializers.ModelSerializer):
    avg_rating = serializers.ReadOnlyField()
    review_count = serializers.ReadOnlyField()
    primary_image_url = serializers.SerializerMethodField()
    host_name = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = ['id', 'title', 'city', 'country', 'property_type', 'price_per_night',
                  'max_guests', 'bedrooms', 'bathrooms', 'avg_rating', 'review_count',
                  'primary_image_url', 'host_name', 'is_active', 'created_at']

    def get_primary_image_url(self, obj):
        request = self.context.get('request')

        # Try prefetched images first (fast path)
        if hasattr(obj, '_prefetched_objects_cache') and 'images' in obj._prefetched_objects_cache:
            images = obj._prefetched_objects_cache['images']
            primary = next((i for i in images if i.is_primary), None)
            if not primary and images:
                primary = images[0]
            if primary and primary.image:
                return request.build_absolute_uri(primary.image.url) if request else primary.image.url

        # Fall back to DB query
        primary = obj.images.filter(is_primary=True).first()
        if not primary:
            primary = obj.images.first()
        if primary and primary.image:
            return request.build_absolute_uri(primary.image.url) if request else primary.image.url

        return None

    def get_host_name(self, obj):
        return f"{obj.host.first_name} {obj.host.last_name}".strip() or obj.host.username


class PropertyDetailSerializer(PropertyListSerializer):
    images = PropertyImageSerializer(many=True, read_only=True)
    host = UserSerializer(read_only=True)

    class Meta(PropertyListSerializer.Meta):
        fields = PropertyListSerializer.Meta.fields + [
            'description', 'address', 'amenities', 'latitude', 'longitude', 'images', 'host'
        ]


class PropertyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = [
            # ── CRITICAL: id must be returned so frontend can upload images ──
            'id',
            'title', 'description', 'property_type', 'city', 'country', 'address',
            'price_per_night', 'max_guests', 'bedrooms', 'bathrooms', 'amenities',
            'latitude', 'longitude'
        ]
        # id is auto-generated, never written by user
        read_only_fields = ['id']

    def create(self, validated_data):
        validated_data['host'] = self.context['request'].user
        return super().create(validated_data)