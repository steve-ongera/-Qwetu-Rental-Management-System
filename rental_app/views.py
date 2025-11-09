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
    
    return render(request, 'auth/login.html')


def logout_view(request):
    """Handle user logout"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


@login_required
def admin_dashboard(request):

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


from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Q
from decimal import Decimal
from datetime import timedelta

@login_required
def tenant_dashboard(request):
    """Tenant dashboard"""
    if request.user.user_type != 'tenant':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('admin_dashboard')
    
    # Get active tenancy
    try:
        active_tenancy = Tenancy.objects.select_related(
            'room', 
            'room__room_type', 
            'apartment'
        ).get(
            tenant=request.user,
            status='active',
            is_deleted=False
        )
    except Tenancy.DoesNotExist:
        active_tenancy = None
    
    # Current month and date
    today = timezone.now().date()
    current_month = today.replace(day=1)
    
    # Initialize context variables
    context = {
        'active_tenancy': active_tenancy,
        'current_rent_due': None,
        'rent_dues': [],
        'payment_history': [],
        'water_bills': [],
        'electricity_bills': [],
        'total_paid_this_year': Decimal('0.00'),
        'notifications': [],
        'overdue_count': 0,
        'pending_water_bills': 0,
        'pending_electricity_bills': 0,
        'days_until_due': None,
        'recent_activities': [],
    }
    
    # If tenant has active tenancy
    if active_tenancy:
        # Current rent due
        try:
            current_rent_due = RentDue.objects.get(
                tenancy=active_tenancy,
                month_for=current_month,
                is_deleted=False
            )
            context['current_rent_due'] = current_rent_due
            
            # Calculate days until due
            if current_rent_due.status in ['unpaid', 'partially_paid']:
                days_diff = (current_rent_due.due_date - today).days
                context['days_until_due'] = days_diff
        except RentDue.DoesNotExist:
            pass
        
        # All rent dues (last 6 months)
        rent_dues = RentDue.objects.filter(
            tenancy=active_tenancy,
            is_deleted=False
        ).order_by('-month_for')[:6]
        context['rent_dues'] = rent_dues
        
        # Count overdue rent
        overdue_count = RentDue.objects.filter(
            tenancy=active_tenancy,
            status='overdue',
            is_deleted=False
        ).count()
        context['overdue_count'] = overdue_count
        
        # Payment history (last 10 payments)
        payment_history = RentPayment.objects.filter(
            tenant=request.user,
            status='completed',
            is_deleted=False
        ).select_related('tenancy', 'tenancy__room').order_by('-payment_date')[:10]
        context['payment_history'] = payment_history
        
        # Water bills (last 5 months)
        water_bills = WaterBill.objects.filter(
            tenancy=active_tenancy
        ).order_by('-bill_month')[:5]
        context['water_bills'] = water_bills
        
        # Pending water bills
        pending_water_bills = WaterBill.objects.filter(
            tenancy=active_tenancy,
            status='pending'
        ).count()
        context['pending_water_bills'] = pending_water_bills
        
        # Electricity bills (last 5 months)
        electricity_bills = ElectricityBill.objects.filter(
            tenancy=active_tenancy
        ).order_by('-bill_month')[:5]
        context['electricity_bills'] = electricity_bills
        
        # Pending electricity bills
        pending_electricity_bills = ElectricityBill.objects.filter(
            tenancy=active_tenancy,
            status='pending'
        ).count()
        context['pending_electricity_bills'] = pending_electricity_bills
        
        # Total paid this year
        year_start = today.replace(month=1, day=1)
        total_paid_this_year = RentPayment.objects.filter(
            tenant=request.user,
            payment_date__gte=year_start,
            status='completed',
            is_deleted=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        context['total_paid_this_year'] = total_paid_this_year
        
        # Recent activities (payments, bills, etc.)
        recent_activities = []
        
        # Recent payments
        recent_payments = RentPayment.objects.filter(
            tenant=request.user,
            is_deleted=False
        ).order_by('-payment_date')[:3]
        
        for payment in recent_payments:
            recent_activities.append({
                'type': 'payment',
                'icon': 'check-lg',
                'icon_bg': 'success',
                'title': 'Payment Confirmed',
                'description': f'Your {payment.payment_for_month.strftime("%B %Y")} rent payment was received - ${payment.amount}',
                'date': payment.payment_date
            })
        
        # Recent water bills
        recent_water = WaterBill.objects.filter(
            tenancy=active_tenancy
        ).order_by('-bill_month')[:2]
        
        for bill in recent_water:
            recent_activities.append({
                'type': 'water_bill',
                'icon': 'droplet',
                'icon_bg': 'warning' if bill.status == 'pending' else 'success',
                'title': 'Water Bill Generated' if bill.status == 'pending' else 'Water Bill Paid',
                'description': f'{bill.bill_month.strftime("%B %Y")} water bill - ${bill.total_amount}',
                'date': bill.created_at
            })
        
        # Recent electricity bills
        recent_electricity = ElectricityBill.objects.filter(
            tenancy=active_tenancy
        ).order_by('-purchase_date')[:2]
        
        for bill in recent_electricity:
            recent_activities.append({
                'type': 'electricity',
                'icon': 'lightning',
                'icon_bg': 'primary',
                'title': 'Electricity Token',
                'description': f'{bill.units_purchased} units purchased - Token: {bill.token_number}',
                'date': bill.purchase_date
            })
        
        # Sort by date and limit to 5 most recent
        recent_activities = sorted(recent_activities, key=lambda x: x['date'], reverse=True)[:5]
        context['recent_activities'] = recent_activities
    
    # Notifications (unread, last 5)
    notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).order_by('-created_at')[:5]
    context['notifications'] = notifications
    context['unread_notifications_count'] = notifications.count()
    
    return render(request, 'tenant_dashboard.html', context)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from django.core.paginator import Paginator
from .models import Apartment, Room, RoomType, Tenancy
from decimal import Decimal


# ==================== APARTMENT VIEWS ====================

@login_required
def apartment_list(request):
    """List all apartments with search and filter"""
    apartments = Apartment.objects.filter(
        owner=request.user
    ).annotate(
        total_rooms=Count('rooms'),
        occupied_rooms=Count('rooms', filter=Q(rooms__status='occupied'))
    ).order_by('-created_at')
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        apartments = apartments.filter(
            Q(name__icontains=search_query) |
            Q(location__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(apartments, 10)
    page_number = request.GET.get('page')
    apartments_page = paginator.get_page(page_number)
    
    context = {
        'apartments': apartments_page,
        'search_query': search_query,
        'total_apartments': apartments.count(),
    }
    
    return render(request, 'apartments/apartment_list.html', context)


@login_required
def apartment_detail(request, pk):
    """View single apartment details"""
    apartment = get_object_or_404(Apartment, pk=pk, owner=request.user)
    
    # Get rooms for this apartment
    rooms = Room.objects.filter(apartment=apartment).select_related('room_type')
    
    # Statistics
    total_rooms = rooms.count()
    occupied_rooms = rooms.filter(status='occupied').count()
    available_rooms = rooms.filter(status='available').count()
    maintenance_rooms = rooms.filter(status='maintenance').count()
    occupancy_rate = (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0
    
    # Active tenancies
    active_tenancies = Tenancy.objects.filter(
        apartment=apartment,
        status='active'
    ).select_related('tenant', 'room')
    
    context = {
        'apartment': apartment,
        'rooms': rooms,
        'total_rooms': total_rooms,
        'occupied_rooms': occupied_rooms,
        'available_rooms': available_rooms,
        'maintenance_rooms': maintenance_rooms,
        'occupancy_rate': round(occupancy_rate, 2),
        'active_tenancies': active_tenancies,
    }
    
    return render(request, 'apartments/apartment_detail.html', context)


@login_required
def apartment_create(request):
    """Create new apartment"""
    if request.method == 'POST':
        name = request.POST.get('name')
        location = request.POST.get('location')
        total_floors = request.POST.get('total_floors')
        description = request.POST.get('description', '')
        water_rate = request.POST.get('water_rate_per_unit', '0.00')
        
        # Validation
        if not all([name, location, total_floors]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'apartments/apartment_form.html', {'form_data': request.POST})
        
        try:
            apartment = Apartment.objects.create(
                name=name,
                owner=request.user,
                location=location,
                total_floors=int(total_floors),
                description=description,
                water_rate_per_unit=Decimal(water_rate)
            )
            messages.success(request, f'Apartment "{apartment.name}" created successfully!')
            return redirect('apartment_detail', pk=apartment.pk)
        except Exception as e:
            messages.error(request, f'Error creating apartment: {str(e)}')
            return render(request, 'apartments/apartment_form.html', {'form_data': request.POST})
    
    return render(request, 'apartments/apartment_form.html')


@login_required
def apartment_edit(request, pk):
    """Edit existing apartment"""
    apartment = get_object_or_404(Apartment, pk=pk, owner=request.user)
    
    if request.method == 'POST':
        apartment.name = request.POST.get('name')
        apartment.location = request.POST.get('location')
        apartment.total_floors = int(request.POST.get('total_floors'))
        apartment.description = request.POST.get('description', '')
        apartment.water_rate_per_unit = Decimal(request.POST.get('water_rate_per_unit', '0.00'))
        
        try:
            apartment.save()
            messages.success(request, f'Apartment "{apartment.name}" updated successfully!')
            return redirect('apartment_detail', pk=apartment.pk)
        except Exception as e:
            messages.error(request, f'Error updating apartment: {str(e)}')
    
    context = {
        'apartment': apartment,
        'is_edit': True,
    }
    
    return render(request, 'apartments/apartment_form.html', context)


@login_required
def apartment_delete(request, pk):
    """Delete apartment (soft delete)"""
    apartment = get_object_or_404(Apartment, pk=pk, owner=request.user)
    
    if request.method == 'POST':
        # Check if apartment has active tenancies
        active_tenancies = Tenancy.objects.filter(apartment=apartment, status='active').count()
        if active_tenancies > 0:
            messages.error(request, 'Cannot delete apartment with active tenants.')
            return redirect('apartment_detail', pk=pk)
        
        apartment_name = apartment.name
        apartment.delete()
        messages.success(request, f'Apartment "{apartment_name}" deleted successfully!')
        return redirect('apartment_list')
    
    return redirect('apartment_detail', pk=pk)


# ==================== ROOM VIEWS ====================

@login_required
def room_list(request):
    """List all rooms with filters"""
    rooms = Room.objects.filter(
        apartment__owner=request.user
    ).select_related('apartment', 'room_type').order_by('apartment', 'floor_number', 'room_number')
    
    # Filters
    apartment_filter = request.GET.get('apartment', '')
    status_filter = request.GET.get('status', '')
    room_type_filter = request.GET.get('room_type', '')
    search_query = request.GET.get('search', '')
    
    if apartment_filter:
        rooms = rooms.filter(apartment_id=apartment_filter)
    
    if status_filter:
        rooms = rooms.filter(status=status_filter)
    
    if room_type_filter:
        rooms = rooms.filter(room_type_id=room_type_filter)
    
    if search_query:
        rooms = rooms.filter(
            Q(room_number__icontains=search_query) |
            Q(apartment__name__icontains=search_query)
        )
    
    # Get filter options
    apartments = Apartment.objects.filter(owner=request.user)
    room_types = RoomType.objects.all()
    
    # Pagination
    paginator = Paginator(rooms, 20)
    page_number = request.GET.get('page')
    rooms_page = paginator.get_page(page_number)
    
    context = {
        'rooms': rooms_page,
        'apartments': apartments,
        'room_types': room_types,
        'apartment_filter': apartment_filter,
        'status_filter': status_filter,
        'room_type_filter': room_type_filter,
        'search_query': search_query,
        'total_rooms': rooms.count(),
    }
    
    return render(request, 'rooms/room_list.html', context)


@login_required
def room_detail(request, pk):
    """View single room details"""
    room = get_object_or_404(
        Room.objects.select_related('apartment', 'room_type'),
        pk=pk,
        apartment__owner=request.user
    )
    
    # Get current tenancy
    current_tenancy = Tenancy.objects.filter(
        room=room,
        status='active'
    ).select_related('tenant').first()
    
    # Get tenancy history
    tenancy_history = Tenancy.objects.filter(
        room=room
    ).select_related('tenant').order_by('-start_date')
    
    context = {
        'room': room,
        'current_tenancy': current_tenancy,
        'tenancy_history': tenancy_history,
    }
    
    return render(request, 'rooms/room_detail.html', context)


@login_required
def room_create(request):
    """Create new room"""
    apartments = Apartment.objects.filter(owner=request.user)
    room_types = RoomType.objects.all()
    
    if request.method == 'POST':
        apartment_id = request.POST.get('apartment')
        room_number = request.POST.get('room_number')
        room_type_id = request.POST.get('room_type')
        floor_number = request.POST.get('floor_number')
        monthly_rent = request.POST.get('monthly_rent')
        deposit_amount = request.POST.get('deposit_amount')
        
        # Boolean fields
        has_balcony = request.POST.get('has_balcony') == 'on'
        has_shower = request.POST.get('has_shower') == 'on'
        has_kitchen_unit = request.POST.get('has_kitchen_unit') == 'on'
        has_clothes_cabinet = request.POST.get('has_clothes_cabinet') == 'on'
        
        # Validation
        if not all([apartment_id, room_number, room_type_id, floor_number, monthly_rent, deposit_amount]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'rooms/room_form.html', {
                'apartments': apartments,
                'room_types': room_types,
                'form_data': request.POST
            })
        
        try:
            apartment = get_object_or_404(Apartment, pk=apartment_id, owner=request.user)
            room_type = get_object_or_404(RoomType, pk=room_type_id)
            
            # Check if room number already exists in apartment
            if Room.objects.filter(apartment=apartment, room_number=room_number).exists():
                messages.error(request, f'Room number "{room_number}" already exists in this apartment.')
                return render(request, 'rooms/room_form.html', {
                    'apartments': apartments,
                    'room_types': room_types,
                    'form_data': request.POST
                })
            
            room = Room.objects.create(
                apartment=apartment,
                room_number=room_number,
                room_type=room_type,
                floor_number=int(floor_number),
                monthly_rent=Decimal(monthly_rent),
                deposit_amount=Decimal(deposit_amount),
                has_balcony=has_balcony,
                has_shower=has_shower,
                has_kitchen_unit=has_kitchen_unit,
                has_clothes_cabinet=has_clothes_cabinet,
                status='available'
            )
            
            messages.success(request, f'Room "{room.room_number}" created successfully!')
            return redirect('room_detail', pk=room.pk)
        except Exception as e:
            messages.error(request, f'Error creating room: {str(e)}')
            return render(request, 'rooms/room_form.html', {
                'apartments': apartments,
                'room_types': room_types,
                'form_data': request.POST
            })
    
    context = {
        'apartments': apartments,
        'room_types': room_types,
    }
    
    return render(request, 'rooms/room_form.html', context)


@login_required
def room_edit(request, pk):
    """Edit existing room"""
    room = get_object_or_404(
        Room.objects.select_related('apartment'),
        pk=pk,
        apartment__owner=request.user
    )
    
    apartments = Apartment.objects.filter(owner=request.user)
    room_types = RoomType.objects.all()
    
    if request.method == 'POST':
        room.room_number = request.POST.get('room_number')
        room.room_type_id = request.POST.get('room_type')
        room.floor_number = int(request.POST.get('floor_number'))
        room.monthly_rent = Decimal(request.POST.get('monthly_rent'))
        room.deposit_amount = Decimal(request.POST.get('deposit_amount'))
        room.has_balcony = request.POST.get('has_balcony') == 'on'
        room.has_shower = request.POST.get('has_shower') == 'on'
        room.has_kitchen_unit = request.POST.get('has_kitchen_unit') == 'on'
        room.has_clothes_cabinet = request.POST.get('has_clothes_cabinet') == 'on'
        
        try:
            room.save()
            messages.success(request, f'Room "{room.room_number}" updated successfully!')
            return redirect('room_detail', pk=room.pk)
        except Exception as e:
            messages.error(request, f'Error updating room: {str(e)}')
    
    context = {
        'room': room,
        'apartments': apartments,
        'room_types': room_types,
        'is_edit': True,
    }
    
    return render(request, 'rooms/room_form.html', context)


@login_required
def room_delete(request, pk):
    """Delete room"""
    room = get_object_or_404(
        Room.objects.select_related('apartment'),
        pk=pk,
        apartment__owner=request.user
    )
    
    if request.method == 'POST':
        # Check if room is occupied
        if room.status == 'occupied':
            messages.error(request, 'Cannot delete an occupied room.')
            return redirect('room_detail', pk=pk)
        
        room_number = room.room_number
        apartment_pk = room.apartment.pk
        room.delete()
        messages.success(request, f'Room "{room_number}" deleted successfully!')
        return redirect('apartment_detail', pk=apartment_pk)
    
    return redirect('room_detail', pk=pk)


# ==================== ROOM TYPE VIEWS ====================

@login_required
def room_type_list(request):
    """List all room types"""
    room_types = RoomType.objects.annotate(
        total_rooms=Count('room', filter=Q(room__apartment__owner=request.user))
    ).order_by('name')
    
    context = {
        'room_types': room_types,
    }
    
    return render(request, 'room_types/room_type_list.html', context)


@login_required
def room_type_detail(request, pk):
    """View single room type details"""
    room_type = get_object_or_404(RoomType, pk=pk)
    
    # Get rooms of this type owned by the user
    rooms = Room.objects.filter(
        room_type=room_type,
        apartment__owner=request.user
    ).select_related('apartment')
    
    # Statistics
    total_rooms = rooms.count()
    occupied_rooms = rooms.filter(status='occupied').count()
    available_rooms = rooms.filter(status='available').count()
    
    context = {
        'room_type': room_type,
        'rooms': rooms,
        'total_rooms': total_rooms,
        'occupied_rooms': occupied_rooms,
        'available_rooms': available_rooms,
    }
    
    return render(request, 'room_types/room_type_detail.html', context)


@login_required
def room_type_create(request):
    """Create new room type - Admin only"""
    if not request.user.is_superuser:
        messages.error(request, 'Only administrators can create room types.')
        return redirect('room_type_list')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        
        if not name:
            messages.error(request, 'Please provide a room type name.')
            return render(request, 'room_types/room_type_form.html', {'form_data': request.POST})
        
        try:
            room_type = RoomType.objects.create(
                name=name,
                description=description
            )
            messages.success(request, f'Room type "{room_type.get_name_display()}" created successfully!')
            return redirect('room_type_detail', pk=room_type.pk)
        except Exception as e:
            messages.error(request, f'Error creating room type: {str(e)}')
            return render(request, 'room_types/room_type_form.html', {'form_data': request.POST})
    
    # Get available room choices
    room_choices = RoomType.ROOM_CHOICES
    
    context = {
        'room_choices': room_choices,
    }
    
    return render(request, 'room_types/room_type_form.html', context)


@login_required
def room_type_edit(request, pk):
    """Edit existing room type - Admin only"""
    if not request.user.is_superuser:
        messages.error(request, 'Only administrators can edit room types.')
        return redirect('room_type_list')
    
    room_type = get_object_or_404(RoomType, pk=pk)
    
    if request.method == 'POST':
        room_type.name = request.POST.get('name')
        room_type.description = request.POST.get('description', '')
        
        try:
            room_type.save()
            messages.success(request, f'Room type "{room_type.get_name_display()}" updated successfully!')
            return redirect('room_type_detail', pk=room_type.pk)
        except Exception as e:
            messages.error(request, f'Error updating room type: {str(e)}')
    
    room_choices = RoomType.ROOM_CHOICES
    
    context = {
        'room_type': room_type,
        'room_choices': room_choices,
        'is_edit': True,
    }
    
    return render(request, 'room_types/room_type_form.html', context)


@login_required
def room_type_delete(request, pk):
    """Delete room type - Admin only"""
    if not request.user.is_superuser:
        messages.error(request, 'Only administrators can delete room types.')
        return redirect('room_type_list')
    
    room_type = get_object_or_404(RoomType, pk=pk)
    
    if request.method == 'POST':
        # Check if any rooms use this type
        rooms_count = Room.objects.filter(room_type=room_type).count()
        if rooms_count > 0:
            messages.error(request, f'Cannot delete room type. {rooms_count} rooms are using this type.')
            return redirect('room_type_detail', pk=pk)
        
        room_type_name = room_type.get_name_display()
        room_type.delete()
        messages.success(request, f'Room type "{room_type_name}" deleted successfully!')
        return redirect('room_type_list')
    
    return redirect('room_type_detail', pk=pk)


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum, Max
from django.utils import timezone
from django.core.paginator import Paginator
from .models import User, Tenancy, Room, Apartment, RentDue, RentPayment
from decimal import Decimal
from datetime import datetime, timedelta


# ==================== TENANT VIEWS ====================

@login_required
def tenant_list(request):
    """List all tenants (active and inactive)"""
    # Get all tenants for this admin's apartments
    tenants = User.objects.filter(
        user_type='tenant',
        tenancies__apartment__owner=request.user
    ).distinct().annotate(
        total_tenancies=Count('tenancies'),
        active_tenancy_count=Count('tenancies', filter=Q(tenancies__status='active'))
    ).order_by('-created_at')
    
    # Filters
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    apartment_filter = request.GET.get('apartment', '')
    
    if status_filter:
        tenants = tenants.filter(user_status=status_filter)
    
    if search_query:
        tenants = tenants.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(phone_number__icontains=search_query) |
            Q(national_id__icontains=search_query)
        )
    
    if apartment_filter:
        tenants = tenants.filter(tenancies__apartment_id=apartment_filter)
    
    # Get apartments for filter
    apartments = Apartment.objects.filter(owner=request.user)
    
    # Statistics
    total_tenants = tenants.count()
    active_tenants = tenants.filter(user_status='active').count()
    inactive_tenants = tenants.filter(user_status='inactive').count()
    
    # Pagination
    paginator = Paginator(tenants, 20)
    page_number = request.GET.get('page')
    tenants_page = paginator.get_page(page_number)
    
    context = {
        'tenants': tenants_page,
        'total_tenants': total_tenants,
        'active_tenants': active_tenants,
        'inactive_tenants': inactive_tenants,
        'apartments': apartments,
        'status_filter': status_filter,
        'search_query': search_query,
        'apartment_filter': apartment_filter,
    }
    
    return render(request, 'tenants/tenant_list.html', context)

@login_required
def tenant_detail(request, pk):
    """View single tenant details"""
    # Get tenant ensuring it's a tenant user
    tenant = get_object_or_404(
        User.objects.filter(user_type='tenant'),
        pk=pk
    )

    # Verify this tenant belongs to one of the admin's apartments
    if not Tenancy.objects.filter(
        tenant=tenant,
        apartment__owner=request.user
    ).exists():
        messages.error(request, 'Tenant not found.')
        return redirect('tenant_list')

    # Get all tenancies for this tenant
    tenancies = Tenancy.objects.filter(
        tenant=tenant,
        apartment__owner=request.user
    ).select_related('room', 'apartment').order_by('-start_date')

    # Current active tenancy
    current_tenancy = tenancies.filter(status='active').first()

    # Payment history (fetch top 10 latest)
    payments_qs = RentPayment.objects.filter(
        tenant=tenant,
        apartment__owner=request.user
    ).select_related('tenancy', 'tenancy__room').order_by('-payment_date')

    payments = list(payments_qs[:10])  # Convert slice to list before further filtering

    # Calculate total paid — apply filter to full queryset, not sliced list
    total_paid = payments_qs.filter(status='completed').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    # Outstanding dues
    outstanding_dues = RentDue.objects.filter(
        tenant=tenant,
        tenancy__apartment__owner=request.user,
        status__in=['unpaid', 'partially_paid', 'overdue']
    ).select_related('tenancy', 'tenancy__room')

    total_outstanding = outstanding_dues.aggregate(
        total=Sum('balance')
    )['total'] or Decimal('0.00')

    context = {
        'tenant': tenant,
        'current_tenancy': current_tenancy,
        'tenancies': tenancies,
        'payments': payments,
        'outstanding_dues': outstanding_dues,
        'total_outstanding': total_outstanding,
        'total_paid': total_paid,
    }

    return render(request, 'tenants/tenant_detail.html', context)

from django.contrib.auth.hashers import make_password
from django.db import IntegrityError

@login_required
def tenant_create(request):
    """Create new tenant (user account)"""
    if request.method == 'POST':
        # Get form data
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        national_id = request.POST.get('national_id', '').strip()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        # Validation
        if not all([first_name, last_name, phone_number, username, password]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'tenants/tenant_form.html', {'form_data': request.POST})
        
        # Check if username exists
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'tenants/tenant_form.html', {'form_data': request.POST})
        
        # Check if phone number exists
        if User.objects.filter(phone_number=phone_number).exists():
            messages.error(request, 'Phone number already exists.')
            return render(request, 'tenants/tenant_form.html', {'form_data': request.POST})
        
        # Check if national ID exists (if provided)
        if national_id and User.objects.filter(national_id=national_id).exists():
            messages.error(request, 'National ID already exists.')
            return render(request, 'tenants/tenant_form.html', {'form_data': request.POST})
        
        try:
            # Create tenant without password validation
            tenant = User(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone_number=phone_number,
                national_id=national_id if national_id else None,
                user_type='tenant',
                user_status='active',
                password=make_password(password)  # Hash password manually
            )
            tenant.save()
            
            messages.success(request, f'Tenant "{tenant.get_full_name()}" created successfully!')
            return redirect('tenant_detail', pk=tenant.pk)
            
        except IntegrityError as e:
            # Catch database integrity errors (unique constraints)
            error_msg = str(e)
            if 'phone_number' in error_msg:
                messages.error(request, 'Phone number already exists.')
            elif 'national_id' in error_msg:
                messages.error(request, 'National ID already exists.')
            elif 'username' in error_msg:
                messages.error(request, 'Username already exists.')
            else:
                messages.error(request, f'Database error: {error_msg}')
            return render(request, 'tenants/tenant_form.html', {'form_data': request.POST})
            
        except Exception as e:
            messages.error(request, f'Error creating tenant: {str(e)}')
            return render(request, 'tenants/tenant_form.html', {'form_data': request.POST})
    
    return render(request, 'tenants/tenant_form.html')


@login_required
def tenant_edit(request, pk):
    """Edit existing tenant"""
    tenant = get_object_or_404(
        User.objects.filter(user_type='tenant'),
        pk=pk
    )
    
    # Verify this tenant belongs to one of admin's apartments
    if not Tenancy.objects.filter(
        tenant=tenant,
        apartment__owner=request.user
    ).exists():
        messages.error(request, 'Tenant not found.')
        return redirect('tenant_list')
    
    if request.method == 'POST':
        tenant.first_name = request.POST.get('first_name')
        tenant.last_name = request.POST.get('last_name')
        tenant.email = request.POST.get('email')
        tenant.phone_number = request.POST.get('phone_number')
        tenant.national_id = request.POST.get('national_id') or None
        tenant.user_status = request.POST.get('user_status')
        
        # Check if phone number is taken by another user
        if User.objects.filter(phone_number=tenant.phone_number).exclude(pk=tenant.pk).exists():
            messages.error(request, 'Phone number already exists.')
            return render(request, 'tenants/tenant_form.html', {'tenant': tenant, 'is_edit': True})
        
        # Check if national ID is taken by another user
        if tenant.national_id and User.objects.filter(national_id=tenant.national_id).exclude(pk=tenant.pk).exists():
            messages.error(request, 'National ID already exists.')
            return render(request, 'tenants/tenant_form.html', {'tenant': tenant, 'is_edit': True})
        
        try:
            tenant.save()
            messages.success(request, f'Tenant "{tenant.get_full_name()}" updated successfully!')
            return redirect('tenant_detail', pk=tenant.pk)
        except Exception as e:
            messages.error(request, f'Error updating tenant: {str(e)}')
    
    context = {
        'tenant': tenant,
        'is_edit': True,
    }
    
    return render(request, 'tenants/tenant_form.html', context)


@login_required
def tenant_delete(request, pk):
    """Soft delete tenant (archive)"""
    tenant = get_object_or_404(
        User.objects.filter(user_type='tenant'),
        pk=pk
    )
    
    # Verify this tenant belongs to one of admin's apartments
    if not Tenancy.objects.filter(
        tenant=tenant,
        apartment__owner=request.user
    ).exists():
        messages.error(request, 'Tenant not found.')
        return redirect('tenant_list')
    
    if request.method == 'POST':
        # Check if tenant has active tenancies
        active_tenancies = Tenancy.objects.filter(tenant=tenant, status='active').count()
        if active_tenancies > 0:
            messages.error(request, 'Cannot delete tenant with active tenancies.')
            return redirect('tenant_detail', pk=pk)
        
        # Soft delete
        tenant.user_status = 'archived'
        tenant.is_deleted = True
        tenant.deleted_at = timezone.now()
        tenant.save()
        
        messages.success(request, f'Tenant "{tenant.get_full_name()}" archived successfully!')
        return redirect('tenant_list')
    
    return redirect('tenant_detail', pk=pk)


# ==================== ACTIVE TENANT VIEWS ====================

@login_required
def active_tenant_list(request):
    """List only active tenants with current tenancies"""
    # Get tenants with active tenancies
    active_tenancies = Tenancy.objects.filter(
        apartment__owner=request.user,
        status='active'
    ).select_related('tenant', 'room', 'apartment').order_by('apartment', 'room__room_number')
    
    # Filters
    apartment_filter = request.GET.get('apartment', '')
    search_query = request.GET.get('search', '')
    payment_status_filter = request.GET.get('payment_status', '')
    
    if apartment_filter:
        active_tenancies = active_tenancies.filter(apartment_id=apartment_filter)
    
    if search_query:
        active_tenancies = active_tenancies.filter(
            Q(tenant__first_name__icontains=search_query) |
            Q(tenant__last_name__icontains=search_query) |
            Q(room__room_number__icontains=search_query)
        )
    
    # Get current month rent dues for payment status filter
    today = timezone.now().date()
    current_month = today.replace(day=1)
    
    if payment_status_filter:
        tenancy_ids = RentDue.objects.filter(
            month_for=current_month,
            status=payment_status_filter
        ).values_list('tenancy_id', flat=True)
        active_tenancies = active_tenancies.filter(id__in=tenancy_ids)
    
    # Annotate with payment status
    tenancy_list = []
    for tenancy in active_tenancies:
        # Get current month due
        current_due = RentDue.objects.filter(
            tenancy=tenancy,
            month_for=current_month
        ).first()
        
        tenancy.current_due_status = current_due.status if current_due else 'N/A'
        tenancy.current_balance = current_due.balance if current_due else Decimal('0.00')
        tenancy_list.append(tenancy)
    
    # Get apartments for filter
    apartments = Apartment.objects.filter(owner=request.user)
    
    # Statistics
    total_active = len(tenancy_list)
    paid_count = sum(1 for t in tenancy_list if t.current_due_status == 'paid')
    unpaid_count = sum(1 for t in tenancy_list if t.current_due_status in ['unpaid', 'overdue'])
    
    # Pagination
    paginator = Paginator(tenancy_list, 20)
    page_number = request.GET.get('page')
    tenancies_page = paginator.get_page(page_number)
    
    context = {
        'active_tenancies': tenancies_page,
        'total_active': total_active,
        'paid_count': paid_count,
        'unpaid_count': unpaid_count,
        'apartments': apartments,
        'apartment_filter': apartment_filter,
        'search_query': search_query,
        'payment_status_filter': payment_status_filter,
    }
    
    return render(request, 'tenants/active_tenant_list.html', context)


# ==================== TENANCY VIEWS ====================

@login_required
def tenancy_list(request):
    """List all tenancies with filters"""
    tenancies = Tenancy.objects.filter(
        apartment__owner=request.user
    ).select_related('tenant', 'room', 'apartment').order_by('-start_date')
    
    # Filters
    status_filter = request.GET.get('status', '')
    apartment_filter = request.GET.get('apartment', '')
    search_query = request.GET.get('search', '')
    
    if status_filter:
        tenancies = tenancies.filter(status=status_filter)
    
    if apartment_filter:
        tenancies = tenancies.filter(apartment_id=apartment_filter)
    
    if search_query:
        tenancies = tenancies.filter(
            Q(tenant__first_name__icontains=search_query) |
            Q(tenant__last_name__icontains=search_query) |
            Q(room__room_number__icontains=search_query)
        )
    
    # Get apartments for filter
    apartments = Apartment.objects.filter(owner=request.user)
    
    # Statistics
    total_tenancies = tenancies.count()
    active_count = tenancies.filter(status='active').count()
    terminated_count = tenancies.filter(status='terminated').count()
    
    # Pagination
    paginator = Paginator(tenancies, 20)
    page_number = request.GET.get('page')
    tenancies_page = paginator.get_page(page_number)
    
    context = {
        'tenancies': tenancies_page,
        'total_tenancies': total_tenancies,
        'active_count': active_count,
        'terminated_count': terminated_count,
        'apartments': apartments,
        'status_filter': status_filter,
        'apartment_filter': apartment_filter,
        'search_query': search_query,
    }
    
    return render(request, 'tenants/tenancy_list.html', context)


@login_required
def tenancy_detail(request, pk):
    """View single tenancy details"""
    tenancy = get_object_or_404(
        Tenancy.objects.select_related('tenant', 'room', 'apartment'),
        pk=pk,
        apartment__owner=request.user
    )
    
    # Payment history for this tenancy
    payments = RentPayment.objects.filter(
        tenancy=tenancy
    ).order_by('-payment_date')
    
    # Rent dues for this tenancy
    rent_dues = RentDue.objects.filter(
        tenancy=tenancy
    ).order_by('-due_date')
    
    # Calculate totals
    total_paid = payments.filter(status='completed').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    total_due = rent_dues.aggregate(
        total=Sum('amount_due')
    )['total'] or Decimal('0.00')
    
    total_balance = rent_dues.aggregate(
        total=Sum('balance')
    )['total'] or Decimal('0.00')
    
    # Duration calculation
    if tenancy.end_date:
        duration_days = (tenancy.end_date - tenancy.start_date).days
        duration_months = duration_days // 30
    else:
        duration_days = (timezone.now().date() - tenancy.start_date).days
        duration_months = duration_days // 30
    
    context = {
        'tenancy': tenancy,
        'payments': payments,
        'rent_dues': rent_dues,
        'total_paid': total_paid,
        'total_due': total_due,
        'total_balance': total_balance,
        'duration_months': duration_months,
        'duration_days': duration_days,
    }
    
    return render(request, 'tenants/tenancy_detail.html', context)


@login_required
def tenancy_create(request):
    """Create new tenancy"""
    # Get available rooms and tenants
    available_rooms = Room.objects.filter(
        apartment__owner=request.user,
        status='available'
    ).select_related('apartment', 'room_type')
    
    # Get all tenants (for selecting existing or need to create new)
    tenants = User.objects.filter(user_type='tenant', user_status='active')
    
    apartments = Apartment.objects.filter(owner=request.user)
    
    if request.method == 'POST':
        tenant_id = request.POST.get('tenant')
        room_id = request.POST.get('room')
        start_date = request.POST.get('start_date')
        deposit_paid = request.POST.get('deposit_paid')
        move_in_condition = request.POST.get('move_in_condition', '')
        
        # Validation
        if not all([tenant_id, room_id, start_date, deposit_paid]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'tenants/tenancy_form.html', {
                'available_rooms': available_rooms,
                'tenants': tenants,
                'apartments': apartments,
                'form_data': request.POST
            })
        
        try:
            tenant = get_object_or_404(User, pk=tenant_id, user_type='tenant')
            room = get_object_or_404(Room, pk=room_id, apartment__owner=request.user)
            
            # Check if room is available
            if room.status != 'available':
                messages.error(request, 'Selected room is not available.')
                return render(request, 'tenants/tenancy_form.html', {
                    'available_rooms': available_rooms,
                    'tenants': tenants,
                    'apartments': apartments,
                    'form_data': request.POST
                })
            
            # Check if tenant has active tenancy
            if Tenancy.objects.filter(tenant=tenant, status='active').exists():
                messages.error(request, 'Tenant already has an active tenancy.')
                return render(request, 'tenants/tenancy_form.html', {
                    'available_rooms': available_rooms,
                    'tenants': tenants,
                    'apartments': apartments,
                    'form_data': request.POST
                })
            
            # Create tenancy
            tenancy = Tenancy.objects.create(
                tenant=tenant,
                room=room,
                apartment=room.apartment,
                start_date=datetime.strptime(start_date, '%Y-%m-%d').date(),
                deposit_paid=Decimal(deposit_paid),
                move_in_condition=move_in_condition,
                status='active'
            )
            
            # Update room status
            room.status = 'occupied'
            room.save()
            
            # Create first month rent due
            first_due_date = tenancy.start_date.replace(day=3)
            if first_due_date < tenancy.start_date:
                # If start date is after 3rd, due date is next month
                if first_due_date.month == 12:
                    first_due_date = first_due_date.replace(year=first_due_date.year + 1, month=1)
                else:
                    first_due_date = first_due_date.replace(month=first_due_date.month + 1)
            
            RentDue.objects.create(
                tenancy=tenancy,
                tenant=tenant,
                due_date=first_due_date,
                month_for=tenancy.start_date.replace(day=1),
                amount_due=room.monthly_rent,
                balance=room.monthly_rent,
                status='unpaid'
            )
            
            messages.success(request, f'Tenancy created successfully for {tenant.get_full_name()}!')
            return redirect('tenancy_detail', pk=tenancy.pk)
            
        except Exception as e:
            messages.error(request, f'Error creating tenancy: {str(e)}')
            return render(request, 'tenants/tenancy_form.html', {
                'available_rooms': available_rooms,
                'tenants': tenants,
                'apartments': apartments,
                'form_data': request.POST
            })
    
    context = {
        'available_rooms': available_rooms,
        'tenants': tenants,
        'apartments': apartments,
    }
    
    return render(request, 'tenants/tenancy_form.html', context)


@login_required
def tenancy_edit(request, pk):
    """Edit existing tenancy"""
    tenancy = get_object_or_404(
        Tenancy.objects.select_related('tenant', 'room', 'apartment'),
        pk=pk,
        apartment__owner=request.user
    )
    
    if request.method == 'POST':
        tenancy.deposit_paid = Decimal(request.POST.get('deposit_paid'))
        tenancy.move_in_condition = request.POST.get('move_in_condition', '')
        
        # Only allow editing end date and status for termination
        if request.POST.get('status') == 'terminated':
            tenancy.status = 'terminated'
            tenancy.end_date = datetime.strptime(request.POST.get('end_date'), '%Y-%m-%d').date()
            tenancy.termination_reason = request.POST.get('termination_reason')
            tenancy.move_out_condition = request.POST.get('move_out_condition', '')
            
            # Handle deposit refund
            tenancy.deposit_refunded = request.POST.get('deposit_refunded') == 'on'
            if tenancy.deposit_refunded:
                tenancy.deposit_refund_amount = Decimal(request.POST.get('deposit_refund_amount', '0.00'))
                tenancy.deposit_deduction_reason = request.POST.get('deposit_deduction_reason', '')
            
            # Update room status
            tenancy.room.status = 'available'
            tenancy.room.save()
        
        try:
            tenancy.save()
            messages.success(request, 'Tenancy updated successfully!')
            return redirect('tenancy_detail', pk=tenancy.pk)
        except Exception as e:
            messages.error(request, f'Error updating tenancy: {str(e)}')
    
    context = {
        'tenancy': tenancy,
        'is_edit': True,
    }
    
    return render(request, 'tenants/tenancy_form.html', context)


@login_required
def tenancy_terminate(request, pk):
    """Terminate a tenancy"""
    tenancy = get_object_or_404(
        Tenancy.objects.select_related('tenant', 'room'),
        pk=pk,
        apartment__owner=request.user,
        status='active'
    )
    
    if request.method == 'POST':
        end_date = request.POST.get('end_date')
        termination_reason = request.POST.get('termination_reason')
        move_out_condition = request.POST.get('move_out_condition', '')
        deposit_refunded = request.POST.get('deposit_refunded') == 'on'
        deposit_refund_amount = request.POST.get('deposit_refund_amount', '0.00')
        deposit_deduction_reason = request.POST.get('deposit_deduction_reason', '')
        
        try:
            tenancy.status = 'terminated'
            tenancy.end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            tenancy.termination_reason = termination_reason
            tenancy.move_out_condition = move_out_condition
            tenancy.deposit_refunded = deposit_refunded
            tenancy.deposit_refund_amount = Decimal(deposit_refund_amount) if deposit_refunded else Decimal('0.00')
            tenancy.deposit_deduction_reason = deposit_deduction_reason
            tenancy.save()
            
            # Update room status
            tenancy.room.status = 'available'
            tenancy.room.save()
            
            messages.success(request, f'Tenancy terminated successfully!')
            return redirect('tenancy_detail', pk=tenancy.pk)
            
        except Exception as e:
            messages.error(request, f'Error terminating tenancy: {str(e)}')
    
    context = {
        'tenancy': tenancy,
    }
    
    return render(request, 'tenants/tenancy_terminate.html', context)


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, F
from django.core.paginator import Paginator
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta
from .models import (
    RentPayment, RentDue, WaterBill, ElectricityBill, 
    Tenancy, Apartment, User, Notification
)


# ==================== RENT PAYMENTS VIEWS ====================
@login_required
def rent_payments_list(request):
    """List all rent payments"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    # Get filters
    status_filter = request.GET.get('status', '')
    apartment_filter = request.GET.get('apartment', '')
    search_query = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Base query
    payments = RentPayment.objects.filter(is_deleted=False).select_related(
        'tenant', 'tenancy', 'apartment', 'tenancy__room'
    )
    
    # Apply filters
    if status_filter:
        payments = payments.filter(status=status_filter)
    
    if apartment_filter:
        payments = payments.filter(apartment_id=apartment_filter)
    
    if search_query:
        payments = payments.filter(
            Q(tenant__first_name__icontains=search_query) |
            Q(tenant__last_name__icontains=search_query) |
            Q(mpesa_transaction_id__icontains=search_query) |
            Q(tenancy__room__room_number__icontains=search_query)
        )
    
    if date_from:
        payments = payments.filter(payment_date__gte=date_from)
    
    if date_to:
        payments = payments.filter(payment_date__lte=date_to)
    
    # Statistics
    total_payments = payments.count()
    completed_payments = payments.filter(status='completed').count()
    pending_payments = payments.filter(status='pending').count()
    total_amount = payments.filter(status='completed').aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    # Pagination
    paginator = Paginator(payments.order_by('-payment_date'), 20)
    page_number = request.GET.get('page')
    payments_page = paginator.get_page(page_number)
    
    # Get apartments for filter
    apartments = Apartment.objects.filter(owner=request.user)
    
    context = {
        'payments': payments_page,
        'total_payments': total_payments,
        'completed_payments': completed_payments,
        'pending_payments': pending_payments,
        'total_amount': total_amount,
        'apartments': apartments,
        'status_filter': status_filter,
        'apartment_filter': apartment_filter,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'payments/rent_payments_list.html', context)

