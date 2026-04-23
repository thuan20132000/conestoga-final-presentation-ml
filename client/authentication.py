from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .auth import decode_client_token
from .models import Client


class ClientJWTAuthentication(BaseAuthentication):
    """
    DRF authentication class for client JWT tokens.

    Checks for Bearer token with token_type 'client_access'.
    Returns (Client instance, payload) or None (to allow fallthrough to other authenticators).
    """

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header[7:]
        payload = decode_client_token(token)

        if payload is None:
            return None

        token_type = payload.get("token_type")
        if token_type != "client_access":
            return None

        client_id = payload.get("client_id")
        if not client_id:
            return None

        try:
            client = Client.objects.get(id=client_id, is_active=True, is_deleted=False)
        except Client.DoesNotExist:
            raise AuthenticationFailed("Client not found or inactive.")

        return (client, payload)

    def authenticate_header(self, request):
        return "Bearer"
