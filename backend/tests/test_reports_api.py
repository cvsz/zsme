from datetime import date

from app.db.models import BankAccount, BusinessPartner, FinancialDocument


def _login(client) -> dict[str, str]:
    response = client.post(
        "/v1/auth/login",
        json={
            "tenant_slug": "demo",
            "email": "admin@example.com",
            "password": "correct horse battery staple",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_trial_balance_is_derived_from_posted_ledger(client, seeded_user, ledger_ready) -> None:
    headers = {**_login(client), "Idempotency-Key": "report-post-1"}
    posting = client.post(
        "/v1/accounting/journal-entries",
        headers=headers,
        json={
            "reference": "REPORT-001",
            "journal_date": "2026-09-08",
            "source_type": "manual",
            "lines": [
                {"account_code": "1100", "debit": "1070.00"},
                {"account_code": "4000", "credit": "1000.00"},
                {"account_code": "2101", "credit": "70.00"},
            ],
        },
    )
    assert posting.status_code == 201

    response = client.get(
        "/v1/reports/trial-balance?from_date=2026-09-01&to_date=2026-09-30",
        headers={"Authorization": headers["Authorization"]},
    )

    assert response.status_code == 200
    assert response.json()["total_debit"] == "1070.00"
    assert response.json()["total_credit"] == "1070.00"
    rows = {row["account_code"]: row for row in response.json()["rows"]}
    assert rows["1100"]["debit"] == "1070.00"
    assert rows["4000"]["credit"] == "1000.00"
    assert rows["2101"]["credit"] == "70.00"


def test_trial_balance_excludes_unposted_and_out_of_range_entries(
    client, seeded_user, ledger_ready
) -> None:
    response = client.get(
        "/v1/reports/trial-balance?from_date=2027-01-01&to_date=2027-01-31",
        headers=_login(client),
    )

    assert response.status_code == 200
    assert response.json()["rows"] == []
    assert response.json()["total_debit"] == "0.00"
    assert response.json()["total_credit"] == "0.00"


def test_cash_flow_uses_configured_cash_accounts_and_posted_ledger(
    client, db_session, seeded_user, ledger_ready
) -> None:
    db_session.add(
        BankAccount(
            tenant_id=seeded_user.tenant_id,
            organization_id=seeded_user.organization_id,
            account_code="BANK-REPORT-1",
            name="Operating bank",
            bank_name="Report bank",
            currency_code="THB",
            ledger_account_code="1001",
        )
    )
    db_session.commit()

    auth = _login(client)
    for key, reference, journal_date, lines in (
        (
            "cash-flow-opening",
            "CASH-FLOW-OPENING",
            "2026-08-31",
            [
                {"account_code": "1001", "debit": "500.00"},
                {"account_code": "4000", "credit": "500.00"},
            ],
        ),
        (
            "cash-flow-inflow",
            "CASH-FLOW-INFLOW",
            "2026-09-08",
            [
                {"account_code": "1001", "debit": "100.00"},
                {"account_code": "4000", "credit": "100.00"},
            ],
        ),
        (
            "cash-flow-outflow",
            "CASH-FLOW-OUTFLOW",
            "2026-09-10",
            [
                {"account_code": "5000", "debit": "40.00"},
                {"account_code": "1001", "credit": "40.00"},
            ],
        ),
    ):
        response = client.post(
            "/v1/accounting/journal-entries",
            headers={**auth, "Idempotency-Key": key},
            json={
                "reference": reference,
                "journal_date": journal_date,
                "source_type": "manual",
                "lines": lines,
            },
        )
        assert response.status_code == 201

    response = client.get(
        "/v1/reports/cash-flow?from_date=2026-09-01&to_date=2026-09-30",
        headers=auth,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["method"] == "direct_cash_account_movement"
    assert body["currency_code"] == "THB"
    assert body["configuration_status"] == "ready"
    assert body["mapped_account_count"] == 1
    assert body["opening_cash"] == "500.00"
    assert body["total_inflow"] == "100.00"
    assert body["total_outflow"] == "40.00"
    assert body["net_change"] == "60.00"
    assert body["closing_cash"] == "560.00"
    assert body["rows"] == [
        {
            "account_code": "1001",
            "account_name": "Operating bank",
            "opening_balance": "500.00",
            "inflow": "100.00",
            "outflow": "40.00",
            "net_change": "60.00",
            "closing_balance": "560.00",
        }
    ]


def test_cash_flow_rejects_currency_mismatch_in_active_mapping(
    client, db_session, seeded_user, ledger_ready
) -> None:
    db_session.add(
        BankAccount(
            tenant_id=seeded_user.tenant_id,
            organization_id=seeded_user.organization_id,
            account_code="BANK-REPORT-USD",
            name="USD operating bank",
            bank_name="Report bank",
            currency_code="USD",
            ledger_account_code="1001",
        )
    )
    db_session.commit()

    response = client.get(
        "/v1/reports/cash-flow?from_date=2026-09-01&to_date=2026-09-30",
        headers=_login(client),
    )

    assert response.status_code == 409
    assert "organization currency THB" in response.json()["detail"]


def test_cash_flow_marks_inactive_mappings_as_configuration_required(
    client, db_session, seeded_user, ledger_ready
) -> None:
    db_session.add(
        BankAccount(
            tenant_id=seeded_user.tenant_id,
            organization_id=seeded_user.organization_id,
            account_code="BANK-REPORT-INACTIVE",
            name="Archived bank",
            bank_name="Report bank",
            currency_code="THB",
            ledger_account_code="1001",
            is_active=False,
        )
    )
    db_session.commit()

    response = client.get(
        "/v1/reports/cash-flow?from_date=2026-09-01&to_date=2026-09-30",
        headers=_login(client),
    )

    assert response.status_code == 200
    assert response.json()["configuration_status"] == "configuration_required"
    assert response.json()["mapped_account_count"] == 0
    assert response.json()["rows"] == []


def test_report_family_is_derived_from_posted_ledger_and_documents(
    client, db_session, seeded_user, ledger_ready
) -> None:
    partner = BusinessPartner(
        tenant_id=seeded_user.tenant_id,
        organization_id=seeded_user.organization_id,
        partner_code="CUS-REPORT-1",
        partner_type="customer",
        display_name="Report customer",
    )
    db_session.add(partner)
    db_session.flush()
    db_session.add(
        FinancialDocument(
            tenant_id=seeded_user.tenant_id,
            organization_id=seeded_user.organization_id,
            document_type="sales_invoice",
            document_number="INV-REPORT-1",
            partner_id=partner.id,
            issue_date=date(2026, 8, 1),
            due_date=date(2026, 8, 1),
            currency_code="THB",
            control_account_code="1100",
            tax_account_code="2101",
            subtotal="1000.00",
            tax_total="70.00",
            total="1070.00",
            status="posted",
        )
    )
    db_session.commit()

    headers = {**_login(client), "Idempotency-Key": "report-family-post-1"}
    posting = client.post(
        "/v1/accounting/journal-entries",
        headers=headers,
        json={
            "reference": "REPORT-FAMILY-001",
            "journal_date": "2026-09-08",
            "source_type": "manual",
            "lines": [
                {"account_code": "1100", "debit": "1070.00"},
                {"account_code": "4000", "credit": "1000.00"},
                {"account_code": "2101", "credit": "70.00"},
            ],
        },
    )
    assert posting.status_code == 201
    auth = {"Authorization": headers["Authorization"]}

    profit_loss_response = client.get(
        "/v1/reports/profit-loss?from_date=2026-01-01&to_date=2026-12-31",
        headers=auth,
    )
    balance_sheet_response = client.get("/v1/reports/balance-sheet?as_of=2026-09-08", headers=auth)
    general_ledger_response = client.get(
        "/v1/reports/general-ledger?from_date=2026-01-01&to_date=2026-12-31",
        headers=auth,
    )
    aged_response = client.get("/v1/reports/aged-receivable?as_of=2026-09-08", headers=auth)

    assert profit_loss_response.status_code == 200
    assert profit_loss_response.json()["total_revenue"] == "1000.00"
    assert profit_loss_response.json()["net_income"] == "1000.00"
    assert balance_sheet_response.status_code == 200
    assert balance_sheet_response.json()["total_assets"] == "1070.00"
    assert balance_sheet_response.json()["total_liabilities_and_equity"] == "1070.00"
    assert general_ledger_response.status_code == 200
    assert len(general_ledger_response.json()["rows"]) == 3
    assert general_ledger_response.json()["total_debit"] == "1070.00"
    assert aged_response.status_code == 200
    assert aged_response.json()["total_outstanding"] == "1070.00"
    assert aged_response.json()["current_total"] == "0.00"
    assert aged_response.json()["overdue_total"] == "1070.00"
    assert aged_response.json()["bucket_totals"]["31_60"] == "1070.00"
    assert aged_response.json()["rows"][0]["bucket"] == "31_60"
