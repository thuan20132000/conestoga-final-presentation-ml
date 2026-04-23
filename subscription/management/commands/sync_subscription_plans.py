from django.core.management.base import BaseCommand
from subscription.models import SubscriptionPlan, BillingCycle
from payment.stripe_service import StripeService


BILLING_CYCLE_CONFIG = [
    (BillingCycle.MONTHLY, 'stripe_price_id_monthly', 'month', 1),
    (BillingCycle.QUARTERLY, 'stripe_price_id_quarterly', 'month', 3),
    (BillingCycle.YEARLY, 'stripe_price_id_yearly', 'year', 1),
]

PRICE_FIELD_MAP = {
    BillingCycle.MONTHLY: 'price_monthly',
    BillingCycle.QUARTERLY: 'price_quarterly',
    BillingCycle.YEARLY: 'price_yearly',
}


class Command(BaseCommand):
    help = "Sync active SubscriptionPlan records to Stripe Products and Prices."

    def handle(self, *args, **options):
        stripe_service = StripeService()
        plans = SubscriptionPlan.objects.filter(is_active=True)

        if not plans.exists():
            self.stdout.write(self.style.WARNING("No active subscription plans found."))
            return

        for plan in plans:
            self.stdout.write(f"Processing plan: {plan.name} ({plan.tier})")

            # Create or verify Stripe Product
            if not plan.stripe_product_id:
                product = stripe_service.create_stripe_product(
                    name=plan.name,
                    description=plan.description or f"{plan.name} subscription plan",
                )
                plan.stripe_product_id = product.id
                self.stdout.write(f"  Created Stripe Product: {product.id}")
            else:
                self.stdout.write(f"  Stripe Product already exists: {plan.stripe_product_id}")

            # Create Prices for each billing cycle
            for cycle, price_id_field, interval, interval_count in BILLING_CYCLE_CONFIG:
                existing_price_id = getattr(plan, price_id_field)
                if existing_price_id:
                    self.stdout.write(f"  [{cycle}] Stripe Price already exists: {existing_price_id}")
                    continue

                plan_price_field = PRICE_FIELD_MAP[cycle]
                amount = getattr(plan, plan_price_field)
                amount_cents = int(amount * 100)

                price = stripe_service.create_stripe_price(
                    product_id=plan.stripe_product_id,
                    amount_cents=amount_cents,
                    currency=plan.currency,
                    interval=interval,
                    interval_count=interval_count,
                )
                setattr(plan, price_id_field, price.id)
                self.stdout.write(f"  [{cycle}] Created Stripe Price: {price.id} ({amount_cents} cents)")

            plan.save()
            self.stdout.write(self.style.SUCCESS(f"  Plan '{plan.name}' synced successfully."))

        self.stdout.write(self.style.SUCCESS("sync_subscription_plans complete."))
