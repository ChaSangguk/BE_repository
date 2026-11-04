from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase


class AgreementContractTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.user = users.create(email="member@example.test", nickname="member")
        cls.other = users.create(email="other@example.test", nickname="other")

    def setUp(self):
        self.client.force_authenticate(self.user)


    def test_api_11_required_and_unknown_terms(self):
        terms = apps.get_model("accounts", "Term").objects
        term = terms.create(type="SERVICE", version="contract-test", content="Required", is_required=True, effective_at=timezone.now())
        path = "/v1/me/agreements"
        for pk, status, code in (
            (term.pk, 400, "REQUIRED_TERM_NOT_AGREED"),
            (9223372036854775807, 404, "TERM_NOT_FOUND"),
        ):
            response = self.client.post(path, {"agreements": [{"termId": str(pk), "agreed": False}]}, format="json")
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.json()["error"]["code"], code)
        for _ in range(2):
            response = self.client.post(path, {"agreements": [{"termId": str(term.pk), "agreed": True}]}, format="json")
            self.assertEqual(response.status_code, 200)
            states = response.json()["data"]["agreements"]
            state, = [item for item in states if item["termId"] == str(term.pk)]
            self.assertIs(state["agreed"], True)
            self.assertIsInstance(state["agreedAt"], str)
        agreements = apps.get_model("accounts", "UserTermAgreement").objects
        self.assertEqual(agreements.filter(user=self.user, term=term).count(), 1)
