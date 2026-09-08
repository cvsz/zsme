"use client";

import {
  ArrowDownLeft,
  ArrowUpRight,
  Banknote,
  CheckCircle2,
  CircleAlert,
  FileCheck2,
  FilePlus2,
  FileUp,
  Filter,
  Landmark,
  Link2,
  LockKeyhole,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  UploadCloud,
  X,
} from "lucide-react";
import Link from "next/link";
import { type FormEvent, useEffect, useState, useSyncExternalStore } from "react";

import { DataCard } from "@/components/design-system/data-card";
import { StatusBadge } from "@/components/design-system/status-badge";
import {
  ApiConfigurationError,
  ApiError,
  getAccessToken,
  getApiBaseUrl,
  getServerApiBaseUrl,
  subscribeToApiBaseUrl,
} from "@/lib/api-client";
import {
  createBankAccount,
  createBankingIdempotencyKey,
  importBankTransactions,
  listBankAccounts,
  listBankTransactions,
  reconcileBankTransaction,
  type BankAccount,
  type BankTransaction,
  type BankTransactionImport,
} from "@/lib/banking";
import { formatMoney } from "@/lib/documents";
import { listPayments, type PaymentRecord } from "@/lib/payments";

const workflow = [
  { label: "Import", detail: "Bring in a signed statement or provider feed", icon: UploadCloud },
  { label: "Validate", detail: "Check dates, amounts and duplicate identifiers", icon: ShieldCheck },
  { label: "Match", detail: "Link movements to posted receipts or disbursements", icon: Link2 },
  { label: "Reconcile", detail: "Commit an auditable bank-to-ledger result", icon: CheckCircle2 },
] as const;

const controls = [
  { label: "Statement intake", detail: "CSV, OFX and provider adapters will use a committed import batch.", icon: FileUp },
  { label: "Duplicate protection", detail: "External transaction IDs are unique per bank account.", icon: ShieldCheck },
  { label: "Signed movement", detail: "Positive and negative amounts determine receipt or disbursement direction.", icon: Banknote },
  { label: "Immutable source", detail: "Imported descriptions, dates and amounts cannot be edited after ingestion.", icon: LockKeyhole },
] as const;

type LoadState = "idle" | "ready" | "error";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function formatDate(value: string): string {
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(date);
}

function safeError(error: unknown, action: "load" | "create" | "import" | "reconcile"): string {
  if (error instanceof ApiConfigurationError) {
    return "Connect the API endpoint before using live banking data.";
  }
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return "Your session has expired. Sign in again to continue.";
    }
    if (error.status === 403) {
      return "Your role cannot perform this banking action in the current organization.";
    }
    if (error.status === 409) {
      return "The banking operation conflicts with current organization controls.";
    }
  }
  return action === "load"
    ? "Live banking data is unavailable. Retry the request or review the API connection."
    : `The banking ${action} could not be completed. Review the fields and try again.`;
}

