from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Client, ClientSocialAccount




@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'email', 'phone', 'is_active', 'is_vip', 'created_at', 'updated_at']
    list_filter = ['is_active', 'is_vip', 'created_at', 'updated_at']
    search_fields = ['first_name', 'last_name', 'email', 'phone']
    ordering = ['last_name', 'first_name']
    list_per_page = 25
    list_max_show_all = 100
    list_editable = ['is_active', 'is_vip']
    list_display_links = ['first_name', 'last_name']
    list_filter = ['is_active', 'is_vip', 'created_at', 'updated_at']


@admin.register(ClientSocialAccount)
class ClientSocialAccountAdmin(admin.ModelAdmin):
    list_display = ['client', 'provider', 'provider_user_id', 'email', 'created_at']
    list_filter = ['provider', 'created_at']
    search_fields = ['client__first_name', 'client__last_name', 'email', 'provider_user_id']
    ordering = ['-created_at']
    list_per_page = 25
    raw_id_fields = ['client']
