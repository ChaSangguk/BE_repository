from rest_framework import serializers

from .models import DebateParticipant, Stance, StanceHistory


class JoinedDebateSerializer(serializers.ModelSerializer):
    debateId = serializers.IntegerField(source="debate_id")
    title = serializers.CharField(source="debate.title")
    status = serializers.CharField(source="debate.status")
    currentStance = serializers.CharField(source="current_stance")

    class Meta:
        model = DebateParticipant
        fields = ("debateId", "title", "status", "currentStance")

class StanceChangeInput(serializers.Serializer):
    stance = serializers.ChoiceField(choices=Stance.choices)
    opinionId = serializers.IntegerField(min_value=1, max_value=2**63 - 1)
    version = serializers.IntegerField(min_value=0, max_value=2**31 - 1)


class StanceStateSerializer(serializers.ModelSerializer):
    initialStance = serializers.CharField(source="initial_stance")
    currentStance = serializers.CharField(source="current_stance")

    class Meta:
        model = DebateParticipant
        fields = ("initialStance", "currentStance", "version")


class StanceEventSerializer(serializers.ModelSerializer):
    fromStance = serializers.CharField(source="from_stance")
    toStance = serializers.CharField(source="to_stance")
    changedAt = serializers.DateTimeField(source="changed_at")
    opinionId = serializers.IntegerField(source="persuasion.opinion_id", allow_null=True)

    class Meta:
        model = StanceHistory
        fields = ("fromStance", "toStance", "changedAt", "opinionId")

