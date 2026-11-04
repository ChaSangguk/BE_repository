import hashlib
import json
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from accounts.models import APIIdempotencyRecord, User
from discussions.models import Opinion, Persuasion

from .api_contract import ContractError
from .models import Debate, DebateParticipant, StanceHistory


class StanceConflict(ContractError):
    def __init__(self, code, message, *, details=None):
        super().__init__(409, code, message, details=details)


@transaction.atomic
def change_stance(
    *, debate_id, user, stance, idempotency_key, request_path, opinion_id=None, version=None,
):
    if (
        not idempotency_key
        or len(idempotency_key) > 128
        or not idempotency_key.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in idempotency_key)
    ):
        raise ContractError(400, "IDEMPOTENCY_KEY_INVALID", "Use a nonblank key of up to 128 characters.")

    # All writes that race with closing should lock the debate before related rows.
    debate = (
        Debate.objects.with_deadline().select_for_update()
        .exclude(status=Debate.Status.DRAFT).filter(pk=debate_id).first()
    )
    if debate is None:
        raise ContractError(404, "NOT_FOUND", "Debate not found.")
    if user.status != User.Status.ACTIVE:
        raise ContractError(403, "FORBIDDEN", "This account cannot change stance.")

    participant = DebateParticipant.objects.select_for_update().filter(
        debate=debate, user=user,
    ).first()
    if participant is None:
        raise ContractError(403, "NOT_PARTICIPANT", "Only participants can change stance.")

    scope = {
        "user": user,
        "http_method": "PATCH",
        "request_path": request_path,
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
            raise StanceConflict("IDEMPOTENCY_KEY_REUSED", "This key was used with a different request.")
        if saved.status != APIIdempotencyRecord.Status.COMPLETED:
            raise StanceConflict("REQUEST_PROCESSING", "The original request is still processing.")
        if not isinstance(saved.response_body, dict) or "data" not in saved.response_body:
            # Legacy responses have no event ID. Keep the key occupied without replaying or mutating.
            raise StanceConflict("IDEMPOTENCY_KEY_REUSED", "This key belongs to an earlier API response format.")
        return saved.response_body, saved.response_status

    if debate.effective_status(timezone.now()) != Debate.Status.OPEN:
        raise StanceConflict("DEBATE_NOT_OPEN", "This debate is no longer open.")
    if version is not None and participant.version != version:
        raise StanceConflict(
            "STANCE_CONFLICT", "Refresh the current stance before retrying.",
            details={"currentStance": participant.current_stance, "version": participant.version},
        )
    if participant.current_stance == stance:
        raise ContractError(400, "VALIDATION_ERROR", "Choose a different stance.")

    opinion = None
    if opinion_id is not None:
        opinion = Opinion.objects.select_for_update(of=("self",)).filter(
            pk=opinion_id, debate=debate, participant__debate=debate,
            status=Opinion.Status.VISIBLE,
        ).exclude(participant=participant).first()
        if opinion is None:
            raise ContractError(
                400, "OPINION_DEBATE_MISMATCH", "Choose an eligible opinion in this debate.",
            )
    if debate.deadline is not None and debate.deadline <= timezone.now():
        raise StanceConflict("DEBATE_NOT_OPEN", "This debate is no longer open.")

    previous = participant.current_stance
    persuasion = None
    if opinion is not None:
        persuasion = Persuasion.objects.create(
            opinion=opinion, persuaded_user=user, from_stance=previous, to_stance=stance,
        )
    event = StanceHistory.objects.create(
        participant=participant, from_stance=previous, to_stance=stance,
        persuasion=persuasion,
    )
    participant.current_stance = stance
    participant.version += 1
    participant.save(update_fields=["current_stance", "version"])
    response = {"data": {
        "currentStance": participant.current_stance,
        "eventId": str(event.pk),
        "persuasionId": str(persuasion.pk) if persuasion is not None else None,
        "reward": None,
    }}
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
    return response, 200
