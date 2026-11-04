from django.urls import path
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from debates.api_contract import ContractError
from debates.serializers import utc
from engagement.models import Notification
from features.common import MemberView, identifier, optional_id, page


def notification_item(row):
    return {
        "notificationId": str(row.pk), "type": row.type, "title": row.title, "body": row.body,
        "targetType": row.target_type, "targetId": optional_id(row.target_id),
        "isRead": row.is_read, "createdAt": utc(row.created_at),
    }


class Notifications(MemberView):
    def get(self, request):
        unread_only = request.query_params.get("unreadOnly", "false")
        if unread_only not in {"true", "false"}:
            raise ContractError(400, "VALIDATION_ERROR", "Use true or false for unreadOnly.")
        rows = Notification.objects.filter(user=request.user)
        unread = rows.filter(is_read=False)
        return page(
            request, unread if unread_only == "true" else rows, "notifications",
            notification_item, unreadCount=unread.count(),
        )


class MarkRead(MemberView):
    def patch(self, request, notification_id):
        notification_id = identifier(notification_id)
        if request.data.get("isRead") is not True:
            raise ContractError(400, "VALIDATION_ERROR", "Use isRead=true.")
        rows = Notification.objects.filter(pk=notification_id)
        if not rows.filter(user=request.user).update(is_read=True):
            if rows.exists():
                raise ContractError(403, "NOT_NOTIFICATION_OWNER", "This notification belongs to another member.")
            raise NotFound()
        return Response({"data": {"notificationId": str(notification_id), "isRead": True}})


class ReadAll(MemberView):
    def post(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({"data": {"updatedCount": count}})


urlpatterns = [
    path("me/notifications", Notifications.as_view()),
    path("me/notifications/read-all", ReadAll.as_view()),
    path("me/notifications/<str:notification_id>", MarkRead.as_view()),
]
