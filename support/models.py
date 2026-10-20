import os
import uuid

from django.conf import settings
from django.db import models


def attachment_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()[:8]
    return f"chat/{uuid.uuid4().hex}{ext}"


class Conversation(models.Model):
    """One support thread per customer, like a WhatsApp chat with the business."""

    customer = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversation")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_chats",
        limit_choices_to={"is_staff": True},
    )
    closed = models.BooleanField(default=False, help_text="Closed chats re-open automatically when the customer writes.")
    customer_unread = models.PositiveIntegerField(default=0)
    staff_unread = models.PositiveIntegerField(default=0)
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_preview = models.CharField(max_length=140, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_message_at"]

    def __str__(self):
        return f"Chat with {self.customer.get_full_name() or self.customer.username}"

    @property
    def customer_name(self):
        return self.customer.get_full_name() or self.customer.username


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    from_staff = models.BooleanField(default=False)
    body = models.TextField(blank=True)
    attachment = models.FileField(upload_to=attachment_path, blank=True)
    page = models.CharField(max_length=300, blank=True, help_text="Page the customer was on when they wrote.")
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created", "id"]

    def __str__(self):
        return f"{'Staff' if self.from_staff else 'Customer'}: {self.body[:60]}"

    @property
    def is_image(self):
        return self.attachment and self.attachment.name.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))

    def as_dict(self):
        sender = (self.sender.get_full_name() or self.sender.username) if self.sender else ""
        return {
            "id": self.id,
            "body": self.body,
            "from_staff": self.from_staff,
            "sender": sender,
            "time": self.created.isoformat(),
            "attachment": self.attachment.url if self.attachment else "",
            "attachment_name": os.path.basename(self.attachment.name) if self.attachment else "",
            "is_image": bool(self.is_image),
        }
