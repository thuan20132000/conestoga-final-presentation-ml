# Payment Management System

A comprehensive payment management system for the BookNgon AI appointment booking platform. This system handles all aspects of payment processing, tracking, and management for appointments and services.

## Features

### Core Functionality
- **Payment Processing**: Handle various payment methods (cash, credit card, debit card, online payments, etc.)
- **Payment Tracking**: Complete audit trail with transaction history
- **Refund Management**: Full and partial refunds with proper tracking
- **Split Payments**: Support for splitting payments across multiple payment methods
- **Payment Status Management**: Track payment lifecycle from pending to completed
- **Processing Fee Calculation**: Automatic calculation of processing fees per payment method
- **Payment Gateway Integration**: Support for multiple payment gateways
- **Business-Specific Configuration**: Each business can configure its own payment methods and gateways

### Advanced Features
- **Dashboard Statistics**: Comprehensive payment analytics and reporting
- **Transaction History**: Detailed audit trail for all payment activities
- **Admin Interface**: Full Django admin integration for payment management
- **API Endpoints**: RESTful API for all payment operations
- **Management Commands**: CLI tools for payment administration and maintenance

## Models

### PaymentStatus
Defines the various states a payment can be in:
- `pending` - Payment is pending processing
- `processing` - Payment is being processed
- `completed` - Payment completed successfully
- `failed` - Payment processing failed
- `cancelled` - Payment was cancelled
- `refunded` - Payment fully refunded
- `partially_refunded` - Payment partially refunded
- `chargeback` - Payment charged back

### PaymentMethod
Configures payment methods for each business:
- Payment type (cash, credit card, debit card, etc.)
- Processing fee configuration (percentage and/or fixed amount)
- Active/inactive status
- Default payment method designation

### Payment
Main payment model containing:
- Payment details (amount, currency, transaction type)
- Related entities (business, client, appointment)
- Payment method and status
- External transaction ID and gateway response
- Processing fees and net amount calculation
- Audit timestamps and staff tracking

### PaymentSplit
Handles split payments across multiple payment methods:
- Individual amounts per payment method
- Processing fees per split
- Individual status tracking
- External transaction IDs per split

### Refund
Manages refund operations:
- Refund type (full, partial, chargeback)
- Refund reason tracking
- Amount and status management
- Staff tracking for audit purposes

### PaymentTransaction
Provides detailed transaction history:
- Event type tracking (payment initiated, processed, completed, etc.)
- Status change tracking
- Metadata and descriptions
- Staff attribution

### PaymentGateway
Configures payment gateway integrations:
- Gateway type (Stripe, PayPal, Square, etc.)
- API credentials and configuration
- Capability flags (refunds, partial refunds, recurring)
- Test/production mode settings

## API Endpoints

### Payment Methods
- `GET /api/payment/payment-methods/` - List payment methods
- `POST /api/payment/payment-methods/` - Create payment method
- `GET /api/payment/payment-methods/{id}/` - Get payment method details
- `PUT/PATCH /api/payment/payment-methods/{id}/` - Update payment method
- `DELETE /api/payment/payment-methods/{id}/` - Delete payment method
- `POST /api/payment/payment-methods/set_default/` - Set default payment method

### Payment Statuses
- `GET /api/payment/payment-statuses/` - List payment statuses (read-only)

### Payment Gateways
- `GET /api/payment/payment-gateways/` - List payment gateways
- `POST /api/payment/payment-gateways/` - Create payment gateway
- `GET /api/payment/payment-gateways/{id}/` - Get payment gateway details
- `PUT/PATCH /api/payment/payment-gateways/{id}/` - Update payment gateway
- `DELETE /api/payment/payment-gateways/{id}/` - Delete payment gateway

### Payments
- `GET /api/payment/payments/` - List payments with filtering and search
- `POST /api/payment/payments/` - Create new payment
- `GET /api/payment/payments/{id}/` - Get payment details
- `PUT/PATCH /api/payment/payments/{id}/` - Update payment
- `DELETE /api/payment/payments/{id}/` - Delete payment
- `GET /api/payment/payments/dashboard_stats/` - Get payment statistics
- `POST /api/payment/payments/{id}/process_payment/` - Process payment
- `POST /api/payment/payments/{id}/fail_payment/` - Mark payment as failed

### Payment Splits
- `GET /api/payment/payment-splits/` - List payment splits
- `POST /api/payment/payment-splits/` - Create payment split
- `GET /api/payment/payment-splits/{id}/` - Get payment split details
- `PUT/PATCH /api/payment/payment-splits/{id}/` - Update payment split
- `DELETE /api/payment/payment-splits/{id}/` - Delete payment split

### Refunds
- `GET /api/payment/refunds/` - List refunds
- `POST /api/payment/refunds/` - Create refund
- `GET /api/payment/refunds/{id}/` - Get refund details
- `PUT/PATCH /api/payment/refunds/{id}/` - Update refund
- `DELETE /api/payment/refunds/{id}/` - Delete refund
- `POST /api/payment/refunds/{id}/process_refund/` - Process refund

### Payment Transactions
- `GET /api/payment/payment-transactions/` - List payment transactions (read-only)
- `GET /api/payment/payment-transactions/{id}/` - Get transaction details (read-only)

## Filtering and Search

