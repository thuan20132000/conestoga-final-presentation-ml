from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from business.models import Business, BusinessType
from client.models import Client
from gift.models import GiftCard
from payment.models import Payment, PaymentMethod, PaymentMethodType, PaymentStatusType


@override_settings(
    STRIPE_SECRET_KEY="sk_test",
    STRIPE_WEBHOOK_SECRET="whsec_test",
    STRIPE_PUBLISHABLE_KEY="pk_test",
)
class GiftCardStripePaymentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.business_type = BusinessType.objects.create(name="Salon")
        self.business = Business.objects.create(
            name="Test Business",
            business_type=self.business_type,
            currency="USD",
        )
        self.purchaser = Client.objects.create(
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            primary_business=self.business,
        )
        self.payment_method = PaymentMethod.objects.create(
            business=self.business,
            name="Stripe",
            payment_type=PaymentMethodType.ONLINE,
            is_active=True,
            is_default=True,
            processing_fee_percentage=Decimal("0.00"),
            processing_fee_fixed=Decimal("0.00"),
        )

    @patch("payment.stripe_service.stripe.PaymentIntent.create")
    def test_create_online_payment_intent(self, mock_create):
        mock_intent = MagicMock()
        mock_intent.id = "pi_test_123"
        mock_intent.client_secret = "secret_123"
        mock_intent.status = "requires_payment_method"
        mock_create.return_value = mock_intent

        response = self.client.post(
            "/api/online-payment-intent/",
            data={
                "business": str(self.business.id),
                "purchaser": self.purchaser.id,
                "initial_amount": "25.00",
                "currency": "USD",
                "recipient_name": "John Doe",
                "recipient_email": "john.doe@example.com",
                "recipient_phone": "+1234567890",
                "message": "Happy birthday!",
                "notes": "Gift card for John Doe",
            },
            format="json",
        )
        print("response:: ", response)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["payment_intent_id"], "pi_test_123")
        self.assertEqual(response.data["client_secret"], "secret_123")

        payment = Payment.objects.get(id=response.data["payment_id"])
        self.assertEqual(payment.status, PaymentStatusType.PENDING)
        self.assertEqual(payment.external_transaction_id, "pi_test_123")
        self.assertEqual(payment.payment_method, self.payment_method)

    @patch("payment.stripe_service.stripe.Webhook.construct_event")
    def test_stripe_webhook_creates_gift_card(self, mock_construct_event):
        payment = Payment.objects.create(
            business=self.business,
            client=self.purchaser,
            amount=Decimal("30.00"),
            currency="USD",
            payment_method=self.payment_method,
            payment_method_type=PaymentMethodType.ONLINE,
            status=PaymentStatusType.PENDING,
            external_transaction_id="pi_test_456",
        )

        mock_construct_event.return_value = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_test_456",
                    "amount": 3000,
                    "currency": "usd",
                    "status": "succeeded",
                    "metadata": {
                        "business_id": str(self.business.id),
                        "payment_id": str(payment.id),
                        "initial_amount": "30.00",
                        "currency": "USD",
                    },
                }
            },
        }

        response = self.client.post(
            "/api/gift-cards/stripe/webhook/",
            data="{}",
            content_type="application/json",
            **{"HTTP_STRIPE_SIGNATURE": "sig_test"},
        )

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatusType.COMPLETED)
        self.assertTrue(GiftCard.objects.filter(payment=payment).exists())
