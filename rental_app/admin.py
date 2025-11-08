from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.db.models import Sum, Count, Q
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    User, Apartment, RoomType, Room, Tenancy, 
    RentPayment, RentDue, ElectricityBill, WaterBill,
    PaymentReport, Notification
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'get_full_name', 'user_type', 'user_status', 'phone_number', 'is_active', 'created_at')
    list_filter = ('user_type', 'user_status', 'is_active', 'is_staff', 'created_at')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone_number', 'national_id')
    ordering = ('-created_at',)
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('user_type', 'user_status', 'phone_number', 'national_id', 'profile_picture')
        }),
        ('Soft Delete', {
            'fields': ('is_deleted', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Info', {
            'fields': ('user_type', 'phone_number', 'national_id', 'email', 'first_name', 'last_name')
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Show non-deleted users by default
        if not request.GET.get('show_deleted'):
            qs = qs.filter(is_deleted=False)
        return qs


@admin.register(Apartment)
class ApartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'location', 'total_floors', 'total_rooms', 'occupied_rooms', 'water_rate_per_unit', 'created_at')
    list_filter = ('owner', 'created_at')
    search_fields = ('name', 'location', 'owner__username', 'owner__email')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'owner', 'location', 'total_floors', 'description')
        }),
        ('Billing', {
            'fields': ('water_rate_per_unit',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def total_rooms(self, obj):
        return obj.rooms.count()
    total_rooms.short_description = 'Total Rooms'
    
    def occupied_rooms(self, obj):
        occupied = obj.rooms.filter(status='occupied').count()
        total = obj.rooms.count()
        if total > 0:
            percentage = (occupied / total) * 100
            color = 'green' if percentage > 70 else 'orange' if percentage > 40 else 'red'
            return format_html(
                '<span style="color: {};">{}/{} ({:.1f}%)</span>',
                color, occupied, total, percentage
            )
        return '0/0'
    occupied_rooms.short_description = 'Occupancy'


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ('get_name_display', 'description')
    search_fields = ('name', 'description')


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'apartment', 'room_type', 'floor_number', 'monthly_rent', 'deposit_amount', 'status', 'features_summary', 'current_tenant')
    list_filter = ('apartment', 'room_type', 'status', 'floor_number', 'has_balcony', 'has_shower')
    search_fields = ('room_number', 'apartment__name')
    ordering = ('apartment', 'floor_number', 'room_number')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('apartment', 'room_number', 'room_type', 'floor_number')
        }),
        ('Features', {
            'fields': ('has_balcony', 'has_shower', 'has_kitchen_unit', 'has_clothes_cabinet')
        }),
        ('Pricing', {
            'fields': ('monthly_rent', 'deposit_amount')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def features_summary(self, obj):
        features = []
        if obj.has_balcony:
            features.append('🏠 Balcony')
        if obj.has_shower:
            features.append('🚿 Shower')
        if obj.has_kitchen_unit:
            features.append('🍳 Kitchen')
        if obj.has_clothes_cabinet:
            features.append('👔 Cabinet')
        return ' | '.join(features) if features else 'None'
    features_summary.short_description = 'Features'
    
    def current_tenant(self, obj):
        active_tenancy = obj.tenancies.filter(status='active').first()
        if active_tenancy:
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:rental_app_tenancy_change', args=[active_tenancy.pk]),
                active_tenancy.tenant.get_full_name()
            )
        return '-'
    current_tenant.short_description = 'Current Tenant'


@admin.register(Tenancy)
class TenancyAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'room', 'apartment', 'start_date', 'end_date', 'status', 'deposit_paid', 'deposit_status', 'created_at')
    list_filter = ('status', 'apartment', 'start_date', 'deposit_refunded', 'termination_reason')
    search_fields = ('tenant__username', 'tenant__email', 'tenant__first_name', 'tenant__last_name', 'room__room_number')
    date_hierarchy = 'start_date'
    readonly_fields = ('created_at', 'updated_at', 'switched_to_link', 'switched_from_link')
    
    fieldsets = (
        ('Tenancy Information', {
            'fields': ('tenant', 'room', 'apartment', 'start_date', 'end_date', 'status', 'termination_reason')
        }),
        ('Deposit', {
            'fields': ('deposit_paid', 'deposit_refunded', 'deposit_refund_amount', 'deposit_deduction_reason')
        }),
        ('Room Condition', {
            'fields': ('move_in_condition', 'move_out_condition'),
            'classes': ('collapse',)
        }),
        ('Room Switching', {
            'fields': ('switched_to_link', 'switched_from_link'),
            'classes': ('collapse',)
        }),
        ('Soft Delete', {
            'fields': ('is_deleted', 'deleted_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def deposit_status(self, obj):
        if obj.deposit_refunded:
            if obj.deposit_refund_amount == obj.deposit_paid:
                return format_html('<span style="color: green;">✓ Fully Refunded</span>')
            else:
                return format_html('<span style="color: orange;">⚠ Partially Refunded</span>')
        return format_html('<span style="color: blue;">Held</span>')
    deposit_status.short_description = 'Deposit Status'
    
    def switched_to_link(self, obj):
        if obj.switched_to_tenancy:
            url = reverse('admin:rental_app_tenancy_change', args=[obj.switched_to_tenancy.pk])
            return format_html('<a href="{}">View New Tenancy (Room {})</a>', url, obj.switched_to_tenancy.room.room_number)
        return '-'
    switched_to_link.short_description = 'Switched To'
    
    def switched_from_link(self, obj):
        if obj.switched_from_tenancy:
            url = reverse('admin:rental_app_tenancy_change', args=[obj.switched_from_tenancy.pk])
            return format_html('<a href="{}">View Previous Tenancy (Room {})</a>', url, obj.switched_from_tenancy.room.room_number)
        return '-'
    switched_from_link.short_description = 'Switched From'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.GET.get('show_deleted'):
            qs = qs.filter(is_deleted=False)
        return qs


@admin.register(RentPayment)
class RentPaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_date', 'tenant', 'room_number', 'amount', 'months_covered', 'payment_for_month', 'payment_method', 'status', 'mpesa_transaction_id')
    list_filter = ('status', 'payment_method', 'payment_date', 'is_late_payment', 'apartment')
    search_fields = ('tenant__username', 'tenant__email', 'mpesa_transaction_id', 'tenancy__room__room_number')
    date_hierarchy = 'payment_date'
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('tenancy', 'tenant', 'apartment', 'amount', 'payment_date', 'payment_method', 'status')
        }),
        ('Period Covered', {
            'fields': ('months_covered', 'payment_for_month')
        }),
        ('M-Pesa Details', {
            'fields': ('mpesa_transaction_id', 'mpesa_phone_number'),
            'classes': ('collapse',)
        }),
        ('Late Payment', {
            'fields': ('is_late_payment', 'late_payment_fee'),
            'classes': ('collapse',)
        }),
        ('Additional Info', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Soft Delete', {
            'fields': ('is_deleted', 'deleted_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def room_number(self, obj):
        return obj.tenancy.room.room_number
    room_number.short_description = 'Room'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.GET.get('show_deleted'):
            qs = qs.filter(is_deleted=False)
        return qs


@admin.register(RentDue)
class RentDueAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'room_number', 'month_for', 'due_date', 'amount_due', 'amount_paid', 'balance', 'status', 'reported_to_office')
    list_filter = ('status', 'due_date', 'reported_to_office', 'tenancy__apartment')
    search_fields = ('tenant__username', 'tenant__email', 'tenancy__room__room_number')
    date_hierarchy = 'due_date'
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Due Information', {
            'fields': ('tenancy', 'tenant', 'due_date', 'month_for')
        }),
        ('Amounts', {
            'fields': ('amount_due', 'amount_paid', 'balance', 'status')
        }),
        ('Office Report', {
            'fields': ('reported_to_office', 'report_date', 'report_notes'),
            'classes': ('collapse',)
        }),
        ('Soft Delete', {
            'fields': ('is_deleted', 'deleted_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def room_number(self, obj):
        return obj.tenancy.room.room_number
    room_number.short_description = 'Room'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.GET.get('show_deleted'):
            qs = qs.filter(is_deleted=False)
        return qs


@admin.register(ElectricityBill)
class ElectricityBillAdmin(admin.ModelAdmin):
    list_display = ('bill_month', 'room_number', 'tenant', 'token_number', 'units_purchased', 'amount', 'purchase_date', 'status')
    list_filter = ('status', 'bill_month', 'purchase_date')
    search_fields = ('token_number', 'tenancy__tenant__username', 'tenancy__room__room_number')
    date_hierarchy = 'bill_month'
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Bill Information', {
            'fields': ('tenancy', 'bill_month', 'status')
        }),
        ('Token Details', {
            'fields': ('token_number', 'units_purchased', 'amount', 'purchase_date')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def room_number(self, obj):
        return obj.tenancy.room.room_number
    room_number.short_description = 'Room'
    
    def tenant(self, obj):
        return obj.tenancy.tenant.get_full_name()
    tenant.short_description = 'Tenant'


@admin.register(WaterBill)
class WaterBillAdmin(admin.ModelAdmin):
    list_display = ('bill_month', 'room_number', 'tenant', 'units_consumed', 'rate_per_unit', 'total_amount', 'due_date', 'payment_date', 'status')
    list_filter = ('status', 'bill_month', 'due_date')
    search_fields = ('tenancy__tenant__username', 'tenancy__room__room_number')
    date_hierarchy = 'bill_month'
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Bill Information', {
            'fields': ('tenancy', 'bill_month', 'due_date', 'payment_date', 'status')
        }),
        ('Consumption', {
            'fields': ('previous_reading', 'current_reading', 'units_consumed')
        }),
        ('Billing', {
            'fields': ('rate_per_unit', 'total_amount')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def room_number(self, obj):
        return obj.tenancy.room.room_number
    room_number.short_description = 'Room'
    
    def tenant(self, obj):
        return obj.tenancy.tenant.get_full_name()
    tenant.short_description = 'Tenant'


@admin.register(PaymentReport)
class PaymentReportAdmin(admin.ModelAdmin):
    list_display = ('report_date', 'tenant', 'room_number', 'rent_month', 'expected_payment_date', 'resolved', 'resolved_date')
    list_filter = ('resolved', 'report_date', 'expected_payment_date')
    search_fields = ('tenancy__tenant__username', 'tenancy__tenant__email', 'reason')
    date_hierarchy = 'report_date'
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Report Information', {
            'fields': ('tenancy', 'rent_due', 'report_date', 'reason', 'expected_payment_date')
        }),
        ('Admin Response', {
            'fields': ('admin_notes', 'resolved', 'resolved_date')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def tenant(self, obj):
        return obj.tenancy.tenant.get_full_name()
    tenant.short_description = 'Tenant'
    
    def room_number(self, obj):
        return obj.tenancy.room.room_number
    room_number.short_description = 'Room'
    
    def rent_month(self, obj):
        return obj.rent_due.month_for.strftime('%B %Y')
    rent_month.short_description = 'Rent Month'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'notification_type', 'title', 'is_read', 'read_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('user__username', 'user__email', 'title', 'message')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Notification Information', {
            'fields': ('user', 'notification_type', 'title', 'message')
        }),
        ('Status', {
            'fields': ('is_read', 'read_at')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


# Customize admin site headers
admin.site.site_header = "Qwetu Rental Management System"
admin.site.site_title = "Qwetu Admin"
admin.site.index_title = "Welcome to Qwetu Administration"