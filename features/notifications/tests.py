from django.apps import apps
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase


class NotificationContractTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.user = users.create(email="member@example.test", nickname="member")
        cls.other = users.create(email="other@example.test", nickname="other")

    def setUp(self):
        self.client.force_authenticate(self.user)
        notifications = apps.get_model("engagement", "Notification").objects
        self.unread = notifications.create(user=self.user, type="REPLY", title="Unread")
        notifications.create(user=self.user, type="REPLY", title="Read", is_read=True)
        self.foreign = notifications.create(user=self.other, type="REPLY", title="Private")

    def test_api_50_filters_and_counts_only_own_unread(self):
        response = self.client.get("/v1/me/notifications", {"unreadOnly": "true"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["meta"], {"nextCursor": None})
        self.assertEqual(body["data"]["unreadCount"], 1)
        item, = body["data"]["notifications"]
        self.assertEqual(item["notificationId"], str(self.unread.pk))
        self.assertIs(item["isRead"], False)
        self.assertIsNone(item["body"])
        self.assertIsNone(item["targetType"])
        self.assertIsNone(item["targetId"])

    def test_api_51_only_owner_can_mark_read_and_false_is_invalid(self):
        path = f"/v1/me/notifications/{self.unread.pk}"
        response = self.client.patch(path, {"isRead": False}, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(
            f"/v1/me/notifications/{self.foreign.pk}", {"isRead": True}, format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "NOT_NOTIFICATION_OWNER")
        for _ in range(2):
            response = self.client.patch(path, {"isRead": True}, format="json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"data": {"notificationId": str(self.unread.pk), "isRead": True}})
        self.foreign.refresh_from_db()
        self.assertFalse(self.foreign.is_read)

    def test_api_52_bulk_read_is_scoped_and_repeated_request_updates_zero(self):
        for count in (1, 0):
            response = self.client.post("/v1/me/notifications/read-all")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"data": {"updatedCount": count}})
        self.foreign.refresh_from_db()
        self.assertFalse(self.foreign.is_read)
