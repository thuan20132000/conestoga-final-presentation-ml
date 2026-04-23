from rest_framework.permissions import BasePermission

from .models import Client


class IsClientAuthenticated(BasePermission):
    """Allows access only to authenticated Client users."""

    def has_permission(self, request, view):
        return isinstance(request.user, Client) and request.user.is_active
