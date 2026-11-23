from django.urls import path

from chat.views import message_create
from . import views


app_name = "conversations"
urlpatterns = [
    path("", views.conversation_list, name="list"),
    path("conversations/new/", views.conversation_create, name="create"),
    path("conversations/<uuid:conversation_id>/", views.conversation_detail, name="detail"),
    path("conversations/<uuid:conversation_id>/messages/", message_create, name="message_create"),
    path("conversations/<uuid:conversation_id>/delete/", views.conversation_delete, name="delete"),
    path("conversations/<uuid:conversation_id>/rename/", views.conversation_rename, name="rename"),
    path("conversations/<uuid:conversation_id>/lock/", views.conversation_lock, name="lock"),
    path("conversations/<uuid:conversation_id>/unlock/", views.conversation_unlock, name="unlock"),
    path("conversations/<uuid:conversation_id>/export/<str:format>/", views.conversation_export, name="export"),
    path("conversations/<uuid:conversation_id>/share/", views.conversation_share_create, name="share_create"),
    path("conversations/<uuid:conversation_id>/share/revoke/", views.conversation_share_revoke, name="share_revoke"),
    path("shared/<str:token>/", views.conversation_shared, name="shared"),
]
