"""
Management command to seed Qwetu database with realistic Kenyan data
Usage: python manage.py seed_data [--clear]
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from rental_app.models import (
    Apartment, RoomType, Room, Tenancy, RentPayment, 
    RentDue, ElectricityBill, WaterBill, Notification
)
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from decimal import Decimal
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds the database with realistic Kenyan rental data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before seeding',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing existing data...'))
            self.clear_data()
        
        self.stdout.write(self.style.SUCCESS('Starting data seeding...'))
        
        with transaction.atomic():
            # Create room types
            room_types = self.create_room_types()
            self.stdout.write(self.style.SUCCESS(f'✓ Created {len(room_types)} room types'))
            
            # Create admins
            admins = self.create_admins()
            self.stdout.write(self.style.SUCCESS(f'✓ Created {len(admins)} admin users'))
            
            # Create apartments
            apartments = self.create_apartments(admins)
            self.stdout.write(self.style.SUCCESS(f'✓ Created {len(apartments)} apartments'))
            
            # Create rooms
            rooms = self.create_rooms(apartments, room_types)
            self.stdout.write(self.style.SUCCESS(f'✓ Created {len(rooms)} rooms'))
            
            # Create tenants
            tenants = self.create_tenants()
            self.stdout.write(self.style.SUCCESS(f'✓ Created {len(tenants)} tenant users'))
            
            # Create tenancies
            tenancies = self.create_tenancies(tenants, rooms, apartments)
            self.stdout.write(self.style.SUCCESS(f'✓ Created {len(tenancies)} tenancies'))
            
            # Create rent payments
            rent_payments = self.create_rent_payments(tenancies)
            self.stdout.write(self.style.SUCCESS(f'✓ Created {len(rent_payments)} rent payments'))
            
            # Create rent dues
            rent_dues = self.create_rent_dues(tenancies)
            self.stdout.write(self.style.SUCCESS(f'✓ Created {len(rent_dues)} rent dues'))
            
            # Create utility bills
            electricity_bills = self.create_electricity_bills(tenancies)
            water_bills = self.create_water_bills(tenancies)
            self.stdout.write(self.style.SUCCESS(f'✓ Created {len(electricity_bills)} electricity bills'))
            self.stdout.write(self.style.SUCCESS(f'✓ Created {len(water_bills)} water bills'))
            
            # Create notifications
            notifications = self.create_notifications(tenants, admins)
            self.stdout.write(self.style.SUCCESS(f'✓ Created {len(notifications)} notifications'))
        
        self.stdout.write(self.style.SUCCESS('\n🎉 Database seeding completed successfully!'))
        self.print_summary()

    def clear_data(self):
        """Clear all existing data"""
        Notification.objects.all().delete()
        WaterBill.objects.all().delete()
        ElectricityBill.objects.all().delete()
        RentDue.objects.all().delete()
        RentPayment.objects.all().delete()
        Tenancy.objects.all().delete()
        Room.objects.all().delete()
        Apartment.objects.all().delete()
        RoomType.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        self.stdout.write(self.style.SUCCESS('✓ Cleared existing data'))

    def create_room_types(self):
        """Create room types"""
        room_types_data = [
            ('bedsitter', 'Self-contained bedsitter with private bathroom'),
            ('single_room', 'Single room with shared amenities'),
            ('one_bedroom', 'One bedroom apartment with living room'),
            ('two_bedroom', 'Two bedroom apartment with living room'),
            ('three_bedroom', 'Three bedroom apartment with living room'),
        ]
        
        room_types = []
        for name, description in room_types_data:
            room_type, created = RoomType.objects.get_or_create(
                name=name,
                defaults={'description': description}
            )
            room_types.append(room_type)
        
        return room_types

    def create_admins(self):
        """Create admin users"""
        admins_data = [
            {
                'username': 'admin_kamau',
                'email': 'kamau@qwetu.co.ke',
                'first_name': 'James',
                'last_name': 'Kamau',
                'phone_number': '+254712345001',
                'national_id': '12345678'
            },
            {
                'username': 'admin_njeri',
                'email': 'njeri@qwetu.co.ke',
                'first_name': 'Mary',
                'last_name': 'Njeri',
                'phone_number': '+254723456001',
                'national_id': '23456789'
            },
        ]
        
        admins = []
        for admin_data in admins_data:
            admin, created = User.objects.get_or_create(
                username=admin_data['username'],
                defaults={
                    **admin_data,
                    'user_type': 'admin',
                    'user_status': 'active',
                    'is_staff': True,
                }
            )
            if created:
                admin.set_password('admin123')
                admin.save()
            admins.append(admin)
        
        return admins

    def create_apartments(self, admins):
        """Create apartments in various Nairobi locations"""
        apartments_data = [
            {
                'name': 'Sunrise Apartments',
                'location': 'Kilimani, Nairobi',
                'total_floors': 5,
                'description': 'Modern apartments in the heart of Kilimani with 24/7 security',
                'water_rate_per_unit': Decimal('50.00')
            },
            {
                'name': 'Madaraka View Court',
                'location': 'Madaraka, Nairobi',
                'total_floors': 4,
                'description': 'Affordable housing near SGR terminus',
                'water_rate_per_unit': Decimal('45.00')
            },
            {
                'name': 'Westlands Heights',
                'location': 'Westlands, Nairobi',
                'total_floors': 6,
                'description': 'Premium apartments with parking and gym facilities',
                'water_rate_per_unit': Decimal('60.00')
            },
            {
                'name': 'Embakasi Paradise',
                'location': 'Embakasi, Nairobi',
                'total_floors': 3,
                'description': 'Family-friendly apartments near major shopping centers',
                'water_rate_per_unit': Decimal('40.00')
            },
        ]
        
        apartments = []
        for i, apt_data in enumerate(apartments_data):
            apartment, created = Apartment.objects.get_or_create(
                name=apt_data['name'],
                defaults={
                    **apt_data,
                    'owner': admins[i % len(admins)]
                }
            )
            apartments.append(apartment)
        
        return apartments

    def create_rooms(self, apartments, room_types):
        """Create rooms for each apartment"""
        rooms = []
        
        # Room configurations for different types
        room_configs = {
            'bedsitter': {'rent_range': (8000, 15000), 'deposit_multiplier': 1},
            'single_room': {'rent_range': (5000, 10000), 'deposit_multiplier': 1},
            'one_bedroom': {'rent_range': (15000, 25000), 'deposit_multiplier': 1},
            'two_bedroom': {'rent_range': (25000, 40000), 'deposit_multiplier': 1},
            'three_bedroom': {'rent_range': (40000, 70000), 'deposit_multiplier': 1},
        }
        
        for apartment in apartments:
            room_counter = 1
            
            # Create mix of room types per apartment
            for floor in range(1, apartment.total_floors + 1):
                rooms_per_floor = random.randint(4, 8)
                
                for i in range(rooms_per_floor):
                    room_type = random.choice(room_types)
                    config = room_configs[room_type.name]
                    
                    monthly_rent = Decimal(random.randint(*config['rent_range']))
                    deposit = monthly_rent * config['deposit_multiplier']
                    
                    # Room number format: A1, A2, B1, B2, etc.
                    room_number = f"{chr(64 + floor)}{room_counter}"
                    room_counter += 1
                    
                    room = Room.objects.create(
                        apartment=apartment,
                        room_number=room_number,
                        room_type=room_type,
                        floor_number=floor,
                        has_balcony=random.choice([True, False]),
                        has_shower=True,
                        has_kitchen_unit=room_type.name != 'single_room',
                        has_clothes_cabinet=True,
                        monthly_rent=monthly_rent,
                        deposit_amount=deposit,
                        status=random.choice(['available', 'occupied', 'occupied', 'occupied'])  # More occupied
                    )
                    rooms.append(room)
        
        return rooms

    def create_tenants(self):
        """Create tenant users with Kenyan names"""
        kenyan_names = [
            ('John', 'Mwangi', '+254712345678', '34567890'),
            ('Grace', 'Achieng', '+254723456789', '45678901'),
            ('Peter', 'Ochieng', '+254734567890', '56789012'),
            ('Sarah', 'Wanjiku', '+254745678901', '67890123'),
            ('David', 'Kipchoge', '+254756789012', '78901234'),
            ('Faith', 'Nyambura', '+254767890123', '89012345'),
            ('Samuel', 'Otieno', '+254778901234', '90123456'),
            ('Jane', 'Wambui', '+254789012345', '01234567'),
            ('Michael', 'Kimani', '+254790123456', '12345670'),
            ('Lucy', 'Adhiambo', '+254701234567', '23456701'),
            ('Joseph', 'Mutua', '+254712345670', '34567012'),
            ('Ann', 'Chebet', '+254723456701', '45670123'),
            ('Daniel', 'Karanja', '+254734567012', '56701234'),
            ('Mercy', 'Wangari', '+254745670123', '67012345'),
            ('Brian', 'Omondi', '+254756701234', '70123456'),
            ('Christine', 'Njoki', '+254767012345', '01234568'),
            ('Edwin', 'Kiplagat', '+254770123456', '12345679'),
            ('Rose', 'Njeri', '+254701234568', '23456780'),
            ('Patrick', 'Kamau', '+254712345679', '34567891'),
            ('Elizabeth', 'Auma', '+254723456780', '45678902'),
        ]
        
        tenants = []
        for i, (first_name, last_name, phone, national_id) in enumerate(kenyan_names):
            username = f"{first_name.lower()}_{last_name.lower()}"
            email = f"{username}@gmail.com"
            
            tenant, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'phone_number': phone,
                    'national_id': national_id,
                    'user_type': 'tenant',
                    'user_status': 'active',
                }
            )
            if created:
                tenant.set_password('tenant123')
                tenant.save()
            tenants.append(tenant)
        
        return tenants

    def create_tenancies(self, tenants, rooms, apartments):
        """Create tenancies for occupied rooms"""
        occupied_rooms = [room for room in rooms if room.status == 'occupied']
        tenancies = []
        
        available_tenants = tenants.copy()
        random.shuffle(available_tenants)
        
        for i, room in enumerate(occupied_rooms):
            if i >= len(available_tenants):
                break
            
            tenant = available_tenants[i]
            
            # Random start date in the past (1-12 months ago)
            months_ago = random.randint(1, 12)
            start_date = date.today() - relativedelta(months=months_ago)
            
            tenancy = Tenancy.objects.create(
                tenant=tenant,
                room=room,
                apartment=room.apartment,
                start_date=start_date,
                deposit_paid=room.deposit_amount,
                status='active',
                move_in_condition='Good condition - all fixtures working properly',
            )
            tenancies.append(tenancy)
        
        # Create some past tenancies (moved out)
        for i in range(min(5, len(tenants) - len(occupied_rooms))):
            tenant = tenants[len(occupied_rooms) + i]
            room = random.choice(rooms)
            
            start_date = date.today() - relativedelta(months=random.randint(12, 24))
            end_date = date.today() - relativedelta(months=random.randint(1, 6))
            
            tenancy = Tenancy.objects.create(
                tenant=tenant,
                room=room,
                apartment=room.apartment,
                start_date=start_date,
                end_date=end_date,
                deposit_paid=room.deposit_amount,
                deposit_refunded=True,
                deposit_refund_amount=room.deposit_amount * Decimal('0.9'),  # 10% deduction
                deposit_deduction_reason='Minor wall repairs needed',
                status='terminated',
                termination_reason='vacated',
                move_in_condition='Good condition',
                move_out_condition='Minor wear and tear on walls',
            )
            tenancies.append(tenancy)
        
        return tenancies

    def create_rent_payments(self, tenancies):
        """Create rent payment history"""
        payments = []
        
        active_tenancies = [t for t in tenancies if t.status == 'active']
        
        for tenancy in active_tenancies:
            # Calculate months since tenancy started
            months_since_start = (date.today().year - tenancy.start_date.year) * 12 + \
                                (date.today().month - tenancy.start_date.month)
            
            # Create payments for each month
            for month_offset in range(months_since_start + 1):
                payment_month = tenancy.start_date + relativedelta(months=month_offset)
                
                # 80% chance of on-time payment
                if random.random() < 0.8:
                    # Random payment method
                    payment_method = random.choice(['mpesa', 'mpesa', 'mpesa', 'cash', 'bank_transfer'])
                    
                    # Some tenants pay multiple months in advance
                    months_covered = random.choices([1, 2, 3, 4, 6], weights=[70, 15, 8, 4, 3])[0]
                    
                    amount = tenancy.room.monthly_rent * months_covered
                    
                    # Payment date (usually early in the month)
                    payment_date = payment_month.replace(day=random.randint(1, 5))
                    
                    mpesa_id = None
                    mpesa_phone = None
                    if payment_method == 'mpesa':
                        mpesa_id = f"QA{random.randint(10000000, 99999999)}"
                        mpesa_phone = tenancy.tenant.phone_number
                    
                    payment = RentPayment.objects.create(
                        tenancy=tenancy,
                        tenant=tenancy.tenant,
                        apartment=tenancy.apartment,
                        amount=amount,
                        payment_date=payment_date,
                        payment_method=payment_method,
                        mpesa_transaction_id=mpesa_id,
                        mpesa_phone_number=mpesa_phone,
                        months_covered=months_covered,
                        payment_for_month=payment_month,
                        status='completed',
                        is_late_payment=False,
                    )
                    payments.append(payment)
        
        return payments

    def create_rent_dues(self, tenancies):
        """Create rent due records"""
        dues = []
        
        active_tenancies = [t for t in tenancies if t.status == 'active']
        
        for tenancy in active_tenancies:
            # Calculate months since tenancy started
            months_since_start = (date.today().year - tenancy.start_date.year) * 12 + \
                                (date.today().month - tenancy.start_date.month)
            
            # Create dues for each month
            for month_offset in range(months_since_start + 2):  # Include next month
                month_for = tenancy.start_date + relativedelta(months=month_offset)
                due_date = month_for.replace(day=3)
                
                # Check if payment exists
                payment = RentPayment.objects.filter(
                    tenancy=tenancy,
                    payment_for_month=month_for,
                    status='completed'
                ).first()
                
                amount_due = tenancy.room.monthly_rent
                amount_paid = payment.amount if payment else Decimal('0.00')
                balance = amount_due - amount_paid
                
                if balance <= 0:
                    status = 'paid'
                elif amount_paid > 0:
                    status = 'partially_paid'
                elif due_date < date.today():
                    status = 'overdue'
                else:
                    status = 'unpaid'
                
                due = RentDue.objects.create(
                    tenancy=tenancy,
                    tenant=tenancy.tenant,
                    due_date=due_date,
                    month_for=month_for,
                    amount_due=amount_due,
                    amount_paid=amount_paid,
                    balance=balance,
                    status=status,
                )
                dues.append(due)
        
        return dues

    def create_electricity_bills(self, tenancies):
        """Create electricity bills"""
        bills = []
        
        active_tenancies = [t for t in tenancies if t.status == 'active']
        
        for tenancy in active_tenancies:
            # Create bills for last 3 months
            for i in range(3):
                bill_month = date.today() - relativedelta(months=i)
                bill_month = bill_month.replace(day=1)
                
                units = Decimal(random.randint(50, 200))
                amount = units * Decimal('20.00')  # KSH 20 per unit
                
                bill = ElectricityBill.objects.create(
                    tenancy=tenancy,
                    bill_month=bill_month,
                    token_number=f"TOKEN{random.randint(1000000000, 9999999999)}",
                    units_purchased=units,
                    amount=amount,
                    purchase_date=bill_month + timedelta(days=random.randint(1, 15)),
                    status='paid',
                )
                bills.append(bill)
        
        return bills

    def create_water_bills(self, tenancies):
        """Create water bills"""
        bills = []
        
        active_tenancies = [t for t in tenancies if t.status == 'active']
        
        for tenancy in active_tenancies:
            previous_reading = Decimal('0.00')
            
            # Create bills for last 3 months
            for i in range(2, -1, -1):
                bill_month = date.today() - relativedelta(months=i)
                bill_month = bill_month.replace(day=1)
                
                units_consumed = Decimal(random.randint(5, 20))
                current_reading = previous_reading + units_consumed
                
                rate = tenancy.apartment.water_rate_per_unit
                total_amount = units_consumed * rate
                
                due_date = bill_month.replace(day=28)
                payment_date = None
                status = 'pending'
                
                # 70% chance bill is paid
                if random.random() < 0.7 or i > 0:
                    payment_date = due_date + timedelta(days=random.randint(1, 5))
                    status = 'paid'
                elif bill_month < date.today().replace(day=1):
                    status = 'overdue'
                
                bill = WaterBill.objects.create(
                    tenancy=tenancy,
                    bill_month=bill_month,
                    units_consumed=units_consumed,
                    rate_per_unit=rate,
                    total_amount=total_amount,
                    previous_reading=previous_reading,
                    current_reading=current_reading,
                    due_date=due_date,
                    payment_date=payment_date,
                    status=status,
                )
                bills.append(bill)
                
                previous_reading = current_reading
        
        return bills

    def create_notifications(self, tenants, admins):
        """Create sample notifications"""
        notifications = []
        
        notification_templates = [
            ('rent_due', 'Rent Payment Due', 'Your rent for {} is due on the 3rd. Please make payment to avoid late fees.'),
            ('payment_received', 'Payment Received', 'We have received your payment of KES {} for {}. Thank you!'),
            ('water_bill', 'Water Bill Generated', 'Your water bill for {} is KES {}. Please settle by end of month.'),
            ('general', 'Welcome to Qwetu', 'Welcome to Qwetu Rental Management System. We\'re glad to have you!'),
        ]
        
        # Create notifications for some tenants
        for tenant in random.sample(tenants, min(10, len(tenants))):
            template = random.choice(notification_templates)
            
            notification = Notification.objects.create(
                user=tenant,
                notification_type=template[0],
                title=template[1],
                message=template[2].format('November 2025', 'KES 15,000'),
                is_read=random.choice([True, False]),
            )
            notifications.append(notification)
        
        # Create notifications for admins
        for admin in admins:
            notification = Notification.objects.create(
                user=admin,
                notification_type='general',
                title='New Tenant Registered',
                message='A new tenant has registered in your apartment. Please review their application.',
                is_read=random.choice([True, False]),
            )
            notifications.append(notification)
        
        return notifications

    def print_summary(self):
        """Print summary of seeded data"""
        self.stdout.write(self.style.SUCCESS('\n' + '='*50))
        self.stdout.write(self.style.SUCCESS('DATABASE SUMMARY'))
        self.stdout.write(self.style.SUCCESS('='*50))
        self.stdout.write(f"Admins: {User.objects.filter(user_type='admin').count()}")
        self.stdout.write(f"Tenants: {User.objects.filter(user_type='tenant').count()}")
        self.stdout.write(f"Apartments: {Apartment.objects.count()}")
        self.stdout.write(f"Rooms: {Room.objects.count()}")
        self.stdout.write(f"  - Available: {Room.objects.filter(status='available').count()}")
        self.stdout.write(f"  - Occupied: {Room.objects.filter(status='occupied').count()}")
        self.stdout.write(f"Active Tenancies: {Tenancy.objects.filter(status='active').count()}")
        self.stdout.write(f"Rent Payments: {RentPayment.objects.count()}")
        self.stdout.write(f"Rent Dues: {RentDue.objects.count()}")
        self.stdout.write(f"Electricity Bills: {ElectricityBill.objects.count()}")
        self.stdout.write(f"Water Bills: {WaterBill.objects.count()}")
        self.stdout.write(f"Notifications: {Notification.objects.count()}")
        self.stdout.write(self.style.SUCCESS('='*50))
        self.stdout.write(self.style.SUCCESS('\nLOGIN CREDENTIALS'))
        self.stdout.write(self.style.SUCCESS('='*50))
        self.stdout.write('Admin: admin_kamau / admin123')
        self.stdout.write('Admin: admin_njeri / admin123')
        self.stdout.write('Tenant: john_mwangi / tenant123')
        self.stdout.write('(All tenants use password: tenant123)')
        self.stdout.write(self.style.SUCCESS('='*50 + '\n'))