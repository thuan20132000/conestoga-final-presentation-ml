from django.contrib import admin
from webpush.models import PushInformation, Group, SubscriptionInfo
from .models import Notification
from webpush.utils import _send_notification
import json

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "channel","title", "body", "business", "to", "status", "created_at", "sent_at")
    list_filter = ("channel", "status","business")
    search_fields = ("to", "title", "body")
    readonly_fields = ("created_at", "sent_at")



@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    list_filter = ("name",)
    search_fields = ("name",)

@admin.register(SubscriptionInfo)
class SubscriptionInfoAdmin(admin.ModelAdmin):
    list_display = ("id", "endpoint", "auth", "p256dh", "browser", "user_agent")
    list_filter = ("browser",)
    search_fields = ("endpoint",)
    

# Unregister the default PushInformation admin and register our custom one
admin.site.unregister(PushInformation)

@admin.register(PushInformation)
class PushInformationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "subscription", "group")
    list_filter = ("group",)
    search_fields = ("user__email", "user__username")
    raw_id_fields = ("user", "subscription")
    
    actions = ["send_notification"]

    def send_notification(self, request, queryset):
        payload = {
            "title": "🔔 New Feature Added", 
            "body": "You can now edit your time entry and clock in/out from the app. Please reload your app receive the latest updates."
        }
        for device in queryset:
            notification = _send_notification(device.subscription, json.dumps(payload), 0)
            if notification:
                self.message_user(request, "Notification sent successfully")
            else:
                self.message_user(request, "Notification failed to send")
    send_notification.short_description = "Send Notification"
    send_notification.allowed_permissions = ("change",)