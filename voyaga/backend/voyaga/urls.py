from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

T = TemplateView.as_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.core.urls')),
    path('api/properties/', include('apps.properties.urls')),
    path('api/bookings/', include('apps.bookings.urls')),
    path('api/payments/', include('apps.payments.urls')),

    path('', T(template_name='index.html'), name='home'),
    path('properties', T(template_name='properties.html'), name='properties'),
    path('property/<int:pk>', T(template_name='property_detail.html'), name='property_detail'),
    path('dashboard', T(template_name='dashboard.html'), name='dashboard'),
    path('bookings', T(template_name='bookings.html'), name='bookings'),
    path('about', T(template_name='about.html'), name='about'),
    path('profile', T(template_name='profile.html'), name='profile'),
    path('my-listings', T(template_name='my_listings.html'), name='my_listings'),
    path('list-property', T(template_name='list_property.html'), name='list_property'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)