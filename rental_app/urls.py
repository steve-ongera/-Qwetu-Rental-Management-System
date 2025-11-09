from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboards
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('tenant-dashboard/', views.tenant_dashboard, name='tenant_dashboard'),

    # Apartment URLs
    path('apartments/', views.apartment_list, name='apartment_list'),
    path('apartments/create/', views.apartment_create, name='apartment_create'),
    path('apartments/<int:pk>/', views.apartment_detail, name='apartment_detail'),
    path('apartments/<int:pk>/edit/', views.apartment_edit, name='apartment_edit'),
    path('apartments/<int:pk>/delete/', views.apartment_delete, name='apartment_delete'),
    
    # Room URLs
    path('rooms/', views.room_list, name='room_list'),
    path('rooms/create/', views.room_create, name='room_create'),
    path('rooms/<int:pk>/', views.room_detail, name='room_detail'),
    path('rooms/<int:pk>/edit/', views.room_edit, name='room_edit'),
    path('rooms/<int:pk>/delete/', views.room_delete, name='room_delete'),
    
    # Room Type URLs
    path('room-types/', views.room_type_list, name='room_type_list'),
    path('room-types/create/', views.room_type_create, name='room_type_create'),
    path('room-types/<int:pk>/', views.room_type_detail, name='room_type_detail'),
    path('room-types/<int:pk>/edit/', views.room_type_edit, name='room_type_edit'),
    path('room-types/<int:pk>/delete/', views.room_type_delete, name='room_type_delete'),
]