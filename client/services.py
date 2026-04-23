import random
import logging
from datetime import timedelta

from django.utils import timezone

from .models import Client, ClientOTP, ClientSocialAccount
from .auth import (
    generate_client_tokens,
    decode_client_token,
    CLIENT_OTP_EXPIRY_MINUTES,
    CLIENT_OTP_LENGTH,
)
from notifications.services import EmailService, SMSService

logger = logging.getLogger(__name__)


class ClientAuthService:
    """Handles OTP-based authentication for clients."""

    @staticmethod
    def register(first_name, last_name, email, phone, business_id):
        """
        Register a new client for a business. Sends OTP to verify identity.
        Returns (success: bool, message: str, client: Client|None).
        """
        from business.models import Business

        # Validate business exists
        try:
            business = Business.objects.get(id=business_id, is_deleted=False)
        except Business.DoesNotExist:
            return False, "Business not found.", None

        # Check for existing client with same email or phone in this business
        if email:
            existing = Client.objects.filter(
                primary_business_id=business_id,
                email__iexact=email,
                is_active=True,
                is_deleted=False,
            ).first()
            if existing:
                return (
                    False,
                    "A client with this email already exists for this business.",
                    None,
                )

        if phone:
            existing = Client.objects.filter(
                primary_business_id=business_id,
                phone=phone,
                is_active=True,
                is_deleted=False,
            ).first()
            if existing:
                return (
                    False,
                    "A client with this phone number already exists for this business.",
                    None,
                )

        # Create client
        client = Client.objects.create(
            first_name=first_name,
            last_name=last_name or "",
            email=email or None,
            phone=phone or None,
            primary_business=business,
            is_active=True,
        )

        # Determine identifier for OTP
        if email:
            identifier = email
            identifier_type = "email"
        else:
            identifier = phone
            identifier_type = "phone"

        # Send OTP for verification
        code = "".join([str(random.randint(0, 9)) for _ in range(CLIENT_OTP_LENGTH)])
        expires_at = timezone.now() + timedelta(minutes=CLIENT_OTP_EXPIRY_MINUTES)

        ClientOTP.objects.create(
            client=client,
            code=code,
            identifier=identifier,
            identifier_type=identifier_type,
            business_id=business_id,
            expires_at=expires_at,
        )

        business_name = business.name
        if identifier_type == "email":
            EmailService().send_async(
                subject=f"Your Verification Code - {business_name}",
                to_email=identifier,
                template="emails/client_otp.html",
                context={
                    "client_name": client.get_full_name(),
                    "otp_code": code,
                    "expiry_minutes": CLIENT_OTP_EXPIRY_MINUTES,
                    "business_name": business_name,
                },
            )
        elif identifier_type == "phone":
            message = f"Your {business_name} verification code is: {code}. It expires in {CLIENT_OTP_EXPIRY_MINUTES} minutes."
            SMSService().send_async(
                to_phone=identifier,
                body=message,
                business_id=business_id,
            )

        return True, "Registration successful. OTP sent for verification.", client

    @staticmethod
    def request_otp(identifier, identifier_type, business_id):
        """
        Find a client by email/phone + business, generate OTP, and send it.
        Returns (success: bool, message: str, client: Client|None).
        """
        lookup = {
            "primary_business_id": business_id,
            "is_active": True,
            "is_deleted": False,
        }
        if identifier_type == "email":
            lookup["email__iexact"] = identifier
        elif identifier_type == "phone":
            lookup["phone"] = identifier
        else:
            return False, "Invalid identifier type. Use 'email' or 'phone'.", None

        client = Client.objects.filter(**lookup).first()
        if not client:
            return False, "No account found. Please contact your salon.", None

        # Invalidate previous unused OTPs for this client + business
        ClientOTP.objects.filter(
            client=client,
            business_id=business_id,
            is_used=False,
        ).update(is_used=True)

        # Generate new OTP
        code = "".join([str(random.randint(0, 9)) for _ in range(CLIENT_OTP_LENGTH)])
        expires_at = timezone.now() + timedelta(minutes=CLIENT_OTP_EXPIRY_MINUTES)

        ClientOTP.objects.create(
            client=client,
            code=code,
            identifier=identifier,
            identifier_type=identifier_type,
            business_id=business_id,
            expires_at=expires_at,
        )

        # Send OTP
        business_name = (
            client.primary_business.name if client.primary_business else "BookNgon"
        )
        if identifier_type == "email":
            EmailService().send_async(
                subject=f"Your Login Code - {business_name}",
                to_email=identifier,
                template="emails/client_otp.html",
                context={
                    "client_name": client.get_full_name(),
                    "otp_code": code,
                    "expiry_minutes": CLIENT_OTP_EXPIRY_MINUTES,
                    "business_name": business_name,
                },
            )
        elif identifier_type == "phone":
            message = f"Your {business_name} login code is: {code}. It expires in {CLIENT_OTP_EXPIRY_MINUTES} minutes."
            SMSService().send_async(
                to_phone=identifier,
                body=message,
                business_id=business_id,
            )

        return True, "OTP sent successfully.", client

    @staticmethod
    def verify_otp(identifier, identifier_type, business_id, code):
        """
        Verify OTP and return JWT tokens.
        Returns (success: bool, data: dict|str).
        """
        otp = (
            ClientOTP.objects.filter(
                identifier=identifier,
                identifier_type=identifier_type,
                business_id=business_id,
                code=code,
                is_used=False,
            )
            .order_by("-created_at")
            .first()
        )

        if not otp:
            return False, "Invalid OTP code."

        if otp.is_expired:
            otp.is_used = True
            otp.save()
            return False, "OTP has expired. Please request a new one."

        # Mark OTP as used
        otp.is_used = True
        otp.save()

        client = otp.client
        tokens = generate_client_tokens(client)

        return True, {
            "tokens": tokens,
            "client": {
                "id": str(client.id),
                "first_name": client.first_name,
                "last_name": client.last_name,
                "email": client.email,
                "phone": client.phone,
                "primary_business_id": (
                    str(client.primary_business_id)
                    if client.primary_business_id
                    else None
                ),
            },
        }

    @staticmethod
    def refresh_token(refresh_token_str):
        """
        Validate refresh token and return new access token.
        Returns (success: bool, data: dict|str).
        """
        payload = decode_client_token(refresh_token_str)

        if payload is None:
            return False, "Invalid or expired refresh token."

        if payload.get("token_type") != "client_refresh":
            return False, "Invalid token type."

        client_id = payload.get("client_id")
        try:
            client = Client.objects.get(id=client_id, is_active=True, is_deleted=False)
        except Client.DoesNotExist:
            return False, "Client not found or inactive."

        tokens = generate_client_tokens(client)
        return True, {"tokens": tokens}

    @staticmethod
    def google_login(google_id_token, business_id):
        """
        Verify Google ID token, find or create client, return JWT tokens.
        Uses ClientSocialAccount for identity lookup to avoid duplicates.
        Returns (success: bool, data: dict|str).
        """
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        from django.conf import settings
        from business.models import Business

        google_client_id = getattr(settings, "GOOGLE_CLIENT_ID", "")
        if not google_client_id:
            return False, "Google login is not configured."

        # Verify the Google ID token
        try:
            idinfo = id_token.verify_oauth2_token(
                google_id_token,
                google_requests.Request(),
                google_client_id,
                clock_skew_in_seconds=10,
            )
        except ValueError:
            return False, "Invalid Google token."

        email = idinfo.get("email")
        if not email or not idinfo.get("email_verified"):
            return False, "Google account email is not verified."

        provider_user_id = idinfo.get("sub")

        # Validate business exists
        try:
            business = Business.objects.get(id=business_id, is_deleted=False)
        except Business.DoesNotExist:
            return False, "Business not found."

        is_new_client = False

        # Step 1: look up by provider identity
        social_account = ClientSocialAccount.objects.select_related("client").filter(
            provider="google",
            provider_user_id=provider_user_id,
        ).first()

        if social_account:
            client = social_account.client
            # Keep the stored email in sync if it changed
            if social_account.email != email:
                social_account.email = email
                social_account.save(update_fields=["email", "updated_at"])
        else:
            # Step 2: link to an existing client matched by email
            client = Client.objects.filter(
                primary_business_id=business_id,
                email__iexact=email,
                is_active=True,
                is_deleted=False,
            ).first()

            # Step 3: create a brand-new client
            if not client:
                client = Client.objects.create(
                    first_name=idinfo.get("given_name", ""),
                    last_name=idinfo.get("family_name", ""),
                    email=email,
                    primary_business=business,
                    is_active=True,
                )
                is_new_client = True

            ClientSocialAccount.objects.create(
                client=client,
                provider="google",
                provider_user_id=provider_user_id,
                email=email,
            )

        tokens = generate_client_tokens(client)

        return True, {
            "tokens": tokens,
            "client": {
                "id": str(client.id),
                "first_name": client.first_name,
                "last_name": client.last_name,
                "email": client.email,
                "phone": client.phone,
                "primary_business_id": (
                    str(client.primary_business_id)
                    if client.primary_business_id
                    else None
                ),
            },
            "is_new_client": is_new_client,
        }

    @staticmethod
    def facebook_login(facebook_access_token, business_id):
        """
        Verify Facebook access token via Graph API, find or create client, return JWT tokens.
        Uses ClientSocialAccount for identity lookup to avoid duplicates.
        Returns (success: bool, data: dict|str).
        """
        import requests as http_requests
        from django.conf import settings
        from business.models import Business

        app_id = getattr(settings, "FACEBOOK_APP_ID", "")
        app_secret = getattr(settings, "FACEBOOK_APP_SECRET", "")
        if not app_id or not app_secret:
            return False, "Facebook login is not configured."

        # Verify the token belongs to this app and check granted scopes
        try:
            inspect_resp = http_requests.get(
                "https://graph.facebook.com/debug_token",
                params={
                    "input_token": facebook_access_token,
                    "access_token": f"{app_id}|{app_secret}",
                },
                timeout=10,
            )
            inspect_resp.raise_for_status()
            inspect_data = inspect_resp.json().get("data", {})
        except Exception:
            return False, "Failed to inspect Facebook token."

        if not inspect_data.get("is_valid") or inspect_data.get("app_id") != app_id:
            return False, "Facebook token is not valid for this application."

        granted_scopes = inspect_data.get("scopes", [])

        # Fetch user profile — request email only when permission was granted
        fields = "id,first_name,last_name"
        if "email" in granted_scopes:
            fields += ",email"

        try:
            response = http_requests.get(
                "https://graph.facebook.com/me",
                params={"fields": fields, "access_token": facebook_access_token},
                timeout=10,
            )
            response.raise_for_status()
            fb_data = response.json()
        except Exception:
            return False, "Failed to verify Facebook token."

        if "error" in fb_data:
            return False, "Invalid Facebook token."

        provider_user_id = fb_data.get("id")
        email = fb_data.get("email") if isinstance(fb_data.get("email"), str) else None

        # Validate business exists
        try:
            business = Business.objects.get(id=business_id, is_deleted=False)
        except Business.DoesNotExist:
            return False, "Business not found."

        is_new_client = False

        # Step 1: look up by provider identity
        social_account = ClientSocialAccount.objects.select_related("client").filter(
            provider="facebook",
            provider_user_id=provider_user_id,
        ).first()

        if social_account:
            client = social_account.client
            # Keep the stored email in sync if it changed
            if email and social_account.email != email:
                social_account.email = email
                social_account.save(update_fields=["email", "updated_at"])
        else:
            client = None

            # Step 2: link to an existing client matched by email (if email was granted)
            if email:
                client = Client.objects.filter(
                    primary_business_id=business_id,
                    email__iexact=email,
                    is_active=True,
                    is_deleted=False,
                ).first()

            # Step 3: create a brand-new client
            if not client:
                client = Client.objects.create(
                    first_name=fb_data.get("first_name", ""),
                    last_name=fb_data.get("last_name", ""),
                    email=email,
                    primary_business=business,
                    is_active=True,
                )
                is_new_client = True

            ClientSocialAccount.objects.create(
                client=client,
                provider="facebook",
                provider_user_id=provider_user_id,
                email=email,
            )

        tokens = generate_client_tokens(client)

        return True, {
            "tokens": tokens,
            "client": {
                "id": str(client.id),
                "first_name": client.first_name,
                "last_name": client.last_name,
                "email": client.email,
                "phone": client.phone,
                "primary_business_id": (
                    str(client.primary_business_id)
                    if client.primary_business_id
                    else None
                ),
            },
            "is_new_client": is_new_client,
        }
