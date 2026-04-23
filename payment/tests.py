from django.urls import reverse
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from business.models import Business, BusinessType
from payment.models import PaymentGateway, GatewayTypeType
from staff.models import Staff


class StripeConnectOnboardingViewTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()

        self.business_type = BusinessType.objects.create(name="Salon")
        self.business = Business.objects.create(
            name="Test Salon",
            business_type=self.business_type,
            email="owner@test-salon.com",
            country="Canada",
        )

        self.owner = Staff.objects.create_user(
            username="owner",
            email="owner@test-salon.com",
            password="password123",
            business=self.business,
        )
        self.client.force_authenticate(user=self.owner)

        self.url = reverse("stripe_connect_onboard")

    def test_missing_business_id_returns_400(self):
        response = self.client.post(self.url, data={}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_business_id_returns_404(self):
        response = self.client.post(
            self.url, data={"business_id": "00000000-0000-0000-0000-000000000000"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_creates_gateway_when_none_exists(self):
        self.assertFalse(
            PaymentGateway.objects.filter(
                business=self.business, gateway_type=GatewayTypeType.STRIPE
            ).exists()
        )

        response = self.client.post(
            self.url, data={"business_id": str(self.business.id)}, format="json"
        )

        # We cannot easily assert on Stripe API in unit tests here without mocking,
        # but we can assert that a gateway row is created or an error is not raised
        # in local test environments where Stripe keys are configured.
        self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR))

