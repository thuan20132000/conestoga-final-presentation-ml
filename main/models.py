from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    """Base model"""
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    class Meta:
        abstract = True
        
    def __str__(self):
        return f"{self.id} - {self.created_at}"
      
      
class SoftDeleteModel(BaseModel):
    """Soft delete model"""
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        abstract = True
        
    def soft_delete(self):
        self.is_deleted = True
        if self.is_active:
            self.is_active = False
        self.deleted_at = timezone.now()
        self.save()
        
    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save()
      
    def __str__(self):
        return f"{self.id} - {self.created_at}"