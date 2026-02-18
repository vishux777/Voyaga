from django.db import models
from django.conf import settings
from apps.properties.models import Property


class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]

    guest = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookings'
    )
    listing = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='bookings')
    check_in = models.DateField()
    check_out = models.DateField()
    guests_count = models.IntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.guest.email} → {self.listing.title} ({self.check_in} - {self.check_out})"

    @classmethod
    def has_conflict(cls, listing, check_in, check_out, exclude_id=None):
        qs = cls.objects.filter(
            listing=listing,
            status__in=['pending', 'confirmed'],
            check_in__lt=check_out,
            check_out__gt=check_in
        )
        if exclude_id:
            qs = qs.exclude(id=exclude_id)
        return qs.exists()


class Review(models.Model):
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews_given'
    )
    prop = models.ForeignKey(
        'properties.Property', on_delete=models.CASCADE, related_name='reviews'
    )
    booking = models.OneToOneField(
        Booking, on_delete=models.CASCADE, related_name='review'
    )
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('reviewer', 'prop')

    def __str__(self):
        return f"{self.reviewer.email} → {self.prop.title} ({self.rating}★)"