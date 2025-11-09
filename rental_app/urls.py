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

     # Tenant URLs
    path('tenants/', views.tenant_list, name='tenant_list'),
    path('tenants/create/', views.tenant_create, name='tenant_create'),
    path('tenants/<int:pk>/', views.tenant_detail, name='tenant_detail'),
    path('tenants/<int:pk>/edit/', views.tenant_edit, name='tenant_edit'),
    path('tenants/<int:pk>/delete/', views.tenant_delete, name='tenant_delete'),
    
    # Active Tenants URLs
    path('active-tenants/', views.active_tenant_list, name='active_tenant_list'),
    
    # Tenancy URLs
    path('tenancies/', views.tenancy_list, name='tenancy_list'),
    path('tenancies/create/', views.tenancy_create, name='tenancy_create'),
    path('tenancies/<int:pk>/', views.tenancy_detail, name='tenancy_detail'),
    path('tenancies/<int:pk>/edit/', views.tenancy_edit, name='tenancy_edit'),
    path('tenancies/<int:pk>/terminate/', views.tenancy_terminate, name='tenancy_terminate'),

    # ==================== RENT PAYMENTS ====================
    path('payments/rent/', views.rent_payments_list, name='rent_payments_list'),
    path('payments/rent/pending/', views.rent_payments_pending, name='rent_payments_pending'),
    path('payments/rent/create/', views.rent_payment_create, name='rent_payment_create'),
    path('payments/rent/<str:mpesa_transaction_id>/', views.rent_payment_detail, name='rent_payment_detail'),
    path('payments/rent/<int:pk>/edit/', views.rent_payment_edit, name='rent_payment_edit'),
    path('payments/rent/<int:pk>/delete/', views.rent_payment_delete, name='rent_payment_delete'),
    
    # ==================== RENT DUES ====================
    path('payments/dues/', views.rent_dues_list, name='rent_dues_list'),
    path('payments/dues/create/', views.rent_due_create, name='rent_due_create'),
    path('payments/dues/<int:pk>/', views.rent_due_detail, name='rent_due_detail'),
    path('payments/dues/<int:pk>/edit/', views.rent_due_edit, name='rent_due_edit'),
    path('payments/dues/<int:pk>/delete/', views.rent_due_delete, name='rent_due_delete'),
    
    # ==================== WATER BILLS ====================
    path('payments/water/', views.water_bills_list, name='water_bills_list'),
    path('payments/water/create/', views.water_bill_create, name='water_bill_create'),
    path('payments/water/<int:pk>/', views.water_bill_detail, name='water_bill_detail'),
    path('payments/water/<int:pk>/edit/', views.water_bill_edit, name='water_bill_edit'),
    path('payments/water/<int:pk>/delete/', views.water_bill_delete, name='water_bill_delete'),
    
    # ==================== ELECTRICITY BILLS ====================
    path('payments/electricity/', views.electricity_bills_list, name='electricity_bills_list'),
    path('payments/electricity/create/', views.electricity_bill_create, name='electricity_bill_create'),
    path('payments/electricity/<int:pk>/', views.electricity_bill_detail, name='electricity_bill_detail'),
    path('payments/electricity/<int:pk>/edit/', views.electricity_bill_edit, name='electricity_bill_edit'),
    path('payments/electricity/<int:pk>/delete/', views.electricity_bill_delete, name='electricity_bill_delete'),
    
    # ==================== DEPOSITS ====================
    path('payments/deposits/', views.deposits_list, name='deposits_list'),
    path('payments/deposits/<int:pk>/', views.deposit_detail, name='deposit_detail'),
    path('payments/deposits/<int:pk>/refund/', views.deposit_refund, name='deposit_refund'),
]