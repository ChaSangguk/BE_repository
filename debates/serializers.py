from rest_framework import serializers

from .models import DebateParticipant


class JoinedDebateSerializer(serializers.ModelSerializer):
    debateId = serializers.IntegerField(source="debate_id")
    title = serializers.CharField(source="debate.title")
    status = serializers.CharField(source="debate.status")
    currentStance = serializers.CharField(source="current_stance")

    class Meta:
        model = DebateParticipant
        fields = ("debateId", "title", "status", "currentStance")
