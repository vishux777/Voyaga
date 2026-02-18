from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User
from apps.bookings.models import Review


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'username', 'first_name', 'last_name', 'role', 'password', 'password2']

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError("Passwords don't match.")
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(username=data['email'], password=data['password'])
        if not user:
            raise serializers.ValidationError("Invalid credentials.")
        data['user'] = user
        return data


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name', 'role',
                  'avatar', 'bio', 'phone', 'wallet_balance', 'is_verified', 'created_at']
        read_only_fields = ['id', 'wallet_balance', 'is_verified', 'created_at']


class ReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.SerializerMethodField()
    reviewer_avatar = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ['id', 'reviewer', 'reviewer_name', 'reviewer_avatar',
                  'prop', 'booking', 'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'reviewer', 'created_at']

    def get_reviewer_name(self, obj):
        return f"{obj.reviewer.first_name} {obj.reviewer.last_name}".strip() or obj.reviewer.username

    def get_reviewer_avatar(self, obj):
        if obj.reviewer.avatar:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.reviewer.avatar.url) if request else obj.reviewer.avatar.url
        return None

    def validate(self, data):
        booking = data.get('booking')
        request = self.context.get('request')
        if booking and booking.guest != request.user:
            raise serializers.ValidationError("You can only review your own bookings.")
        if booking and booking.status != 'completed':
            raise serializers.ValidationError("Can only review completed bookings.")
        return data

    def create(self, validated_data):
        validated_data['reviewer'] = self.context['request'].user
        validated_data['prop'] = validated_data['booking'].listing
        return super().create(validated_data)