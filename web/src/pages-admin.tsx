import { useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  Building2,
  Check,
  Download,
  ExternalLink,
  FileArchive,
  KeyRound,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
  Upload,
  Zap,
} from "lucide-react";
import { api, download, params, send, setSession } from "./api";
import { PrivateLogo, useAction, useAuth, useData, useDirectory } from "./main";
import { CompanyProfilePanel } from "./pages-billing";
import type {
  Audit,
  Automation,
  AutomationRun,
  Definition,
  Integration,
  Organization,
  Session,
  SyncRun,
  User,
  WorkspaceSettings,
} from "./types";
import {
  Badge,
  Button,
  Dialog,
  Empty,
  ErrorBox,
  Fields,
  FormDialog,
  QueryNotice,
  Load,
  PageHeading,
  Panel,
  Stat,
  Table,
  dateTime,
  options,
  type Field,
  type Values,
} from "./ui";

export function PlatformPage() {
  const nav = useNavigate();
  const action = useAction();
  const q = useData<{
    organizations: Organization[];
    total: number;
    active: number;
    users: number;
    leads: number;
  }>("/platform");
  const [dialog, setDialog] = useState<Organization | "new" | null>(null);
  const [detail, setDetail] = useState<Organization | null>(null);
  const [remove, setRemove] = useState<Organization | null>(null);
  const [error, setError] = useState<unknown>(null);
  const info = useData<{ organization: Organization; members: User[] }>(
    `/platform/organizations/${detail?.id}`,
    !!detail,
  );
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
        eyebrow="PLATFORM WORKSPACE"
        title="Room for every organization."
        description="Independent workspaces. Deliberate access. A clear platform view."
        actions={
          <Button onClick={() => setDialog("new")}>
            <Plus size={17} />
            Create organization
          </Button>
        }
      />
      {error !== null && <ErrorBox error={error} />}
      <Load query={q}>
        {(data) => (
          <>
            <div className="stats-grid">
              <Stat
                label="Organizations"
                value={data.total}
                detail="Independent client workspaces"
                accent
              />
              <Stat
                label="Active organizations"
                value={data.active}
                detail={`${data.total - data.active} suspended`}
              />
              <Stat
                label="Organization members"
                value={data.users}
                detail="Across client organizations"
              />
              <Stat
                label="Active lead records"
                value={data.leads}
                detail="Across client organizations"
              />
            </div>
            <Panel
              title="Organizations"
              description="Use a recorded support session to access a client workspace."
            >
              {data.organizations.length ? (
                <Table
                  headers={[
                    "Organization",
                    "Members",
                    "Leads",
                    "Created",
                    "State",
                    "Actions",
                  ]}
                >
                  {data.organizations.map((o) => (
                    <tr key={o.id}>
                      <td>
                        <button
                          className="text-button strong"
                          onClick={() => setDetail(o)}
                        >
                          {o.name}
                        </button>
                      </td>
                      <td>{o.users}</td>
                      <td>{o.leads}</td>
                      <td>{dateTime(o.created_at)}</td>
                      <td>
                        <Badge value={o.active ? "active" : "suspended"} />
                      </td>
                      <td>
                        <div className="inline-actions">
                          <button onClick={() => setDialog(o)}>Edit</button>
                          <button
                            disabled={!o.active}
                            onClick={() => support(o.id)}
                          >
                            Support access ↗
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
                          <button onClick={() => setRemove(o)}>Delete</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </Table>
              ) : (
                <Empty
                  title="Create the first workspace"
                  description="Provision an organization and its initial administrator."
                />
              )}
            </Panel>
            <Panel
              title="Organization growth"
              description="Organizations created by calendar month"
            >
              <div className="growth-list">
                {Object.entries(
                  data.organizations.reduce<Record<string, number>>((r, o) => {
                    const month = o.created_at.slice(0, 7);
                    r[month] = (r[month] || 0) + 1;
                    return r;
                  }, {}),
                )
                  .sort()
                  .map(([month, count]) => (
                    <div key={month}>
                      <strong>{month}</strong>
                      <span>
                        {count} new organization{count !== 1 ? "s" : ""}
                      </span>
                      <div style={{ width: `${Math.min(count * 20, 100)}%` }} />
                    </div>
                  ))}
              </div>
            </Panel>
          </>
        )}
      </Load>
      {dialog && (
        <FormDialog
          title={
            dialog === "new"
              ? "Create an independent workspace"
              : "Edit organization"
          }
          fields={[
            { name: "name", label: "Organization name", required: true },
            ...(dialog === "new"
              ? [
                  {
                    name: "admin_name",
                    label: "First administrator",
                    required: true,
                  },
                  {
                    name: "phone",
                    label: "Administrator phone",
                    type: "tel",
                    required: true,
                  },
                  {
                    name: "password",
                    label: "Initial password",
                    type: "password",
                    required: true,
                    hint: "At least 12 characters. Share securely.",
                  },
                ]
              : []),
          ]}
          initial={dialog === "new" ? {} : { name: dialog.name }}
          onClose={() => setDialog(null)}
          onSubmit={(v) =>
            action(() =>
              dialog === "new"
                ? send("/platform/organizations", {
                    name: v.name,
                    admin: {
                      name: v.admin_name,
                      phone: v.phone,
                      password: v.password,
                      role: "admin",
                    },
                  })
                : send(
                    `/platform/organizations/${dialog.id}`,
                    { name: v.name },
                    "PATCH",
                  ),
            )
          }
        />
      )}
      {detail && (
        <Dialog title={detail.name} onClose={() => setDetail(null)}>
          <div className="dialog-content">
            <Load query={info}>
              {(d) => (
                <Table headers={["Member", "Role", "State"]}>
                  {d.members.map((u) => (
                    <tr key={u.id}>
                      <td>{u.name}</td>
                      <td>
                        <Badge value={u.role} />
                      </td>
                      <td>
                        <Badge value={u.active ? "active" : "inactive"} />
                      </td>
                    </tr>
                  ))}
                </Table>
              )}
            </Load>
            <p className="help-text">
              Branding and logos can be managed through a recorded support
              session in Workspace settings.
            </p>
          </div>
          <footer>
            <Button
              onClick={() => support(detail.id)}
              disabled={!detail.active}
            >
              Enter support workspace <ArrowRight size={16} />
            </Button>
          </footer>
        </Dialog>
      )}
      {remove && (
        <FormDialog
          title={`Delete ${remove.name}?`}
          description="Access will be revoked and the organization archived. Records are retained for operator-assisted recovery."
          fields={[
            {
              name: "confirmation",
              label: `Type “${remove.name}” to confirm`,
              required: true,
            },
          ]}
          submitLabel="Delete organization"
          onClose={() => setRemove(null)}
          onSubmit={(v) =>
            action(() =>
              api(
                `/platform/organizations/${remove.id}?confirmation=${encodeURIComponent(String(v.confirmation))}`,
                { method: "DELETE" },
              ),
            )
          }
        />
      )}
    </>
  );
}

export function SettingsPage() {
  const { session } = useAuth();
  const q = useData<{ name: string; settings: WorkspaceSettings }>("/settings");
  const defs = useData<Definition[]>("/definitions");
  const exceptions = useData<
    { id: string; day: string; working: boolean; label: string }[]
  >("/schedule-exceptions");
  const action = useAction();
  const [values, setValues] = useState<Values>({});
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [success, setSuccess] = useState(false);
  const [busy, setBusy] = useState(false);
  const [edit, setEdit] = useState<Definition | true | null>(null);
  const [holiday, setHoliday] = useState(false);
  useEffect(() => {
    if (dirty) return;
    if (q.data) {
      const s = q.data.settings;
      setValues({
        name: q.data.name,
        brand_name: s.brand_name || "",
        pharma_enabled: !!s.pharma_enabled,
        weekdays: (s.weekdays || [0, 1, 2, 3, 4]).join(","),
        daily_hours: s.daily_hours || "8",
        configure: !!s.workplace,
        workplace_name: s.workplace?.name || "",
        latitude: String(s.workplace?.latitude ?? ""),
        longitude: String(s.workplace?.longitude ?? ""),
        radius: String(s.workplace?.radius || 200),
        timezone: s.workplace?.timezone || "Asia/Kolkata",
      });
      setDirty(false);
    }
  }, [q.data, dirty]);
  const fields: Field[] = [
    { name: "name", label: "Organization name", required: true },
    { name: "brand_name", label: "Workspace brand name" },
    {
      name: "weekdays",
      label: "Working weekdays",
      required: true,
      hint: "0 Monday through 6 Sunday, comma-separated.",
    },
    {
      name: "daily_hours",
      label: "Standard daily target hours",
      type: "number",
      step: ".01",
      min: ".01",
      max: "24",
      required: true,
    },
    {
      name: "pharma_enabled",
      label: "Enable healthcare / pharma qualification fields",
      type: "checkbox",
      wide: true,
    },
    {
      name: "configure",
      label: "Configure geofenced workplace",
      type: "checkbox",
      wide: true,
    },
    ...(values.configure
      ? [
          { name: "workplace_name", label: "Workplace name", required: true },
          {
            name: "timezone",
            label: "Workplace IANA timezone",
            required: true,
          },
          {
            name: "latitude",
            label: "Latitude",
            type: "number",
            step: "any",
            min: "-90",
            max: "90",
            required: true,
          },
          {
            name: "longitude",
            label: "Longitude",
            type: "number",
            step: "any",
            min: "-180",
            max: "180",
            required: true,
          },
          {
            name: "radius",
            label: "Allowed radius (meters)",
            type: "number",
            min: "25",
            max: "5000",
            required: true,
          },
        ]
      : []),
  ];
  const definitionFields: Field[] = [
    {
      name: "kind",
      label: "Definition type",
      required: true,
      defaultValue: "field",
      options: options(["field", "category", "stage"]),
    },
    {
      name: "key",
      label: "Unique key",
      required: true,
      hint: "Lowercase letters, numbers, underscores or hyphens.",
    },
    { name: "label", label: "Display label", required: true },
    {
      name: "position",
      label: "Display order",
      type: "number",
      min: "0",
      defaultValue: "0",
    },
    {
      name: "type",
      label: "Custom-field type",
      options: options(["text", "number", "boolean", "date", "select"]),
      defaultValue: "text",
    },
    {
      name: "options",
      label: "Select options",
      hint: "One option per line.",
      type: "textarea",
    },
    { name: "required", label: "Custom field is required", type: "checkbox" },
    { name: "active", label: "Active", type: "checkbox", defaultValue: true },
    {
      name: "color",
      label: "Stage color",
      type: "color",
      defaultValue: "#137b65",
    },
    { name: "closed", label: "Stage is closed", type: "checkbox" },
    { name: "won", label: "Stage represents won", type: "checkbox" },
  ];
  return (
    <>
      <PageHeading
        eyebrow="MAKE THE WORKSPACE YOURS"
        title="Workspace settings"
        description="Configure the details that make this CRM fit your team."
      />
      {error !== null && <ErrorBox error={error} />}
      {success && (
        <div className="success-notice">
          <Check size={17} />
          Workspace settings saved.
        </div>
      )}
      <div className="settings-grid">
        <CompanyProfilePanel />
        <Panel
          title="Organization & working day"
          description="Workplace changes apply to future check-ins. Existing midnight cutoffs remain fixed."
        >
          <Load query={q}>
            {() => (
              <form
                className="settings-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  setBusy(true);
                  setError(null);
                  setSuccess(false);
                  void action(() =>
                    send(
                      "/settings",
                      {
                        name: values.name,
                        brand_name: values.brand_name,
                        weekdays: String(values.weekdays)
                          .split(",")
                          .map((x) => Number(x.trim())),
                        daily_hours: values.daily_hours,
                        pharma_enabled: values.pharma_enabled,
                        workplace: values.configure
                          ? {
                              name: values.workplace_name,
                              latitude: Number(values.latitude),
                              longitude: Number(values.longitude),
                              accuracy: 0,
                              radius: Number(values.radius),
                              timezone: values.timezone,
                            }
                          : null,
                      },
                      "PUT",
                    ),
                  )
                    .then(() => api<Session>("/auth/me"))
                    .then((s) => {
                      setSession(s);
                      setSuccess(true);
                      setDirty(false);
                    })
                    .catch(setError)
                    .finally(() => setBusy(false));
                }}
              >
                <Fields
                  fields={fields.filter(
                    (f) =>
                      !(
                        q.data?.settings.industry === "real_estate" &&
                        f.name === "pharma_enabled"
                      ),
                  )}
                  values={values}
                  set={(k, v) => {
                    setValues((s) => ({ ...s, [k]: v }));
                    setDirty(true);
                  }}
                />
                <Button disabled={busy || !dirty}>
                  {busy ? "Saving…" : "Save workspace settings"}
                </Button>
              </form>
            )}
          </Load>
        </Panel>
        <div>
          <Panel
            title="Organization logo"
            description="Transparent PNG and WebP assets keep their background."
          >
            <div className="settings-block">
              <div className="logo-placeholder">
                {session?.organization?.settings.logo_id ? (
                  <PrivateLogo
                    id={session.organization.settings.logo_id}
                    alt="Organization logo preview"
                  />
                ) : (
                  <Building2 size={30} />
                )}
                <span>
                  {session?.organization?.settings.logo_id
                    ? "Logo uploaded"
                    : "No logo uploaded"}
                </span>
              </div>
              <label className="button secondary">
                <Upload size={16} />
                Upload logo
                <input
                  className="visually-hidden"
                  aria-label="Upload organization logo"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      const data = new FormData();
                      data.set("file", file);
                      void action(() =>
                        api("/settings/logo", { method: "POST", body: data }),
                      )
                        .then(() => api<Session>("/auth/me"))
                        .then(setSession)
                        .catch(setError);
                    }
                  }}
                />
              </label>
              {session?.organization?.settings.logo_id && (
                <button
                  className="text-button"
                  onClick={() =>
                    void action(() =>
                      api("/settings/logo", { method: "DELETE" }),
                    )
                      .then(() => api<Session>("/auth/me"))
                      .then(setSession)
                      .catch(setError)
                  }
                >
                  Remove logo
                </button>
              )}
            </div>
          </Panel>
          <Panel
            title="Working-day exceptions"
            description="Holidays and one-off working days."
            action={
              <button className="text-button" onClick={() => setHoliday(true)}>
                <Plus size={15} />
                Add
              </button>
            }
          >
            <Load query={exceptions}>
              {(days) =>
                days.length ? (
                  <div className="exception-list">
                    {days.map((d) => (
                      <div key={d.id}>
                        <span>
                          <strong>{d.label}</strong>
                          <small>
                            {d.day} · {d.working ? "Working day" : "Holiday"}
                          </small>
                        </span>
                        <button
                          aria-label={`Remove ${d.label}`}
                          className="icon-button"
                          onClick={() =>
                            void action(() =>
                              api(`/schedule-exceptions/${d.id}`, {
                                method: "DELETE",
                              }),
                            ).catch(setError)
                          }
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <Empty
                    title="Your regular schedule applies"
                    description="Add a holiday or one-off working day."
                  />
                )
              }
            </Load>
          </Panel>
        </div>
      </div>
      <Panel
        title="Fields, categories & pipeline"
        description="Server-validated definitions for your workspace."
        action={
          <Button variant="secondary" onClick={() => setEdit(true)}>
            <Plus size={16} />
            Add definition
          </Button>
        }
      >
        <Load query={defs}>
          {(items) => (
            <Table
              headers={[
                "Label",
                "Type",
                "Key",
                "Configuration",
                "Order",
                "State",
                "Actions",
              ]}
            >
              {items.map((d) => (
                <tr key={d.id}>
                  <td>{d.label}</td>
                  <td>{d.kind}</td>
                  <td>
                    <code>{d.key}</code>
                  </td>
                  <td>
                    {d.kind === "field"
                      ? `${d.config.type}${d.config.required ? " · required" : ""}`
                      : d.kind === "stage"
                        ? d.config.won
                          ? "Won stage"
                          : d.config.closed
                            ? "Closed stage"
                            : "Open stage"
                        : "Category"}
                  </td>
                  <td>{d.position}</td>
                  <td>
                    <Badge value={d.active ? "active" : "inactive"} />
                  </td>
                  <td>
                    <div className="inline-actions">
                      <button onClick={() => setEdit(d)}>Edit</button>
                      <button
                        onClick={() =>
                          void action(() =>
                            api(`/definitions/${d.id}`, { method: "DELETE" }),
                          ).catch(setError)
                        }
                      >
                        Deactivate
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </Table>
          )}
        </Load>
      </Panel>
      {edit && (
        <FormDialog
          title={
            edit === true ? "Add a workspace definition" : "Edit definition"
          }
          fields={definitionFields}
          initial={
            edit === true
              ? {}
              : {
                  kind: edit.kind,
                  key: edit.key,
                  label: edit.label,
                  position: String(edit.position),
                  type: edit.config.type || "text",
                  options: edit.config.options?.join("\n") || "",
                  required: !!edit.config.required,
                  active: edit.active,
                  color: edit.config.color || "#137b65",
                  closed: !!edit.config.closed,
                  won: !!edit.config.won,
                }
          }
          description="Keys are permanent after creation. Field settings apply to custom fields; color and closed/won settings apply to stages."
          onClose={() => setEdit(null)}
          onSubmit={(v) =>
            action(() =>
              send(
                edit === true ? "/definitions" : `/definitions/${edit.id}`,
                {
                  kind: v.kind,
                  key: v.key,
                  label: v.label,
                  position: Number(v.position),
                  active: v.active,
                  config:
                    v.kind === "field"
                      ? {
                          type: v.type,
                          required: v.required,
                          ...(v.type === "select"
                            ? {
                                options: String(v.options)
                                  .split("\n")
                                  .map((x) => x.trim())
                                  .filter(Boolean),
                              }
                            : {}),
                        }
                      : v.kind === "stage"
                        ? { color: v.color, closed: v.closed, won: v.won }
                        : {},
                },
                edit === true ? "POST" : "PUT",
              ),
            )
          }
        />
      )}
      {holiday && (
        <FormDialog
          title="A day that’s different"
          fields={[
            { name: "day", label: "Date", type: "date", required: true },
            { name: "label", label: "Name / reason", required: true },
            {
              name: "working",
              label: "Treat as a working day",
              type: "checkbox",
            },
          ]}
          onClose={() => setHoliday(false)}
          onSubmit={(v) => action(() => send("/schedule-exceptions", v))}
        />
      )}
    </>
  );
}

export function AutomationsPage() {
  const { session } = useAuth();
  const q = useData<{ rules: Automation[]; runs: AutomationRun[] }>(
    "/automations",
  );
  const [edit, setEdit] = useState<Automation | true | null>(null);
  const action = useAction();
  const [error, setError] = useState<unknown>(null);
  const dir = useDirectory();
  return (
    <>
      <PageHeading
        eyebrow="GOOD PROCESS, LESS REPETITION"
        title="Automations"
        description="Optional automatic rules for repetitive work. Overdue callback alerts already appear in the bell without creating a rule."
        actions={
          session?.role === "admin" && (
            <Button onClick={() => setEdit(true)}>
              <Plus size={17} />
              Create rule
            </Button>
          )
        }
      />
      {error !== null && <ErrorBox error={error} />}
      <QueryNotice query={dir} />
      <Load query={q}>
        {(data) => (
          <>
            <div className="automation-grid">
              {data.rules.length ? (
                data.rules.map((r) => (
                  <Panel key={r.id}>
                    <div className="automation-card">
                      <div>
                        <span className="automation-icon">
                          <Zap size={22} />
                        </span>
                        <Badge value={r.enabled ? "enabled" : "paused"} />
                      </div>
                      <h2>{r.name}</h2>
                      <p>
                        When <strong>{r.trigger.replaceAll("_", " ")}</strong>
                      </p>
                      <p>
                        Then <strong>{r.action.replaceAll("_", " ")}</strong>
                      </p>
                      {Object.keys(r.conditions).length > 0 && (
                        <pre>{JSON.stringify(r.conditions, null, 2)}</pre>
                      )}
                      <div className="inline-actions">
                        {session?.role === "admin" && (
                          <>
                            <button onClick={() => setEdit(r)}>
                              Edit rule
                            </button>
                            <button
                              onClick={() =>
                                void action(() =>
                                  send(
                                    `/automations/${r.id}`,
                                    {
                                      name: r.name,
                                      trigger: r.trigger,
                                      conditions: r.conditions,
                                      action: r.action,
                                      config: r.config,
                                      enabled: !r.enabled,
                                    },
                                    "PUT",
                                  ),
                                ).catch(setError)
                              }
                            >
                              {r.enabled ? "Pause" : "Enable"}
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  </Panel>
                ))
              ) : (
                <Panel>
                  <Empty
                    title="A little less repetitive work"
                    description="Create tasks, add notes or hand leads to a manager when a rule matches."
                  />
                </Panel>
              )}
            </div>
            <Panel
              title="Execution history"
              description="Retries are idempotent; automation actions do not recursively trigger more automation."
            >
              {data.runs.length ? (
                <Table headers={["When", "Rule", "State", "Details"]}>
                  {data.runs.map((r) => (
                    <tr key={r.id}>
                      <td>{dateTime(r.created_at)}</td>
                      <td>
                        {data.rules.find((x) => x.id === r.rule_id)?.name ||
                          "Rule"}
                      </td>
                      <td>
                        <Badge value={r.state} />
                      </td>
                      <td>{r.error || "Action applied"}</td>
                    </tr>
                  ))}
                </Table>
              ) : (
                <Empty
                  title="No rule executions yet"
                  description="Matching events and scheduled callbacks will appear here."
                />
              )}
            </Panel>
          </>
        )}
      </Load>
      {edit && (
        <FormDialog
          dependencies={[dir]}
          title={
            edit === true ? "Create an internal automation" : "Edit automation"
          }
          description="Condition keys: status, source, category, stage. Every exposed trigger is handled by the durable worker."
          fields={[
            { name: "name", label: "Rule name", required: true, wide: true },
            {
              name: "trigger",
              label: "When this happens",
              required: true,
              options: options([
                "lead_created",
                "lead_assigned",
                "status_changed",
                "callback_due",
                "task_completed",
              ]),
              defaultValue: "lead_created",
            },
            {
              name: "action",
              label: "Take this action",
              required: true,
              options: options(["create_task", "add_note", "assign_manager"]),
              defaultValue: "create_task",
            },
            {
              name: "conditions",
              label: "Conditions (JSON)",
              type: "textarea",
              defaultValue: "{}",
              hint: 'Example: {"source":"website"}',
            },
            { name: "title", label: "Task title" },
            {
              name: "delay_minutes",
              label: "Task delay in minutes",
              type: "number",
              min: "0",
              defaultValue: "0",
            },
            { name: "text", label: "Note text", type: "textarea" },
            {
              name: "manager_id",
              label: "Selected manager",
              options: (dir.data || [])
                .filter((u) => u.role === "manager")
                .map((u) => ({ value: u.id, label: u.name })),
            },
            {
              name: "enabled",
              label: "Rule enabled",
              type: "checkbox",
              defaultValue: true,
            },
          ]}
          initial={
            edit === true
              ? {}
              : {
                  name: edit.name,
                  trigger: edit.trigger,
                  action: edit.action,
                  conditions: JSON.stringify(edit.conditions, null, 2),
                  title: String(edit.config.title || ""),
                  delay_minutes: String(edit.config.delay_minutes || 0),
                  text: String(edit.config.text || ""),
                  manager_id: String(edit.config.manager_id || ""),
                  enabled: edit.enabled,
                }
          }
          onClose={() => setEdit(null)}
          onSubmit={(v) => {
            let conditions: unknown;
            try {
              conditions = JSON.parse(String(v.conditions));
            } catch {
              throw new Error("Conditions must contain valid JSON");
            }
            return action(() =>
              send(
                edit === true ? "/automations" : `/automations/${edit.id}`,
                {
                  name: v.name,
                  trigger: v.trigger,
                  action: v.action,
                  conditions,
                  enabled: v.enabled,
                  config:
                    v.action === "create_task"
                      ? {
                          title: v.title,
                          delay_minutes: Number(v.delay_minutes),
                        }
                      : v.action === "add_note"
                        ? { text: v.text }
                        : { manager_id: v.manager_id },
                },
                edit === true ? "POST" : "PUT",
              ),
            );
          }}
        />
      )}
    </>
  );
}

export function IntegrationsPage() {
  const { session } = useAuth();
  const q = useData<{ items: Integration[]; runs: SyncRun[] }>("/integrations");
  const [edit, setEdit] = useState<Integration | null>(null);
  const [error, setError] = useState<unknown>(null);
  const action = useAction();
  return (
    <>
      <PageHeading
        eyebrow="CONNECT THE RIGHT PIECES"
        title="Integrations"
        description="Real adapters, clear setup and visible delivery history."
      />
      {error !== null && <ErrorBox error={error} />}
      <Load query={q}>
        {(data) => (
          <>
            <div className="integration-grid">
              {data.items.map((i) => (
                <Panel key={i.provider}>
                  <div className="integration-card">
                    <div>
                      <span className={`provider-logo ${i.provider}`}>
                        {i.provider === "indiamart" ? "im" : "JD"}
                      </span>
                      <Badge value={i.state} />
                    </div>
                    <h2>
                      {i.provider === "indiamart" ? "IndiaMART" : "Justdial"}
                    </h2>
                    <p>
                      {i.provider === "indiamart"
                        ? "Poll CRM enquiries using your credentialed IndiaMART account. A safe overlapping cursor prevents retry duplicates."
                        : "Receive lead enquiries through an organization-specific token-protected webhook."}
                    </p>
                    <dl className="detail-list">
                      <div>
                        <dt>Last delivery / sync</dt>
                        <dd>{dateTime(i.last_sync)}</dd>
                      </div>
                      <div>
                        <dt>Credential</dt>
                        <dd>
                          {i.configured
                            ? "Encrypted · masked"
                            : "Not configured"}
                        </dd>
                      </div>
                    </dl>
                    {i.last_error && (
                      <div className="error-box">
                        <p>{i.last_error}</p>
                      </div>
                    )}
                    {session?.role === "admin" && (
                      <div className="integration-actions">
                        <Button variant="secondary" onClick={() => setEdit(i)}>
                          {i.configured ? "Configure" : "Set up connection"}
                        </Button>
                        {i.configured && (
                          <>
                            <button
                              className="text-button"
                              onClick={() =>
                                void action(() =>
                                  send(
                                    `/integrations/${i.provider}`,
                                    { enabled: !i.enabled },
                                    "PUT",
                                  ),
                                ).catch(setError)
                              }
                            >
                              {i.enabled ? "Pause" : "Enable"}
                            </button>
                            {i.provider === "indiamart" && (
                              <button
                                className="text-button"
                                onClick={() =>
                                  void action(() =>
                                    api(`/integrations/${i.provider}/sync`, {
                                      method: "POST",
                                    }),
                                  ).catch(setError)
                                }
                              >
                                <RefreshCw size={14} />
                                Sync now
                              </button>
                            )}
                            <button
                              className="text-button"
                              onClick={() =>
                                void action(() =>
                                  api(`/integrations/${i.provider}`, {
                                    method: "DELETE",
                                  }),
                                ).catch(setError)
                              }
                            >
                              Disconnect
                            </button>
                          </>
                        )}
                      </div>
                    )}
                    <details>
                      <summary>Setup instructions</summary>
                      <p>
                        {i.provider === "indiamart"
                          ? "Generate a CRM key in the IndiaMART seller account. Confirm the current v2 API entitlement with the provider, then paste the key here. Polling runs every 15 minutes when the worker is online."
                          : "Agree lead-push activation and the payload mapping with your Justdial account manager. Use the endpoint below and send the configured secret in the X-Webhook-Token header."}
                      </p>
                      {i.provider === "justdial" && (
                        <code className="endpoint-code">
                          POST {window.location.origin}/api/webhooks/justdial/
                          {session?.organization?.id}
                        </code>
                      )}
                      <p className="help-text">
                        Setup does not verify provider delivery. A real
                        credential and successful delivery are required.
                        Provider-specific account contracts must be confirmed
                        before production use.
                      </p>
                    </details>
                  </div>
                </Panel>
              ))}
            </div>
            <Panel title="Delivery & sync history">
              {data.runs.length ? (
                <Table
                  headers={[
                    "When",
                    "State",
                    "Imported",
                    "Duplicates",
                    "Invalid",
                    "Details",
                  ]}
                >
                  {data.runs.map((r) => (
                    <tr key={r.id}>
                      <td>{dateTime(r.created_at)}</td>
                      <td>
                        <Badge value={r.state} />
                      </td>
                      <td>{r.imported}</td>
                      <td>{r.duplicates}</td>
                      <td>{r.invalid}</td>
                      <td>{r.error || "Completed"}</td>
                    </tr>
                  ))}
                </Table>
              ) : (
                <Empty
                  title="No deliveries yet"
                  description="Completed and failed runs appear here after an integration is configured."
                />
              )}
            </Panel>
            <p className="help-text">
              TradeIndia, website, manual and referral are lead source labels.
              They do not imply a connected external service.
            </p>
          </>
        )}
      </Load>
      {edit && (
        <FormDialog
          title={`Configure ${edit.provider === "indiamart" ? "IndiaMART" : "Justdial"}`}
          fields={[
            {
              name: "credential",
              label:
                edit.provider === "indiamart"
                  ? "CRM API key"
                  : "Private webhook token",
              type: "password",
              required: !edit.configured,
              hint: "Minimum 16 characters. Leave blank to preserve an existing credential.",
            },
            {
              name: "enabled",
              label: "Enable integration",
              type: "checkbox",
              defaultValue: true,
            },
          ]}
          onClose={() => setEdit(null)}
          onSubmit={(v) =>
            action(() =>
              send(
                `/integrations/${edit.provider}`,
                {
                  ...(v.credential ? { credential: v.credential } : {}),
                  enabled: v.enabled,
                },
                "PUT",
              ),
            )
          }
        />
      )}
    </>
  );
}

export function AuditPage() {
  const [qText, setQ] = useState("");
  const [actionFilter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<unknown>(null);
  const p = params({ q: qText, action: actionFilter, page });
  const q = useData<Audit[]>("/audit?" + p);
  return (
    <>
      <PageHeading
        eyebrow="THE CONTEXT BEHIND THE CHANGE"
        title="Audit trail"
        description="Who changed what, when, and where it came from."
        actions={
          <Button
            variant="secondary"
            onClick={() =>
              void download("/audit?" + p + "&export=true", "audit.csv").catch(
                setError,
              )
            }
          >
            <Download size={16} />
            Export audit
          </Button>
        }
      />
      <div className="filter-row">
        <input
          placeholder="Search audit summaries"
          aria-label="Search audit"
          value={qText}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
        />
        <input
          placeholder="Action, e.g. created"
          aria-label="Filter audit action"
          value={actionFilter}
          onChange={(e) => {
            setFilter(e.target.value);
            setPage(1);
          }}
        />
      </div>
      {error !== null && <ErrorBox error={error} />}
      <Panel>
        <Load query={q}>
          {(rows) =>
            rows.length ? (
              <>
                <Table
                  headers={[
                    "When",
                    "Entity",
                    "Action",
                    "What changed",
                    "Details",
                  ]}
                >
                  {rows.map((r) => (
                    <tr key={r.id}>
                      <td>{dateTime(r.created_at)}</td>
                      <td>{r.entity}</td>
                      <td>
                        <Badge value={r.action} />
                      </td>
                      <td>{r.summary}</td>
                      <td>
                        <details>
                          <summary>Inspect</summary>
                          <pre>{JSON.stringify(r.details, null, 2)}</pre>
                          <small>Actor: {r.actor_id || "System"}</small>
                        </details>
                      </td>
                    </tr>
                  ))}
                </Table>
                <div className="pagination">
                  <span>Page {page}</span>
                  <div>
                    <Button
                      variant="secondary"
                      disabled={page <= 1}
                      onClick={() => setPage(page - 1)}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={rows.length < 50}
                      onClick={() => setPage(page + 1)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              </>
            ) : (
              <Empty title="No matching changes" />
            )
          }
        </Load>
      </Panel>
    </>
  );
}

export function BackupsPage() {
  const q =
    useData<{ id: string; created_at: string; size: number }[]>("/backups");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const action = useAction();
  return (
    <>
      <PageHeading
        eyebrow="YOUR DATA, WITH YOU"
        title="Data snapshots"
        description="Download an organization-scoped application JSON snapshot."
        actions={
          <Button
            disabled={busy}
            onClick={() => {
              setBusy(true);
              void action(() => api("/backups", { method: "POST" }))
                .catch(setError)
                .finally(() => setBusy(false));
            }}
          >
            <Plus size={17} />
            {busy ? "Creating…" : "Create snapshot"}
          </Button>
        }
      />
      <div className="policy-box">
        <FileArchive size={25} />
        <div>
          <h3>An application snapshot</h3>
          <p>
            Includes permitted workspace records. Passwords, provider
            credentials, sessions and file bytes are excluded. For disaster
            recovery, back up PostgreSQL and private attachment storage together
            using the operator runbook.
          </p>
        </div>
      </div>
      {error !== null && <ErrorBox error={error} />}
      <Panel>
        <Load query={q}>
          {(rows) =>
            rows.length ? (
              <Table headers={["Created", "Format", "Size", "Actions"]}>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td>{dateTime(r.created_at)}</td>
                    <td>Application JSON</td>
                    <td>{Math.ceil(r.size / 1024)} KB</td>
                    <td>
                      <button
                        className="text-button"
                        onClick={() =>
                          void download(
                            "/backups/" + r.id,
                            "workspace-snapshot.json",
                          ).catch(setError)
                        }
                      >
                        <Download size={15} />
                        Download
                      </button>
                    </td>
                  </tr>
                ))}
              </Table>
            ) : (
              <Empty
                title="Keep a snapshot of your work"
                description="Create a snapshot to export your organization’s application data."
              />
            )
          }
        </Load>
      </Panel>
    </>
  );
}

export function SecurityPage() {
  const { session } = useAuth();
  const [dialog, setDialog] = useState("");
  const [setup, setSetup] = useState<{ secret: string; uri: string } | null>(
    null,
  );
  const me = useData<Session>("/auth/me");
  const action = useAction();
  const enabled = me.data?.user.totp_enabled ?? session?.user.totp_enabled;
  return (
    <>
      <PageHeading
        eyebrow="YOUR ACCOUNT, PROTECTED"
        title="Account & security"
        description="Manage your password and optional authenticator protection."
      />
      <QueryNotice query={me} />
      {session?.acting_as && (
        <p className="notice">
          You are signed in as this member. Their password and authenticator
          settings are protected during administrator access.
        </p>
      )}
      <div className="settings-grid">
        <Panel title="Your account">
          <dl className="detail-list account-details">
            <div>
              <dt>Name</dt>
              <dd>{session?.user.name}</dd>
            </div>
            <div>
              <dt>Login phone</dt>
              <dd>{session?.user.phone}</dd>
            </div>
            <div>
              <dt>Role</dt>
              <dd>
                <Badge value={session?.role || "member"} />
              </dd>
            </div>
            <div>
              <dt>Organization</dt>
              <dd>{session?.organization?.name || "Platform owner"}</dd>
            </div>
          </dl>
        </Panel>
        <div>
          <Panel
            title="Password"
            description="Changing your password revokes other sessions."
          >
            <div className="settings-block">
              <Button
                disabled={!!session?.acting_as}
                variant="secondary"
                onClick={() => setDialog("password")}
              >
                <KeyRound size={16} />
                Change password
              </Button>
            </div>
          </Panel>
          <Panel
            title="Authenticator app"
            description="Require a six-digit code when signing in."
          >
            <div className="settings-block">
              <Badge value={enabled ? "enabled" : "not enabled"} />
              <p className="help-text">
                Use an authenticator app that supports time-based one-time
                codes.
              </p>
              <Button
                disabled={!!session?.acting_as}
                variant="secondary"
                onClick={() => setDialog(enabled ? "disable" : "setup")}
              >
                <ShieldCheck size={16} />
                {enabled ? "Disable authenticator" : "Set up authenticator"}
              </Button>
            </div>
          </Panel>
        </div>
      </div>
      {dialog === "password" && (
        <FormDialog
          title="Change password"
          fields={[
            {
              name: "current",
              label: "Current password",
              type: "password",
              required: true,
            },
            {
              name: "password",
              label: "New password",
              type: "password",
              required: true,
              hint: "At least 12 characters.",
            },
          ]}
          onClose={() => setDialog("")}
          onSubmit={(v) => action(() => send("/auth/password", v))}
        />
      )}
      {dialog === "setup" && (
        <FormDialog
          title="Set up your authenticator"
          fields={[
            {
              name: "password",
              label: "Confirm your password",
              type: "password",
              required: true,
            },
          ]}
          submitLabel="Generate setup key"
          onClose={() => setDialog("")}
          onSubmit={(v) =>
            send<{ secret: string; uri: string }>("/auth/2fa/setup", v).then(
              setSetup,
            )
          }
        />
      )}
      {setup && (
        <Dialog
          title="Add the account to your authenticator"
          onClose={() => setSetup(null)}
        >
          <div className="dialog-content">
            <p>
              Add a new time-based account in your authenticator using this
              setup key.
            </p>
            <code className="setup-secret">{setup.secret}</code>
            <p className="help-text">
              Account: {session?.user.phone} · six digits · 30-second interval.
              Keep this key private.
            </p>
            <a className="text-button" href={setup.uri}>
              Open a compatible authenticator <ExternalLink size={14} />
            </a>
            <Button
              onClick={() => {
                setSetup(null);
                setDialog("enable");
              }}
            >
              I’ve added the account <ArrowRight size={16} />
            </Button>
          </div>
        </Dialog>
      )}
      {["enable", "disable"].includes(dialog) && (
        <FormDialog
          title={
            dialog === "enable"
              ? "Enable authenticator protection"
              : "Disable authenticator protection"
          }
          fields={[
            {
              name: "password",
              label: "Current password",
              type: "password",
              required: true,
            },
            {
              name: "code",
              label: "Six-digit authenticator code",
              required: true,
            },
          ]}
          onClose={() => setDialog("")}
          onSubmit={(v) => action(() => send(`/auth/2fa/${dialog}`, v))}
        />
      )}
    </>
  );
}
