from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ["created", "from_staff", "sender", "body", "attachment", "page"]
    readonly_fields = ["created", "from_staff", "sender", "body", "attachment", "page"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["customer", "last_preview", "staff_unread", "assigned_to", "closed", "last_message_at", "open_chat"]
    list_filter = ["closed", "assigned_to"]
    search_fields = ["customer__username", "customer__email", "customer__first_name", "messages__body"]
    readonly_fields = ["customer", "created", "last_message_at", "last_preview", "open_chat"]
    fields = ["customer", "assigned_to", "closed", "open_chat", "last_message_at", "created"]
    inlines = [MessageInline]

    @admin.display(description="Reply")
    def open_chat(self, obj):
        return format_html('<a class="mi-btn" href="{}">Open in inbox →</a>', reverse("support:inbox_thread", args=[obj.pk]))
