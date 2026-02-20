from django.urls import path
from . import views

urlpatterns = [
    path('', views.PropertyListView.as_view()),
    path('create/', views.PropertyCreateView.as_view()),
    path('my/', views.MyPropertiesView.as_view(), name='my_properties'),
    path('recommendations/', views.RecommendationsView.as_view()),
    path('<int:pk>/', views.PropertyDetailView.as_view()),
    path('<int:pk>/update/', views.PropertyUpdateView.as_view()),
    path('<int:pk>/images/', views.PropertyImageUploadView.as_view()),
    path('<int:pk>/delist/', views.PropertyDelistView.as_view(), name='property_delist'),
    path('<int:pk>/activate/', views.PropertyActivateView.as_view(), name='property_activate'),
]