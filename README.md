# Qwetu Rental Management System

A comprehensive Django-based rental management system designed for Kenyan apartment owners and tenants. Qwetu enables efficient property management with support for multiple payment options, room switching, and complete tenant history tracking.

## 🏢 Overview

Qwetu is a full-featured rental management platform that allows:
- **Apartment Owners/Admins**: Manage multiple apartments, track payments, monitor occupancy, and handle tenant requests
- **Tenants**: Pay rent in advance (1-9 months), view payment history, switch rooms, and report payment issues

## ✨ Key Features

### For Admins
- 🏗️ **Multi-Apartment Management**: Manage multiple buildings from one dashboard
- 🏠 **Room Management**: Track different room types (bedsitter, single room, 1-bedroom, 2-bedroom, 3-bedroom)
- 💰 **Payment Tracking**: Monitor all rent payments, water bills, and electricity usage
- 📊 **Financial Reports**: View payment history, outstanding balances, and revenue analytics
- 👥 **Tenant Management**: Complete tenant profiles with full history retention
- 🔔 **Notifications**: Automated alerts for due payments, late payments, and tenant reports

### For Tenants
- 💳 **M-Pesa Integration**: Pay rent using M-Pesa STK Push
- 📅 **Advance Payments**: Pay rent for multiple months in advance (1-9 months)
- 🔄 **Room Switching**: Transfer to different rooms while maintaining payment history
- 📱 **Payment History**: View complete payment records and receipts
- ⚡ **Electricity Tracking**: Token-based electricity monitoring
- 💧 **Water Bills**: Monthly water consumption tracking
- 📝 **Payment Reports**: Report inability to pay by the due date (3rd of each month)

## 🗂️ System Architecture

### Core Models

#### User Management
- **User**: Custom user model supporting both admins and tenants
  - Soft delete support (data never lost)
  - User status tracking (active, inactive, archived)
  - Profile management with photos and documents

#### Property Management
- **Apartment**: Building/property information
- **RoomType**: Room categories with descriptions
- **Room**: Individual units with unique identifiers (e.g., A1, B2, C3)
  - Floor number tracking
  - Features: balcony, shower, kitchen unit, clothes cabinet
  - Pricing: monthly rent and deposit amounts

#### Tenancy Management
- **Tenancy**: Tenant-room relationships
  - Room switching support with linked tenancies
  - Deposit management (paid, refunded, deductions)
  - Move-in/move-out condition tracking
  - Termination reasons
  - Soft delete (history preserved)

#### Financial Management
- **RentPayment**: All rent transactions
  - M-Pesa transaction tracking
  - Multi-month payment support
  - Late payment fees
  - Complete payment history retention
  
- **RentDue**: Monthly rent obligations
  - Due date tracking (3rd of each month)
  - Payment status monitoring
  - Balance calculations
  - Office reporting for payment issues

- **ElectricityBill**: Token-based electricity tracking
- **WaterBill**: Monthly water consumption and billing

#### Communication
- **PaymentReport**: Tenant reports for payment difficulties
- **Notification**: System-wide notification management

## 🚀 Getting Started

### Prerequisites
```bash
Python 3.8+
Django 4.2+
PostgreSQL 12+ (recommended) or SQLite for development
```

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/qwetu.git
cd qwetu
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
Create a `.env` file in the project root:
```env
SECRET_KEY=your-secret-key-here
DEBUG=True
DATABASE_URL=postgresql://user:password@localhost:5432/qwetu_db

# M-Pesa Configuration
MPESA_CONSUMER_KEY=your-consumer-key
MPESA_CONSUMER_SECRET=your-consumer-secret
MPESA_SHORTCODE=your-shortcode
MPESA_PASSKEY=your-passkey
MPESA_CALLBACK_URL=https://yourdomain.com/api/mpesa/callback/
```

5. **Run migrations**
```bash
python manage.py makemigrations
python manage.py migrate
```

6. **Create superuser**
```bash
python manage.py createsuperuser
```

7. **Load initial data (optional)**
```bash
python manage.py loaddata initial_room_types.json
```

8. **Run development server**
```bash
python manage.py runserver
```

Visit `http://localhost:8000` to access the application.

## 📋 Usage Examples

