from datetime import timezone

from rest_framework import serializers

from .api_contract import MAX_ID
from .models import DebateParticipant, Stance


def utc(value):
    if value is not None:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return None


class JoinedDebateSerializer(serializers.BaseSerializer):
    def to_representation(self, participant):
        debate = participant.debate
        status = debate.effective_status(self.context["as_of"])
        closed_at = debate.deadline if debate.status != status else debate.closed_at
        return {
            "id": str(debate.pk),
            "kind": debate.type,
            "title": debate.title,
            "status": status,
            "createdAt": utc(debate.created_at),
            "categoryId": str(debate.category_id),
            "participantCount": debate.participant_count,
            "opinionCount": debate.opinion_count,
            "viewCount": debate.view_count,
            "startedAt": utc(debate.started_at),
            "endsAt": utc(debate.deadline),
            "closedAt": utc(closed_at),
            "canceledAt": utc(debate.canceled_at),
            "currentStance": participant.current_stance,
        }

class StanceChangeInput(serializers.Serializer):
    stance = serializers.ChoiceField(choices=Stance.choices)
    opinionId = serializers.RegexField(r"\A[1-9][0-9]{0,18}\Z", required=False, trim_whitespace=False)
    version = serializers.IntegerField(min_value=0, max_value=2**31 - 1, required=False)

    def validate_opinionId(self, value):
        if not isinstance(self.initial_data["opinionId"], str) or int(value) > MAX_ID:
            raise serializers.ValidationError("Use a positive 64-bit ID as a decimal string.")
        return int(value)


class StanceStateSerializer(serializers.ModelSerializer):
    initialStance = serializers.CharField(source="initial_stance")
    currentStance = serializers.CharField(source="current_stance")

    class Meta:
        model = DebateParticipant
        fields = ("initialStance", "currentStance", "version")


class StanceEventSerializer(serializers.BaseSerializer):
    def to_representation(self, event):
        return {
            "id": str(event.pk),
            "fromStance": event.from_stance,
            "toStance": event.to_stance,
            "changedAt": utc(event.changed_at),
            "persuasionId": str(event.persuasion_id) if event.persuasion_id is not None else None,
        }
