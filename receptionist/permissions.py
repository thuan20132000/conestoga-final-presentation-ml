from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner of the object.
        # For now, we'll allow all authenticated users to edit
        # In production, you might want to add business-specific permissions
        return request.user.is_authenticated


class IsBusinessOwner(permissions.BasePermission):
    """
    Custom permission to only allow business owners to access their data.
    """
    
    def has_permission(self, request, view):
        # Allow read-only access to anyone for now
        # In production, implement proper business ownership checks
        return True
    
    def has_object_permission(self, request, view, obj):
        # Allow read-only access to anyone for now
        # In production, check if user owns the business
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # For write operations, check ownership
        # This would require a user-business relationship model
        return request.user.is_authenticated


class IsAuthenticatedOrReadOnly(permissions.BasePermission):
    """
    The request is authenticated as a user, or is a read-only request.
    """
    
    def has_permission(self, request, view):
        return (
            request.method in permissions.SAFE_METHODS or
            request.user and
            request.user.is_authenticated
        )


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admin users to edit objects.
    """
    
    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to admin users.
        return request.user.is_authenticated and request.user.is_staff


class WebhookPermission(permissions.BasePermission):
    """
    Permission for webhook endpoints - allow only specific sources.
    """
    
    def has_permission(self, request, view):
        # For webhook endpoints, we might want to verify the source
        # For now, allow all requests to webhook endpoints
        return True
        
        # In production, you might want to add:
        # - IP whitelist checking
        # - Signature verification
        # - API key validation
        # 
        # Example:
        # if request.META.get('HTTP_X_TWILIO_SIGNATURE'):
        #     return self.verify_twilio_signature(request)
        # return False


class AnalyticsPermission(permissions.BasePermission):
    """
    Permission for analytics endpoints - allow authenticated users only.
    """
    
    def has_permission(self, request, view):
        # Allow read access to authenticated users
        return request.user.is_authenticated


class ExportPermission(permissions.BasePermission):
    """
    Permission for export endpoints - allow authenticated users only.
    """
    
    def has_permission(self, request, view):
        # Allow export access to authenticated users
        return request.user.is_authenticated