### Creating an Apartment
```python
from qwetu.models import Apartment, User

admin = User.objects.get(email='admin@example.com')
apartment = Apartment.objects.create(
    name='Sunrise Apartments',
    owner=admin,
    location='Nairobi, Kenya',
    total_floors=5,
    water_rate_per_unit=50.00
)
```

### Adding Rooms
```python
from qwetu.models import Room, RoomType

room_type = RoomType.objects.get(name='bedsitter')
room = Room.objects.create(
    apartment=apartment,
    room_number='A1',
    room_type=room_type,
    floor_number=1,
    has_balcony=True,
    has_shower=True,
    has_kitchen_unit=True,
    has_clothes_cabinet=True,
    monthly_rent=15000.00,
    deposit_amount=15000.00,
    status='available'
)
```

### Creating a Tenancy
```python
from qwetu.models import Tenancy
from datetime import date

tenancy = Tenancy.objects.create(
    tenant=tenant_user,
    room=room,
    apartment=apartment,
    start_date=date.today(),
    deposit_paid=15000.00,
    status='active'
)
```

### Recording Rent Payment (Multiple Months)
```python
from qwetu.models import RentPayment
from datetime import date

payment = RentPayment.objects.create(
    tenancy=tenancy,
    tenant=tenant_user,
    apartment=apartment,
    amount=45000.00,  # 3 months
    payment_method='mpesa',
    mpesa_transaction_id='QA12XYZ789',
    months_covered=3,
    payment_for_month=date(2025, 11, 1),
    status='completed'
)
```

### Switching Rooms
```python
from datetime import date

# End current tenancy
old_tenancy = Tenancy.objects.get(tenant=tenant_user, status='active')
old_tenancy.end_date = date.today()
old_tenancy.status = 'switched'
old_tenancy.termination_reason = 'room_switch'
old_tenancy.save()

# Create new tenancy
new_room = Room.objects.get(room_number='B5')
new_tenancy = Tenancy.objects.create(
    tenant=tenant_user,
    room=new_room,
    apartment=apartment,
    start_date=date.today(),
    deposit_paid=0,  # Deposit transferred from old room
    status='active',
    switched_from_tenancy=old_tenancy
)

# Link tenancies
old_tenancy.switched_to_tenancy = new_tenancy
old_tenancy.save()
```

## 🔒 Data Retention Policy

**Qwetu uses a soft-delete approach - NO DATA IS EVER PERMANENTLY DELETED**

- Tenant accounts are marked as "archived" when they move out
- Tenancy records are preserved with end dates
- Payment history is maintained indefinitely
- Room switch history is tracked with linked tenancies
- All financial records are retained for audit purposes

## 📊 Database Indexes

Optimized indexes for common queries:
- Tenant payment history lookup
- Apartment payment reports
- Active tenancy queries
- Due date and status filtering

## 🔐 Security Considerations

- All sensitive data encrypted at rest
- User passwords hashed using Django's built-in authentication
- M-Pesa transactions validated with callbacks
- Role-based access control (Admin vs Tenant)
- Soft delete prevents data loss from accidental deletions

## 🧪 Testing

Run the test suite:
```bash
python manage.py test
```

Run with coverage:
```bash
coverage run --source='.' manage.py test
coverage report
```

## 📱 API Documentation

API endpoints documentation available at `/api/docs/` when running the server.

Key endpoints:
- `/api/auth/login/` - User authentication
- `/api/rooms/` - Room listing and availability
- `/api/payments/` - Payment processing and history
- `/api/tenancies/` - Tenancy management
- `/api/mpesa/stk-push/` - M-Pesa payment initiation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👥 Authors

- Your Name - Initial work

## 🙏 Acknowledgments

- Django framework
- M-Pesa Daraja API
- Kenyan rental management best practices

## 📞 Support

For support, email support@qwetu.co.ke or create an issue in the repository.

## 🗺️ Roadmap

- [ ] SMS notifications integration
- [ ] Bulk payment import
- [ ] Maintenance request system
- [ ] Visitor management
- [ ] Document management (lease agreements)
- [ ] Mobile app (Android/iOS)
- [ ] Multi-language support (English, Swahili)
- [ ] Analytics dashboard
- [ ] Automated rent reminders
- [ ] Tenant portal improvements

---

Built with Love for Kenyan property managers and tenants