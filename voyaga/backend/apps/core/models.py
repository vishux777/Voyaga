from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
import random
import string


class User(AbstractUser):
    ROLE_GUEST = 'guest'
    ROLE_HOST = 'host'
    ROLE_ADMIN = 'admin'
    ROLE_CHOICES = [(ROLE_GUEST, 'Guest'), (ROLE_HOST, 'Host'), (ROLE_ADMIN, 'Admin')]

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_GUEST)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    loyalty_points = models.IntegerField(default=0)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

    @property
    def loyalty_tier(self):
        if self.loyalty_points >= 5000:
            return 'Platinum'
        elif self.loyalty_points >= 2000:
            return 'Gold'
        elif self.loyalty_points >= 500:
            return 'Silver'
        return 'Explorer'

    @property
    def loyalty_discount(self):
        """Percentage discount based on tier"""
        tiers = {'Platinum': 10, 'Gold': 7, 'Silver': 5, 'Explorer': 0}
        return tiers.get(self.loyalty_tier, 0)


class OTPCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    @classmethod
    def generate(cls, user):
        code = ''.join(random.choices(string.digits, k=6))
        return cls.objects.create(user=user, code=code)

    def __str__(self):
        return f"{self.user.email} - {self.code}"


class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=200)
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def log(cls, user, action, details=None, request=None):
        ip = None
        if request:
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
        cls.objects.create(user=user, action=action, details=details or {}, ip_address=ip)


class Notification(models.Model):
    TYPES = [
        ('booking', 'Booking'),
        ('cancellation', 'Cancellation'),
        ('review', 'Review'),
        ('system', 'System'),
        ('payout', 'Payout'),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications'
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    notif_type = models.CharField(max_length=20, choices=TYPES, default='system')
    link = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.email} — {self.title}'