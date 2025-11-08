from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json
from calendar import monthrange

from .models import (
    User, Apartment, Room, Tenancy, RentPayment, 
    RentDue, WaterBill, ElectricityBill, Notification
)


def login_view(request):
    """Handle user login"""
    if request.user.is_authenticated:
        # Redirect based on user type
        if request.user.user_type == 'admin':
            return redirect('admin_dashboard')
        else:
            return redirect('tenant_dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if user.user_status == 'active':
                login(request, user)
                messages.success(request, f'Welcome back, {user.get_full_name()}!')
                
                # Redirect based on user type
                if user.user_type == 'admin':
                    return redirect('admin_dashboard')
                else:
                    return redirect('tenant_dashboard')
            else:
                messages.error(request, 'Your account is inactive. Please contact support.')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'login.html')


def logout_view(request):
    """Handle user logout"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


@login_required
def admin_dashboard(request):
    """Admin dashboard with analytics"""
    if request.user.user_type != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('tenant_dashboard')
    
    # Get all apartments owned by this admin
    apartments = Apartment.objects.filter(owner=request.user)
    
    # Current month and year
    today = timezone.now().date()
    current_month = today.replace(day=1)
    last_month = (current_month - timedelta(days=1)).replace(day=1)
    
    # Summary Statistics
    total_apartments = apartments.count()
    total_rooms = Room.objects.filter(apartment__owner=request.user).count()
    occupied_rooms = Room.objects.filter(
        apartment__owner=request.user,
        status='occupied'
    ).count()
    available_rooms = Room.objects.filter(
        apartment__owner=request.user,
        status='available'
    ).count()
    
    # Active tenancies
    active_tenancies = Tenancy.objects.filter(
        apartment__owner=request.user,
        status='active'
    ).count()
    
    # Financial Statistics - Current Month
    current_month_payments = RentPayment.objects.filter(
        apartment__owner=request.user,
        payment_for_month=current_month,
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Expected rent for current month
    expected_rent = RentDue.objects.filter(
        tenancy__apartment__owner=request.user,
        month_for=current_month
    ).aggregate(total=Sum('amount_due'))['total'] or Decimal('0.00')
    
    # Outstanding rent
    outstanding_rent = RentDue.objects.filter(
        tenancy__apartment__owner=request.user,
        status__in=['unpaid', 'partially_paid', 'overdue']
    ).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
    
    # Overdue payments count
    overdue_count = RentDue.objects.filter(
        tenancy__apartment__owner=request.user,
        status='overdue'
    ).count()
    
    # Revenue trend - Last 6 months (for line chart)
    revenue_data = []
    months_labels = []
    for i in range(5, -1, -1):
        month_date = (current_month - timedelta(days=i*30)).replace(day=1)
        month_revenue = RentPayment.objects.filter(
            apartment__owner=request.user,
            payment_for_month=month_date,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        revenue_data.append(float(month_revenue))
        months_labels.append(month_date.strftime('%b %Y'))
    
    # Payment status distribution (for donut chart)
    payment_status = {
        'paid': RentDue.objects.filter(
            tenancy__apartment__owner=request.user,
            month_for=current_month,
            status='paid'
        ).count(),
        'partially_paid': RentDue.objects.filter(
            tenancy__apartment__owner=request.user,
            month_for=current_month,
            status='partially_paid'
        ).count(),
        'unpaid': RentDue.objects.filter(
            tenancy__apartment__owner=request.user,
            month_for=current_month,
            status='unpaid'
        ).count(),
        'overdue': RentDue.objects.filter(
            tenancy__apartment__owner=request.user,
            status='overdue'
        ).count(),
    }
    
    # Apartment-wise revenue (for bar chart)
    apartment_revenue = []
    apartment_labels = []
    for apartment in apartments[:10]:  # Top 10 apartments
        apt_revenue = RentPayment.objects.filter(
            apartment=apartment,
            payment_for_month=current_month,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        apartment_revenue.append(float(apt_revenue))
        apartment_labels.append(apartment.name)
    
    # Occupancy rate
    occupancy_rate = (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0
    
    # Recent payments
    recent_payments = RentPayment.objects.filter(
        apartment__owner=request.user,
        status='completed'
    ).select_related('tenant', 'tenancy__room').order_by('-payment_date')[:5]
    
    # Pending payment reports
    payment_reports = RentDue.objects.filter(
        tenancy__apartment__owner=request.user,
        reported_to_office=True,
        status__in=['unpaid', 'overdue']
    ).select_related('tenant', 'tenancy__room').order_by('-report_date')[:5]
    
    # Recent notifications
    notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).order_by('-created_at')[:5]
    
    context = {
        'total_apartments': total_apartments,
        'total_rooms': total_rooms,
        'occupied_rooms': occupied_rooms,
        'available_rooms': available_rooms,
        'active_tenancies': active_tenancies,
        'current_month_payments': current_month_payments,
        'expected_rent': expected_rent,
        'outstanding_rent': outstanding_rent,
        'overdue_count': overdue_count,
        'occupancy_rate': round(occupancy_rate, 2),
        'revenue_data': json.dumps(revenue_data),
        'months_labels': json.dumps(months_labels),
        'payment_status': json.dumps(list(payment_status.values())),
        'payment_status_labels': json.dumps(list(payment_status.keys())),
        'apartment_revenue': json.dumps(apartment_revenue),
        'apartment_labels': json.dumps(apartment_labels),
        'recent_payments': recent_payments,
        'payment_reports': payment_reports,
        'notifications': notifications,
    }
    
    return render(request, 'admin_dashboard.html', context)


@login_required
def tenant_dashboard(request):
    """Tenant dashboard"""
    if request.user.user_type != 'tenant':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('admin_dashboard')
    
    # Get active tenancy
    try:
        active_tenancy = Tenancy.objects.get(
            tenant=request.user,
            status='active'
        )
    except Tenancy.DoesNotExist:
        active_tenancy = None
    
    # Current month
    today = timezone.now().date()
    current_month = today.replace(day=1)
    
    # Rent dues
    if active_tenancy:
        # Current rent due
        try:
            current_rent_due = RentDue.objects.get(
                tenancy=active_tenancy,
                month_for=current_month
            )
        except RentDue.DoesNotExist:
            current_rent_due = None
        
        # All rent dues
        rent_dues = RentDue.objects.filter(
            tenancy=active_tenancy
        ).order_by('-month_for')[:6]
        
        # Payment history
        payment_history = RentPayment.objects.filter(
            tenant=request.user,
            status='completed'
        ).order_by('-payment_date')[:10]
        
        # Water bills
        water_bills = WaterBill.objects.filter(
            tenancy=active_tenancy
        ).order_by('-bill_month')[:5]
        
        # Electricity bills
        electricity_bills = ElectricityBill.objects.filter(
            tenancy=active_tenancy
        ).order_by('-bill_month')[:5]
        
        # Total paid this year
        year_start = today.replace(month=1, day=1)
        total_paid_this_year = RentPayment.objects.filter(
            tenant=request.user,
            payment_date__gte=year_start,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
    else:
        current_rent_due = None
        rent_dues = []
        payment_history = []
        water_bills = []
        electricity_bills = []
        total_paid_this_year = Decimal('0.00')
    
    # Notifications
    notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).order_by('-created_at')[:5]
    
    context = {
        'active_tenancy': active_tenancy,
        'current_rent_due': current_rent_due,
        'rent_dues': rent_dues,
        'payment_history': payment_history,
        'water_bills': water_bills,
        'electricity_bills': electricity_bills,
        'total_paid_this_year': total_paid_this_year,
        'notifications': notifications,
    }
    
    return render(request, 'tenant_dashboard.html', context)