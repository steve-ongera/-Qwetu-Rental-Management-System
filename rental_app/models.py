from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal


class User(AbstractUser):
    """Custom user model for both admin and tenants"""
    USER_TYPE_CHOICES = (
        ('admin', 'Admin'),
        ('tenant', 'Tenant'),
    )
    USER_STATUS = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('archived', 'Archived'),  # For moved out tenants
    )
    
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)
    user_status = models.CharField(max_length=20, choices=USER_STATUS, default='active')
    phone_number = models.CharField(max_length=15, unique=True)
    national_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    
    # Soft delete - never actually delete user data
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_full_name()} - {self.user_type}"


class Apartment(models.Model):
    """Apartment/Building managed by admin"""
    name = models.CharField(max_length=200)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='apartments', limit_choices_to={'user_type': 'admin'})
    location = models.CharField(max_length=300)
    total_floors = models.IntegerField(validators=[MinValueValidator(1)])
    description = models.TextField(blank=True)
    water_rate_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class RoomType(models.Model):
    """Different types of rooms available"""
    ROOM_CHOICES = (
        ('bedsitter', 'Bedsitter'),
        ('single_room', 'Single Room'),
        ('one_bedroom', 'One Bedroom'),
        ('two_bedroom', 'Two Bedroom'),
        ('three_bedroom', 'Three Bedroom'),
    )
    name = models.CharField(max_length=50, choices=ROOM_CHOICES)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.get_name_display()


class Room(models.Model):
    """Individual rooms in the apartment"""
    ROOM_STATUS = (
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('maintenance', 'Under Maintenance'),
    )
    
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name='rooms')
    room_number = models.CharField(max_length=10)  # e.g., A1, B2, C3
    room_type = models.ForeignKey(RoomType, on_delete=models.PROTECT)
    floor_number = models.IntegerField(validators=[MinValueValidator(0)])
    
    # Room features
    has_balcony = models.BooleanField(default=False)
    has_shower = models.BooleanField(default=True)
    has_kitchen_unit = models.BooleanField(default=True)
    has_clothes_cabinet = models.BooleanField(default=True)
    
    # Pricing
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    
    status = models.CharField(max_length=20, choices=ROOM_STATUS, default='available')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('apartment', 'room_number')
        ordering = ['floor_number', 'room_number']

    def __str__(self):
        return f"{self.apartment.name} - Room {self.room_number}"


class Tenancy(models.Model):
    """Tenant occupancy record - tracks each room occupation separately"""
    TENANCY_STATUS = (
        ('active', 'Active'),
        ('terminated', 'Terminated'),
        ('suspended', 'Suspended'),
        ('switched', 'Switched Room'),  # When tenant moves to another room
    )
    
    TERMINATION_REASON = (
        ('vacated', 'Tenant Vacated'),
        ('evicted', 'Evicted'),
        ('room_switch', 'Switched to Another Room'),
        ('other', 'Other'),
    )
    
    tenant = models.ForeignKey(User, on_delete=models.PROTECT, related_name='tenancies', limit_choices_to={'user_type': 'tenant'})
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name='tenancies')
    apartment = models.ForeignKey(Apartment, on_delete=models.PROTECT, related_name='tenancies')  # Denormalized for easy querying
    
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    deposit_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    deposit_refunded = models.BooleanField(default=False)
    deposit_refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    deposit_deduction_reason = models.TextField(blank=True)  # Why deposit was partially refunded
    
    status = models.CharField(max_length=20, choices=TENANCY_STATUS, default='active')
    termination_reason = models.CharField(max_length=20, choices=TERMINATION_REASON, null=True, blank=True)
    
    # Room condition tracking
    move_in_condition = models.TextField(blank=True)
    move_out_condition = models.TextField(blank=True)
    
    # Room switching tracking
    switched_to_tenancy = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='previous_tenancy')
    switched_from_tenancy = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='next_tenancy')
    
    # Soft delete - never actually delete tenant data
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Tenancies'
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['apartment', 'status']),
        ]

    def __str__(self):
        return f"{self.tenant.get_full_name()} - {self.room.room_number} ({self.start_date} to {self.end_date or 'Present'})"


