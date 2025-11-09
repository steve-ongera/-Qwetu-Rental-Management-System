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

@login_required
def tenant_create(request):
    """Create new tenant (user account)"""
    if request.method == 'POST':
        # Get form data
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone_number')
        national_id = request.POST.get('national_id')
        username = request.POST.get('username')
        password = request.POST.get('password')
        
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
            tenant = User.objects.create_user(
                username=username,
                password=password,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone_number=phone_number,
                national_id=national_id if national_id else None,
                user_type='tenant',
                user_status='active'
            )
            messages.success(request, f'Tenant "{tenant.get_full_name()}" created successfully!')
            return redirect('tenant_detail', pk=tenant.pk)
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