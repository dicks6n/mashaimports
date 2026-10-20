from django.urls import path

from . import views

app_name = "support"

urlpatterns = [
    path("chat/", views.chat_page, name="chat"),
    path("chat/messages/", views.customer_messages, name="messages"),
    path("chat/send/", views.customer_send, name="send"),
    path("inbox/", views.inbox, name="inbox"),
    path("inbox/poll/", views.staff_poll, name="inbox_poll"),
    path("inbox/<int:pk>/", views.inbox, name="inbox_thread"),
    path("inbox/<int:pk>/messages/", views.staff_messages, name="inbox_messages"),
    path("inbox/<int:pk>/send/", views.staff_send, name="inbox_send"),
    path("inbox/<int:pk>/close/", views.staff_toggle_closed, name="inbox_close"),
]