@login_required
def rent_payments_pending(request):
    """List pending rent payments"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    payments = RentPayment.objects.filter(
        is_deleted=False,
        status='pending'
    ).select_related('tenant', 'tenancy', 'apartment', 'tenancy__room')
    
    # Pagination
    paginator = Paginator(payments.order_by('-payment_date'), 20)
    page_number = request.GET.get('page')
    payments_page = paginator.get_page(page_number)
    
    context = {
        'payments': payments_page,
        'page_title': 'Pending Payments',
    }
    
    return render(request, 'payments/rent_payments_pending.html', context)


@login_required
def rent_payment_detail(request, mpesa_transaction_id):
    """View rent payment details using M-Pesa transaction ID"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    payment = get_object_or_404(
        RentPayment,
        mpesa_transaction_id=mpesa_transaction_id,
        is_deleted=False
    )
    
    context = {
        'payment': payment,
    }
    
    return render(request, 'payments/rent_payment_detail.html', context)


@login_required
def rent_payment_create(request):
    """Create new rent payment (manual entry)"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        tenancy_id = request.POST.get('tenancy')
        amount = request.POST.get('amount')
        payment_method = request.POST.get('payment_method')
        payment_for_month = request.POST.get('payment_for_month')
        months_covered = request.POST.get('months_covered', 1)
        notes = request.POST.get('notes', '')
        
        try:
            tenancy = Tenancy.objects.get(pk=tenancy_id, status='active')
            
            payment = RentPayment.objects.create(
                tenancy=tenancy,
                tenant=tenancy.tenant,
                apartment=tenancy.apartment,
                amount=Decimal(amount),
                payment_method=payment_method,
                payment_for_month=payment_for_month,
                months_covered=int(months_covered),
                status='completed' if payment_method != 'mpesa' else 'pending',
                notes=notes
            )
            
            # Update rent due
            update_rent_due_after_payment(payment)
            
            # Create notification
            Notification.objects.create(
                user=tenancy.tenant,
                notification_type='payment_received',
                title='Payment Received',
                message=f'Payment of KES {amount} received for {payment_for_month}.'
            )
            
            messages.success(request, 'Payment recorded successfully.')
            return redirect('rent_payment_detail', mpesa_transaction_id=payment.mpesa_transaction_id or payment.pk)
        
        except Exception as e:
            messages.error(request, f'Error creating payment: {str(e)}')
    
    # Get active tenancies
    tenancies = Tenancy.objects.filter(
        status='active',
        is_deleted=False
    ).select_related('tenant', 'room', 'apartment')
    
    context = {
        'tenancies': tenancies,
    }
    
    return render(request, 'payments/rent_payment_form.html', context)


@login_required
def rent_payment_edit(request, pk):
    """Edit rent payment"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    payment = get_object_or_404(RentPayment, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        amount = request.POST.get('amount')
        payment_method = request.POST.get('payment_method')
        status = request.POST.get('status')
        notes = request.POST.get('notes', '')
        
        try:
            payment.amount = Decimal(amount)
            payment.payment_method = payment_method
            payment.status = status
            payment.notes = notes
            payment.save()
            
            # Update rent due if status changed to completed
            if status == 'completed':
                update_rent_due_after_payment(payment)
            
            messages.success(request, 'Payment updated successfully.')
            return redirect('rent_payment_detail', mpesa_transaction_id=payment.mpesa_transaction_id or payment.pk)
        
        except Exception as e:
            messages.error(request, f'Error updating payment: {str(e)}')
    
    context = {
        'payment': payment,
        'is_edit': True,
    }
    
    return render(request, 'payments/rent_payment_form.html', context)


