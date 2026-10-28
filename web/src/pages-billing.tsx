import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Building2,
  Banknote,
  Check,
  CreditCard,
  Download,
  Plus,
  QrCode,
  Search,
  ShieldCheck,
  Upload,
} from "lucide-react";
import { api, download, send, setSession } from "./api";
import { PrivateLogo, useAction, useAuth, useData } from "./main";
import { DistributionChart } from "./charts";
import type { Session, User } from "./types";
import type {
  BillingConfig,
  BillingData,
  Company,
  CompanyProfile,
  Payment,
  Plan,
  Subscription,
} from "./estate-types";
import {
  Badge,
  Button,
  Dialog,
  Empty,
  ErrorBox,
  FormDialog,
  Load,
  PageHeading,
  Panel,
  Stat,
  Table,
  dateTime,
  money,
  options,
  type Field,
  type Values,
} from "./ui";

export const companyProfileFields: Field[] = [
  { name: "contact_name", label: "Company contact person", maxLength: 120 },
  { name: "email", label: "Company email", type: "email", maxLength: 160 },
  { name: "phone", label: "Company contact phone", maxLength: 30 },
  { name: "city", label: "Company city", maxLength: 100 },
  { name: "state", label: "Company state", maxLength: 100 },
  { name: "address", label: "Company address", maxLength: 500, wide: true },
  {
    name: "website",
    label: "Company website",
    type: "url",
    hint: "Include https://",
    maxLength: 240,
  },
  { name: "rera_number", label: "Agency RERA number", maxLength: 100 },
  { name: "gst_number", label: "GST number", maxLength: 30 },
];
const profileOf = (v: Values) =>
  Object.fromEntries(
    companyProfileFields.map((f) => [f.name, v[f.name] || ""]),
  );
const valuesOf = (v: object): Values =>
  Object.fromEntries(
    Object.entries(v).map(([key, value]) => [
      key,
      value == null ? "" : typeof value === "boolean" ? value : String(value),
    ]),
  );
function UploadControl({
  label,
  accept,
  path,
  field = "file",
  onError,
}: {
  label: string;
  accept: string;
  path: string;
  field?: string;
  onError: (e: unknown) => void;
}) {
  const [busy, setBusy] = useState(false),
    action = useAction();
  return (
    <label className="button secondary file-upload">
      <Upload size={16} />
      {busy ? "Uploading…" : label}
      <input
        className="visually-hidden"
        type="file"
        accept={accept}
        aria-label={label}
        disabled={busy}
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (!file) return;
          const body = new FormData();
          body.set(field, file);
          setBusy(true);
          onError(null);
          void action(() => api(path, { method: "POST", body }))
            .catch(onError)
            .finally(() => setBusy(false));
        }}
      />
    </label>
  );
}

