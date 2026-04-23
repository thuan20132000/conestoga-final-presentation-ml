from enum import Enum

class AIConfigurationStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    ERROR = "error"
    DELETED = "deleted"
    ARCHIVED = "archived"
    PENDING_DELETION = "pending_deletion"
    PENDING_ARCHIVAL = "pending_archival"
    PENDING_ACTIVATION = "pending_activation"
    PENDING_INACTIVATION = "pending_inactivation"