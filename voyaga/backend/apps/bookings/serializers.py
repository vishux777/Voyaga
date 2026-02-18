from rest_framework import serializers
from .models import Booking
from apps.properties.serializers import PropertyListSerializer


class BookingSerializer(serializers.ModelSerializer):
    property_detail = PropertyListSerializer(source='listing', read_only=True)
    nights = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = ['id', 'guest', 'listing', 'property_detail', 'check_in', 'check_out',
                  'guests_count', 'total_price', 'status', 'notes', 'nights', 'created_at']
        read_only_fields = ['id', 'guest', 'total_price', 'status', 'created_at']

    def get_nights(self, obj):
        return (obj.check_out - obj.check_in).days

    def validate(self, data):
        listing = data.get('listing')
        check_in = data.get('check_in')
        check_out = data.get('check_out')

        if not listing:
            raise serializers.ValidationError("listing: This field is required.")
        if check_in >= check_out:
            raise serializers.ValidationError("Check-out must be after check-in.")
        if (check_out - check_in).days < 1:
            raise serializers.ValidationError("Minimum stay is 1 night.")
        if data.get('guests_count', 1) > listing.max_guests:
            raise serializers.ValidationError(f"Max guests allowed: {listing.max_guests}")
        if Booking.has_conflict(listing, check_in, check_out):
            raise serializers.ValidationError("Selected dates are not available.")

        return data

    def create(self, validated_data):
        listing = validated_data['listing']
        nights = (validated_data['check_out'] - validated_data['check_in']).days
        validated_data['total_price'] = listing.price_per_night * nights
        validated_data['guest'] = self.context['request'].user
        return super().create(validated_data)