@login_required
def rent_payment_delete(request, pk):
    """Soft delete rent payment"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        payment = get_object_or_404(RentPayment, pk=pk, is_deleted=False)
        payment.is_deleted = True
        payment.deleted_at = timezone.now()
        payment.save()
        
        messages.success(request, 'Payment deleted successfully.')
        return redirect('rent_payments_list')
    
    return redirect('rent_payments_list')


# ==================== RENT DUES VIEWS ====================

@login_required
def rent_dues_list(request):
    """List all rent dues"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    # Get filters
    status_filter = request.GET.get('status', '')
    apartment_filter = request.GET.get('apartment', '')
    search_query = request.GET.get('search', '')
    
    # Base query
    dues = RentDue.objects.filter(is_deleted=False).select_related(
        'tenant', 'tenancy', 'tenancy__room', 'tenancy__apartment'
    )
    
    # Apply filters
    if status_filter:
        dues = dues.filter(status=status_filter)
    
    if apartment_filter:
        dues = dues.filter(tenancy__apartment_id=apartment_filter)
    
    if search_query:
        dues = dues.filter(
            Q(tenant__first_name__icontains=search_query) |
            Q(tenant__last_name__icontains=search_query) |
            Q(tenancy__room__room_number__icontains=search_query)
        )
    
    # Statistics
    total_dues = dues.count()
    overdue_count = dues.filter(status='overdue').count()
    unpaid_count = dues.filter(status='unpaid').count()
    total_balance = dues.aggregate(total=Sum('balance'))['total'] or 0
    
    # Pagination
    paginator = Paginator(dues.order_by('-due_date'), 20)
    page_number = request.GET.get('page')
    dues_page = paginator.get_page(page_number)
    
    # Get apartments for filter
    apartments = Apartment.objects.filter(owner=request.user)
    
    context = {
        'dues': dues_page,
        'total_dues': total_dues,
        'overdue_count': overdue_count,
        'unpaid_count': unpaid_count,
        'total_balance': total_balance,
        'apartments': apartments,
        'status_filter': status_filter,
        'apartment_filter': apartment_filter,
        'search_query': search_query,
    }
    
    return render(request, 'payments/rent_dues_list.html', context)


