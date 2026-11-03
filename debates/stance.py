import hashlib
import json
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError

from accounts.models import APIIdempotencyRecord, User
from discussions.models import Opinion, Persuasion

from .models import Debate, DebateParticipant, StanceHistory
from .serializers import StanceStateSerializer


class StanceConflict(APIException):
    status_code = 409

    def __init__(self, detail):
        self.detail = detail


@transaction.atomic
def change_stance(*, debate_id, user, stance, opinion_id, version, idempotency_key=None):
    # All writes that race with closing should lock the debate before related rows.
    debate = (
        Debate.objects.with_deadline().select_for_update()
        .exclude(status=Debate.Status.DRAFT).filter(pk=debate_id).first()
    )
    if debate is None:
        raise NotFound("Debate not found.")
    if user.status != User.Status.ACTIVE:
        raise PermissionDenied("This account cannot change stance.")

    participant = DebateParticipant.objects.select_for_update().filter(
        debate=debate, user=user,
    ).first()
    if participant is None:
        raise NotFound("Participation not found.")

    scope = None
    if idempotency_key is not None:
        if len(idempotency_key) > 128 or not idempotency_key.strip():
            raise ValidationError({"idempotencyKey": "Use a nonblank key of up to 128 characters."})
        scope = {
            "user": user,
            "http_method": "PATCH",
            "request_path": f"/v1/debates/{debate_id}/me/stance",
            "idempotency_key": idempotency_key,
        }
        request_hash = hashlib.sha256(
            json.dumps([stance, opinion_id, version]).encode(),
        ).hexdigest()
        saved = APIIdempotencyRecord.objects.filter(
            **scope, expires_at__gt=timezone.now(),
        ).first()
        if saved is not None:
            if saved.request_hash != request_hash:
                raise StanceConflict({"code": "idempotency_key_reused"})
            if saved.status != APIIdempotencyRecord.Status.COMPLETED:
                raise StanceConflict({"code": "request_processing"})
            return saved.response_body

    if debate.status == Debate.Status.CANCELED:
        raise StanceConflict({"code": "debate_canceled"})
    if debate.status != Debate.Status.OPEN or (
        debate.deadline is not None and debate.deadline <= timezone.now()
    ):
        raise StanceConflict({"code": "debate_closed"})
    if participant.version != version:
        raise StanceConflict({
            "code": "stance_conflict",
            "currentStance": participant.current_stance,
            "version": participant.version,
        })
    if participant.current_stance == stance:
        raise ValidationError({"stance": "Choose a different stance."})

    opinion = Opinion.objects.select_for_update(of=("self",)).filter(
        pk=opinion_id, debate=debate, participant__debate=debate,
        status=Opinion.Status.VISIBLE,
    ).exclude(participant=participant).first()
    if opinion is None:
        raise ValidationError({"opinionId": "Choose a visible opinion by another participant."})

    if debate.deadline is not None and debate.deadline <= timezone.now():
        raise StanceConflict({"code": "debate_closed"})

    previous = participant.current_stance
    persuasion = Persuasion.objects.create(
        opinion=opinion, persuaded_user=user, from_stance=previous, to_stance=stance,
    )
    StanceHistory.objects.create(
        participant=participant, from_stance=previous, to_stance=stance,
        persuasion=persuasion,
    )
    participant.current_stance = stance
    participant.version += 1
    participant.save(update_fields=["current_stance", "version"])
    response = StanceStateSerializer(participant).data
    if scope is not None:
        APIIdempotencyRecord.objects.update_or_create(
            **scope,
            defaults={
                "request_hash": request_hash,
                "status": APIIdempotencyRecord.Status.COMPLETED,
                "response_status": 200,
                "response_body": response,
                "expires_at": timezone.now() + timedelta(hours=24),
            },
        )
    return response
