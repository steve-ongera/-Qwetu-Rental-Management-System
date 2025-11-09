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