@login_required
def rent_due_detail(request, pk):
    """View rent due details"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    due = get_object_or_404(RentDue, pk=pk, is_deleted=False)
    
    # Get related payments
    related_payments = RentPayment.objects.filter(
        tenancy=due.tenancy,
        payment_for_month=due.month_for,
        status='completed',
        is_deleted=False
    )
    
    context = {
        'due': due,
        'related_payments': related_payments,
    }
    
    return render(request, 'payments/rent_due_detail.html', context)


@login_required
def rent_due_create(request):
    """Create new rent due"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        tenancy_id = request.POST.get('tenancy')
        month_for = request.POST.get('month_for')
        amount_due = request.POST.get('amount_due')
        
        try:
            tenancy = Tenancy.objects.get(pk=tenancy_id, status='active')
            
            # Check if due already exists
            if RentDue.objects.filter(tenancy=tenancy, month_for=month_for).exists():
                messages.error(request, 'Rent due for this month already exists.')
                return redirect('rent_due_create')
            
            # Calculate due date (3rd of the month)
            month_date = datetime.strptime(month_for, '%Y-%m-%d')
            due_date = month_date.replace(day=3)
            
            due = RentDue.objects.create(
                tenancy=tenancy,
                tenant=tenancy.tenant,
                due_date=due_date,
                month_for=month_for,
                amount_due=Decimal(amount_due),
                balance=Decimal(amount_due),
                status='unpaid'
            )
            
            # Create notification
            Notification.objects.create(
                user=tenancy.tenant,
                notification_type='rent_due',
                title='Rent Due',
                message=f'Rent of KES {amount_due} is due on {due_date.strftime("%B %d, %Y")}.'
            )
            
            messages.success(request, 'Rent due created successfully.')
            return redirect('rent_due_detail', pk=due.pk)
        
        except Exception as e:
            messages.error(request, f'Error creating rent due: {str(e)}')
    
    # Get active tenancies
    tenancies = Tenancy.objects.filter(
        status='active',
        is_deleted=False
    ).select_related('tenant', 'room', 'apartment')
    
    context = {
        'tenancies': tenancies,
    }
    
    return render(request, 'payments/rent_due_form.html', context)


