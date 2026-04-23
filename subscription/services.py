from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

from django.utils import timezone

from .models import BusinessSubscription, SubscriptionPlan, SubscriptionStatus, BillingCycle
from payment.stripe_service import StripeService
from business.models import Business

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

PRICE_ID_FIELD = {
    BillingCycle.MONTHLY: 'stripe_price_id_monthly',
    BillingCycle.QUARTERLY: 'stripe_price_id_quarterly',
    BillingCycle.YEARLY: 'stripe_price_id_yearly',
}


def _ts_to_datetime(ts) -> datetime | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=dt_timezone.utc)


class SubscriptionService:
    def __init__(self):
        self.stripe = StripeService()

    def get_or_create_stripe_customer(self, business) -> str:
        try:
            sub = business.subscription
            if sub.stripe_customer_id:
                return sub.stripe_customer_id
        except BusinessSubscription.DoesNotExist:
            pass

        customer = self.stripe.create_customer(
            email=business.email or '',
            name=business.name,
            metadata={'business_id': str(business.id)},
        )
        return customer.id

    def create_subscription(
        self,
        business,
        plan_id: int,
        billing_cycle: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """
        Creates a Stripe Checkout Session for subscription.
        Returns checkout_url — redirect the user to this URL to complete payment.
        BusinessSubscription is created by the checkout.session.completed webhook.
        """
        plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
        
        # Stripe price ID for the plan
        price_id = getattr(plan, PRICE_ID_FIELD[billing_cycle])
        
        if not price_id:
            raise ValueError(
                f"Plan '{plan.name}' has no Stripe price ID for billing cycle '{billing_cycle}'. "
                "Run sync_subscription_plans first."
            )

        customer_id = self.get_or_create_stripe_customer(business)

        session = self.stripe.create_subscription_checkout_session(
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            customer_id=customer_id,
            trial_days=plan.trial_days,
            metadata={
                'business_id': str(business.id),
                'plan_id': str(plan_id),
                'billing_cycle': billing_cycle,
            },
        )
        return session.url

    def cancel_subscription(
        self,
        business_subscription: BusinessSubscription,
        immediate: bool = False,
    ) -> BusinessSubscription:
        try:
            if business_subscription.stripe_subscription_id:
                stripe_sub = self.stripe.cancel_subscription(
                    subscription_id=business_subscription.stripe_subscription_id,
                    at_period_end=not immediate,
                )
                
                if immediate:
                    business_subscription.status = SubscriptionStatus.CANCELLED
                    business_subscription.cancelled_at = timezone.now()
                    business_subscription.is_active = False
                else:
                    business_subscription.cancel_at_period_end = True
                    business_subscription.status = stripe_sub.get('status', business_subscription.status)
                    business_subscription.is_active = True

            business_subscription.save()
            return business_subscription

        except Exception as e:
            logger.error("Cancel Subscription error: %s", e)
            business_subscription.status = SubscriptionStatus.CANCELLED
            business_subscription.cancelled_at = timezone.now()
            business_subscription.is_active = False
            business_subscription.save()
            return business_subscription

    def change_plan(self, business_subscription: BusinessSubscription, new_plan_id: int, new_billing_cycle: str) -> BusinessSubscription:
        plan = SubscriptionPlan.objects.get(id=new_plan_id, is_active=True)
        price_id = getattr(plan, PRICE_ID_FIELD[new_billing_cycle])
        if not price_id:
            raise ValueError(
                f"Plan '{plan.name}' has no Stripe price ID for billing cycle '{new_billing_cycle}'. "
                "Run sync_subscription_plans first."
            )

        stripe_sub = self.stripe.change_subscription_plan(
            subscription_id=business_subscription.stripe_subscription_id,
            new_price_id=price_id,
        )

        business_subscription.plan = plan
        business_subscription.billing_cycle = new_billing_cycle
        business_subscription.status = stripe_sub.get('status', business_subscription.status)
        business_subscription.current_period_start = _ts_to_datetime(stripe_sub.get('current_period_start'))
        business_subscription.current_period_end = _ts_to_datetime(stripe_sub.get('current_period_end'))
        business_subscription.cancel_at_period_end = stripe_sub.get('cancel_at_period_end', False)
        business_subscription.save()
        return business_subscription

    def handle_webhook_event(self, event) -> None:
        event_type = event.get('type')
        data_object = event.get('data', {}).get('object', {})
        
        
        handlers = {
            'checkout.session.completed': self._handle_checkout_session_completed,
            'customer.subscription.updated': self._handle_subscription_updated,
            'customer.subscription.deleted': self._handle_subscription_deleted,
            'invoice.payment_succeeded': self._handle_invoice_payment_succeeded,
            'invoice.payment_failed': self._handle_invoice_payment_failed,
            'invoice.paid': self._handle_invoice_paid,
        }

        handler = handlers.get(event_type)
        if handler:
            try:
                handler(data_object)
            except Exception as e:
                logger.error("Error handling subscription webhook event %s: %s", event_type, e)

    def _get_subscription_by_stripe_id(self, stripe_sub_id: str):
        return BusinessSubscription.objects.filter(stripe_subscription_id=stripe_sub_id).first()

    def _handle_checkout_session_completed(self, session_obj) -> None:
        """Create BusinessSubscription after successful Stripe Checkout."""
        if session_obj.get('mode') != 'subscription':
            return

        metadata = session_obj.get('metadata') or {}
        business_id = metadata.get('business_id')
        plan_id = metadata.get('plan_id')
        billing_cycle = metadata.get('billing_cycle')

        if not all([business_id, plan_id, billing_cycle]):
            logger.warning("checkout.session.completed missing subscription metadata: %s", metadata)
            return
        
        stripe_subscription_id = session_obj.get('subscription')
        stripe_customer_id = session_obj.get('customer')

        try:
            business = Business.objects.get(id=business_id)
            plan = SubscriptionPlan.objects.get(id=plan_id)
        except (Business.DoesNotExist, SubscriptionPlan.DoesNotExist) as e:
            logger.error("checkout.session.completed lookup error: %s", e)
            return

        # Retrieve the Stripe Subscription to get period dates
        current_period_start = None
        current_period_end = None
        trial_end = None
        sub_status = SubscriptionStatus.ACTIVE
        try:
            stripe_sub = self.stripe.retrieve_subscription(stripe_subscription_id)
            # Stripe returns a "items": {"data": [ ... ]} array—even for single subscriptions.
            # Use those period timestamps if present on the first item, else fallback to plain keys.
            items_data = stripe_sub.get("items", {}).get("data", [])
            if items_data and isinstance(items_data[0], dict):
                item = items_data[0]
                current_period_start = _ts_to_datetime(item.get('current_period_start'))
                current_period_end = _ts_to_datetime(item.get('current_period_end'))
                trial_end = _ts_to_datetime(item.get('trial_end')) or _ts_to_datetime(stripe_sub.get('trial_end'))
            else:
                current_period_start = _ts_to_datetime(stripe_sub.get('current_period_start'))
                current_period_end = _ts_to_datetime(stripe_sub.get('current_period_end'))
                trial_end = _ts_to_datetime(stripe_sub.get('trial_end'))
            sub_status = stripe_sub.status
        except Exception as e:
            logger.warning("Could not retrieve Stripe subscription %s: %s", stripe_subscription_id, e)

        BusinessSubscription.objects.update_or_create(
            business=business,
            defaults={
                'plan': plan,
                'billing_cycle': billing_cycle,
                'status': sub_status,
                'stripe_subscription_id': stripe_subscription_id,
                'stripe_customer_id': stripe_customer_id,
                'current_period_start': current_period_start,
                'current_period_end': current_period_end,
                'trial_end': trial_end,
                'cancel_at_period_end': False,
                'is_active': True,
                'cancelled_at': None,
                'is_deleted': False,
                'deleted_at': None,
            },
        )
        logger.info("BusinessSubscription created/updated for business %s via checkout", business_id)

    def _handle_subscription_updated(self, subscription_obj) -> None:
        stripe_sub_id = subscription_obj.get('id')
        sub = self._get_subscription_by_stripe_id(stripe_sub_id)
        if not sub:
            logger.warning("No BusinessSubscription found for stripe_subscription_id=%s", stripe_sub_id)
            return

        sub.status = subscription_obj.get('status', sub.status)
        sub.current_period_start = _ts_to_datetime(subscription_obj.get('current_period_start'))
        sub.current_period_end = _ts_to_datetime(subscription_obj.get('current_period_end'))
        sub.cancel_at_period_end = subscription_obj.get('cancel_at_period_end', False)
        sub.trial_end = _ts_to_datetime(subscription_obj.get('trial_end'))
        sub.save()

    def _handle_subscription_deleted(self, subscription_obj) -> None:
        stripe_sub_id = subscription_obj.get('id')
        sub = self._get_subscription_by_stripe_id(stripe_sub_id)
        if not sub:
            return

        sub.status = SubscriptionStatus.CANCELLED
        sub.cancelled_at = timezone.now()
        sub.is_active = False
        sub.save()

    def _handle_invoice_payment_succeeded(self, invoice_obj) -> None:
        stripe_sub_id = invoice_obj.get('subscription')
        if not stripe_sub_id:
            return

        sub = self._get_subscription_by_stripe_id(stripe_sub_id)
        if not sub:
            return

        sub.status = SubscriptionStatus.ACTIVE
        sub.is_active = True
        period_end = invoice_obj.get('lines', {}).get('data', [{}])[0].get('period', {}).get('end')
        period_start = invoice_obj.get('lines', {}).get('data', [{}])[0].get('period', {}).get('start')
        if period_start:
            sub.current_period_start = _ts_to_datetime(period_start)
        if period_end:
            sub.current_period_end = _ts_to_datetime(period_end)
        sub.save()

    def _handle_invoice_payment_failed(self, invoice_obj) -> None:
        stripe_sub_id = invoice_obj.get('subscription')
        if not stripe_sub_id:
            return

        sub = self._get_subscription_by_stripe_id(stripe_sub_id)
        if not sub:
            return

        sub.status = SubscriptionStatus.PAST_DUE
        sub.save()

    def _handle_invoice_paid(self, invoice_obj) -> None:
        stripe_sub_id = invoice_obj.get('subscription')
        if not stripe_sub_id:
            return

        sub = self._get_subscription_by_stripe_id(stripe_sub_id)
        if not sub:
            return

        sub.status = SubscriptionStatus.ACTIVE
        sub.is_active = True
        sub.save()
        
    
    def retrieve_subscription_info(self, subscription_id: str) -> dict:
        stripe_sub = self.stripe.retrieve_subscription(subscription_id)
        return stripe_sub