from django.db import models
from simple_history.models import HistoricalRecords


class ServiceCategory(models.Model):
    """Categories for organizing services (e.g., Hair Services, Nail Services, etc.)"""
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE, related_name='service_categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_online_booking = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    color_code = models.CharField(max_length=10, blank=True, null=True)
    icon = models.CharField(max_length=100, blank=True, null=True)
    image = models.ImageField(upload_to='service_categories/', blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    history = HistoricalRecords()
    
    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'Service Categories'
    
    def __str__(self):
        return f"{self.business.name} - {self.name}"


class Service(models.Model):
    """Services offered by the business"""
    business = models.ForeignKey('business.Business', on_delete=models.CASCADE, related_name='services')
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    duration_minutes = models.PositiveIntegerField(help_text="Duration in minutes")
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price in local currency")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    requires_staff = models.BooleanField(default=True)
    max_capacity = models.PositiveIntegerField(default=1, help_text="Maximum number of clients for this service")
    is_online_booking = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    color_code = models.CharField(max_length=10, blank=True, null=True)
    icon = models.CharField(max_length=100, blank=True, null=True)
    image = models.ImageField(upload_to='services/', blank=True, null=True)
    
    history = HistoricalRecords()
    
    class Meta:
        ordering = ['sort_order', 'name']
    
    def __str__(self):
        return f"{self.business.name} - {self.name}"
    
    def save(self, *args, **kwargs):
        """Save the service and update the sort order"""
        if not self.color_code and self.category.color_code:
            self.color_code = self.category.color_code
        super().save(*args, **kwargs)