class RentPayment(models.Model):
    """Rent payment records"""
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    
    PAYMENT_METHOD = (
        ('mpesa', 'M-Pesa STK Push'),
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
    )
    
    tenancy = models.ForeignKey(Tenancy, on_delete=models.PROTECT, related_name='rent_payments')
    tenant = models.ForeignKey(User, on_delete=models.PROTECT, related_name='rent_payments')  # Denormalized for history
    apartment = models.ForeignKey(Apartment, on_delete=models.PROTECT, related_name='rent_payments')  # Denormalized for reporting
    
    # Payment details
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    payment_date = models.DateTimeField(default=timezone.now)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD, default='mpesa')
    
    # M-Pesa transaction details
    mpesa_transaction_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    mpesa_phone_number = models.CharField(max_length=15, null=True, blank=True)
    
    # Period covered by this payment
    months_covered = models.IntegerField(default=1, validators=[MinValueValidator(1)])  # Can pay for multiple months
    payment_for_month = models.DateField()  # The month this payment is for
    
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    
    # Late payment tracking
    is_late_payment = models.BooleanField(default=False)
    late_payment_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    notes = models.TextField(blank=True)
    
    # Soft delete - never actually delete payment data
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['tenant', 'payment_date']),
            models.Index(fields=['apartment', 'payment_date']),
        ]

    def __str__(self):
        return f"Payment {self.amount} by {self.tenant.get_full_name()} - {self.payment_for_month}"


class RentDue(models.Model):
    """Track rent due for each tenant per month"""
    DUE_STATUS = (
        ('paid', 'Paid'),
        ('partially_paid', 'Partially Paid'),
        ('unpaid', 'Unpaid'),
        ('overdue', 'Overdue'),
    )
    
    tenancy = models.ForeignKey(Tenancy, on_delete=models.PROTECT, related_name='rent_dues')
    tenant = models.ForeignKey(User, on_delete=models.PROTECT, related_name='rent_dues')  # Denormalized for history
    due_date = models.DateField()  # Always 3rd of each month
    month_for = models.DateField()  # The month this rent is for
    
    amount_due = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    status = models.CharField(max_length=20, choices=DUE_STATUS, default='unpaid')
    
    # Office reporting for inability to pay
    reported_to_office = models.BooleanField(default=False)
    report_date = models.DateTimeField(null=True, blank=True)
    report_notes = models.TextField(blank=True)
    
    # Soft delete - never actually delete due records
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tenancy', 'month_for')
        ordering = ['-due_date']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['due_date', 'status']),
        ]

    def __str__(self):
        return f"Rent due for {self.tenant.get_full_name()} - {self.month_for}"


class ElectricityBill(models.Model):
    """Electricity bills per room (token-based)"""
    BILL_STATUS = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    )
    
    tenancy = models.ForeignKey(Tenancy, on_delete=models.CASCADE, related_name='electricity_bills')
    
    bill_month = models.DateField()
    token_number = models.CharField(max_length=100, unique=True)
    units_purchased = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    
    purchase_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=BILL_STATUS, default='paid')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-bill_month']

    def __str__(self):
        return f"Electricity Bill - {self.tenancy.room.room_number} - {self.bill_month}"


class WaterBill(models.Model):
    """Water bills per room (paid monthly to apartment owner)"""
    BILL_STATUS = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    )
    
    tenancy = models.ForeignKey(Tenancy, on_delete=models.CASCADE, related_name='water_bills')
    
    bill_month = models.DateField()
    units_consumed = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    rate_per_unit = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    
    previous_reading = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    current_reading = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    due_date = models.DateField()
    payment_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=BILL_STATUS, default='pending')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tenancy', 'bill_month')
        ordering = ['-bill_month']

    def __str__(self):
        return f"Water Bill - {self.tenancy.room.room_number} - {self.bill_month}"


class PaymentReport(models.Model):
    """Reports from tenants about inability to pay rent"""
    tenancy = models.ForeignKey(Tenancy, on_delete=models.CASCADE, related_name='payment_reports')
    rent_due = models.ForeignKey(RentDue, on_delete=models.CASCADE, related_name='reports')
    
    report_date = models.DateTimeField(default=timezone.now)
    reason = models.TextField()
    expected_payment_date = models.DateField(null=True, blank=True)
    
    admin_notes = models.TextField(blank=True)
    resolved = models.BooleanField(default=False)
    resolved_date = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-report_date']

    def __str__(self):
        return f"Payment Report - {self.tenancy.tenant.get_full_name()} - {self.report_date}"


class Notification(models.Model):
    """Notifications for users"""
    NOTIFICATION_TYPE = (
        ('rent_due', 'Rent Due'),
        ('payment_received', 'Payment Received'),
        ('payment_overdue', 'Payment Overdue'),
        ('water_bill', 'Water Bill'),
        ('maintenance', 'Maintenance'),
        ('general', 'General'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPE)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.user.get_full_name()}"