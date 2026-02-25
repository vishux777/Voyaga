from django.contrib import admin
from .models import Booking, Review

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['id', 'guest', 'listing', 'check_in', 'check_out', 'total_price', 'status']
    list_filter = ['status']
    search_fields = ['guest__email', 'listing__title']

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['reviewer', 'prop', 'rating', 'created_at']