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
]