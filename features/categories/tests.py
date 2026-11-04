from django.apps import apps
from rest_framework.test import APITestCase


class CategoryContractTests(APITestCase):
    def test_api_13_public_categories_use_stable_order_and_string_ids(self):
        categories = apps.get_model("debates", "Category").objects
        first = categories.create(name="First", sort_order=2)
        second = categories.create(name="Second", sort_order=2)
        earlier = categories.create(name="Earlier", sort_order=1)
        response = self.client.get("/v1/categories")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("meta", response.json())
        rows = response.json()["data"]["categories"]
        expected = [earlier, first, second]
        self.assertEqual(
            [row for row in rows if row["id"] in {str(item.pk) for item in expected}],
            [{"id": str(item.pk), "name": item.name, "sortOrder": item.sort_order} for item in expected],
        )
