import jwt
import uuid
from datetime import timedelta

from django.conf import settings
from django.utils import timezone


# Client JWT lifetimes (matching staff token config)
CLIENT_ACCESS_TOKEN_LIFETIME = timedelta(days=30)
CLIENT_REFRESH_TOKEN_LIFETIME = timedelta(days=90)
CLIENT_OTP_EXPIRY_MINUTES = 5
CLIENT_OTP_LENGTH = 6


def generate_client_tokens(client):
    """Generate access and refresh JWT tokens for a Client instance."""
    now = timezone.now()

    access_payload = {
        "client_id": str(client.id),
        "business_id": (
            str(client.primary_business_id) if client.primary_business_id else None
        ),
        "token_type": "client_access",
        "jti": str(uuid.uuid4()),
        "iat": now.timestamp(),
        "exp": (now + CLIENT_ACCESS_TOKEN_LIFETIME).timestamp(),
    }

    refresh_payload = {
        "client_id": str(client.id),
        "business_id": (
            str(client.primary_business_id) if client.primary_business_id else None
        ),
        "token_type": "client_refresh",
        "jti": str(uuid.uuid4()),
        "iat": now.timestamp(),
        "exp": (now + CLIENT_REFRESH_TOKEN_LIFETIME).timestamp(),
    }

    access_token = jwt.encode(access_payload, settings.SECRET_KEY, algorithm="HS256")
    refresh_token = jwt.encode(refresh_payload, settings.SECRET_KEY, algorithm="HS256")

    return {
        "access": access_token,
        "refresh": refresh_token,
    }


def decode_client_token(token):
    """Decode and validate a client JWT token. Returns payload dict or None."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
