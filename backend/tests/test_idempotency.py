from uuid import uuid4

from app.core.idempotency import (
    claim_idempotency,
    complete_idempotency,
    request_hash,
)


def test_idempotency_claim_and_replay_work_across_database_dialects(
    db_session, seeded_user
) -> None:
    payload_hash = request_hash({"amount": "1070.00"})
    first = claim_idempotency(
        db_session,
        tenant_id=seeded_user.tenant_id,
        organization_id=seeded_user.organization_id,
        key="dialect-idempotency-1",
        operation="test.operation",
        request_hash=payload_hash,
    )

    assert first.replayed is False

    resource_id = uuid4()
    complete_idempotency(
        db_session,
        first,
        resource_id=resource_id,
        response_status=201,
        response_body={"resource_id": str(resource_id)},
    )
    db_session.commit()

    replay = claim_idempotency(
        db_session,
        tenant_id=seeded_user.tenant_id,
        organization_id=seeded_user.organization_id,
        key="dialect-idempotency-1",
        operation="test.operation",
        request_hash=payload_hash,
    )

    assert replay.replayed is True
    assert replay.record.resource_id == resource_id
    assert replay.record.response_status == 201