@login_required
def rent_due_edit(request, pk):
    """Edit rent due"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    due = get_object_or_404(RentDue, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        amount_due = request.POST.get('amount_due')
        amount_paid = request.POST.get('amount_paid')
        status = request.POST.get('status')
        
        try:
            due.amount_due = Decimal(amount_due)
            due.amount_paid = Decimal(amount_paid)
            due.balance = Decimal(amount_due) - Decimal(amount_paid)
            due.status = status
            due.save()
            
            messages.success(request, 'Rent due updated successfully.')
            return redirect('rent_due_detail', pk=due.pk)
        
        except Exception as e:
            messages.error(request, f'Error updating rent due: {str(e)}')
    
    context = {
        'due': due,
        'is_edit': True,
    }
    
    return render(request, 'payments/rent_due_form.html', context)


@login_required
def rent_due_delete(request, pk):
    """Soft delete rent due"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        due = get_object_or_404(RentDue, pk=pk, is_deleted=False)
        due.is_deleted = True
        due.deleted_at = timezone.now()
        due.save()
        
        messages.success(request, 'Rent due deleted successfully.')
        return redirect('rent_dues_list')
    
    return redirect('rent_dues_list')


# ==================== WATER BILLS VIEWS ====================

@login_required
def water_bills_list(request):
    """List all water bills"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    # Get filters
    status_filter = request.GET.get('status', '')
    apartment_filter = request.GET.get('apartment', '')
    search_query = request.GET.get('search', '')
    
    # Base query
    bills = WaterBill.objects.all().select_related(
        'tenancy', 'tenancy__tenant', 'tenancy__room', 'tenancy__apartment'
    )
    
    # Apply filters
    if status_filter:
        bills = bills.filter(status=status_filter)
    
    if apartment_filter:
        bills = bills.filter(tenancy__apartment_id=apartment_filter)
    
    if search_query:
        bills = bills.filter(
            Q(tenancy__tenant__first_name__icontains=search_query) |
            Q(tenancy__tenant__last_name__icontains=search_query) |
            Q(tenancy__room__room_number__icontains=search_query)
        )
    
    # Statistics
    total_bills = bills.count()
    pending_bills = bills.filter(status='pending').count()
    overdue_bills = bills.filter(status='overdue').count()
    total_amount = bills.filter(status='paid').aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    # Pagination
    paginator = Paginator(bills.order_by('-bill_month'), 20)
    page_number = request.GET.get('page')
    bills_page = paginator.get_page(page_number)
    
    # Get apartments for filter
    apartments = Apartment.objects.filter(owner=request.user)
    
    context = {
        'bills': bills_page,
        'total_bills': total_bills,
        'pending_bills': pending_bills,
        'overdue_bills': overdue_bills,
        'total_amount': total_amount,
        'apartments': apartments,
        'status_filter': status_filter,
        'apartment_filter': apartment_filter,
        'search_query': search_query,
    }
    
    return render(request, 'payments/water_bills_list.html', context)


@login_required
def water_bill_detail(request, pk):
    """View water bill details"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    bill = get_object_or_404(WaterBill, pk=pk)
    
    context = {
        'bill': bill,
    }
    
    return render(request, 'payments/water_bill_detail.html', context)


