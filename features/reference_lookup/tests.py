from datetime import timedelta

from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase


class ReferenceLookupContractTests(APITestCase):
    def test_api_41_only_safe_references_return_url(self):
        owner = get_user_model().objects.create(email="owner@example.test", nickname="owner")
        category = apps.get_model("debates", "Category").objects.create(name="Reference")
        now = timezone.now()
        debate = apps.get_model("debates", "Debate").objects.create(
            creator=owner,
            category=category,
            type="ENDLESS",
            title="Reference",
            content="Question",
            status="OPEN",
            started_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=71),
        )
        participant = apps.get_model("debates", "DebateParticipant").objects.create(
            debate=debate, user=owner, anonymous_no=1, initial_stance="PRO", current_stance="PRO",
        )
        opinion = apps.get_model("discussions", "Opinion").objects.create(
            debate=debate, participant=participant, stance_at_write="PRO",
            content="Opinion", content_plain="Opinion", status="VISIBLE",
        )
        references = apps.get_model("discussions", "OpinionReference").objects
        for state, expected_status, code in (
            ("SAFE", 200, None),
            ("PENDING", 409, "REFERENCE_CHECK_PENDING"),
            ("UNSAFE", 403, "REFERENCE_UNSAFE"),
        ):
            with self.subTest(state=state):
                url = f"https://example.test/{state.lower()}"
                reference = references.create(
                    opinion=opinion, url=url, safe_browsing_status=state,
                    checked_at=None if state == "PENDING" else now,
                )
                response = self.client.get(f"/v1/references/{reference.pk}")
                self.assertEqual(response.status_code, expected_status)
                if code is None:
                    self.assertEqual(response.json(), {"data": {"url": url}})
                else:
                    self.assertEqual(response.json()["error"]["code"], code)
                    self.assertNotContains(response, url, status_code=expected_status)