### Payment Filters
- `date_from` / `date_to` - Filter by date range
- `amount_min` / `amount_max` - Filter by amount range
- `status_name` - Filter by payment status
- `transaction_type` - Filter by transaction type
- `business_id` - Filter by business
- `client_id` - Filter by client
- `appointment_id` - Filter by appointment
- `payment_method_id` - Filter by payment method
- `is_completed` / `is_pending` / `is_failed` / `is_refunded` - Boolean filters
- `search` - Search across payment ID, client name, transaction ID, service name

### Payment Method Filters
- `payment_type` - Filter by payment type
- `is_active` - Filter by active status
- `is_default` - Filter by default status
- `business_id` - Filter by business

### Refund Filters
- `date_from` / `date_to` - Filter by date range
- `amount_min` / `amount_max` - Filter by amount range
- `refund_type` - Filter by refund type
- `refund_reason` - Filter by refund reason
- `status_name` - Filter by status
- `payment_id` - Filter by payment
- `business_id` - Filter by business
- `client_id` - Filter by client

## Management Commands

### create_payment_statuses
Creates default payment statuses in the system.
```bash
python manage.py create_payment_statuses
```

### create_sample_payment_methods
Creates sample payment methods for businesses.
```bash
python manage.py create_sample_payment_methods [--business-id BUSINESS_ID]
```

### payment_stats
Displays payment statistics and analytics.
```bash
python manage.py payment_stats [--business-id BUSINESS_ID] [--days DAYS]
```

### cleanup_payments
Cleans up old failed and pending payments.
```bash
python manage.py cleanup_payments [--days DAYS] [--dry-run]
```

## Usage Examples

### Creating a Payment
```python
from payment.models import Payment, PaymentStatus, PaymentMethod
from business.models import Business
from client.models import Client
from appointment.models import Appointment

# Get required objects
business = Business.objects.get(id=1)
client = Client.objects.get(id=1)
appointment = Appointment.objects.get(id=1)
payment_method = PaymentMethod.objects.filter(business=business).first()
pending_status = PaymentStatus.objects.get(name='pending')

# Create payment
payment = Payment.objects.create(
    business=business,
    client=client,
    appointment=appointment,
    amount=50.00,
    currency='CAD',
    payment_method=payment_method,
    status=pending_status,
    transaction_type='payment'
)
```

### Processing a Payment
```python
# Process the payment
payment.external_transaction_id = f"txn_{timezone.now().timestamp()}"
payment.gateway_response = {
    'status': 'success',
    'transaction_id': payment.external_transaction_id,
    'processed_at': timezone.now().isoformat()
}

completed_status = PaymentStatus.objects.get(name='completed')
payment.status = completed_status
payment.save()
```

### Creating a Refund
```python
from payment.models import Refund

refund = Refund.objects.create(
    payment=payment,
    refund_type='full',
    refund_reason='client_request',
    amount=50.00,
    status=PaymentStatus.objects.get(name='pending')
)
```

### Dashboard Statistics
```python
from payment.models import Payment
from django.db.models import Sum, Count

# Get payment statistics
stats = Payment.objects.filter(
    business_id=1,
    created_at__date__gte=date_from
).aggregate(
    total_payments=Count('id'),
    total_amount=Sum('amount'),
    total_fees=Sum('processing_fee'),
    net_amount=Sum('net_amount')
)
```

## Admin Interface

The payment system includes a comprehensive Django admin interface with:

- **Payment Management**: View, edit, and manage all payments with detailed information
- **Payment Method Configuration**: Configure payment methods for each business
- **Refund Management**: Process and track refunds
- **Transaction History**: View detailed transaction logs
- **Status Management**: Manage payment statuses and their display properties
- **Gateway Configuration**: Configure payment gateways and their settings

### Admin Features
- Color-coded status displays
- Inline editing for related objects
- Advanced filtering and search
- Bulk operations
- Export capabilities
- Detailed audit trails

## Integration with Existing Systems

### Appointment Integration
- Payments are linked to appointments
- Automatic price calculation from appointment services
- Payment status affects appointment completion
- Integration with appointment booking flow

### Business Integration
- Each business has its own payment methods and gateways
- Business-specific processing fee configurations
- Multi-tenant payment processing

### Client Integration
- Payment history per client
- Client-specific payment preferences
- Integration with client management system

### Staff Integration
- Staff can process payments
- Audit trail for staff actions
- Permission-based payment processing

## Security Considerations

- External transaction IDs are stored for audit purposes
- Gateway responses are stored as JSON for debugging
- Processing fees are calculated automatically
- All payment actions are logged with timestamps
- Staff attribution for all payment operations
- Secure handling of payment gateway credentials

## Future Enhancements

- **Recurring Payments**: Support for subscription-based services
- **Payment Plans**: Installment payment options
- **Advanced Analytics**: More detailed reporting and analytics
- **Mobile Payments**: Integration with mobile payment systems
- **International Payments**: Multi-currency support
- **Fraud Detection**: Basic fraud detection and prevention
- **Webhook Support**: Real-time payment status updates

## Dependencies

- Django 5.2+
- Django REST Framework
- django-filter
- Python 3.11+

## Installation

1. The payment app is already included in `INSTALLED_APPS`
2. Run migrations: `python manage.py migrate`
3. Create payment statuses: `python manage.py create_payment_statuses`
4. Create sample payment methods: `python manage.py create_sample_payment_methods`

## Support

For issues or questions regarding the payment management system, please refer to the main project documentation or contact the development team.