@login_required
def water_bill_create(request):
    """Create new water bill"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        tenancy_id = request.POST.get('tenancy')
        bill_month = request.POST.get('bill_month')
        previous_reading = request.POST.get('previous_reading')
        current_reading = request.POST.get('current_reading')
        rate_per_unit = request.POST.get('rate_per_unit')
        
        try:
            tenancy = Tenancy.objects.get(pk=tenancy_id, status='active')
            
            # Calculate units and total
            prev_reading = Decimal(previous_reading)
            curr_reading = Decimal(current_reading)
            rate = Decimal(rate_per_unit)
            units = curr_reading - prev_reading
            total = units * rate
            
            # Calculate due date (usually 7 days from bill creation)
            due_date = timezone.now().date() + timedelta(days=7)
            
            bill = WaterBill.objects.create(
                tenancy=tenancy,
                bill_month=bill_month,
                previous_reading=prev_reading,
                current_reading=curr_reading,
                units_consumed=units,
                rate_per_unit=rate,
                total_amount=total,
                due_date=due_date,
                status='pending'
            )
            
            # Create notification
            Notification.objects.create(
                user=tenancy.tenant,
                notification_type='water_bill',
                title='Water Bill Generated',
                message=f'Water bill of KES {total} for {bill_month} is due on {due_date}.'
            )
            
            messages.success(request, 'Water bill created successfully.')
            return redirect('water_bill_detail', pk=bill.pk)
        
        except Exception as e:
            messages.error(request, f'Error creating water bill: {str(e)}')
    
    # Get active tenancies
    tenancies = Tenancy.objects.filter(
        status='active',
        is_deleted=False
    ).select_related('tenant', 'room', 'apartment')
    
    context = {
        'tenancies': tenancies,
    }
    
    return render(request, 'payments/water_bill_form.html', context)


@login_required
def water_bill_edit(request, pk):
    """Edit water bill"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    bill = get_object_or_404(WaterBill, pk=pk)
    
    if request.method == 'POST':
        previous_reading = request.POST.get('previous_reading')
        current_reading = request.POST.get('current_reading')
        rate_per_unit = request.POST.get('rate_per_unit')
        status = request.POST.get('status')
        
        try:
            prev_reading = Decimal(previous_reading)
            curr_reading = Decimal(current_reading)
            rate = Decimal(rate_per_unit)
            units = curr_reading - prev_reading
            total = units * rate
            
            bill.previous_reading = prev_reading
            bill.current_reading = curr_reading
            bill.units_consumed = units
            bill.rate_per_unit = rate
            bill.total_amount = total
            bill.status = status
            
            if status == 'paid' and not bill.payment_date:
                bill.payment_date = timezone.now()
            
            bill.save()
            
            messages.success(request, 'Water bill updated successfully.')
            return redirect('water_bill_detail', pk=bill.pk)
        
        except Exception as e:
            messages.error(request, f'Error updating water bill: {str(e)}')
    
    context = {
        'bill': bill,
        'is_edit': True,
    }
    
    return render(request, 'payments/water_bill_form.html', context)


@login_required
def water_bill_delete(request, pk):
    """Delete water bill"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        bill = get_object_or_404(WaterBill, pk=pk)
        bill.delete()
        
        messages.success(request, 'Water bill deleted successfully.')
        return redirect('water_bills_list')
    
    return redirect('water_bills_list')


# ==================== ELECTRICITY BILLS VIEWS ====================

@login_required
def electricity_bills_list(request):
    """List all electricity bills"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    # Get filters
    status_filter = request.GET.get('status', '')
    apartment_filter = request.GET.get('apartment', '')
    search_query = request.GET.get('search', '')
    
    # Base query
    bills = ElectricityBill.objects.all().select_related(
        'tenancy', 'tenancy__tenant', 'tenancy__room', 'tenancy__apartment'
    )
    
    # Apply filters
    if status_filter:
        bills = bills.filter(status=status_filter)
    
    if apartment_filter:
        bills = bills.filter(tenancy__apartment_id=apartment_filter)
    
    if search_query:
        bills = bills.filter(
            Q(tenancy__tenant__first_name__icontains=search_query) |
            Q(tenancy__tenant__last_name__icontains=search_query) |
            Q(token_number__icontains=search_query) |
            Q(tenancy__room__room_number__icontains=search_query)
        )
    
    # Statistics
    total_bills = bills.count()
    paid_bills = bills.filter(status='paid').count()
    total_units = bills.filter(status='paid').aggregate(
        total=Sum('units_purchased')
    )['total'] or 0
    total_amount = bills.filter(status='paid').aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    # Pagination
    paginator = Paginator(bills.order_by('-bill_month'), 20)
    page_number = request.GET.get('page')
    bills_page = paginator.get_page(page_number)
    
    # Get apartments for filter
    apartments = Apartment.objects.filter(owner=request.user)
    
    context = {
        'bills': bills_page,
        'total_bills': total_bills,
        'paid_bills': paid_bills,
        'total_units': total_units,
        'total_amount': total_amount,
        'apartments': apartments,
        'status_filter': status_filter,
        'apartment_filter': apartment_filter,
        'search_query': search_query,
    }
    
    return render(request, 'payments/electricity_bills_list.html', context)


@login_required
def electricity_bill_detail(request, pk):
    """View electricity bill details"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    bill = get_object_or_404(ElectricityBill, pk=pk)
    
    context = {
        'bill': bill,
    }
    
    return render(request, 'payments/electricity_bill_detail.html', context)


@login_required
def electricity_bill_create(request):
    """Create new electricity bill"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        tenancy_id = request.POST.get('tenancy')
        bill_month = request.POST.get('bill_month')
        token_number = request.POST.get('token_number')
        units_purchased = request.POST.get('units_purchased')
        amount = request.POST.get('amount')
        
        try:
            tenancy = Tenancy.objects.get(pk=tenancy_id, status='active')
            
            bill = ElectricityBill.objects.create(
                tenancy=tenancy,
                bill_month=bill_month,
                token_number=token_number,
                units_purchased=Decimal(units_purchased),
                amount=Decimal(amount),
                status='paid'
            )
            
            messages.success(request, 'Electricity bill created successfully.')
            return redirect('electricity_bill_detail', pk=bill.pk)
        
        except Exception as e:
            messages.error(request, f'Error creating electricity bill: {str(e)}')
    
    # Get active tenancies
    tenancies = Tenancy.objects.filter(
        status='active',
        is_deleted=False
    ).select_related('tenant', 'room', 'apartment')
    
    context = {
        'tenancies': tenancies,
    }
    
    return render(request, 'payments/electricity_bill_form.html', context)


@login_required
def electricity_bill_edit(request, pk):
    """Edit electricity bill"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    bill = get_object_or_404(ElectricityBill, pk=pk)
    
    if request.method == 'POST':
        token_number = request.POST.get('token_number')
        units_purchased = request.POST.get('units_purchased')
        amount = request.POST.get('amount')
        status = request.POST.get('status')
        
        try:
            bill.token_number = token_number
            bill.units_purchased = Decimal(units_purchased)
            bill.amount = Decimal(amount)
            bill.status = status
            bill.save()
            
            messages.success(request, 'Electricity bill updated successfully.')
            return redirect('electricity_bill_detail', pk=bill.pk)
        
        except Exception as e:
            messages.error(request, f'Error updating electricity bill: {str(e)}')
    
    context = {
        'bill': bill,
        'is_edit': True,
    }
    
    return render(request, 'payments/electricity_bill_form.html', context)


@login_required
def electricity_bill_delete(request, pk):
    """Delete electricity bill"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        bill = get_object_or_404(ElectricityBill, pk=pk)
        bill.delete()
        
        messages.success(request, 'Electricity bill deleted successfully.')
        return redirect('electricity_bills_list')
    
    return redirect('electricity_bills_list')


# ==================== DEPOSITS VIEWS ====================

@login_required
def deposits_list(request):
    """List all deposits"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    # Get filters
    status_filter = request.GET.get('status', '')
    apartment_filter = request.GET.get('apartment', '')
    search_query = request.GET.get('search', '')
    
    # Base query
    tenancies = Tenancy.objects.filter(is_deleted=False).select_related(
        'tenant', 'room', 'apartment'
    )
    
    # Apply filters
    if status_filter:
        tenancies = tenancies.filter(status=status_filter)
    
    if apartment_filter:
        tenancies = tenancies.filter(apartment_id=apartment_filter)
    
    if search_query:
        tenancies = tenancies.filter(
            Q(tenant__first_name__icontains=search_query) |
            Q(tenant__last_name__icontains=search_query) |
            Q(room__room_number__icontains=search_query)
        )
    
    # Statistics
    total_deposits = tenancies.aggregate(total=Sum('deposit_paid'))['total'] or 0
    refunded_deposits = tenancies.filter(
        deposit_refunded=True
    ).aggregate(total=Sum('deposit_refund_amount'))['total'] or 0
    pending_refunds = tenancies.filter(
        status='terminated',
        deposit_refunded=False
    ).count()
    
    # Pagination
    paginator = Paginator(tenancies.order_by('-created_at'), 20)
    page_number = request.GET.get('page')
    tenancies_page = paginator.get_page(page_number)
    
    # Get apartments for filter
    apartments = Apartment.objects.filter(owner=request.user)
    
    context = {
        'tenancies': tenancies_page,
        'total_deposits': total_deposits,
        'refunded_deposits': refunded_deposits,
        'pending_refunds': pending_refunds,
        'apartments': apartments,
        'status_filter': status_filter,
        'apartment_filter': apartment_filter,
        'search_query': search_query,
    }
    
    return render(request, 'payments/deposits_list.html', context)


@login_required
def deposit_detail(request, pk):
    """View deposit details"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    tenancy = get_object_or_404(Tenancy, pk=pk, is_deleted=False)
    
    context = {
        'tenancy': tenancy,
    }
    
    return render(request, 'payments/deposit_detail.html', context)


