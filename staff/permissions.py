from rest_framework import permissions


class IsStaff(permissions.BasePermission):
    """
    Permission to check if the user is an authenticated Staff member.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            hasattr(request.user, 'role')
        )


class IsManager(permissions.BasePermission):
    """
    Permission to check if the user is a Manager or Owner.
    Managers and owners typically have the highest level of access.
    """
    
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        
        if not hasattr(request.user, 'role') or not request.user.role:
            return False
        
        # Manager and owner roles have manager-level permissions
        return request.user.role.name in ['manager', 'owner']
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)

class IsBusinessManager(permissions.BasePermission):
    """
    Permission to check if the user is a Manager or Owner of the business.
    """
    def has_permission(self, request, view):
        user = request.user
        business_id = request.query_params.get('business_id')
        role = user.role.name if user.role else None
        if role not in ['Manager', 'Owner']:
            return False
        
        if not business_id:
            return False
        
        return str(user.business_id) == str(business_id)

class IsBusinessManagerOrReceptionist(permissions.BasePermission):
    """
    Permission to check if the user is a Manager or Owner or Receptionist of the business.
    """
    def has_permission(self, request, view):
        user = request.user
        business_id = request.query_params.get('business_id')
        role = user.role.name if user.role else None
        if role not in ['Manager', 'Owner', 'Receptionist']:
            return False
        
        if not business_id:
            return False
        
        return str(user.business_id) == str(business_id)

class IsEmployee(permissions.BasePermission):
    """
    Permission to check if the user is an Employee (stylist, technician, assistant, etc.).
    Employees have standard staff access but limited management capabilities.
    """
    
    # Employee roles (non-manager, non-receptionist)
    EMPLOYEE_ROLES = ['stylist', 'technician', 'assistant', 'other']
    
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        
        if not hasattr(request.user, 'role') or not request.user.role:
            return False
        
        return request.user.role.name in self.EMPLOYEE_ROLES
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsReceptionist(permissions.BasePermission):
    """
    Permission to check if the user is a Receptionist.
    Receptionists typically handle appointments, clients, and front desk operations.
    """
    
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        
        if not hasattr(request.user, 'role') or not request.user.role:
            return False
        
        return request.user.role.name == 'receptionist'
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsManagerOrEmployee(permissions.BasePermission):
    """
    Permission to check if the user is a Manager or Employee.
    Allows access to both manager and employee roles.
    """
    
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        
        if not hasattr(request.user, 'role') or not request.user.role:
            return False
        
        role_name = request.user.role.name
        employee_roles = ['stylist', 'technician', 'assistant', 'other']
        
        return role_name in ['manager', 'owner'] or role_name in employee_roles
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsManagerOrReceptionist(permissions.BasePermission):
    """
    Permission to check if the user is a Manager or Receptionist.
    Allows access for both management and front desk operations.
    """
    
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        
        if not hasattr(request.user, 'role') or not request.user.role:
            return False
        
        return request.user.role.name in ['manager', 'owner', 'receptionist']
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsManagerOrEmployeeOrReceptionist(permissions.BasePermission):
    """
    Permission to check if the user is a Manager, Employee, or Receptionist.
    Allows access for all staff types.
    """
    
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        
        if not hasattr(request.user, 'role') or not request.user.role:
            return False
        
        # All staff roles except those without a role
        return True
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsStaffOrReadOnly(permissions.BasePermission):
    """
    Permission to allow read access to anyone, but write access only to authenticated staff.
    """
    
    def has_permission(self, request, view):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to authenticated staff
        return (
            request.user and
            request.user.is_authenticated and
            hasattr(request.user, 'role')
        )


class IsManagerOrReadOnly(permissions.BasePermission):
    """
    Permission to allow read access to anyone, but write access only to managers/owners.
    """
    
    def has_permission(self, request, view):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to managers/owners
        if not (request.user and request.user.is_authenticated):
            return False
        
        if not hasattr(request.user, 'role') or not request.user.role:
            return False
        
        return request.user.role.name in ['manager', 'owner']
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to managers/owners
        if not (request.user and request.user.is_authenticated):
            return False
        
        if not hasattr(request.user, 'role') or not request.user.role:
            return False
        
        return request.user.role.name in ['manager', 'owner']