export function SuperAdminPage() {
  const q = useData<{
    organizations: (Company & { users: number })[];
    total: number;
    active: number;
    users: number;
    leads: number;
  }>("/platform");
  const [search, setSearch] = useState(""),
    [editing, setEditing] = useState<Company | true | null>(null),
    [detail, setDetail] = useState<Company | null>(null),
    [error, setError] = useState<unknown>(null);
  const [archive, setArchive] = useState<Company | null>(null),
    action = useAction(),
    nav = useNavigate();
  function support(id: string) {
    void action(() =>
      api<Session>(`/platform/organizations/${id}/support`, { method: "POST" }),
    )
      .then((s) => {
        setSession(s);
        nav("/app/overview");
      })
      .catch(setError);
  }
  return (
    <>
      <PageHeading
        eyebrow="SUPER ADMIN · REAL ESTATE"
        title="One platform. Independent companies."
        description="Onboard real estate teams, manage their identity and keep every company's workspace separate."
        actions={
          <Button onClick={() => setEditing(true)}>
            <Plus size={17} />
            Create company
          </Button>
        }
      />
      {error !== null && <ErrorBox error={error} />}
      <Load query={q}>
        {(d) => (
          <>
            <div className="stats-grid">
              <Stat
                label="Companies"
                value={d.total}
                detail="Independent workspaces"
                accent
              />
              <Stat
                label="Active companies"
                value={d.active}
                detail={d.total - d.active + " suspended"}
              />
              <Stat
                label="Team members"
                value={d.users}
                detail="Across company workspaces"
              />
              <Stat
                label="Customer enquiries"
                value={d.leads}
                detail="Company data stays separate"
              />
            </div>
            <div className="crm-platform-charts">
              <Panel
                title="Subscription health"
                description="Current plan status across your companies. Payment claims still require your verification."
              >
                <DistributionChart
                  label="Company subscriptions"
                  unit="companies"
                  items={Object.entries(
                    d.organizations.reduce<Record<string, number>>(
                      (counts, company) => {
                        const state =
                          company.subscription?.effective_status ||
                          "not-configured";
                        const label =
                          (
                            {
                              active: "Active plan",
                              trial: "Trial",
                              "past-due": "Renewal overdue",
                              cancelled: "Cancelled",
                              "not-configured": "No plan set",
                            } as Record<string, string>
                          )[state] || state.replaceAll("-", " ");
                        counts[label] = (counts[label] || 0) + 1;
                        return counts;
                      },
                      {},
                    ),
                  ).map(([label, value]) => ({ label, value }))}
                />
              </Panel>
              <Panel
                title="Company team sizes"
                description="Your five largest workspaces by current team size."
              >
                {d.organizations.length ? (
                  <div className="crm-team-list">
                    {[...d.organizations]
                      .sort((a, b) => b.users - a.users)
                      .slice(0, 5)
                      .map((company, index) => (
                        <div key={company.id}>
                          <span className="crm-team-rank">{index + 1}</span>
                          <span className="crm-team-name">
                            <button
                              className="text-button"
                              onClick={() => setDetail(company)}
                            >
                              {company.name}
                            </button>
                            <small>
                              {company.active
                                ? "Workspace active"
                                : "Workspace suspended"}
                            </small>
                            <span className="crm-bar-track" aria-hidden="true">
                              <i
                                style={{
                                  width: `${(company.users / Math.max(...d.organizations.map((org) => org.users), 1)) * 100}%`,
                                }}
                              />
                            </span>
                          </span>
                          <strong>
                            {company.users}
                            <small>people</small>
                          </strong>
                        </div>
                      ))}
                  </div>
                ) : (
                  <Empty
                    title="No companies yet"
                    description="Create a company to see its subscription and team activity here."
                  />
                )}
              </Panel>
            </div>
            <Panel
              title="Company directory"
              description="Profiles, branding and subscription terms in one place."
              action={
                <div className="search-field">
                  <Search size={16} />
                  <input
                    aria-label="Search companies"
                    placeholder="Find a company"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
              }
            >
              {d.organizations.filter((o) =>
                o.name.toLowerCase().includes(search.toLowerCase()),
              ).length ? (
                <Table
                  headers={[
                    "Real estate company",
                    "Workspace",
                    "Subscription",
                    "Renewal",
                    "Team",
                    "Actions",
                  ]}
                >
                  {d.organizations
                    .filter((o) =>
                      o.name.toLowerCase().includes(search.toLowerCase()),
                    )
                    .map((o) => (
                      <tr key={o.id}>
                        <td>
                          <div className="company-identity">
                            <div className="company-avatar">
                              {o.settings.logo_id ? (
                                <PrivateLogo
                                  id={o.settings.logo_id}
                                  path={`/platform/organizations/${o.id}/logo`}
                                  alt={o.name + " logo"}
                                />
                              ) : (
                                <Building2 size={21} />
                              )}
                            </div>
                            <div>
                              <button
                                className="text-button strong"
                                onClick={() => setDetail(o)}
                              >
                                {o.name}
                              </button>
                              <small className="block muted">
                                {o.settings.company_profile?.city ||
                                  "Company profile not completed"}
                              </small>
                            </div>
                          </div>
                        </td>
                        <td>
                          <Badge value={o.active ? "active" : "suspended"} />
                        </td>
                        <td>
                          {o.subscription ? (
                            <>
                              <strong className="block">
                                {o.subscription.plan_name}
                              </strong>
                              <Badge value={o.subscription.effective_status} />
                            </>
                          ) : (
                            <span className="muted">Not configured</span>
                          )}
                        </td>
                        <td>{o.subscription?.ends_on || "—"}</td>
                        <td>
                          {o.subscription
                            ? `${o.subscription.used_seats} / ${o.subscription.seats}`
                            : o.users}
                        </td>
                        <td>
                          <div className="inline-actions">
                            <button onClick={() => setDetail(o)}>Manage</button>
                            <button onClick={() => setEditing(o)}>
                              Edit profile
                            </button>
                            <button
                              onClick={() =>
                                void action(() =>
                                  send(
                                    `/platform/organizations/${o.id}`,
                                    { active: !o.active },
                                    "PATCH",
                                  ),
                                ).catch(setError)
                              }
                            >
                              {o.active ? "Suspend" : "Reactivate"}
                            </button>
                            <button onClick={() => setArchive(o)}>
                              Archive
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                </Table>
              ) : (
                <Empty
                  title={
                    search
                      ? "No matching companies"
                      : "Create your first real estate company"
                  }
                  description="Provision the company profile and its first administrator, then add its logo."
                />
              )}
            </Panel>
          </>
        )}
      </Load>
      {editing && (
        <FormDialog
          title={
            editing === true
              ? "Create a real estate company"
              : "Edit company profile"
          }
          description={
            editing === true
              ? "Creates a separate company workspace with a five-seat trial. Share the administrator credentials securely."
              : "Company profile and branding are independent from other workspaces."
          }
          fields={[
            {
              name: "name",
              label: "Company name",
              required: true,
              maxLength: 160,
            },
            {
              name: "brand_name",
              label: "Workspace brand name",
              maxLength: 160,
            },
            ...companyProfileFields,
            ...(editing === true
              ? [
                  {
                    name: "admin_name",
                    label: "First administrator",
                    required: true,
                  },
                  {
                    name: "admin_phone",
                    label: "Administrator login phone",
                    required: true,
                    hint: "Include country code, e.g. +91",
                  },
                  {
                    name: "password",
                    label: "Initial administrator password",
                    type: "password",
                    required: true,
                    hint: "At least 12 characters",
                  },
                  {
                    name: "trial_days",
                    label: "Trial length (days)",
                    type: "number",
                    min: "1",
                    max: "90",
                    step: "1",
                    required: true,
                    defaultValue: "14",
                  },
                ]
              : []),
          ]}
          initial={
            editing === true
              ? {}
              : {
                  ...valuesOf(editing.settings.company_profile || {}),
                  name: editing.name,
                  brand_name: editing.settings.brand_name || "",
                }
          }
          submitLabel={
            editing === true ? "Create company" : "Save company profile"
          }
          onClose={() => setEditing(null)}
          onSubmit={async (v) => {
            if (editing === true) {
              const created = await action(() =>
                send<{ organization: Company }>("/platform/organizations", {
                  name: v.name,
                  brand_name: v.brand_name,
                  industry: "real_estate",
                  profile: profileOf(v),
                  trial_days: Number(v.trial_days),
                  admin: {
                    name: v.admin_name,
                    phone: v.admin_phone,
                    password: v.password,
                    role: "admin",
                  },
                }),
              );
              setDetail({ ...created.organization, subscription: null });
              return created;
            }
            return action(() =>
              send(
                `/platform/organizations/${editing.id}`,
                {
                  name: v.name,
                  brand_name: v.brand_name,
                  profile: profileOf(v),
                },
                "PATCH",
              ),
            );
          }}
        />
      )}
      {detail && (
        <CompanyDialog
          company={detail}
          close={() => setDetail(null)}
          support={() => support(detail.id)}
        />
      )}
      {archive && (
        <FormDialog
          title={"Archive " + archive.name + "?"}
          description="Company access is revoked and records are retained for operator-assisted recovery."
          fields={[
            {
              name: "confirmation",
              label: "Type company name to confirm",
              required: true,
            },
          ]}
          submitLabel="Archive company"
          onClose={() => setArchive(null)}
          onSubmit={(v) =>
            action(() =>
              api(
                `/platform/organizations/${archive.id}?confirmation=${encodeURIComponent(String(v.confirmation))}`,
                { method: "DELETE" },
              ),
            )
          }
        />
      )}
    </>
  );
}

function CompanyDialog({
  company: initial,
  close,
  support,
}: {
  company: Company;
  close: () => void;
  support: () => void;
}) {
  const q = useData<{
    organization: Company;
    subscription: Subscription | null;
    members: User[];
  }>(`/platform/organizations/${initial.id}`);
  const plans = useData<{ plans: Plan[] }>("/platform/billing"),
    [terms, setTerms] = useState(false),
    [administrator, setAdministrator] = useState<User | true | null>(null),
    [memberBusy, setMemberBusy] = useState<string | null>(null),
    [error, setError] = useState<unknown>(null),
    action = useAction();
  return (
    <Dialog title={initial.name} onClose={close}>
      <div className="dialog-content">
        {error !== null && <ErrorBox error={error} />}
        <Load query={q}>
          {(d) => (
            <>
              <div className="company-profile-header">
                <div className="company-avatar large">
                  {d.organization.settings.logo_id ? (
                    <PrivateLogo
                      id={d.organization.settings.logo_id}
                      path={`/platform/organizations/${initial.id}/logo`}
                      alt="Company logo"
                    />
                  ) : (
                    <Building2 size={32} />
                  )}
                </div>
                <div>
                  <h3>{d.organization.settings.brand_name || initial.name}</h3>
                  <p>
                    {d.organization.settings.company_profile?.email ||
                      "Add company contact details from Edit profile"}
                  </p>
                  <UploadControl
                    label={
                      d.organization.settings.logo_id
                        ? "Change company logo"
                        : "Upload company logo"
                    }
                    accept="image/png,image/jpeg,image/webp"
                    path={`/platform/organizations/${initial.id}/logo`}
                    onError={setError}
                  />
                  {d.organization.settings.logo_id && (
                    <Button
                      variant="secondary"
                      onClick={() => {
                        setError(null);
                        void action(() =>
                          api(`/platform/organizations/${initial.id}/logo`, {
                            method: "DELETE",
                          }),
                        ).catch(setError);
                      }}
                    >
                      Remove company logo
                    </Button>
                  )}
                </div>
              </div>
              <dl className="brief-grid">
                {companyProfileFields.map((f) => (
                  <div key={f.name}>
                    <dt>{f.label}</dt>
                    <dd>
                      {d.organization.settings.company_profile?.[
                        f.name as keyof CompanyProfile
                      ] || "Not recorded"}
                    </dd>
                  </div>
                ))}
              </dl>
              <div className="subscription-strip">
                <div>
                  <small>COMPANY SUBSCRIPTION</small>
                  <h3>{d.subscription?.plan_name || "Not configured"}</h3>
                  <p>
                    {d.subscription
                      ? `${d.subscription.used_seats} / ${d.subscription.seats} seats · ${d.subscription.starts_on} to ${d.subscription.ends_on}`
                      : "Set subscription terms or start a trial."}
                  </p>
                  {d.subscription && (
                    <Badge value={d.subscription.effective_status} />
                  )}
                </div>
                <Button variant="secondary" onClick={() => setTerms(true)}>
                  Manage subscription
                </Button>
              </div>
              <div className="section-intro estate-line">
                <div>
                  <h3>Company administrators & team</h3>
                  <p>
                    Manage administrator logins here. Open the support workspace
                    to manage other team roles.
                  </p>
                </div>
                <Button
                  variant="secondary"
                  onClick={() => setAdministrator(true)}
                >
                  <Plus size={16} />
                  Add administrator
                </Button>
              </div>
              <Table
                headers={["Member", "Role", "Status", "Administrator actions"]}
              >
                {d.members.map((u) => (
                  <tr key={u.id}>
                    <td>
                      {u.name}
                      <small className="block muted">{u.phone}</small>
                    </td>
                    <td>
                      {u.role === "admin"
                        ? "Company admin"
                        : u.role.replaceAll("_", " ")}
                    </td>
                    <td>
                      <Badge value={u.active ? "active" : "inactive"} />
                    </td>
                    <td>
                      {u.role === "admin" ? (
                        <div className="inline-actions">
                          <button onClick={() => setAdministrator(u)}>
                            Edit administrator
                          </button>
                          <button
                            disabled={
                              memberBusy === u.id ||
                              (u.active &&
                                d.members.filter(
                                  (m) => m.role === "admin" && m.active,
                                ).length === 1)
                            }
                            aria-label={`${u.active ? "Deactivate" : "Reactivate"} administrator ${u.name}`}
                            onClick={() => {
                              setError(null);
                              setMemberBusy(u.id);
                              void action(() =>
                                send(
                                  `/platform/organizations/${initial.id}/admins/${u.id}`,
                                  { active: !u.active },
                                  "PATCH",
                                ),
                              )
                                .catch(setError)
                                .finally(() => setMemberBusy(null));
                            }}
                          >
                            {u.active ? "Deactivate" : "Reactivate"}
                          </button>
                          {u.active &&
                            d.members.filter(
                              (m) => m.role === "admin" && m.active,
                            ).length === 1 && (
                              <small>Keep one active administrator.</small>
                            )}
                        </div>
                      ) : (
                        <span className="muted">
                          Managed in company workspace
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </Table>
              {administrator && (
                <FormDialog
                  title={
                    administrator === true
                      ? "Add company administrator"
                      : "Edit company administrator"
                  }
                  description="Administrators use a team seat. Changing a login phone, password or active status revokes that administrator's existing sessions. Existing authenticator settings are retained."
                  fields={[
                    {
                      name: "name",
                      label: "Administrator name",
                      required: true,
                      maxLength: 120,
                    },
                    {
                      name: "phone",
                      label: "Administrator login phone",
                      required: true,
                      maxLength: 30,
                      hint: "Include country code, e.g. +91",
                    },
                    {
                      name: "password",
                      label:
                        administrator === true
                          ? "Administrator password"
                          : "New password (optional)",
                      type: "password",
                      required: administrator === true,
                      maxLength: 200,
                      hint:
                        administrator === true
                          ? "At least 12 characters"
                          : "Leave blank to keep the password. A new password needs at least 12 characters.",
                    },
                  ]}
                  initial={
                    administrator === true
                      ? {}
                      : { name: administrator.name, phone: administrator.phone }
                  }
                  submitLabel={
                    administrator === true
                      ? "Create administrator"
                      : "Save administrator"
                  }
                  onClose={() => setAdministrator(null)}
                  onSubmit={(v) =>
                    action(() =>
                      administrator === true
                        ? send(`/platform/organizations/${initial.id}/admins`, {
                            ...v,
                            role: "admin",
                          })
                        : send(
                            `/platform/organizations/${initial.id}/admins/${administrator.id}`,
                            {
                              name: v.name,
                              phone: v.phone,
                              ...(v.password ? { password: v.password } : {}),
                            },
                            "PATCH",
                          ),
                    )
                  }
                />
              )}
              {terms && (
                <FormDialog
                  title="Manage company subscription"
                  description="Direct changes are recorded in the audit log. Use payment review to activate received UPI or cash payments. Expiry is tracked; workspace suspension is managed separately."
                  dependencies={[plans]}
                  fields={[
                    {
                      name: "plan_id",
                      label: "Subscription plan",
                      options: (plans.data?.plans || []).map((p) => ({
                        value: p.id,
                        label: p.name,
                      })),
                    },
                    {
                      name: "status",
                      label: "Subscription status",
                      options: options([
                        "trial",
                        "active",
                        "past-due",
                        "cancelled",
                      ]),
                      required: true,
                      defaultValue: "trial",
                    },
                    {
                      name: "cycle",
                      label: "Billing cycle",
                      options: options(["monthly", "yearly"]),
                      required: true,
                      defaultValue: "monthly",
                    },
                    {
                      name: "seats",
                      label: "Maximum active team seats",
                      type: "number",
                      min: "1",
                      max: "10000",
                      required: true,
                      defaultValue: "5",
                    },
                    {
                      name: "starts_on",
                      label: "Subscription starts",
                      type: "date",
                      required: true,
                    },
                    {
                      name: "ends_on",
                      label: "Subscription ends",
                      type: "date",
                      required: true,
                    },
                  ]}
                  initial={d.subscription ? valuesOf(d.subscription) : {}}
                  onClose={() => setTerms(false)}
                  onSubmit={(v) =>
                    action(() =>
                      send(
                        `/platform/organizations/${initial.id}/subscription`,
                        {
                          ...v,
                          plan_id: v.plan_id || null,
                          seats: Number(v.seats),
                        },
                        "PUT",
                      ),
                    )
                  }
                />
              )}
            </>
          )}
        </Load>
      </div>
      <footer>
        <Button variant="secondary" onClick={close}>
          Close
        </Button>
        <Button onClick={support} disabled={!initial.active}>
          Enter audited support workspace
        </Button>
      </footer>
    </Dialog>
  );
}

interface PlatformBillingData {
  plans: Plan[];
  config: BillingConfig;
  payments: Payment[];
  pending: number;
  approved_amount: string;
}
const planFields: Field[] = [
  { name: "name", label: "Plan name", required: true, maxLength: 100 },
  {
    name: "seats",
    label: "Included team seats",
    type: "number",
    min: "1",
    max: "10000",
    step: "1",
    required: true,
  },
  {
    name: "monthly_price",
    label: "Monthly price (₹)",
    type: "number",
    min: "0.01",
    max: "99999999",
    step: "0.01",
    required: true,
  },
  {
    name: "yearly_price",
    label: "Yearly price (₹)",
    type: "number",
    min: "0.01",
    max: "99999999",
    step: "0.01",
    required: true,
  },
  {
    name: "description",
    label: "Plan description",
    type: "textarea",
    wide: true,
    maxLength: 1000,
  },
  {
    name: "active",
    label: "Available for companies to purchase",
    type: "checkbox",
    defaultValue: true,
  },
];

export function PlatformBillingPage() {
  const q = useData<PlatformBillingData>("/platform/billing"),
    [plan, setPlan] = useState<Plan | true | null>(null),
    [config, setConfig] = useState(false),
    [error, setError] = useState<unknown>(null),
    action = useAction();
  return (
    <>
      <PageHeading
        eyebrow="SUPER ADMIN · SUBSCRIPTIONS"
        title="Your plans. Flexible payments."
        description="Set subscription prices, enable UPI or cash collection, and verify each payment before activation."
        actions={
          <Button onClick={() => setPlan(true)}>
            <Plus size={17} />
            Create plan
          </Button>
        }
      />
      {error !== null && <ErrorBox error={error} />}
      <Load query={q}>
        {(d) => (
          <>
            <div className="billing-layout">
              <Panel
                title="Receive company payments"
                description="UPI uses your QR and transaction reference. Cash collection is confirmed by you after receipt."
              >
                <div className="payment-qr-preview">
                  {d.config.qr_ready ? (
                    <PrivateLogo
                      id="payment-qr"
                      path="/billing/qr"
                      alt="Your company subscription payment QR"
                    />
                  ) : (
                    <div className="qr-placeholder">
                      <QrCode size={54} strokeWidth={1} />
                      <strong>Add your payment QR</strong>
                      <p>
                        Upload a clear QR image and enter the account holder
                        name. UPI submissions become available when this is
                        ready.
                      </p>
                    </div>
                  )}
                </div>
                <h3>
                  {d.config.payee_name || "Payment account not configured"}
                </h3>
                <p>{d.config.upi_id}</p>
                <p className="preserve-lines muted">{d.config.instructions}</p>
                <div className="method-summary">
                  <Badge
                    value={
                      d.config.upi_enabled !== false ? "active" : "inactive"
                    }
                  />
                  <span>UPI / QR</span>
                </div>
                <div className="method-summary">
                  <Badge value={d.config.cod_enabled ? "active" : "inactive"} />
                  <span>Cash collection (COD)</span>
                </div>
                {d.config.cod_enabled && (
                  <p className="preserve-lines muted">
                    {d.config.cod_instructions ||
                      "Cash must be collected and confirmed by the super admin before activation."}
                  </p>
                )}
                <div className="inline-actions">
                  <Button variant="secondary" onClick={() => setConfig(true)}>
                    Edit payment instructions
                  </Button>
                  <UploadControl
                    label="Upload payment QR"
                    accept="image/png,image/jpeg,image/webp"
                    path="/platform/billing/qr"
                    onError={setError}
                  />
                </div>
              </Panel>
              <div>
                <div className="section-intro">
                  <h2>Subscription plans</h2>
                  <p>
                    Prices are in INR. Each company sees your active plans and
                    pays the displayed amount.
                  </p>
                </div>
                <div className="plan-grid">
                  {d.plans.map((p) => (
                    <article className="plan-card" key={p.id}>
                      <div className="estate-line">
                        <h3>{p.name}</h3>
                        <Badge value={p.active ? "active" : "inactive"} />
                      </div>
                      <strong className="plan-price">
                        {money(p.monthly_price)}
                        <small>/ month</small>
                      </strong>
                      <p>{money(p.yearly_price)} / year</p>
                      <p>
                        <Check size={16} />
                        {p.seats} active team seats
                      </p>
                      <p>{p.description}</p>
                      <Button variant="secondary" onClick={() => setPlan(p)}>
                        Edit plan
                      </Button>
                    </article>
                  ))}
                </div>
                {!d.plans.length && (
                  <Empty
                    title="Set your first subscription plan"
                    description="Choose your own prices and team seat limits. No paid plans are published until you create one."
                    action={
                      <Button onClick={() => setPlan(true)}>Create plan</Button>
                    }
                  />
                )}
              </div>
            </div>
            {config && (
              <FormDialog
                title="Payment methods & instructions"
                fields={[
                  {
                    name: "upi_enabled",
                    label: "Accept UPI / QR payments",
                    type: "checkbox",
                    defaultValue: true,
                  },
                  {
                    name: "cod_enabled",
                    label: "Accept cash collection (COD)",
                    type: "checkbox",
                  },
                  {
                    name: "payee_name",
                    label: "Receiving account / payee name",
                    maxLength: 160,
                    hint: "Required with a QR image before companies can submit UPI payments.",
                  },
                  {
                    name: "upi_id",
                    label: "UPI ID (optional)",
                    maxLength: 160,
                  },
                  {
                    name: "instructions",
                    label: "UPI payment instructions",
                    type: "textarea",
                    wide: true,
                    maxLength: 2000,
                  },
                  {
                    name: "cod_instructions",
                    label: "Cash collection instructions",
                    type: "textarea",
                    wide: true,
                    maxLength: 2000,
                    hint: "Explain who collects cash and how the company should arrange collection. Do not include account passwords.",
                  },
                ]}
                initial={valuesOf(d.config)}
                onClose={() => setConfig(false)}
                onSubmit={(v) =>
                  action(() => send("/platform/billing/config", v, "PUT"))
                }
              />
            )}
          </>
        )}
      </Load>
      {plan && (
        <FormDialog
          title={
            plan === true
              ? "Create subscription plan"
              : "Edit subscription plan"
          }
          fields={planFields}
          initial={plan === true ? {} : valuesOf(plan)}
          onClose={() => setPlan(null)}
          onSubmit={(v) =>
            action(() =>
              send(
                plan === true
                  ? "/platform/plans"
                  : "/platform/plans/" + plan.id,
                { ...v, seats: Number(v.seats) },
                plan === true ? "POST" : "PUT",
              ),
            )
          }
        />
      )}
    </>
  );
}

export function PaymentReviewsPage() {
  const q = useData<PlatformBillingData>("/platform/billing"),
    [status, setStatus] = useState("pending"),
    [method, setMethod] = useState(""),
    [review, setReview] = useState<Payment | null>(null),
    [error, setError] = useState<unknown>(null),
    action = useAction();
  return (
    <>
      <PageHeading
        eyebrow="SUPER ADMIN · PAYMENT REVIEW"
        title="Verify the payment. Activate the company."
        description="Verify UPI references against your receiving account, or confirm cash collected in person. Submissions never activate a plan automatically."
      />
      {error !== null && <ErrorBox error={error} />}
      <Load query={q}>
        {(d) => (
          <>
            <div className="stats-grid">
              <Stat
                label="Awaiting verification"
                value={d.pending}
                detail="UPI claims and cash collection requests"
                accent
              />
              <Stat
                label="Verified subscription receipts"
                value={money(d.approved_amount)}
                detail="Total approved by super admin"
              />
            </div>
            <div className="filter-row">
              <select
                aria-label="Payment review filter"
                value={status}
                onChange={(e) => setStatus(e.target.value)}
              >
                <option value="">All submissions</option>
                {["pending", "approved", "rejected"].map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
              <select
                aria-label="Payment method filter"
                value={method}
                onChange={(e) => setMethod(e.target.value)}
              >
                <option value="">All payment methods</option>
                <option value="upi">UPI / QR</option>
                <option value="cod">Cash (COD)</option>
              </select>
            </div>
            <Panel>
              <PaymentTable
                payments={d.payments.filter(
                  (p) =>
                    (!status || p.status === status) &&
                    (!method || (p.payment_method || "upi") === method),
                )}
                owner
                onReview={setReview}
                onError={setError}
              />
            </Panel>
          </>
        )}
      </Load>
      {review && (
        <FormDialog
          title={"Verify payment from " + review.company_name}
          description={`${money(review.amount)} · ${review.plan_name} · ${review.cycle} · ${review.payment_method === "cod" ? "Cash collection (COD). Only approve after physically receiving the cash." : `UPI reference ${review.reference}. Only approve after confirming receipt in your bank/UPI app.`} Approval activates or extends this company's subscription.`}
          fields={[
            {
              name: "status",
              label: "Verification decision",
              options: [
                {
                  value: "approved",
                  label:
                    review.payment_method === "cod"
                      ? "Cash received — approve"
                      : "Payment received — approve",
                },
                { value: "rejected", label: "Could not verify — reject" },
              ],
              required: true,
            },
            ...(review.payment_method === "cod"
              ? [
                  {
                    name: "cash_received",
                    label: `I confirm ${money(review.amount)} cash was received`,
                    type: "checkbox",
                    wide: true,
                    hint: "Required when approving. Leave unchecked if you reject an uncollected request.",
                  },
                ]
              : []),
            {
              name: "note",
              label: "Verification note",
              type: "textarea",
              min: "3",
              maxLength: 2000,
              required: true,
              wide: true,
            },
          ]}
          onClose={() => setReview(null)}
          submitLabel="Save verification decision"
          onSubmit={(v) =>
            action(() => send(`/platform/payments/${review.id}/review`, v))
          }
        />
      )}
    </>
  );
}

function PaymentTable({
  payments,
  owner = false,
  onReview,
  onError,
}: {
  payments: Payment[];
  owner?: boolean;
  onReview?: (p: Payment) => void;
  onError: (e: unknown) => void;
}) {
  return payments.length ? (
    <Table
      headers={[
        ...(owner ? ["Company"] : []),
        "Plan / reference",
        "Method",
        "Amount",
        "Submitted",
        "Verification",
        "Receipt / action",
      ]}
    >
      {payments.map((p) => (
        <tr key={p.id}>
          {owner && <td>{p.company_name}</td>}
          <td>
            <strong>
              {p.plan_name} · {p.cycle}
            </strong>
            <small className="block">
              {p.reference || `Collection #${p.id.slice(0, 8)}`}
            </small>
          </td>
          <td>{p.payment_method === "cod" ? "Cash (COD)" : "UPI / QR"}</td>
          <td>{money(p.amount)}</td>
          <td>{dateTime(p.created_at)}</td>
          <td>
            <Badge value={p.status} />
            {p.review_note && (
              <small className="block muted">{p.review_note}</small>
            )}
          </td>
          <td>
            {p.receipt_id && (
              <button
                className="text-button"
                onClick={() =>
                  void download(
                    owner
                      ? `/platform/payments/${p.id}/receipt`
                      : "/files/" + p.receipt_id,
                    "payment-receipt",
                  ).catch(onError)
                }
              >
                <Download size={15} />
                Receipt
              </button>
            )}
            {owner && p.status === "pending" && (
              <Button variant="secondary" onClick={() => onReview?.(p)}>
                Verify payment
              </Button>
            )}
          </td>
        </tr>
      ))}
    </Table>
  ) : (
    <Empty
      title="No payment submissions here"
      description={
        owner
          ? "UPI payment claims and cash collection requests will appear here."
          : "Submit a UPI reference or request cash collection for your chosen plan."
      }
    />
  );
}

export function CompanyBillingPage() {
  const q = useData<BillingData>("/billing"),
    [cycle, setCycle] = useState("monthly"),
    [plan, setPlan] = useState<Plan | null>(null),
    [paymentMethod, setPaymentMethod] = useState<"upi" | "cod">("upi"),
    [error, setError] = useState<unknown>(null);
  return (
    <>
      <PageHeading
        eyebrow="YOUR COMPANY SUBSCRIPTION"
        title="A workspace that grows with your team."
        description="Choose a plan and an available payment method. The super admin activates it after verifying UPI receipt or collected cash."
      />
      {error !== null && <ErrorBox error={error} />}
      <Load query={q}>
        {(d) => (
          <>
            {d.subscription && (
              <div className="subscription-strip">
                <div>
                  <span className="eyebrow">CURRENT PLAN</span>
                  <h2>{d.subscription.plan_name}</h2>
                  <p>
                    {d.subscription.used_seats} of {d.subscription.seats} team
                    seats · {d.subscription.starts_on} to{" "}
                    {d.subscription.ends_on}
                  </p>
                </div>
                <Badge value={d.subscription.effective_status} />
              </div>
            )}
            {d.payments.some((p) => p.status === "pending") && (
              <div className="billing-notice">
                <ShieldCheck size={22} />
                <div>
                  <strong>
                    {d.payments.some(
                      (p) =>
                        p.status === "pending" && p.payment_method === "cod",
                    )
                      ? "Your cash collection is pending"
                      : "Your payment is awaiting verification"}
                  </strong>
                  <p>
                    {d.payments.some(
                      (p) =>
                        p.status === "pending" && p.payment_method === "cod",
                    )
                      ? "Arrange collection as instructed. The super admin activates your plan after confirming cash received. No further request is needed."
                      : "The super admin will check the transaction before activating your plan. No further submission is needed."}
                  </p>
                </div>
              </div>
            )}
            {d.config.upi_enabled !== false && !d.config.qr_ready && (
              <div className="billing-notice">
                <QrCode size={22} />
                <p>
                  The super admin is setting up the payment QR. Contact your
                  company administrator before making a payment.
                </p>
              </div>
            )}
            <div className="estate-section-heading">
              <div>
                <h2>Choose your plan</h2>
                <p>
                  All prices are in INR. Team seats include company admins,
                  managers and telecallers.
                </p>
              </div>
              <select
                aria-label="Subscription billing cycle"
                value={cycle}
                onChange={(e) => setCycle(e.target.value)}
              >
                <option value="monthly">Monthly billing</option>
                <option value="yearly">Yearly billing</option>
              </select>
            </div>
            <div className="plan-grid">
              {d.plans.map((p) => (
                <article className="plan-card" key={p.id}>
                  <CreditCard size={23} />
                  <h3>{p.name}</h3>
                  <strong className="plan-price">
                    {money(
                      cycle === "monthly" ? p.monthly_price : p.yearly_price,
                    )}
                    <small>/ {cycle === "monthly" ? "month" : "year"}</small>
                  </strong>
                  <p>{p.seats} active team seats</p>
                  <p>{p.description}</p>
                  <div className="plan-payment-actions">
                    {d.config.upi_enabled !== false && (
                      <Button
                        disabled={
                          !d.config.qr_ready ||
                          d.payments.some((v) => v.status === "pending")
                        }
                        onClick={() => {
                          setPaymentMethod("upi");
                          setPlan(p);
                        }}
                      >
                        <QrCode size={16} />
                        Pay using QR
                      </Button>
                    )}
                    {d.config.cod_enabled && (
                      <Button
                        variant="secondary"
                        disabled={d.payments.some(
                          (v) => v.status === "pending",
                        )}
                        onClick={() => {
                          setPaymentMethod("cod");
                          setPlan(p);
                        }}
                      >
                        <Banknote size={16} />
                        Pay cash (COD)
                      </Button>
                    )}
                  </div>
                  {d.config.upi_enabled === false && !d.config.cod_enabled && (
                    <p className="help-text">
                      Payment methods are paused. Contact the super admin.
                    </p>
                  )}
                </article>
              ))}
            </div>
            {!d.plans.length && (
              <Empty
                title="Plans are being configured"
                description="Your super admin will publish subscription options here."
              />
            )}
            <Panel
              title="Payment history"
              description="Submitted references and the super admin's verification decisions."
            >
              <PaymentTable payments={d.payments} onError={setError} />
            </Panel>
            {plan && (
              <PayByQr
                plan={plan}
                cycle={cycle}
                config={d.config}
                paymentMethod={paymentMethod}
                close={() => setPlan(null)}
              />
            )}
          </>
        )}
      </Load>
    </>
  );
}

function PayByQr({
  plan,
  cycle,
  config,
  paymentMethod,
  close,
}: {
  plan: Plan;
  cycle: string;
  config: BillingConfig;
  paymentMethod: "upi" | "cod";
  close: () => void;
}) {
  const [reference, setReference] = useState(""),
    [receipt, setReceipt] = useState<File | null>(null),
    [confirmed, setConfirmed] = useState(false),
    [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false),
    [requestId] = useState(() => crypto.randomUUID()),
    action = useAction();
  const amount = cycle === "monthly" ? plan.monthly_price : plan.yearly_price;
  const cash = paymentMethod === "cod";
  return (
    <Dialog
      title={(cash ? "Pay cash for " : "Pay for ") + plan.name}
      onClose={() => {
        if (!busy) close();
      }}
      description={
        cash
          ? "Arrange cash collection using the instructions below. Your plan activates after the super admin confirms receiving the money."
          : "Scan the QR in your UPI or banking app. Confirm the payee and amount there before paying."
      }
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (busy || !confirmed) return;
          const body = new FormData();
          body.set("plan_id", plan.id);
          body.set("cycle", cycle);
          body.set("payment_method", paymentMethod);
          if (!cash) body.set("reference", reference);
          body.set("request_id", requestId);
          body.set("quoted_amount", amount);
          if (!cash && receipt) body.set("receipt", receipt);
          setBusy(true);
          setError(null);
          void action(() => api("/billing/payments", { method: "POST", body }))
            .then(close)
            .catch(setError)
            .finally(() => setBusy(false));
        }}
      >
        <div className={cash ? "cash-checkout" : "qr-checkout"}>
          {!cash && (
            <div className="payment-qr-preview">
              <PrivateLogo
                id="company-pay-qr"
                path="/billing/qr"
                alt="Scan this QR to pay your subscription"
              />
            </div>
          )}
          <div>
            <span className="eyebrow">
              {cash ? "CASH TO COLLECT" : "PAY THIS AMOUNT"}
            </span>
            <h2>{money(amount)}</h2>
            <p>
              {plan.name} · {cycle} · {plan.seats} seats
            </p>
            {cash ? (
              <>
                <p className="preserve-lines">
                  {config.cod_instructions ||
                    "Contact the super admin to arrange cash collection."}
                </p>
                <p className="help-text">
                  This is a collection request. It does not mean cash has been
                  received.
                </p>
              </>
            ) : (
              <>
                <strong>{config.payee_name}</strong>
                {config.upi_id && (
                  <p className="copyable-upi">{config.upi_id}</p>
                )}
                <p className="preserve-lines">{config.instructions}</p>
              </>
            )}
          </div>
        </div>
        <div className="form-grid">
          {!cash && (
            <>
              <label className="field wide">
                <span>Transaction reference / UTR *</span>
                <input
                  required
                  minLength={4}
                  maxLength={80}
                  pattern="[A-Za-z0-9/-]+"
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                  placeholder="Copy the reference from your successful payment"
                />
              </label>
              <label className="field wide">
                <span>Payment receipt (optional)</span>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp,application/pdf"
                  onChange={(e) => setReceipt(e.target.files?.[0] || null)}
                />
                <small>PNG, JPEG, WebP or PDF, up to 5 MB.</small>
              </label>
            </>
          )}
          <label className="field check-field wide">
            <input
              type="checkbox"
              checked={confirmed}
              required
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            <span>
              {cash
                ? `I will pay ${money(amount)} in cash. Activation requires confirmed receipt.`
                : `I have paid ${money(amount)} to the payee shown above.`}
            </span>
          </label>
        </div>
        <p className="help-text">
          {cash
            ? "The super admin must confirm collecting the cash before approving your subscription."
            : "Submitting a reference does not confirm payment. Your super admin verifies the money received before activation."}
        </p>
        {error !== null && <ErrorBox error={error} />}
        <footer>
          <Button
            type="button"
            variant="secondary"
            disabled={busy}
            onClick={close}
          >
            Cancel
          </Button>
          <Button disabled={busy || !confirmed}>
            {busy
              ? "Submitting…"
              : cash
                ? "Request cash collection"
                : "Submit payment for verification"}
          </Button>
        </footer>
      </form>
    </Dialog>
  );
}

export function CompanyProfilePanel() {
  const { session } = useAuth(),
    q = useData<{ settings: { company_profile?: CompanyProfile } }>(
      "/settings",
    );
  const [edit, setEdit] = useState(false),
    action = useAction();
  return (
    <Panel
      title="Real estate company profile"
      description="Your agency's business and contact details."
      action={
        <Button variant="secondary" onClick={() => setEdit(true)}>
          Edit company profile
        </Button>
      }
    >
      <Load query={q}>
        {(d) => (
          <dl className="brief-grid">
            {companyProfileFields.map((f) => (
              <div key={f.name}>
                <dt>{f.label}</dt>
                <dd>
                  {d.settings.company_profile?.[
                    f.name as keyof CompanyProfile
                  ] || "Not recorded"}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </Load>
      {edit && (
        <FormDialog
          title="Edit real estate company profile"
          fields={companyProfileFields}
          initial={valuesOf(
            q.data?.settings.company_profile ||
              session?.organization?.settings.company_profile ||
              {},
          )}
          dependencies={[q]}
          onClose={() => setEdit(false)}
          onSubmit={(v) => action(() => send("/company-profile", v, "PUT"))}
        />
      )}
    </Panel>
  );
}