@login_required
def deposit_refund(request, pk):
    """Process deposit refund"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    tenancy = get_object_or_404(Tenancy, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        refund_amount = request.POST.get('refund_amount')
        deduction_reason = request.POST.get('deduction_reason', '')
        
        try:
            tenancy.deposit_refunded = True
            tenancy.deposit_refund_amount = Decimal(refund_amount)
            tenancy.deposit_deduction_reason = deduction_reason
            tenancy.save()
            
            # Create notification
            Notification.objects.create(
                user=tenancy.tenant,
                notification_type='general',
                title='Deposit Refund Processed',
                message=f'Your deposit refund of KES {refund_amount} has been processed.'
            )
            
            messages.success(request, 'Deposit refund processed successfully.')
            return redirect('deposit_detail', pk=tenancy.pk)
        
        except Exception as e:
            messages.error(request, f'Error processing refund: {str(e)}')
    
    context = {
        'tenancy': tenancy,
    }
    
    return render(request, 'payments/deposit_refund_form.html', context)


# ==================== HELPER FUNCTIONS ====================

def update_rent_due_after_payment(payment):
    """Update rent due status after payment"""
    try:
        # Get or create rent due for the payment month
        rent_due, created = RentDue.objects.get_or_create(
            tenancy=payment.tenancy,
            month_for=payment.payment_for_month,
            defaults={
                'tenant': payment.tenant,
                'due_date': datetime.strptime(str(payment.payment_for_month), '%Y-%m-%d').replace(day=3),
                'amount_due': payment.tenancy.room.monthly_rent,
                'amount_paid': 0,
                'balance': payment.tenancy.room.monthly_rent,
                'status': 'unpaid'
            }
        )
        
        # Update payment amount
        rent_due.amount_paid += payment.amount
        rent_due.balance = rent_due.amount_due - rent_due.amount_paid
        
        # Update status
        if rent_due.balance <= 0:
            rent_due.status = 'paid'
        elif rent_due.amount_paid > 0:
            rent_due.status = 'partially_paid'
        else:
            rent_due.status = 'unpaid'
        
        rent_due.save()
        
    except Exception as e:
        print(f"Error updating rent due: {str(e)}")


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Q
from decimal import Decimal
from datetime import timedelta
from .models import (
    Tenancy, RentDue, RentPayment, WaterBill, 
    ElectricityBill, PaymentReport, Notification
)

# Helper decorator
def tenant_required(view_func):
    """Decorator to ensure user is a tenant"""
    def wrapper(request, *args, **kwargs):
        if request.user.user_type != 'tenant':
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('admin_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


# ============= MY TENANCY SECTION =============

@login_required
@tenant_required
def my_room(request):
    """Display tenant's current room details"""
    try:
        active_tenancy = Tenancy.objects.select_related(
            'room', 'room__room_type', 'apartment'
        ).get(
            tenant=request.user,
            status='active',
            is_deleted=False
        )
    except Tenancy.DoesNotExist:
        messages.warning(request, 'You do not have an active tenancy.')
        return redirect('tenant_dashboard')
    
    context = {
        'active_tenancy': active_tenancy,
        'room': active_tenancy.room,
        'apartment': active_tenancy.apartment,
    }
    
    return render(request, 'tenant/my_room.html', context)


@login_required
@tenant_required
def tenancy_details(request):
    """Display tenant's tenancy history and details"""
    # Active tenancy
    active_tenancy = Tenancy.objects.select_related(
        'room', 'room__room_type', 'apartment'
    ).filter(
        tenant=request.user,
        status='active',
        is_deleted=False
    ).first()
    
    # All tenancies (history)
    tenancy_history = Tenancy.objects.select_related(
        'room', 'room__room_type', 'apartment'
    ).filter(
        tenant=request.user,
        is_deleted=False
    ).exclude(status='active').order_by('-start_date')
    
    context = {
        'active_tenancy': active_tenancy,
        'tenancy_history': tenancy_history,
    }
    
    return render(request, 'tenant/tenancy_details.html', context)


@login_required
@tenant_required
def deposit_info(request):
    """Display tenant's deposit information"""
    active_tenancy = Tenancy.objects.select_related(
        'room', 'apartment'
    ).filter(
        tenant=request.user,
        status='active',
        is_deleted=False
    ).first()
    
    # All tenancies with deposit info
    all_tenancies = Tenancy.objects.select_related(
        'room', 'apartment'
    ).filter(
        tenant=request.user,
        is_deleted=False
    ).order_by('-start_date')
    
    context = {
        'active_tenancy': active_tenancy,
        'all_tenancies': all_tenancies,
    }
    
    return render(request, 'tenant/deposit_info.html', context)


# ============= PAYMENTS SECTION =============

# views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import json

from .models import Tenancy, RentDue, RentPayment
from utils.mpesa import MpesaClient
from utils.email_utils import send_payment_receipt


@login_required
@tenant_required
def pay_rent(request):
    """Pay rent via M-Pesa or record payment"""
    try:
        active_tenancy = Tenancy.objects.select_related(
            'room', 'apartment'
        ).get(
            tenant=request.user,
            status='active',
            is_deleted=False
        )
    except Tenancy.DoesNotExist:
        messages.warning(request, 'You do not have an active tenancy.')
        return redirect('tenant_dashboard')
    
    # Get unpaid/partially paid rent dues
    today = timezone.now().date()
    
    unpaid_dues = RentDue.objects.filter(
        tenancy=active_tenancy,
        status__in=['unpaid', 'partially_paid', 'overdue'],
        is_deleted=False
    ).order_by('due_date')
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        
        if payment_method == 'mpesa':
            return handle_mpesa_payment(request, active_tenancy)
        elif payment_method == 'bank_transfer':
            return handle_bank_transfer(request, active_tenancy)
        elif payment_method == 'cash':
            messages.info(request, 'Please visit the office to complete your cash payment.')
            return redirect('tenant_dashboard')
    
    context = {
        'active_tenancy': active_tenancy,
        'unpaid_dues': unpaid_dues,
    }
    
    return render(request, 'tenant/pay_rent.html', context)


def handle_mpesa_payment(request, active_tenancy):
    """Handle M-Pesa STK Push payment"""
    mpesa_phone = request.POST.get('mpesa_phone', '').strip()
    rent_due_id = request.POST.get('rent_due')
    amount = request.POST.get('amount')
    
    # Validation
    if not all([mpesa_phone, rent_due_id, amount]):
        messages.error(request, 'Please fill in all required fields.')
        return redirect('pay_rent')
    
    try:
        amount = Decimal(amount)
        if amount <= 0:
            messages.error(request, 'Invalid payment amount.')
            return redirect('pay_rent')
    except:
        messages.error(request, 'Invalid payment amount.')
        return redirect('pay_rent')
    
    # Get rent due
    try:
        rent_due = RentDue.objects.get(
            id=rent_due_id,
            tenancy=active_tenancy,
            is_deleted=False
        )
    except RentDue.DoesNotExist:
        messages.error(request, 'Invalid rent due selected.')
        return redirect('pay_rent')
    
    # Check if amount exceeds balance
    if amount > rent_due.balance:
        messages.error(request, f'Amount cannot exceed balance of ${rent_due.balance}')
        return redirect('pay_rent')
    
    # Create pending payment record
    payment = RentPayment.objects.create(
        tenancy=active_tenancy,
        tenant=request.user,
        apartment=active_tenancy.apartment,
        amount=amount,
        payment_method='mpesa',
        mpesa_phone_number=mpesa_phone,
        payment_for_month=rent_due.month_for,
        status='pending'
    )
    
    # Initiate M-Pesa STK Push
    mpesa_client = MpesaClient()
    result = mpesa_client.stk_push(
        phone_number=mpesa_phone,
        amount=amount,
        account_reference=f"RENT-{active_tenancy.room.room_number}",
        transaction_desc=f"Rent payment for {rent_due.month_for.strftime('%B %Y')}"
    )
    
    if result['success']:
        # Store checkout request ID for status checking
        payment.mpesa_transaction_id = result['checkout_request_id']
        payment.save()
        
        # Return JSON response with checkout request ID
        return JsonResponse({
            'success': True,
            'message': 'STK Push sent to your phone. Please enter your M-Pesa PIN.',
            'checkout_request_id': result['checkout_request_id'],
            'payment_id': payment.id
        })
    else:
        payment.status = 'failed'
        payment.notes = result.get('error', 'STK Push failed')
        payment.save()
        
        return JsonResponse({
            'success': False,
            'error': result.get('error', 'Payment initiation failed')
        })


@login_required
@tenant_required
def check_payment_status(request, payment_id):
    """Check M-Pesa payment status"""
    try:
        payment = RentPayment.objects.get(
            id=payment_id,
            tenant=request.user
        )
    except RentPayment.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Payment not found'})
    
    if payment.status != 'pending':
        return JsonResponse({
            'success': True,
            'status': payment.status,
            'message': f'Payment is {payment.status}'
        })
    
    # Check with M-Pesa
    mpesa_client = MpesaClient()
    result = mpesa_client.check_transaction_status(payment.mpesa_transaction_id)
    
    if result['success']:
        result_code = result.get('result_code')
        
        if result_code == '0':
            # Payment successful
            with transaction.atomic():
                payment.status = 'completed'
                payment.payment_date = timezone.now()
                payment.save()
                
                # Update rent due
                rent_due = RentDue.objects.get(
                    tenancy=payment.tenancy,
                    month_for=payment.payment_for_month
                )
                rent_due.amount_paid += payment.amount
                rent_due.balance = rent_due.amount_due - rent_due.amount_paid
                
                if rent_due.balance <= 0:
                    rent_due.status = 'paid'
                    rent_due.balance = 0
                elif rent_due.amount_paid > 0:
                    rent_due.status = 'partially_paid'
                
                rent_due.save()
                
                # Send receipt email
                send_payment_receipt(payment)
            
            return JsonResponse({
                'success': True,
                'status': 'completed',
                'message': 'Payment completed successfully!'
            })
        elif result_code == '1032':
            # User cancelled
            payment.status = 'failed'
            payment.notes = 'Payment cancelled by user'
            payment.save()
            
            return JsonResponse({
                'success': True,
                'status': 'failed',
                'message': 'Payment was cancelled'
            })
        else:
            # Still pending or other status
            return JsonResponse({
                'success': True,
                'status': 'pending',
                'message': 'Payment is still processing...'
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Could not check payment status'
    })


def handle_bank_transfer(request, active_tenancy):
    """Handle bank transfer payment recording"""
    transaction_ref = request.POST.get('transaction_ref', '').strip()
    rent_due_id = request.POST.get('rent_due')
    
    if not transaction_ref:
        messages.error(request, 'Please provide transaction reference.')
        return redirect('pay_rent')
    
    try:
        rent_due = RentDue.objects.get(
            id=rent_due_id,
            tenancy=active_tenancy
        )
    except RentDue.DoesNotExist:
        messages.error(request, 'Invalid rent due selected.')
        return redirect('pay_rent')
    
    # Create payment record (pending admin verification)
    payment = RentPayment.objects.create(
        tenancy=active_tenancy,
        tenant=request.user,
        apartment=active_tenancy.apartment,
        amount=rent_due.balance,
        payment_method='bank_transfer',
        payment_for_month=rent_due.month_for,
        status='pending',
        notes=f'Bank transfer reference: {transaction_ref}'
    )
    
    messages.success(request, 'Payment details submitted. Admin will verify and confirm.')
    return redirect('tenant_dashboard')


