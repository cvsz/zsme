from sqlalchemy.exc import IntegrityError

from app.db.models import BusinessPartner


def test_partner_is_bound_to_tenant_and_organization(db_session, seeded_user) -> None:
    partner = BusinessPartner(
        tenant_id=seeded_user.tenant_id,
        organization_id=seeded_user.organization_id,
        partner_code="CUS-0001",
        partner_type="customer",
        display_name="Bangkok Example Co.",
    )
    db_session.add(partner)
    db_session.commit()

    assert partner.tenant_id == seeded_user.tenant_id
    assert partner.organization_id == seeded_user.organization_id
    assert partner.version == 1
    assert partner.is_active is True


def test_partner_code_is_unique_within_organization(db_session, seeded_user) -> None:
    first = BusinessPartner(
        tenant_id=seeded_user.tenant_id,
        organization_id=seeded_user.organization_id,
        partner_code="CUS-0001",
        partner_type="customer",
        display_name="First customer",
    )
    second = BusinessPartner(
        tenant_id=seeded_user.tenant_id,
        organization_id=seeded_user.organization_id,
        partner_code="CUS-0001",
        partner_type="vendor",
        display_name="Second customer",
    )
    db_session.add_all([first, second])

    try:
        db_session.commit()
    except IntegrityError:
        db_session.rollback()
    else:
        raise AssertionError("duplicate partner code was accepted")
