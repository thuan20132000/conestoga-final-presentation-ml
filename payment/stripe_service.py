from __future__ import annotations

from typing import Any, Optional, Tuple

import stripe
from django.conf import settings

from payment.models import PaymentGateway, GatewayTypeType

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

STRIPE_APPLICATION_FEE_PERCENTAGE = 0.05

class StripeService:
    def __init__(self, business_id: Optional[int] = None) -> None:
        self.business_id = business_id
        self.api_key, self.webhook_secret, self.merchant_id = self._resolve_keys(business_id)
        if not self.api_key:
            raise ValueError("Stripe API key is not configured")
        stripe.api_key = self.api_key

    def _resolve_keys(self, business_id: Optional[int]) -> Tuple[str, str, Optional[str]]:
        """
        Resolve API key, webhook secret, and optional connected account ID (merchant_id)
        for the given business. When business_id is None, only platform-level keys are used.
        """
        merchant_id: Optional[str] = None
        if business_id:
            gateway = (
                PaymentGateway.objects.filter(
                    business_id=business_id,
                    gateway_type=GatewayTypeType.STRIPE,
                    is_active=True,
                )
                .order_by("-is_default", "name")
                .first()
            )
            if gateway and gateway.is_active:
                merchant_id = gateway.merchant_id
        return settings.STRIPE_SECRET_KEY, settings.STRIPE_WEBHOOK_SECRET, merchant_id

    def _calculate_application_fee_amount(self, amount_cents: int) -> int:
        return int(amount_cents * STRIPE_APPLICATION_FEE_PERCENTAGE)
    
    def create_payment_intent(
        self,
        amount_cents: int,
        currency: str,
        metadata: dict[str, str],
        description: str,
    ) -> Any:
        params: dict[str, Any] = {
            "amount": amount_cents,
            "currency": currency,
            "metadata": metadata,
            "description": description,
            "automatic_payment_methods": {"enabled": True},
        }

        # If this business has a connected account (Stripe Connect), create a
        # destination charge so funds go directly to the salon's account and
        # the platform keeps an application fee.
        if self.merchant_id:
            params["application_fee_amount"] = self._calculate_application_fee_amount(
                amount_cents
            )
            params["transfer_data"] = {"destination": self.merchant_id}

        return stripe.PaymentIntent.create(**params)

    # -------- Stripe Connect helpers --------

    @staticmethod
    def _configure_platform_key() -> None:
        if not settings.STRIPE_SECRET_KEY:
            raise ValueError("Stripe API key is not configured")
        stripe.api_key = settings.STRIPE_SECRET_KEY

    @staticmethod
    def create_connect_account(
        business_id: Any,
        email: Optional[str] = None,
        country: Optional[str] = None,
    ) -> stripe.Account:
        """
        Create a Stripe Express Connect account for a business using the
        platform secret key. The returned account.id should be stored as
        PaymentGateway.merchant_id.
        """
        StripeService._configure_platform_key()

        account_country = country or "CA"

        return stripe.Account.create(
            type="express",
            country=account_country,
            email=email,
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True},
            },
            metadata={
                "business_id": str(business_id),
            },
        )

    @staticmethod
    def create_account_link(
        account_id: str,
        refresh_url: str,
        return_url: str,
    ) -> stripe.AccountLink:
        """
        Create an onboarding Account Link for a given connected account.
        The caller should redirect the user to account_link.url.
        """
        StripeService._configure_platform_key()

        return stripe.AccountLink.create(
            account=account_id,
            refresh_url=refresh_url,
            return_url=return_url,
            type="account_onboarding",
        )

    def construct_event(self, payload: bytes, signature: str) -> Any:
        if not self.webhook_secret:
            raise ValueError("Stripe webhook secret is not configured")
        return stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=self.webhook_secret,
        )

    def retrieve_payment_intent(self, payment_intent_id: str) -> stripe.PaymentIntent:
        return stripe.PaymentIntent.retrieve(payment_intent_id)

    def retrieve_checkout_session(self, checkout_session_id: str) -> stripe.checkout.Session:
        try:
            response = stripe.checkout.Session.retrieve(checkout_session_id)
            return response
        except Exception as e:
            logger.error("error retrieving Stripe checkout session:: %s", e)
            raise e
    
    def create_customer(self, email: str, name: str, metadata: dict) -> stripe.Customer:
        return stripe.Customer.create(email=email, name=name, metadata=metadata)

    def retrieve_subscription(self, subscription_id: str) -> stripe.Subscription:
        return stripe.Subscription.retrieve(subscription_id)

    def create_subscription_checkout_session(
        self,
        price_id: str,
        success_url: str,
        cancel_url: str,
        customer_email: str = '',
        customer_id: str = None,
        business_id: int = None,
        trial_days: int = 0,
        metadata: dict = None,
    ) -> stripe.checkout.Session:
        metadata = metadata or {}
        params: dict = {
            'mode': 'subscription',
            'line_items': [{'price': price_id, 'quantity': 1}],
            'success_url': success_url,
            'cancel_url': cancel_url,
            'allow_promotion_codes': True,
            'client_reference_id': business_id,
            'metadata': metadata,
            'subscription_data': {'metadata': metadata},
            
        }
        if customer_id:
            params['customer'] = customer_id
        elif customer_email:
            params['customer_email'] = customer_email
        if trial_days > 0:
            params['subscription_data']['trial_period_days'] = trial_days
        return stripe.checkout.Session.create(**params)

    def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> stripe.Subscription:
        if at_period_end:
            return stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
        return stripe.Subscription.cancel(subscription_id)

    def change_subscription_plan(self, subscription_id: str, new_price_id: str) -> stripe.Subscription:
        subscription = stripe.Subscription.retrieve(subscription_id)
        item_id = subscription['items']['data'][0]['id']
        return stripe.Subscription.modify(
            subscription_id,
            items=[{'id': item_id, 'price': new_price_id}],
            proration_behavior='always_invoice',
        )

    def create_stripe_product(self, name: str, description: str) -> stripe.Product:
        return stripe.Product.create(name=name, description=description)

    def create_stripe_price(
        self,
        product_id: str,
        amount_cents: int,
        currency: str,
        interval: str,
        interval_count: int,
    ) -> stripe.Price:
        return stripe.Price.create(
            product=product_id,
            unit_amount=amount_cents,
            currency=currency,
            recurring={'interval': interval, 'interval_count': interval_count},
        )

    def create_checkout_session(
        self,
        amount_cents: int,
        currency: str,
        metadata: dict[str, str],
        description: str,
        success_url: str,
        cancel_url: str,
    ) -> stripe.Checkout.Session:
        try:
            application_fee_amount = self._calculate_application_fee_amount(amount_cents)
            payment_intent_data = {
                "metadata": metadata,
            }
            if self.merchant_id:
                payment_intent_data["application_fee_amount"] = application_fee_amount
                payment_intent_data["transfer_data"] = {
                    "destination": self.merchant_id,
                }
            
            session = stripe.checkout.Session.create(
                line_items=[{
                    "price_data": {
                        "currency": currency,
                        "product_data": {
                            "name": description,
                        },
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata,
                payment_intent_data=payment_intent_data,
            )
            return session
        except Exception as e:
            logger.error("error creating Stripe checkout session:: %s", e)
            raise e
        
    def create_account_login_link(self, account_id: str) -> stripe.Account.LoginLink:
       
        return stripe.Account.create_login_link(account_id)