@csrf_exempt
def mpesa_callback(request):
    """M-Pesa callback endpoint"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Extract callback data
            body = data.get('Body', {}).get('stkCallback', {})
            checkout_request_id = body.get('CheckoutRequestID')
            result_code = body.get('ResultCode')
            
            # Find payment
            try:
                payment = RentPayment.objects.get(
                    mpesa_transaction_id=checkout_request_id
                )
            except RentPayment.DoesNotExist:
                return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'})
            
            if result_code == 0:
                # Payment successful
                callback_metadata = body.get('CallbackMetadata', {}).get('Item', [])
                mpesa_receipt = next(
                    (item['Value'] for item in callback_metadata if item['Name'] == 'MpesaReceiptNumber'),
                    None
                )
                
                with transaction.atomic():
                    payment.status = 'completed'
                    payment.mpesa_transaction_id = mpesa_receipt
                    payment.payment_date = timezone.now()
                    payment.save()
                    
                    # Update rent due
                    rent_due = RentDue.objects.get(
                        tenancy=payment.tenancy,
                        month_for=payment.payment_for_month
                    )
                    rent_due.amount_paid += payment.amount
                    rent_due.balance = rent_due.amount_due - rent_due.amount_paid
                    
                    if rent_due.balance <= 0:
                        rent_due.status = 'paid'
                        rent_due.balance = 0
                    elif rent_due.amount_paid > 0:
                        rent_due.status = 'partially_paid'
                    
                    rent_due.save()
                    
                    # Send receipt
                    send_payment_receipt(payment)
            else:
                # Payment failed
                payment.status = 'failed'
                payment.notes = body.get('ResultDesc', 'Payment failed')
                payment.save()
            
        except Exception as e:
            print(f"Callback error: {str(e)}")
    
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'})


@login_required
@tenant_required
def rent_due(request):
    """Display all rent dues"""
    try:
        active_tenancy = Tenancy.objects.select_related(
            'room', 'apartment'
        ).get(
            tenant=request.user,
            status='active',
            is_deleted=False
        )
    except Tenancy.DoesNotExist:
        messages.warning(request, 'You do not have an active tenancy.')
        return redirect('tenant_dashboard')
    
    # All rent dues
    rent_dues = RentDue.objects.filter(
        tenancy=active_tenancy,
        is_deleted=False
    ).order_by('-month_for')
    
    # Current rent due
    today = timezone.now().date()
    current_month = today.replace(day=1)
    
    current_due = rent_dues.filter(month_for=current_month).first()
    
    # Statistics
    total_paid = rent_dues.filter(status='paid').count()
    total_unpaid = rent_dues.filter(status__in=['unpaid', 'overdue']).count()
    
    context = {
        'active_tenancy': active_tenancy,
        'rent_dues': rent_dues,
        'current_due': current_due,
        'total_paid': total_paid,
        'total_unpaid': total_unpaid,
    }
    
    return render(request, 'tenant/rent_due.html', context)


@login_required
@tenant_required
def payment_history(request):
    """Display tenant's payment history"""
    payments = RentPayment.objects.filter(
        tenant=request.user,
        is_deleted=False
    ).select_related('tenancy', 'tenancy__room', 'apartment').order_by('-payment_date')
    
    # Statistics
    total_payments = payments.filter(status='completed').count()
    total_amount_paid = payments.filter(status='completed').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    # This year
    today = timezone.now().date()
    year_start = today.replace(month=1, day=1)
    this_year_payments = payments.filter(
        payment_date__gte=year_start,
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    context = {
        'payments': payments,
        'total_payments': total_payments,
        'total_amount_paid': total_amount_paid,
        'this_year_payments': this_year_payments,
    }
    
    return render(request, 'tenant/payment_history.html', context)


@login_required
@tenant_required
def report_payment_issue(request):
    """Report inability to pay rent on time"""
    try:
        active_tenancy = Tenancy.objects.select_related(
            'room', 'apartment'
        ).get(
            tenant=request.user,
            status='active',
            is_deleted=False
        )
    except Tenancy.DoesNotExist:
        messages.warning(request, 'You do not have an active tenancy.')
        return redirect('tenant_dashboard')
    
    # Get unpaid rent dues
    unpaid_dues = RentDue.objects.filter(
        tenancy=active_tenancy,
        status__in=['unpaid', 'partially_paid', 'overdue'],
        is_deleted=False
    ).order_by('due_date')
    
    if request.method == 'POST':
        rent_due_id = request.POST.get('rent_due')
        reason = request.POST.get('reason')
        expected_date = request.POST.get('expected_payment_date')
        
        if rent_due_id and reason:
            rent_due = get_object_or_404(RentDue, id=rent_due_id, tenancy=active_tenancy)
            
            PaymentReport.objects.create(
                tenancy=active_tenancy,
                rent_due=rent_due,
                reason=reason,
                expected_payment_date=expected_date if expected_date else None
            )
            
            # Update rent due
            rent_due.reported_to_office = True
            rent_due.report_date = timezone.now()
            rent_due.report_notes = reason
            rent_due.save()
            
            messages.success(request, 'Your payment issue has been reported to the office.')
            return redirect('rent_due')
        else:
            messages.error(request, 'Please fill in all required fields.')
    
    # Previous reports
    previous_reports = PaymentReport.objects.filter(
        tenancy=active_tenancy
    ).select_related('rent_due').order_by('-report_date')[:5]
    
    context = {
        'active_tenancy': active_tenancy,
        'unpaid_dues': unpaid_dues,
        'previous_reports': previous_reports,
    }
    
    return render(request, 'tenant/report_payment_issue.html', context)


# ============= UTILITY BILLS SECTION =============

@login_required
@tenant_required
def water_bills(request):
    """Display tenant's water bills"""
    try:
        active_tenancy = Tenancy.objects.select_related(
            'room', 'apartment'
        ).get(
            tenant=request.user,
            status='active',
            is_deleted=False
        )
    except Tenancy.DoesNotExist:
        messages.warning(request, 'You do not have an active tenancy.')
        return redirect('tenant_dashboard')
    
    bills = WaterBill.objects.filter(
        tenancy=active_tenancy
    ).order_by('-bill_month')
    
    # Statistics
    total_bills = bills.count()
    pending_bills = bills.filter(status='pending').count()
    overdue_bills = bills.filter(status='overdue').count()
    total_amount = bills.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    context = {
        'active_tenancy': active_tenancy,
        'bills': bills,
        'total_bills': total_bills,
        'pending_bills': pending_bills,
        'overdue_bills': overdue_bills,
        'total_amount': total_amount,
    }
    
    return render(request, 'tenant/water_bills.html', context)


@login_required
@tenant_required
def electricity_bills(request):
    """Display tenant's electricity bills"""
    try:
        active_tenancy = Tenancy.objects.select_related(
            'room', 'apartment'
        ).get(
            tenant=request.user,
            status='active',
            is_deleted=False
        )
    except Tenancy.DoesNotExist:
        messages.warning(request, 'You do not have an active tenancy.')
        return redirect('tenant_dashboard')
    
    bills = ElectricityBill.objects.filter(
        tenancy=active_tenancy
    ).order_by('-bill_month')
    
    # Statistics
    total_bills = bills.count()
    total_units = bills.aggregate(total=Sum('units_purchased'))['total'] or Decimal('0.00')
    total_amount = bills.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    context = {
        'active_tenancy': active_tenancy,
        'bills': bills,
        'total_bills': total_bills,
        'total_units': total_units,
        'total_amount': total_amount,
    }
    
    return render(request, 'tenant/electricity_bills.html', context)


@login_required
@tenant_required
def bill_history(request):
    """Display combined utility bill history"""
    try:
        active_tenancy = Tenancy.objects.select_related(
            'room', 'apartment'
        ).get(
            tenant=request.user,
            status='active',
            is_deleted=False
        )
    except Tenancy.DoesNotExist:
        messages.warning(request, 'You do not have an active tenancy.')
        return redirect('tenant_dashboard')
    
    water_bills = WaterBill.objects.filter(
        tenancy=active_tenancy
    ).order_by('-bill_month')
    
    electricity_bills = ElectricityBill.objects.filter(
        tenancy=active_tenancy
    ).order_by('-bill_month')
    
    # Combined statistics
    total_water = water_bills.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_electricity = electricity_bills.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_utilities = total_water + total_electricity
    
    context = {
        'active_tenancy': active_tenancy,
        'water_bills': water_bills,
        'electricity_bills': electricity_bills,
        'total_water': total_water,
        'total_electricity': total_electricity,
        'total_utilities': total_utilities,
    }
    
    return render(request, 'tenant/bill_history.html', context)


# ============= SUPPORT SECTION =============

@login_required
@tenant_required
def notifications(request):
    """Display tenant's notifications"""
    all_notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    unread_notifications = all_notifications.filter(is_read=False)
    
    # Mark as read if requested
    if request.method == 'POST':
        notification_id = request.POST.get('notification_id')
        if notification_id:
            notification = get_object_or_404(Notification, id=notification_id, user=request.user)
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()
            messages.success(request, 'Notification marked as read.')
            return redirect('notifications')
        
        # Mark all as read
        if request.POST.get('mark_all_read'):
            unread_notifications.update(is_read=True, read_at=timezone.now())
            messages.success(request, 'All notifications marked as read.')
            return redirect('notifications')
    
    context = {
        'all_notifications': all_notifications,
        'unread_notifications': unread_notifications,
        'unread_count': unread_notifications.count(),
    }
    
    return render(request, 'tenant/notifications.html', context)


@login_required
@tenant_required
def contact_admin(request):
    """Contact property admin"""
    try:
        active_tenancy = Tenancy.objects.select_related(
            'room', 'apartment', 'apartment__owner'
        ).get(
            tenant=request.user,
            status='active',
            is_deleted=False
        )
    except Tenancy.DoesNotExist:
        messages.warning(request, 'You do not have an active tenancy.')
        return redirect('tenant_dashboard')
    
    if request.method == 'POST':
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        if subject and message:
            # Create notification for admin
            Notification.objects.create(
                user=active_tenancy.apartment.owner,
                notification_type='general',
                title=f'Message from {request.user.get_full_name()}',
                message=f'Subject: {subject}\n\n{message}'
            )
            
            messages.success(request, 'Your message has been sent to the property manager.')
            return redirect('tenant_dashboard')
        else:
            messages.error(request, 'Please fill in all fields.')
    
    context = {
        'active_tenancy': active_tenancy,
        'admin': active_tenancy.apartment.owner,
    }
    
    return render(request, 'tenant/contact_admin.html', context)


@login_required
@tenant_required
def help_faq(request):
    """Help and FAQ page"""
    # FAQ data - in production, this could come from database
    faqs = [
        {
            'category': 'Rent Payments',
            'questions': [
                {
                    'question': 'When is rent due?',
                    'answer': 'Rent is due on the 3rd of every month. Late payments may incur additional fees.'
                },
                {
                    'question': 'How can I pay rent?',
                    'answer': 'You can pay rent via M-Pesa STK Push, bank transfer, or cash at the office.'
                },
                {
                    'question': 'What if I cannot pay rent on time?',
                    'answer': 'Please report your payment issue through the "Report Payment Issue" page as soon as possible.'
                },
            ]
        },
        {
            'category': 'Utility Bills',
            'questions': [
                {
                    'question': 'How are water bills calculated?',
                    'answer': 'Water bills are calculated based on your meter reading multiplied by the rate per unit.'
                },
                {
                    'question': 'Where can I find my electricity token?',
                    'answer': 'Your electricity tokens are displayed in the Electricity Bills section and sent via SMS.'
                },
            ]
        },
        {
            'category': 'Tenancy',
            'questions': [
                {
                    'question': 'How do I request room maintenance?',
                    'answer': 'Contact your property manager through the "Contact Admin" page with details of the issue.'
                },
                {
                    'question': 'When will my deposit be refunded?',
                    'answer': 'Deposits are refunded after tenancy termination, subject to room condition inspection.'
                },
            ]
        },
    ]
    
    context = {
        'faqs': faqs,
    }
    
    return render(request, 'tenant/help_faq.html', context)