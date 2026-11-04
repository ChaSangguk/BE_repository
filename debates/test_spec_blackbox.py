"""Black-box contracts for API #26, #27, #28 and #44.

Expected responses come from the workbook and P1 requirements. ORM writes
seed prerequisites. Every behavior assertion uses a public HTTP response.
"""

from datetime import datetime, timedelta

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone


Category = apps.get_model("debates", "Category")
Debate = apps.get_model("debates", "Debate")
Participant = apps.get_model("debates", "DebateParticipant")
StanceHistory = apps.get_model("debates", "StanceHistory")
Statistics = apps.get_model("debates", "DebateStatistics")
Opinion = apps.get_model("discussions", "Opinion")


class DebateSpecBlackBoxTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.member = user_model.objects.create(
            email="member@example.test", nickname="member", status="ACTIVE"
        )
        cls.other = user_model.objects.create(
            email="other@example.test", nickname="other", status="ACTIVE"
        )
        cls.category = Category.objects.create(name="Contract category")
        cls.now = timezone.now()
        cls.debate = cls.make_debate()
        cls.closed = cls.make_debate(status="CLOSED")
        cls.me = cls.join(cls.debate, cls.member, "PRO")
        cls.opinion_author = cls.join(cls.debate, cls.other, "CON", number=2)
        cls.opinion = cls.post(cls.opinion_author)

    def setUp(self):
        self.as_member = self.client_for(self.member)
        self.as_other = self.client_for(self.other)

    @staticmethod
    def client_for(user):
        client = Client()
        client.force_login(user)
        return client

    @classmethod
    def make_debate(cls, status="OPEN", expired=False):
        minutes_elapsed = 12 if expired or status == "CLOSED" else 1
        started_at = cls.now - timedelta(minutes=minutes_elapsed)
        ends_at = started_at + timedelta(minutes=10)
        return Debate.objects.create(
            creator=cls.other,
            category=cls.category,
            type="QUICK",
            title="Contract debate",
            content="A debate seeded for public API contract checks.",
            duration_minutes=10,
            started_at=started_at,
            ends_at=ends_at,
            status=status,
            closed_at=ends_at if status == "CLOSED" else None,
        )

    @staticmethod
    def join(debate, user, stance, number=1):
        participant = Participant.objects.create(
            debate=debate,
            user=user,
            anonymous_no=number,
            initial_stance=stance,
            current_stance=stance,
        )
        Debate.objects.filter(pk=debate.pk).update(participant_count=number)
        return participant

    @staticmethod
    def post(participant, status="VISIBLE"):
        return Opinion.objects.create(
            debate=participant.debate,
            participant=participant,
            stance_at_write=participant.current_stance,
            content="An opinion supporting this position.",
            content_plain="An opinion supporting this position.",
            status=status,
        )

    def change_stance(self, client, debate, body, key=None):
        headers = {} if key is None else {"HTTP_IDEMPOTENCY_KEY": key}
        return client.patch(
            f"/v1/debates/{debate.pk}/me/stance",
            data=body,
            content_type="application/json",
            **headers,
        )

    def get_events(self, client, debate):
        return client.get(f"/v1/debates/{debate.pk}/me/events")

    def assert_status(self, response, status):
        self.assertEqual(response.status_code, status, response.content[:1000])

    def assert_api_error(self, response, status, code=None):
        self.assert_status(response, status)
        error = response.json()["error"]
        self.assertIsInstance(error["code"], str)
        self.assertIsInstance(error["message"], str)
        if code is not None:
            self.assertEqual(error["code"], code)

    def assert_id(self, value):
        self.assertIsInstance(value, str)
        self.assertRegex(value, r"^[0-9]+$")
        self.assertGreater(int(value), 0)

    def utc_timestamp(self, value):
        self.assertIsInstance(value, str)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        self.assertEqual(parsed.utcoffset(), timedelta(0))
        return parsed

    def events(self, client, debate):
        response = self.get_events(client, debate)
        self.assert_status(response, 200)
        body = response.json()
        self.assertNotIn("meta", body)
        events = body["data"]["events"]
        self.assertIsInstance(events, list)
        return events

    def test_26_direct_change_and_exact_replay_record_one_event(self):
        body = {"stance": "CON"}
        first = self.change_stance(self.as_member, self.debate, body, "x")
        self.assert_status(first, 200)
        data = first.json()["data"]
        self.assertEqual(data["currentStance"], "CON")
        self.assert_id(data["eventId"])
        self.assertIsNone(data["persuasionId"])
        self.assertIn("reward", data)

        second = self.change_stance(self.as_member, self.debate, body, "x")
        self.assert_status(second, 200)
        self.assertEqual(second.json(), first.json())

        collision = self.change_stance(
            self.as_member, self.debate, {"stance": "NEUTRAL"}, "x"
        )
        self.assert_api_error(collision, 409, "IDEMPOTENCY_KEY_REUSED")

        [event] = self.events(self.as_member, self.debate)
        self.assertEqual(event["id"], data["eventId"])
        self.assertEqual((event["fromStance"], event["toStance"]), ("PRO", "CON"))
        self.assertIsNone(event["persuasionId"])
        self.utc_timestamp(event["changedAt"])
        self.assertEqual(self.events(self.as_other, self.debate), [])

    def test_26_replay_returns_original_json_after_a_later_change(self):
        first = self.change_stance(
            self.as_member, self.debate, {"stance": "CON"}, "first"
        )
        self.assert_status(first, 200)
        second = self.change_stance(
            self.as_member, self.debate, {"stance": "NEUTRAL"}, "second"
        )
        self.assert_status(second, 200)

        replay = self.change_stance(
            self.as_member, self.debate, {"stance": "CON"}, "first"
        )
        self.assert_status(replay, 200)
        self.assertEqual(replay.json(), first.json())
        self.assertCountEqual(
            [(e["fromStance"], e["toStance"]) for e in self.events(self.as_member, self.debate)],
            [("PRO", "CON"), ("CON", "NEUTRAL")],
        )

    def test_26_persuasion_links_the_success_response_and_event(self):
        response = self.change_stance(
            self.as_member,
            self.debate,
            {"stance": "CON", "opinionId": str(self.opinion.pk)},
            "opinion",
        )
        self.assert_status(response, 200)
        data = response.json()["data"]
        self.assertEqual(data["currentStance"], "CON")
        self.assert_id(data["eventId"])
        self.assert_id(data["persuasionId"])
        self.assertIn("reward", data)
        [event] = self.events(self.as_member, self.debate)
        self.assertEqual(event["id"], data["eventId"])
        self.assertEqual(event["persuasionId"], data["persuasionId"])

    def test_26_key_is_required_and_has_a_128_character_limit(self):
        for key in (None, "", "x" * 129):
            with self.subTest(key=key):
                response = self.change_stance(
                    self.as_member, self.debate, {"stance": "CON"}, key
                )
                self.assert_api_error(response, 400, "IDEMPOTENCY_KEY_INVALID")
        self.assertEqual(self.events(self.as_member, self.debate), [])
        response = self.change_stance(
            self.as_member, self.debate, {"stance": "CON"}, "x" * 128
        )
        self.assert_status(response, 200)

    def test_26_key_scope_includes_member_and_actual_path(self):
        second_debate = self.make_debate()
        self.join(second_debate, self.member, "PRO")
        requests = (
            (self.as_member, self.debate, "CON"),
            (self.as_other, self.debate, "PRO"),
            (self.as_member, second_debate, "NEUTRAL"),
        )
        for client, debate, stance in requests:
            with self.subTest(debate=debate.pk, stance=stance):
                response = self.change_stance(
                    client, debate, {"stance": stance}, "shared-key"
                )
                self.assert_status(response, 200)
                self.assertEqual(response.json()["data"]["currentStance"], stance)

    def test_26_rejects_malformed_stance_or_opinion_id(self):
        invalid_bodies = (
            {},
            {"stance": None},
            {"stance": "INVALID"},
            {"stance": "CON", "opinionId": None},
            {"stance": "CON", "opinionId": self.opinion.pk},
            {"stance": "CON", "opinionId": "0"},
            {"stance": "CON", "opinionId": "-1"},
            {"stance": "CON", "opinionId": "9223372036854775808"},
        )
        for index, body in enumerate(invalid_bodies):
            with self.subTest(body=body):
                response = self.change_stance(
                    self.as_member, self.debate, body, f"invalid-{index}"
                )
                self.assert_api_error(response, 400)
        self.assertEqual(self.events(self.as_member, self.debate), [])

    def test_26_rejects_an_opinion_from_another_debate(self):
        other_debate = self.make_debate()
        other_participant = self.join(other_debate, self.other, "CON")
        opinion = self.post(other_participant)
        response = self.change_stance(
            self.as_member,
            self.debate,
            {"stance": "CON", "opinionId": str(opinion.pk)},
            "other-debate",
        )
        self.assert_api_error(response, 400, "OPINION_DEBATE_MISMATCH")
        self.assertEqual(self.events(self.as_member, self.debate), [])

    def test_26_rejects_deleted_and_hidden_opinions(self):
        for status in ("DELETED", "FILTERED"):
            with self.subTest(opinion_status=status):
                opinion = self.post(self.opinion_author, status=status)
                response = self.change_stance(
                    self.as_member,
                    self.debate,
                    {"stance": "CON", "opinionId": str(opinion.pk)},
                    f"opinion-{status}",
                )
                # P1 prohibits these targets without fixing an error code.
                self.assertIn(response.status_code, (400, 403, 404, 409), response.content)
        self.assertEqual(self.events(self.as_member, self.debate), [])

    def test_26_rejects_closed_and_past_deadline_open_debates(self):
        expired = self.make_debate(expired=True)
        for debate in (self.closed, expired):
            with self.subTest(debate=debate.pk):
                self.join(debate, self.member, "PRO")
                response = self.change_stance(
                    self.as_member, debate, {"stance": "CON"}, "too-late"
                )
                self.assert_api_error(response, 409, "DEBATE_NOT_OPEN")
                self.assertEqual(self.events(self.as_member, debate), [])

    def test_26_and_27_require_membership_and_participation(self):
        outsider_debate = self.make_debate()
        body = {"stance": "CON"}
        self.assert_api_error(
            self.change_stance(self.as_member, outsider_debate, body, "nonparticipant"),
            403,
            "NOT_PARTICIPANT",
        )
        self.assert_api_error(
            self.get_events(self.as_member, outsider_debate), 403, "NOT_PARTICIPANT"
        )
        self.assert_api_error(self.change_stance(Client(), self.debate, body, "anon"), 401)
        self.assert_api_error(self.get_events(Client(), self.debate), 401)

    def test_27_returns_only_own_events_and_sorts_by_timestamp_and_id(self):
        # IDs and timestamps have different orders, with one timestamp tie.
        seeded = []
        for participant, before, after, minutes_ago in (
            (self.me, "NEUTRAL", "CON", 1),
            (self.me, "PRO", "CON", 2),
            (self.opinion_author, "CON", "PRO", 2),
            (self.me, "CON", "NEUTRAL", 2),
        ):
            row = StanceHistory.objects.create(
                participant=participant, from_stance=before, to_stance=after
            )
            changed_at = self.now - timedelta(minutes=minutes_ago)
            StanceHistory.objects.filter(pk=row.pk).update(changed_at=changed_at)
            if participant == self.me:
                seeded.append((changed_at, row.pk, before, after))

        events = self.events(self.as_member, self.debate)
        actual = []
        for event in events:
            self.assert_id(event["id"])
            self.assertIsNone(event["persuasionId"])
            actual.append(
                (
                    self.utc_timestamp(event["changedAt"]),
                    int(event["id"]),
                    event["fromStance"],
                    event["toStance"],
                )
            )
        forward = sorted(seeded)
        self.assertIn(actual, [forward, forward[::-1]])

    def test_28_returns_only_participated_debates_with_optional_status_filter(self):
        self.join(self.closed, self.member, "NEUTRAL")
        other_debate = self.make_debate()
        self.join(other_debate, self.other, "PRO")
        expected_ids = {
            None: [str(self.debate.pk), str(self.closed.pk)],
            "OPEN": [str(self.debate.pk)],
            "CLOSED": [str(self.closed.pk)],
        }
        for status, ids in expected_ids.items():
            with self.subTest(status=status):
                query = {"status": status} if status else {}
                response = self.as_member.get("/v1/me/debates", query)
                self.assert_status(response, 200)
                body = response.json()
                self.assertCountEqual([item["id"] for item in body["data"]["debates"]], ids)
                self.assertIsNone(body["meta"]["nextCursor"])
                for item in body["data"]["debates"]:
                    self.assert_debate_list_item(item)
                    if status:
                        self.assertEqual(item["status"], status)

    def assert_debate_list_item(self, item):
        self.assert_id(item["id"])
        self.assert_id(item["categoryId"])
        self.assertEqual(item["categoryId"], str(self.category.pk))
        self.assertEqual(item["kind"], "QUICK")
        self.assertEqual(item["title"], "Contract debate")
        self.assertIn(item["status"], ("OPEN", "CLOSED"))
        for field in ("participantCount", "opinionCount", "viewCount"):
            self.assertIs(type(item[field]), int)
            self.assertGreaterEqual(item[field], 0)
        for field in ("createdAt", "startedAt", "endsAt"):
            self.utc_timestamp(item[field])
        self.assertIsNone(item["canceledAt"])
        if item["status"] == "CLOSED":
            self.utc_timestamp(item["closedAt"])
        else:
            self.assertIsNone(item["closedAt"])

    def test_28_p1_list_shows_current_stance_after_change(self):
        response = self.change_stance(
            self.as_member, self.debate, {"stance": "CON"}, "list-update"
        )
        self.assert_status(response, 200)
        listing = self.as_member.get("/v1/me/debates", {"status": "OPEN"})
        self.assert_status(listing, 200)
        [item] = listing.json()["data"]["debates"]
        # P1 FC-JN-100-001 requires this value. The workbook omits the
        # field from DebateListItem, so use the name defined by API #26.
        self.assertEqual(item.get("currentStance"), "CON", item)

    def test_28_p1_pages_in_twenty_items_without_duplicates(self):
        ids = [str(self.debate.pk)]
        for _ in range(20):
            debate = self.make_debate()
            self.join(debate, self.member, "NEUTRAL")
            ids.append(str(debate.pk))

        response = self.as_member.get("/v1/me/debates", {"status": "OPEN"})
        self.assert_status(response, 200)
        first = response.json()
        items = first["data"]["debates"]
        self.assertEqual(len(items), 20)
        cursor = first["meta"]["nextCursor"]
        self.assertIsInstance(cursor, str)
        self.assertTrue(cursor)

        response = self.as_member.get(
            "/v1/me/debates", {"status": "OPEN", "cursor": cursor}
        )
        self.assert_status(response, 200)
        second = response.json()
        tail = second["data"]["debates"]
        self.assertEqual(len(tail), 1)
        self.assertCountEqual([item["id"] for item in items + tail], ids)
        self.assertIsNone(second["meta"]["nextCursor"])

    def test_28_rejects_invalid_filter_and_anonymous_requests(self):
        response = self.as_member.get("/v1/me/debates", {"status": "CANCELED"})
        self.assert_api_error(response, 400, "FILTER_INVALID")
        self.assert_api_error(Client().get("/v1/me/debates"), 401)

    def test_44_open_and_uncomputed_closed_results_are_not_ready(self):
        for debate in (self.debate, self.closed):
            with self.subTest(status=debate.status):
                response = Client().get(f"/v1/debates/{debate.pk}/result")
                self.assert_api_error(response, 409, "RESULT_NOT_READY")

    def seed_statistics(self, debate, count, *, gender_hidden=False, age_hidden=False):
        return Statistics.objects.create(
            debate=debate,
            total_participants=count,
            opinion_count=11,
            rebuttal_count=3,
            final_pro=count - 3,
            final_con=2,
            final_neutral=1,
            stance_changed_count=2,
            stance_kept_count=count - 2,
            sankey_data={"fixture": "movement"},
            gender_data={"fixture": "gender"},
            age_data={"fixture": "age"},
            region_data={"fixture": "region"},
            gender_hidden=gender_hidden,
            age_hidden=age_hidden,
            computed_at=self.now.replace(microsecond=0),
        )

    def test_44_public_result_projects_counts_and_masks_hidden_demographics(self):
        counts = {
            "totalParticipants": 20,
            "opinionCount": 11,
            "rebuttalCount": 3,
            "finalPro": 17,
            "finalCon": 2,
            "finalNeutral": 1,
            "stanceChangedCount": 2,
            "stanceKeptCount": 18,
        }
        for gender_hidden, age_hidden in ((True, False), (False, True)):
            with self.subTest(gender_hidden=gender_hidden, age_hidden=age_hidden):
                debate = self.make_debate(status="CLOSED")
                stats = self.seed_statistics(
                    debate, 20, gender_hidden=gender_hidden, age_hidden=age_hidden
                )
                response = Client().get(f"/v1/debates/{debate.pk}/result")
                self.assert_status(response, 200)
                data = response.json()["data"]
                for name, expected in counts.items():
                    value = data["counts"][name]
                    self.assertIs(type(value), int)
                    self.assertEqual(value, expected)

                # Internal JSON formats and the conditions for populating
                # nullable demographic data are deferred in the workbook.
                self.assertIsNotNone(data["sankeyData"])
                for field, hidden in (("gender", gender_hidden), ("age", age_hidden)):
                    self.assertIs(data[f"{field}Hidden"], hidden)
                    self.assertIn(f"{field}Data", data)
                    if hidden:
                        self.assertIsNone(data[f"{field}Data"])
                self.assertIn("regionData", data)
                self.assertEqual(self.utc_timestamp(data["computedAt"]), stats.computed_at)

    def test_44_function_requirement_suppresses_distributions_below_twenty(self):
        # FC-DB-300-008 mandates suppression below 20, without defining
        # its JSON representation or whether exact stance counts are included.
        self.seed_statistics(self.closed, 19)
        response = Client().get(f"/v1/debates/{self.closed.pk}/result")
        self.assert_status(response, 200)
        data = response.json()["data"]
        for field in ("sankeyData", "genderData", "ageData", "regionData"):
            with self.subTest(field=field):
                self.assertIn(data.get(field), (None, [], {}), data)
        for field, expected in (
            ("totalParticipants", 19), ("opinionCount", 11), ("rebuttalCount", 3)
        ):
            with self.subTest(field=field):
                self.assertEqual(data["counts"][field], expected)