export function BankingWorkbench() {
  const configuredEndpoint = useSyncExternalStore(
    subscribeToApiBaseUrl,
    getApiBaseUrl,
    getServerApiBaseUrl,
  );
  const [accounts, setAccounts] = useState<BankAccount[]>([]);
  const [transactions, setTransactions] = useState<BankTransaction[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [loadError, setLoadError] = useState("");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [isAccountFormOpen, setIsAccountFormOpen] = useState(false);
  const [isImportFormOpen, setIsImportFormOpen] = useState(false);
  const [isCreatingAccount, setIsCreatingAccount] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [selectedTransaction, setSelectedTransaction] = useState<BankTransaction | null>(null);
  const [paymentCandidates, setPaymentCandidates] = useState<PaymentRecord[]>([]);
  const [isLoadingPayments, setIsLoadingPayments] = useState(false);
  const [isReconciling, setIsReconciling] = useState(false);
  const [accountSearch, setAccountSearch] = useState("");
  const [transactionSearch, setTransactionSearch] = useState("");
  const [transactionStatus, setTransactionStatus] = useState<"" | "unmatched" | "reconciled">("");

  const canUseWorkspace = Boolean(configuredEndpoint && getAccessToken());
  const viewState: LoadState | "loading" | "disconnected" | "unauthenticated" = !configuredEndpoint
    ? "disconnected"
    : !getAccessToken()
      ? "unauthenticated"
      : loadState === "idle"
        ? "loading"
        : loadState;
  const connectedAccounts = viewState === "disconnected" || viewState === "unauthenticated" ? [] : accounts;
  const connectedTransactions = viewState === "disconnected" || viewState === "unauthenticated" ? [] : transactions;
  const normalizedAccountSearch = accountSearch.trim().toLowerCase();
  const normalizedTransactionSearch = transactionSearch.trim().toLowerCase();
  const visibleAccounts = connectedAccounts.filter((account) => !normalizedAccountSearch || `${account.account_code} ${account.name} ${account.bank_name} ${account.ledger_account_code}`.toLowerCase().includes(normalizedAccountSearch));
  const visibleTransactions = connectedTransactions.filter((transaction) => {
    const matchesStatus = !transactionStatus || transaction.status === transactionStatus;
    const matchesSearch = !normalizedTransactionSearch || `${transaction.external_id} ${transaction.reference || ""} ${transaction.description}`.toLowerCase().includes(normalizedTransactionSearch);
    return matchesStatus && matchesSearch;
  });
  const accountNames = new Map(accounts.map((account) => [account.id, account.name]));
  const unmatched = connectedTransactions.filter((transaction) => transaction.status === "unmatched");
  const reconciled = connectedTransactions.filter((transaction) => transaction.status === "reconciled");
  const incoming = connectedTransactions.filter((transaction) => Number(transaction.amount) > 0).reduce((sum, transaction) => sum + Number(transaction.amount), 0);
  const outgoing = connectedTransactions.filter((transaction) => Number(transaction.amount) < 0).reduce((sum, transaction) => sum + Math.abs(Number(transaction.amount)), 0);

  useEffect(() => {
    const controller = new AbortController();
    if (!configuredEndpoint || !getAccessToken()) {
      return () => controller.abort();
    }

    Promise.all([listBankAccounts(controller.signal), listBankTransactions(undefined, undefined, controller.signal)])
      .then(([accountResult, transactionResult]) => {
        if (!controller.signal.aborted) {
          setAccounts(accountResult);
          setTransactions(transactionResult);
          setLoadError("");
          setLoadState("ready");
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setLoadError(safeError(error, "load"));
          setLoadState("error");
        }
      });

    return () => controller.abort();
  }, [configuredEndpoint, refreshNonce]);

  useEffect(() => {
    if (!selectedTransaction || !configuredEndpoint || !getAccessToken()) {
      return undefined;
    }
    const controller = new AbortController();
    const paymentKind = Number(selectedTransaction.amount) >= 0 ? "receipt" : "disbursement";
    listPayments(paymentKind, { status: "posted" }, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setPaymentCandidates(result);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setPaymentCandidates([]);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoadingPayments(false);
        }
      });
    return () => controller.abort();
  }, [configuredEndpoint, selectedTransaction]);

  const handleCreateAccount = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setActionError("");
    const data = new FormData(event.currentTarget);
    const input = {
      account_code: String(data.get("account_code") || "").trim(),
      name: String(data.get("name") || "").trim(),
      bank_name: String(data.get("bank_name") || "").trim(),
      currency_code: String(data.get("currency_code") || "THB").trim().toUpperCase(),
      ledger_account_code: String(data.get("ledger_account_code") || "").trim(),
    };
    setIsCreatingAccount(true);
    try {
      const created = await createBankAccount(input, createBankingIdempotencyKey("account"));
      setAccounts((current) => [...current, created].sort((left, right) => left.account_code.localeCompare(right.account_code)));
      setIsAccountFormOpen(false);
      setNotice("Bank account created");
    } catch (error: unknown) {
      setActionError(safeError(error, "create"));
    } finally {
      setIsCreatingAccount(false);
    }
  };

  const handleImport = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setActionError("");
    const data = new FormData(event.currentTarget);
    let transactionsPayload: unknown;
    try {
      transactionsPayload = JSON.parse(String(data.get("transactions_json") || ""));
    } catch {
      setActionError("Transactions JSON must be a valid JSON array.");
      return;
    }
    if (!Array.isArray(transactionsPayload) || transactionsPayload.length === 0) {
      setActionError("Transactions JSON must contain at least one transaction.");
      return;
    }
    const accountId = String(data.get("bank_account_id") || "");
    setIsImporting(true);
    try {
      const imported = await importBankTransactions(
        accountId,
        {
          batch_reference: String(data.get("batch_reference") || "").trim(),
          source_name: String(data.get("source_name") || "").trim(),
          transactions: transactionsPayload as BankTransactionImport[],
        },
        createBankingIdempotencyKey("import"),
      );
      setTransactions((current) => [...current, ...imported.transactions]);
      setIsImportFormOpen(false);
      setNotice("Statement imported");
    } catch (error: unknown) {
      setActionError(safeError(error, "import"));
    } finally {
      setIsImporting(false);
    }
  };

  const handleReconcile = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedTransaction) {
      return;
    }
    const paymentId = String(new FormData(event.currentTarget).get("payment_id") || "").trim();
    if (!paymentId) {
      setActionError("Select a posted payment before reconciling the transaction.");
      return;
    }
    setIsReconciling(true);
    setActionError("");
    try {
      const reconciledTransaction = await reconcileBankTransaction(
        selectedTransaction.id,
        paymentId,
        createBankingIdempotencyKey("reconcile"),
      );
      setTransactions((current) => current.map((item) => item.id === reconciledTransaction.id ? reconciledTransaction : item));
      setSelectedTransaction(null);
      setNotice("Transaction reconciled");
    } catch (error: unknown) {
      setActionError(safeError(error, "reconcile"));
    } finally {
      setIsReconciling(false);
    }
  };

  const statusLabel = {
    idle: "Loading workspace",
    loading: "Loading live data",
    ready: `${connectedAccounts.length} live bank account${connectedAccounts.length === 1 ? "" : "s"}`,
    disconnected: "API not connected",
    unauthenticated: "Sign-in required",
    error: "Data unavailable",
  }[viewState];
  const statusTone = viewState === "ready" ? "success" : viewState === "error" || viewState === "unauthenticated" ? "danger" : viewState === "loading" ? "info" : "warning";

  return (
    <div className="page-stack">
      <header className="page-header">
        <div className="page-header-copy">
          <p className="eyebrow">Cash control</p>
          <h1 className="page-title">Banking & reconciliation</h1>
          <p className="page-subtitle">Import bank activity, match settlement records and keep cash-to-ledger differences visible before close.</p>
        </div>
        <div className="page-actions">
          <StatusBadge tone={statusTone}>{statusLabel}</StatusBadge>
          <button className="button button-primary" type="button" disabled={!canUseWorkspace || viewState !== "ready" || connectedAccounts.length === 0} onClick={() => { setActionError(""); setIsImportFormOpen(true); }}>
            <UploadCloud size={15} aria-hidden="true" /> Import statement
          </button>
        </div>
      </header>

      {viewState !== "ready" ? (
        <section className="connection-banner" aria-labelledby="banking-connection-title" role={viewState === "error" ? "alert" : undefined}>
          <div className="connection-banner-copy">
            <Landmark size={19} aria-hidden="true" />
            <div>
              <strong id="banking-connection-title">{viewState === "error" ? "Banking data needs attention" : "Bank feeds stay guarded until the workspace connects"}</strong>
              <p>{viewState === "disconnected" ? "Connect the API to load organization data. No financial values are fabricated in this interface." : viewState === "unauthenticated" ? "Sign in with an organization account before reading or changing cash movements." : viewState === "error" ? loadError : "Imports are tenant-scoped, duplicate-safe and immutable. Reconciliation only links posted payments in the selected organization."}</p>
            </div>
          </div>
          <div className="page-actions">
            {viewState === "error" ? <button className="button button-secondary" type="button" onClick={() => { setAccounts([]); setTransactions([]); setLoadState("idle"); setRefreshNonce((value) => value + 1); }}><RefreshCw size={15} aria-hidden="true" /> Retry banking load</button> : null}
            {viewState === "disconnected" || viewState === "unauthenticated" ? <Link className="button button-secondary" href={viewState === "disconnected" ? "/settings#connections" : "/login"}>{viewState === "disconnected" ? "Review connection" : "Go to sign in"}</Link> : null}
          </div>
        </section>
      ) : null}

      {notice ? <p className="form-message" role="status" aria-live="polite">{notice}</p> : null}
      {actionError ? <p className="form-message" role="alert">{actionError}</p> : null}

      {isAccountFormOpen ? (
        <section className="panel" aria-labelledby="create-bank-account-title">
          <div className="section-heading-row">
            <div className="section-heading"><h2 id="create-bank-account-title">Add bank account</h2><p>Map one active bank account to an existing non-control asset ledger account.</p></div>
            <button className="icon-button" type="button" aria-label="Close create bank account form" onClick={() => setIsAccountFormOpen(false)}><X size={17} aria-hidden="true" /></button>
          </div>
          <form className="form-grid" onSubmit={handleCreateAccount}>
            <div className="panel-grid two-column">
              <div className="field"><label htmlFor="bank-account-code">Account code</label><input id="bank-account-code" name="account_code" required placeholder="BANK-001" /></div>
              <div className="field"><label htmlFor="bank-account-name">Account name</label><input id="bank-account-name" name="name" required placeholder="Operating account" /></div>
              <div className="field"><label htmlFor="bank-name">Bank name</label><input id="bank-name" name="bank_name" required placeholder="Thai bank" /></div>
              <div className="field"><label htmlFor="bank-currency">Currency</label><input id="bank-currency" name="currency_code" required minLength={3} maxLength={3} defaultValue="THB" /></div>
              <div className="field"><label htmlFor="ledger-account">Ledger account</label><input id="ledger-account" name="ledger_account_code" required placeholder="1001" /><small>Must be an active asset account on the server.</small></div>
            </div>
            <div className="page-actions"><button className="button button-primary" type="submit" disabled={isCreatingAccount} aria-busy={isCreatingAccount}><FilePlus2 size={15} aria-hidden="true" /> {isCreatingAccount ? "Creating…" : "Create bank account"}</button><button className="button button-secondary" type="button" onClick={() => setIsAccountFormOpen(false)}>Cancel</button></div>
          </form>
        </section>
      ) : null}

      {isImportFormOpen ? (
        <section className="panel" aria-labelledby="import-statement-title">
          <div className="section-heading-row">
            <div className="section-heading"><h2 id="import-statement-title">Import statement</h2><p>Commit a validated JSON transaction batch. Source dates, amounts and descriptions remain immutable after ingestion.</p></div>
            <button className="icon-button" type="button" aria-label="Close import statement form" onClick={() => setIsImportFormOpen(false)}><X size={17} aria-hidden="true" /></button>
          </div>
          <form className="form-grid" onSubmit={handleImport}>
            <div className="panel-grid two-column">
              <div className="field"><label htmlFor="import-bank-account">Bank account</label><select id="import-bank-account" name="bank_account_id" required defaultValue=""><option value="">Select account</option>{accounts.filter((account) => account.is_active).map((account) => <option key={account.id} value={account.id}>{account.account_code} · {account.name}</option>)}</select></div>
              <div className="field"><label htmlFor="batch-reference">Batch reference</label><input id="batch-reference" name="batch_reference" required placeholder="SCB-2026-09-08" /></div>
              <div className="field"><label htmlFor="source-name">Source name</label><input id="source-name" name="source_name" required placeholder="SCB CSV export" /></div>
              <div className="field"><label htmlFor="import-date">Statement date</label><input id="import-date" type="date" defaultValue={todayIso()} disabled /><small>Source transaction dates are sent in the JSON payload.</small></div>
            </div>
            <div className="field"><label htmlFor="transactions-json">Transactions JSON</label><textarea id="transactions-json" name="transactions_json" required rows={8} placeholder='[{"external_id":"SCB-0001","transaction_date":"2026-09-08","description":"Customer settlement","amount":"1070.00"}]' /><small>Required keys: external_id, transaction_date, description and non-zero amount.</small></div>
            <div className="page-actions"><button className="button button-primary" type="submit" disabled={isImporting} aria-busy={isImporting}><UploadCloud size={15} aria-hidden="true" /> {isImporting ? "Committing…" : "Commit import"}</button><button className="button button-secondary" type="button" onClick={() => setIsImportFormOpen(false)}>Cancel</button></div>
          </form>
        </section>
      ) : null}

      {selectedTransaction ? (
        <section className="panel" aria-labelledby="reconcile-transaction-title">
          <div className="section-heading-row"><div className="section-heading"><h2 id="reconcile-transaction-title">Reconcile transaction</h2><p>{selectedTransaction.external_id} · {selectedTransaction.description} · {formatMoney(selectedTransaction.amount)}</p></div><button className="icon-button" type="button" aria-label="Close reconcile transaction form" onClick={() => setSelectedTransaction(null)}><X size={17} aria-hidden="true" /></button></div>
          <form className="form-grid" onSubmit={handleReconcile}>
            <div className="field"><label htmlFor="reconcile-payment">Posted payment</label><input id="reconcile-payment" name="payment_id" list="payment-candidates" required placeholder={isLoadingPayments ? "Loading posted payments…" : "Select or enter payment ID"} /><datalist id="payment-candidates">{paymentCandidates.map((payment) => <option key={payment.id} value={payment.id}>{payment.payment_number} · {formatMoney(payment.amount, payment.currency_code)}</option>)}</datalist><small>Only a posted payment with matching direction, currency and amount will be accepted.</small></div>
            <div className="page-actions"><button className="button button-primary" type="submit" disabled={isReconciling || isLoadingPayments} aria-busy={isReconciling}><CheckCircle2 size={15} aria-hidden="true" /> {isReconciling ? "Reconciling…" : "Reconcile transaction"}</button><button className="button button-secondary" type="button" onClick={() => setSelectedTransaction(null)}>Cancel</button></div>
          </form>
        </section>
      ) : null}

      <section className="metric-grid" aria-label="Banking metrics">
        <DataCard label="Active bank accounts" value={viewState === "ready" ? String(connectedAccounts.length) : "—"} meta="Organization-scoped accounts" icon={Landmark} />
        <DataCard label="Unmatched movements" value={viewState === "ready" ? String(unmatched.length) : "—"} meta="Awaiting payment match" icon={CircleAlert} />
        <DataCard label="Reconciled this view" value={viewState === "ready" ? formatMoney(reconciled.reduce((sum, transaction) => sum + Math.abs(Number(transaction.amount)), 0).toFixed(2)) : "—"} meta="Committed bank-to-ledger amount" icon={CheckCircle2} />
        <DataCard label="Difference to ledger" value={viewState === "ready" ? formatMoney(unmatched.reduce((sum, transaction) => sum + Math.abs(Number(transaction.amount)), 0).toFixed(2)) : "—"} meta="Unmatched amount requiring review" icon={SlidersHorizontal} />
      </section>

      <nav className="tab-list" aria-label="Banking sections"><a href="/banking" aria-current="page">Overview</a><a href="/banking#accounts">Bank accounts</a><a href="/banking#transactions">Transactions</a><a href="/banking#reconciliation">Reconciliation queue</a></nav>

      <section className="panel" id="accounts" aria-labelledby="bank-account-title">
        <div className="section-heading"><div className="section-heading-row"><div><h2 id="bank-account-title">Bank account register</h2><p>Each account maps to one active asset ledger code and remains scoped to the current organization.</p></div><div className="page-actions"><StatusBadge tone="info"><Landmark size={12} aria-hidden="true" /> Cash control</StatusBadge><button className="button button-secondary" type="button" disabled={!canUseWorkspace || viewState !== "ready"} onClick={() => { setActionError(""); setIsAccountFormOpen(true); }}><Landmark size={15} aria-hidden="true" /> Add bank account</button></div></div></div>
        <div className="workbench-toolbar" aria-label="Bank account filters"><label className="search-trigger workbench-search" htmlFor="bank-account-search"><Search size={16} aria-hidden="true" /><span className="visually-hidden">Search bank accounts</span><input id="bank-account-search" type="search" placeholder="Search account, bank or ledger code" value={accountSearch} onChange={(event) => setAccountSearch(event.target.value)} disabled={!canUseWorkspace || viewState !== "ready"} /></label><span className="page-subtitle"><Filter size={14} aria-hidden="true" /> Local register filter</span></div>
        <div className="data-table-wrap" tabIndex={0} aria-label="Scroll bank account register horizontally" aria-busy={viewState === "loading"}><table className="data-table"><caption>Bank account register</caption><thead><tr><th scope="col">Account</th><th scope="col">Bank</th><th scope="col">Ledger mapping</th><th scope="col">Currency</th><th scope="col">Status</th></tr></thead><tbody>{visibleAccounts.length > 0 ? visibleAccounts.map((account) => <tr key={account.id}><td><strong>{account.account_code}</strong><small className="table-secondary">{account.name}</small></td><td>{account.bank_name}</td><td>{account.ledger_account_code}</td><td>{account.currency_code}</td><td><StatusBadge tone={account.is_active ? "success" : "neutral"}>{account.is_active ? "Active" : "Inactive"}</StatusBadge></td></tr>) : <tr><td className="muted-cell" colSpan={5}>{viewState === "loading" ? "Loading bank accounts…" : viewState === "error" ? "Bank accounts unavailable" : viewState === "ready" && accountSearch ? "No bank accounts match the current filter" : viewState === "ready" ? "No bank accounts to display" : "No connected bank accounts"}</td></tr>}</tbody></table></div>
        {viewState === "ready" && connectedAccounts.length === 0 ? <div className="empty-state workbench-empty"><span className="empty-state-icon" aria-hidden="true"><Landmark size={20} /></span><strong>No connected bank accounts</strong><p>Map an active asset ledger account before importing statements or reconciling cash.</p><StatusBadge tone="info"><Landmark size={12} aria-hidden="true" /> Ready to configure</StatusBadge></div> : null}
      </section>

      <section className="panel" id="transactions" aria-labelledby="bank-transactions-title">
        <div className="section-heading"><div className="section-heading-row"><div><h2 id="bank-transactions-title">Transaction queue</h2><p>Imported source fields are immutable; only approved reconciliation state can change.</p></div><StatusBadge tone="info"><Link2 size={12} aria-hidden="true" /> Match queue</StatusBadge></div></div>
        <div className="banking-queue-summary"><div><ArrowDownLeft size={16} aria-hidden="true" /><span><strong>Incoming</strong><small>Positive statement movements</small></span><b>{viewState === "ready" ? formatMoney(incoming.toFixed(2)) : "—"}</b></div><div><ArrowUpRight size={16} aria-hidden="true" /><span><strong>Outgoing</strong><small>Negative statement movements</small></span><b>{viewState === "ready" ? formatMoney(outgoing.toFixed(2)) : "—"}</b></div></div>
        <div className="workbench-toolbar" aria-label="Transaction filters"><label className="search-trigger workbench-search" htmlFor="bank-transaction-search"><Search size={16} aria-hidden="true" /><span className="visually-hidden">Search bank transactions</span><input id="bank-transaction-search" type="search" placeholder="Search external ID, reference or description" value={transactionSearch} onChange={(event) => setTransactionSearch(event.target.value)} disabled={!canUseWorkspace || viewState !== "ready"} /></label><label className="field-inline" htmlFor="bank-transaction-status"><span className="visually-hidden">Bank transaction status filter</span><select id="bank-transaction-status" aria-label="Bank transaction status filter" value={transactionStatus} onChange={(event) => setTransactionStatus(event.target.value as "" | "unmatched" | "reconciled")} disabled={!canUseWorkspace || viewState !== "ready"}><option value="">All statuses</option><option value="unmatched">Unmatched</option><option value="reconciled">Reconciled</option></select></label><span className="page-subtitle"><Filter size={14} aria-hidden="true" /> Local queue filter</span></div>
        <div className="data-table-wrap" tabIndex={0} aria-label="Scroll bank transactions horizontally" aria-busy={viewState === "loading"}><table className="data-table"><caption>Bank transaction queue</caption><thead><tr><th scope="col">External ID</th><th scope="col">Account</th><th scope="col">Date</th><th scope="col">Description</th><th scope="col">Amount</th><th scope="col">Status</th><th scope="col">Action</th></tr></thead><tbody>{visibleTransactions.length > 0 ? visibleTransactions.map((transaction) => <tr key={transaction.id}><td><strong>{transaction.external_id}</strong><small className="table-secondary">{transaction.reference || "No reference"}</small></td><td>{accountNames.get(transaction.bank_account_id) || "Account unavailable"}</td><td>{formatDate(transaction.transaction_date)}</td><td>{transaction.description}</td><td><strong>{formatMoney(transaction.amount)}</strong></td><td><StatusBadge tone={transaction.status === "reconciled" ? "success" : "warning"}>{transaction.status === "reconciled" ? "Reconciled" : "Unmatched"}</StatusBadge></td><td>{transaction.status === "unmatched" ? <button className="button button-secondary" type="button" onClick={() => { setActionError(""); setIsLoadingPayments(true); setSelectedTransaction(transaction); }}><Link2 size={14} aria-hidden="true" /> Reconcile</button> : <StatusBadge tone="success"><FileCheck2 size={12} aria-hidden="true" /> Linked</StatusBadge>}</td></tr>) : <tr><td className="muted-cell" colSpan={7}>{viewState === "loading" ? "Loading transactions…" : viewState === "error" ? "Transactions unavailable" : viewState === "ready" && (transactionSearch || transactionStatus) ? "No transactions match the current filter" : viewState === "ready" ? "No bank transactions to display" : "No connected bank transactions"}</td></tr>}</tbody></table></div>
      </section>

      <section className="panel"><div className="section-heading"><h2>Controlled cash lifecycle</h2><p>Import, validation, matching and reconciliation remain separated so operators can review evidence at every step.</p></div><div className="banking-control-list">{controls.map(({ label, detail, icon: Icon }) => <div className="banking-control" key={label}><span className="banking-control-icon" aria-hidden="true"><Icon size={16} /></span><span><strong>{label}</strong><small>{detail}</small></span></div>)}</div><ol className="workflow-rail">{workflow.map(({ label, detail, icon: Icon }, index) => <li key={label} className={index === 0 ? "is-current" : undefined}><span className="workflow-icon" aria-hidden="true"><Icon size={17} /></span><span><strong>{label}</strong><small>{detail}</small></span></li>)}</ol></section>
    </div>
  );
}
