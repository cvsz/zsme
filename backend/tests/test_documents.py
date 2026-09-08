from datetime import date
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.db.models import BusinessPartner, FinancialDocument, FinancialDocumentLine


def test_financial_document_calculates_scope_and_version(db_session, seeded_user) -> None:
    partner = BusinessPartner(
        tenant_id=seeded_user.tenant_id,
        organization_id=seeded_user.organization_id,
        partner_code="CUS-DOC-1",
        partner_type="customer",
        display_name="Document customer",
    )
    document = FinancialDocument(
        tenant_id=seeded_user.tenant_id,
        organization_id=seeded_user.organization_id,
        document_type="sales_invoice",
        document_number="INV-0001",
        partner=partner,
        issue_date=date(2026, 9, 8),
        due_date=date(2026, 10, 8),
        currency_code="THB",
        control_account_code="1100",
        tax_account_code="2101",
        subtotal=Decimal("100.00"),
        tax_total=Decimal("7.00"),
        total=Decimal("107.00"),
    )
    document.lines.append(
        FinancialDocumentLine(
            tenant_id=seeded_user.tenant_id,
            organization_id=seeded_user.organization_id,
            line_no=1,
            description="Service",
            quantity=Decimal("1.000"),
            unit_price=Decimal("100.00"),
            tax_rate=Decimal("7.00"),
            net_amount=Decimal("100.00"),
            tax_amount=Decimal("7.00"),
            total_amount=Decimal("107.00"),
            account_code="4000",
        )
    )
    db_session.add(document)
    db_session.commit()

    assert document.tenant_id == seeded_user.tenant_id
    assert document.organization_id == seeded_user.organization_id
    assert document.version == 1
    assert document.status == "draft"
    assert document.lines[0].total_amount == Decimal("107.00")


def test_document_number_is_unique_per_type_and_organization(db_session, seeded_user) -> None:
    partner = BusinessPartner(
        tenant_id=seeded_user.tenant_id,
        organization_id=seeded_user.organization_id,
        partner_code="CUS-DOC-2",
        partner_type="customer",
        display_name="Document customer",
    )
    first = FinancialDocument(
        tenant_id=seeded_user.tenant_id,
        organization_id=seeded_user.organization_id,
        document_type="sales_invoice",
        document_number="INV-0001",
        partner=partner,
        issue_date=date(2026, 9, 8),
        due_date=date(2026, 9, 8),
        currency_code="THB",
        control_account_code="1100",
        subtotal=Decimal("0.00"),
        tax_total=Decimal("0.00"),
        total=Decimal("0.00"),
    )
    second = FinancialDocument(
        tenant_id=seeded_user.tenant_id,
        organization_id=seeded_user.organization_id,
        document_type="sales_invoice",
        document_number="INV-0001",
        partner=partner,
        issue_date=date(2026, 9, 8),
        due_date=date(2026, 9, 8),
        currency_code="THB",
        control_account_code="1100",
        subtotal=Decimal("0.00"),
        tax_total=Decimal("0.00"),
        total=Decimal("0.00"),
    )
    db_session.add_all([first, second])

    try:
        db_session.commit()
    except IntegrityError:
        db_session.rollback()
    else:
        raise AssertionError("duplicate document number was accepted")
