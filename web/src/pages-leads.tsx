import { useEffect, useRef, useState } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  Download,
  File,
  GitMerge,
  History as HistoryIcon,
  Phone,
  Plus,
  ShieldAlert,
  Trash2,
  Upload,
  UserRound,
  Users,
  X,
} from "lucide-react";
import { api, download, params, send } from "./api";
import { useAction, useAuth, useData, useDirectory } from "./main";
import { BuyerBrief } from "./pages-estate";
import { LeadFieldWork } from "./pages-field";
import {
  LeadFilters,
  leadFilterKeys,
  normalizeLeadFilter,
} from "./lead-filters";
import type {
  Definition,
  FileItem,
  History,
  ImportResult,
  Lead,
  PhoneCall,
  SavedView,
  User,
} from "./types";
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
  QueryNotice,
  RecordingBadge,
  Table,
  dateTime,
  duration,
  money,
  options,
  type Field,
  type Values,
} from "./ui";

export const statuses = ["new", "follow-up", "not-picked", "converted", "lost"];
const sources = [
  "manual",
  "website",
  "referral",
  "indiamart",
  "justdial",
  "tradeindia",
  "99acres",
  "magicbricks",
  "housing",
  "walk-in",
  "property-expo",
  "broker",
];
function toDate(value: string | boolean | undefined) {
  return value ? new Date(String(value)).toISOString() : null;
}
export function LeadPicker({
  value,
  onChange,
  label = "Related lead",
  excludeId,
  required = false,
}: {
  value: string;
  onChange: (value: string) => void;
  label?: string;
  excludeId?: string;
  required?: boolean;
}) {
  const [search, setSearch] = useState("");
  const choices = useData<{ items: Lead[]; total: number }>(
    "/leads?" + params({ q: search, size: 25 }),
  );
  const selected = useData<Lead>(`/leads/${value}`, !!value);
  const options = (choices.data?.items || []).filter(
    (lead) => lead.id !== excludeId,
  );
  if (
    selected.data &&
    selected.data.id !== excludeId &&
    !options.some((lead) => lead.id === value)
  )
    options.unshift(selected.data);
  return (
    <>
      <label className="field">
        <span>Search {label.toLowerCase()}</span>
        <input
          aria-label={`Search ${label.toLowerCase()}`}
          type="search"
          value={search}
          placeholder="Search by customer name, phone or city"
          onChange={(event) => setSearch(event.target.value)}
        />
      </label>
      <label className="field">
        <span>{label}</span>
        <select
          aria-label={label}
          required={required}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="">Select a lead…</option>
          {value && !options.some((lead) => lead.id === value) && (
            <option value={value}>
              {selected.isPending
                ? "Loading selected lead…"
                : "Selected lead unavailable — choose another"}
            </option>
          )}
          {options.map((lead) => (
            <option key={lead.id} value={lead.id}>
              {lead.name} · {lead.phone}
            </option>
          ))}
        </select>
      </label>
      <small className="muted">
        {choices.isPending
          ? "Searching leads…"
          : `${choices.data?.total ?? 0} matches. Refine your search to find older records.`}
      </small>
      <QueryNotice query={choices} />
      {value && <QueryNotice query={selected} />}
    </>
  );
}
const interestsField: Field = {
  name: "interests",
  label: "Property / project interests",
  type: "textarea",
  wide: true,
  maxLength: 9629,
  hint: "Enter one property, project or requirement per line, based on what the customer tells you. Up to 30 items, 160 characters each.",
};
function interestValues(value: string | boolean | undefined) {
  return String(value || "")
    .split(/\r?\n|\|/)
    .map((item) => item.trim())
    .filter(Boolean);
}
export function LeadForm({
  lead,
  onClose,
}: {
  lead?: Lead;
  onClose: () => void;
}) {
  const { session } = useAuth();
  const defs = useData<Definition[]>("/definitions");
  const action = useAction();
  const realEstate = session?.organization?.settings.industry === "real_estate";
  const pharmaEnabled =
    !realEstate && !!session?.organization?.settings.pharma_enabled;
  const fields: Field[] = [
    { name: "name", label: "Customer / buyer name", required: true },
    {
      name: "phone",
      label: "Phone number",
      required: true,
      type: "tel",
      hint: "Use +country code for international numbers.",
    },
    { name: "city", label: "City" },
    { name: "state", label: "State / region" },
    {
      name: "source",
      label: "Lead source",
      required: true,
      options: options(sources),
      defaultValue: "manual",
    },
    {
      name: "stage",
      label: "Pipeline stage",
      required: true,
      options: (defs.data || [])
        .filter((d) => d.kind === "stage" && d.active)
        .map((d) => ({ value: d.key, label: d.label })),
      defaultValue: "new",
    },
    interestsField,
    { name: "dnd", label: "Do not disturb", type: "checkbox" },
    { name: "notes", label: "Initial notes", type: "textarea", wide: true },
  ];
  if (realEstate || pharmaEnabled) {
    fields.splice(6, 0, {
      name: "category",
      label: realEstate ? "Property category" : "Primary category",
      options: [
        ...(defs.data || [])
          .filter((d) => d.kind === "category" && d.active)
          .map((d) => ({ value: d.key, label: d.label })),
        ...(lead?.category &&
        !defs.data?.some(
          (d) => d.kind === "category" && d.active && d.key === lead.category,
        )
          ? [
              {
                value: lead.category,
                label:
                  (defs.data?.find(
                    (d) => d.kind === "category" && d.key === lead.category,
                  )?.label || lead.category) + " (previous category)",
              },
            ]
          : []),
      ],
    });
  }
  if (pharmaEnabled) {
    fields.splice(
      7,
      0,
      { name: "drug_license", label: "Drug license number" },
      { name: "specialty", label: "Specialty" },
      {
        name: "credit_limit",
        label: "Credit limit",
        type: "number",
        min: "0",
        step: ".01",
      },
      {
        name: "outstanding",
        label: "Outstanding",
        type: "number",
        min: "0",
        step: ".01",
      },
    );
  }
  for (const d of defs.data || []) {
    if (d.kind === "field" && d.active)
      fields.push({
        name: "custom." + d.key,
        label: d.label,
        required: !!d.config.required,
        type:
          d.config.type === "boolean"
            ? "checkbox"
            : d.config.type === "date"
              ? "date"
              : d.config.type === "number"
                ? "number"
                : "text",
        step: d.config.type === "number" ? "any" : undefined,
        options:
          d.config.type === "select"
            ? [
                ...options(d.config.options || []),
                ...(typeof lead?.custom[d.key] === "string" &&
                !(d.config.options || []).includes(String(lead.custom[d.key]))
                  ? [
                      {
                        value: String(lead.custom[d.key]),
                        label: String(lead.custom[d.key]) + " (previous value)",
                      },
                    ]
                  : []),
              ]
            : undefined,
      });
  }
  const initial: Values = lead
    ? {
        name: lead.name,
        phone: lead.phone,
        city: lead.city,
        state: lead.state,
        source: lead.source,
        stage: lead.stage,
        dnd: lead.dnd,
        notes: lead.notes,
        category: lead.category,
        interests: lead.interests.join("\n"),
        ...Object.fromEntries(
          Object.entries(lead.details).map(([k, v]) => [k, String(v)]),
        ),
        ...Object.fromEntries(
          Object.entries(lead.custom).map(([k, v]) => [
            "custom." + k,
            typeof v === "boolean" ? v : String(v),
          ]),
        ),
      }
    : {};
  return (
    <FormDialog
      title={lead ? "Edit lead" : "Make the next connection"}
      description={
        ["telecaller", "field_executive"].includes(session?.role || "")
          ? "New leads are assigned to you automatically."
          : "New leads begin unassigned. Assign or distribute them when ready."
      }
      fields={fields}
      dependencies={[defs]}
      initial={initial}
      submitLabel={lead ? "Save lead" : "Create lead"}
      onClose={onClose}
      onSubmit={(v) => {
        const custom: Record<string, unknown> = { ...(lead?.custom || {}) };
        for (const d of defs.data || []) {
          if (d.kind !== "field" || !d.active) continue;
          if (v["custom." + d.key] === "" || v["custom." + d.key] === undefined)
            delete custom[d.key];
          else
            custom[d.key] =
              d.config.type === "number"
                ? Number(v["custom." + d.key])
                : v["custom." + d.key];
        }
        const body = {
          name: v.name,
          phone: v.phone,
          city: v.city,
          state: v.state,
          source: v.source,
          stage: v.stage,
          dnd: v.dnd,
          notes: v.notes,
          custom,
          category:
            realEstate || pharmaEnabled
              ? v.category || ""
              : lead?.category || "",
          interests: interestValues(v.interests),
          details: pharmaEnabled
            ? Object.fromEntries(
                ["drug_license", "specialty", "credit_limit", "outstanding"]
                  .filter((k) => v[k] !== undefined && v[k] !== "")
                  .map((k) => [k, v[k]]),
              )
            : lead?.details || {},
        };
        return action(() =>
          send(
            lead ? `/leads/${lead.id}` : "/leads",
            body,
            lead ? "PATCH" : "POST",
          ),
        );
      }}
    />
  );
}

function ImportDialog({ onClose }: { onClose: () => void }) {
  const [file, setFile] = useState<globalThis.File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const action = useAction();
  async function upload(commit: boolean) {
    if (!file) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.set("file", file);
    try {
      const r = await action(() =>
        api<ImportResult>(`/imports?commit=${commit}`, {
          method: "POST",
          body: form,
        }),
      );
      setResult(r);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title="Bring your leads together"
      description="Preview an XLSX or UTF-8 CSV file, then import the valid rows."
      onClose={onClose}
    >
      <div className="dialog-content">
        <div className="upload-zone">
          <Upload size={27} />
          <strong>{file?.name || "Choose a spreadsheet"}</strong>
          <span>CSV or XLSX · up to 10 MiB · 10,000 rows</span>
          <input
            aria-label="Lead import file"
            disabled={busy}
            type="file"
            accept=".csv,.xlsx"
            onChange={(e) => {
              setFile(e.target.files?.[0] || null);
              setResult(null);
              setError(null);
            }}
          />
        </div>
        <button
          className="text-button"
          onClick={() =>
            void download("/imports/template", "lead-template.csv").catch(
              setError,
            )
          }
        >
          <Download size={15} />
          Download template
        </button>
        <p className="help-text">
          Name and phone are required. Optional columns include city, state,
          source, category, interests, stage, notes and JSON custom fields.
          Separate products/services in the interests column with |. Legacy XLS
          files must be saved as XLSX or CSV. Ownership is set by your role.
        </p>
        {error !== null && <ErrorBox error={error} />}
        {result && (
          <>
            <div className="import-counts">
              <span>
                <strong>
                  {result.import_id ? result.imported : result.accepted}
                </strong>
                {result.import_id ? "imported" : "valid rows"}
              </span>
              <span>
                <strong>{result.duplicates}</strong>duplicates
              </span>
              <span>
                <strong>{result.invalid}</strong>invalid
              </span>
              <span>
                <strong>{result.blank_rows}</strong>blank
              </span>
            </div>
            {result.replayed && (
              <p className="notice">
                This exact file was already imported. Existing results are
                shown; no new rows were created.
              </p>
            )}
            {result.preview.length > 0 && (
              <Table headers={["Name", "Phone", "Source"]}>
                {result.preview.slice(0, 5).map((r, i) => (
                  <tr key={i}>
                    <td>{r.name}</td>
                    <td>{r.phone}</td>
                    <td>{r.source}</td>
                  </tr>
                ))}
              </Table>
            )}
            {result.errors.length > 0 && (
              <div className="import-errors">
                <h3>Rows that need attention</h3>
                {result.errors.slice(0, 8).map((r, i) => (
                  <p key={i}>
                    Row {r.row} · {r.column}: {r.message}
                  </p>
                ))}
                {result.import_id && (
                  <button
                    className="text-button"
                    onClick={() =>
                      void download(
                        `/imports/${result.import_id}/errors`,
                        "import-errors.csv",
                      ).catch(setError)
                    }
                  >
                    Download all row errors <Download size={14} />
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </div>
      <footer>
        <Button variant="secondary" onClick={onClose}>
          {result?.import_id ? "Done" : "Cancel"}
        </Button>
        {!result?.import_id && (
          <Button
            disabled={!file || busy}
            onClick={() => void upload(!!result)}
          >
            {busy
              ? "Processing…"
              : result
                ? `Import ${result.accepted} valid leads`
                : "Validate & preview"}
            <ArrowRight size={17} />
          </Button>
        )}
      </footer>
    </Dialog>
  );
}

export function LeadsPage({ lost = false }: { lost?: boolean }) {
  const { session } = useAuth();
  const action = useAction();
  const [sp, setSp] = useSearchParams();
  const [dialog, setDialog] = useState(
    sp.get("create") === "1" ? "create" : "",
  );
  const [selected, setSelected] = useState<string[]>([]);
  const [error, setError] = useState<unknown>(null);
  const f = Object.fromEntries(
    [...sp.entries()]
      .filter(([key]) => leadFilterKeys.includes(key) || key === "page")
      .map(([key, value]) => [key, normalizeLeadFilter(key, value)]),
  );
  if (lost) f.status = "lost";
  const requestedPage = Number(f.page || 1);
  const page =
    Number.isInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1;
  const path = "/leads?" + params({ ...f, page, size: 25 });
  const q = useData<{ items: Lead[]; total: number; page: number }>(path);
  useEffect(() => {
    setSelected([]);
  }, [path]);
  useEffect(() => {
    if (!q.data) return;
    const last = Math.max(1, Math.ceil(q.data.total / 25));
    if (page > last) {
      const next = new URLSearchParams(sp);
      next.set("page", String(last));
      setSp(next, { replace: true });
    }
  }, [q.data, page, sp, setSp]);
  const directory = useDirectory();
  const filterTeam = useData<User[]>(
    "/team",
    !["telecaller", "field_executive"].includes(session?.role || ""),
  );
  const views = useData<SavedView[]>("/saved-views");
  const defs = useData<Definition[]>("/definitions");
  function applyFilters(values: Record<string, string | boolean>) {
    const next = new URLSearchParams();
    for (const key of leadFilterKeys)
      if (values[key] !== undefined && values[key] !== "")
        next.set(key, normalizeLeadFilter(key, values[key]));
    if (lost) next.set("status", "lost");
    setSp(next);
    setSelected([]);
  }
  function filter(key: string, value: string) {
    const next = { ...f, [key]: value };
    if (key === "callback" && next.owner_id === "unassigned")
      delete next.owner_id;
    if (key === "owner_id" && value === "unassigned") delete next.callback;
    applyFilters(next);
  }
  const hasFilters = leadFilterKeys.some(
    (key) => !!f[key] && !(lost && key === "status"),
  );
  function act(fn: () => Promise<unknown>) {
    setError(null);
    void action(fn).catch(setError);
  }
  return (
    <>
      <PageHeading
        eyebrow={
          lost
            ? "RETAIN THE CONTEXT. FIND THE OPPORTUNITY."
            : "EVERY CONNECTION STARTS SOMEWHERE"
        }
        title={lost ? "Lost deals" : "Your leads"}
        description={
          lost
            ? "Reasons, ownership and history — ready for a considered next step."
            : ["telecaller", "field_executive"].includes(session?.role || "")
              ? "Your assigned queue, with overdue callbacks first."
              : "A shared view of every opportunity. Give each one a clear next step."
        }
        actions={
          !lost && (
            <>
              <Button variant="secondary" onClick={() => setDialog("import")}>
                <Upload size={16} />
                Import leads
              </Button>
              <Button onClick={() => setDialog("create")}>
                <Plus size={18} />
                Add a lead
              </Button>
            </>
          )
        }
      />
      <div className="lead-tabs">
        <button
          className={!hasFilters ? "active" : ""}
          aria-pressed={!hasFilters}
          onClick={() => applyFilters({})}
        >
          All {lost ? "lost deals" : "leads"}
        </button>
        {!lost && (
          <>
            <button
              className={f.callback === "overdue" ? "active" : ""}
              aria-pressed={f.callback === "overdue"}
              onClick={() => filter("callback", "overdue")}
            >
              Overdue follow-ups
            </button>
            <button
              className={f.callback === "upcoming" ? "active" : ""}
              aria-pressed={f.callback === "upcoming"}
              onClick={() => filter("callback", "upcoming")}
            >
              Upcoming follow-ups
            </button>
            <button
              className={f.callback === "stale" ? "active" : ""}
              aria-pressed={f.callback === "stale"}
              onClick={() => filter("callback", "stale")}
            >
              Not contacted in 48 hours
            </button>
            {!["telecaller", "field_executive"].includes(
              session?.role || "",
            ) && (
              <button
                className={f.owner_id === "unassigned" ? "active" : ""}
                aria-pressed={f.owner_id === "unassigned"}
                onClick={() => filter("owner_id", "unassigned")}
              >
                Unassigned
              </button>
            )}
          </>
        )}
      </div>
      <QueryNotice query={directory} />
      {!["telecaller", "field_executive"].includes(session?.role || "") && (
        <QueryNotice query={filterTeam} />
      )}
      <QueryNotice query={defs} />
      <QueryNotice query={views} />
      <Panel>
        <LeadFilters
          values={f}
          onChange={applyFilters}
          members={
            filterTeam.data?.map((user) => ({
              id: user.id,
              name: user.name + (user.active ? "" : " (inactive)"),
            })) || directory.data
          }
          definitions={defs.data}
          definitionsQuery={defs}
          role={session?.role || "telecaller"}
          lost={lost}
          total={q.data?.total}
          loading={q.isFetching}
          failed={q.isError}
          realEstate={
            session?.organization?.settings.industry === "real_estate"
          }
          onExport={() =>
            void download("/leads/export?" + params(f), "leads.csv").catch(
              setError,
            )
          }
        />
        <div className="saved-views">
          <span>Saved filters</span>
          {views.data
            ?.filter((v) => v.kind === "leads")
            .map((v) => (
              <span className="view-chip" key={v.id}>
                <button onClick={() => applyFilters(v.filters)}>
                  {v.name}
                </button>
                <button
                  aria-label={`Remove saved filter ${v.name}`}
                  title="Remove this saved filter. Your leads are kept."
                  onClick={() =>
                    act(() => api(`/saved-views/${v.id}`, { method: "DELETE" }))
                  }
                >
                  <X size={12} />
                </button>
              </span>
            ))}
          <button className="text-button" onClick={() => setDialog("save")}>
            + Save filters
          </button>
          {!["telecaller", "field_executive"].includes(session?.role || "") &&
            !lost && (
              <button
                className="text-button distribute-button"
                onClick={() => setDialog("distribute")}
              >
                <Users size={14} />
                Distribute unassigned
              </button>
            )}
        </div>
        {error !== null && <ErrorBox error={error} />}
        {selected.length > 0 && (
          <div className="selection-bar">
            <strong>{selected.length} selected</strong>
            <Button variant="secondary" onClick={() => setDialog("assign")}>
              Assign selected
            </Button>
            <button className="text-button" onClick={() => setSelected([])}>
              Clear
            </button>
          </div>
        )}
        <Load query={q}>
          {(data) =>
            data.items.length ? (
              <>
                <Table
                  headers={[
                    "",
                    "Lead",
                    "Status",
                    "Source",
                    "Owner",
                    "Next follow-up",
                    lost ? "Reason" : "Score",
                    "",
                  ]}
                >
                  {data.items.map((l) => (
                    <tr key={l.id}>
                      <td>
                        <input
                          aria-label={`Select ${l.name}`}
                          type="checkbox"
                          checked={selected.includes(l.id)}
                          onChange={(e) =>
                            setSelected((s) =>
                              e.target.checked
                                ? [...s, l.id]
                                : s.filter((id) => id !== l.id),
                            )
                          }
                        />
                      </td>
                      <td>
                        <Link className="name-cell" to={`/app/leads/${l.id}`}>
                          <span className="lead-avatar">
                            {l.name.slice(0, 2).toUpperCase()}
                          </span>
                          <span>
                            <strong>
                              {l.name}
                              {l.dnd && (
                                <ShieldAlert
                                  size={13}
                                  aria-label="Do not disturb"
                                />
                              )}
                            </strong>
                            <small>
                              {l.phone}
                              {l.city ? ` · ${l.city}` : ""}
                            </small>
                          </span>
                        </Link>
                      </td>
                      <td>
                        <Badge value={l.status} />
                      </td>
                      <td>
                        <span className="source-tag">{l.source}</span>
                      </td>
                      <td>
                        <span className={l.owner_id ? "" : "muted"}>
                          {l.owner_name}
                        </span>
                      </td>
                      <td>
                        <span
                          className={
                            l.follow_up && new Date(l.follow_up) < new Date()
                              ? "overdue-text"
                              : ""
                          }
                        >
                          {dateTime(l.follow_up)}
                        </span>
                      </td>
                      <td>
                        {lost ? (
                          <span className="truncate" title={l.lost_reason}>
                            {l.lost_reason}
                          </span>
                        ) : (
                          <span className={`score ${l.score.band}`}>
                            <i />
                            {l.score.value} <small>{l.score.band}</small>
                          </span>
                        )}
                      </td>
                      <td>
                        <Link
                          className="row-arrow"
                          to={`/app/leads/${l.id}`}
                          aria-label={`Open ${l.name}`}
                        >
                          <ArrowUpRight size={17} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </Table>
                <div className="pagination">
                  <span>
                    Showing {(page - 1) * 25 + 1}–
                    {Math.min(page * 25, data.total)} of {data.total} leads
                  </span>
                  <div>
                    <Button
                      variant="secondary"
                      disabled={page <= 1}
                      onClick={() => {
                        const p = new URLSearchParams(sp);
                        p.set("page", String(page - 1));
                        setSp(p);
                      }}
                    >
                      <ChevronLeft size={16} />
                      Previous
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={page * 25 >= data.total}
                      onClick={() => {
                        const p = new URLSearchParams(sp);
                        p.set("page", String(page + 1));
                        setSp(p);
                      }}
                    >
                      Next
                      <ChevronRight size={16} />
                    </Button>
                  </div>
                </div>
              </>
            ) : (
              <Empty
                title={
                  hasFilters
                    ? "No leads match these filters"
                    : "Your next opportunity starts here"
                }
                description={
                  hasFilters
                    ? "Remove a filter or clear them all to see more leads."
                    : "Add a lead or import a list to get started."
                }
                action={
                  hasFilters ? (
                    <Button
                      variant="secondary"
                      onClick={() => applyFilters({})}
                    >
                      Clear all filters
                    </Button>
                  ) : lost ? undefined : (
                    <Button onClick={() => setDialog("create")}>
                      <Plus size={16} />
                      Add a lead
                    </Button>
                  )
                }
              />
            )
          }
        </Load>
      </Panel>
      {dialog === "create" && (
        <LeadForm
          onClose={() => {
            setDialog("");
            const p = new URLSearchParams(sp);
            p.delete("create");
            setSp(p);
          }}
        />
      )}
      {dialog === "import" && <ImportDialog onClose={() => setDialog("")} />}
      {dialog === "assign" && (
        <FormDialog
          title="Give these leads an owner"
          dependencies={[directory]}
          fields={[
            {
              name: "owner_id",
              label: "Assign to",
              required: true,
              options: (directory.data || [])
                .filter((u) =>
                  ["telecaller", "field_executive"].includes(
                    session?.role || "",
                  )
                    ? u.role === "manager"
                    : ["manager", "telecaller"].includes(u.role),
                )
                .map((u) => ({ value: u.id, label: u.name + " · " + u.role })),
            },
          ]}
          onClose={() => setDialog("")}
          onSubmit={(v) =>
            action(() =>
              send("/leads/assign", {
                lead_ids: selected,
                owner_id: v.owner_id,
              }),
            ).then(() => setSelected([]))
          }
        />
      )}
      {dialog === "save" && (
        <FormDialog
          title="Save these filters"
          description="Reuse this combination of lead filters later. Choose a clear name, such as New leads."
          submitLabel="Save filters"
          fields={[{ name: "name", label: "Filter name", required: true }]}
          onClose={() => setDialog("")}
          onSubmit={(v) =>
            action(() =>
              send("/saved-views", {
                name: v.name,
                kind: "leads",
                filters: Object.fromEntries(
                  Object.entries(f).filter(
                    ([key]) => !["page", "size"].includes(key),
                  ),
                ),
              }),
            )
          }
        />
      )}
      {dialog === "distribute" && (
        <FormDialog
          title="Distribute unassigned leads"
          description="Active telecallers receive leads in a persisted round-robin order. Existing assignments stay in place."
          fields={[]}
          onClose={() => setDialog("")}
          submitLabel="Distribute leads"
          onSubmit={() =>
            action(() =>
              api<{ assigned: number; message?: string }>("/leads/distribute", {
                method: "POST",
              }),
            ).then((r) => {
              if (r.message) setError(new Error(r.message));
            })
          }
        />
      )}
    </>
  );
}

function OutcomeDialog({ lead, onClose }: { lead: Lead; onClose: () => void }) {
  const dir = useDirectory();
  const { session } = useAuth();
  const calls = useData<{ items: PhoneCall[] }>(
    `/phone-calls?lead_id=${lead.id}`,
  );
  const action = useAction();
  const [key] = useState(crypto.randomUUID());
  return (
    <FormDialog
      dependencies={[dir]}
      title="Record the conversation"
      description="Business outcomes are kept separate from device-observed call metadata."
      fields={[
        {
          name: "phone_call_id",
          label: "Linked device call (optional)",
          options: (calls.data?.items || [])
            .filter((c) => c.user_id === session?.user.id)
            .map((c) => ({
              value: c.id,
              label: `${dateTime(c.started_at)} · ${c.direction} · ${duration(c.duration)}`,
            })),
          hint: "Link the exact call to avoid counting this outcome as a second call.",
        },
        {
          name: "outcome",
          label: "Outcome",
          required: true,
          options: options(statuses),
          defaultValue: "follow-up",
        },
        {
          name: "duration",
          label: "Declared duration (seconds)",
          type: "number",
          min: "0",
          max: "86400",
          defaultValue: "0",
        },
        {
          name: "follow_up",
          label: "Next follow-up",
          type: "datetime-local",
          hint: "Required for follow-up. Use a future time.",
        },
        {
          name: "order_value",
          label: "Order value (₹)",
          type: "number",
          min: "0",
          step: ".01",
          defaultValue: "0",
        },
        {
          name: "manager_id",
          label: "Manager handoff",
          options: (dir.data || [])
            .filter((u) => u.role === "manager")
            .map((u) => ({ value: u.id, label: u.name })),
          hint: "Required when marking a deal lost.",
        },
        {
          name: "notes",
          label: "Notes / lost reason",
          type: "textarea",
          wide: true,
        },
      ]}
      onClose={onClose}
      submitLabel="Save outcome"
      onSubmit={(v) =>
        action(() =>
          send(`/leads/${lead.id}/outcomes`, {
            outcome: v.outcome,
            duration: Number(v.duration),
            follow_up: toDate(v.follow_up),
            order_value: v.order_value || "0",
            manager_id: v.manager_id || null,
            notes: v.notes,
            request_id: key,
            phone_call_id: v.phone_call_id || null,
          }),
        )
      }
    >
      <QueryNotice query={calls} />
    </FormDialog>
  );
}

export function AudioFile({ file }: { file: FileItem }) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState<unknown>(null);
  const prior = useRef("");
  function load() {
    void api<Blob>(`/files/${file.id}?inline=true`)
      .then((blob) => {
        if (prior.current) URL.revokeObjectURL(prior.current);
        prior.current = URL.createObjectURL(blob);
        setUrl(prior.current);
      })
      .catch(setError);
  }
  return (
    <div className="audio-file">
      {url ? (
        <audio
          controls
          src={url}
          preload="none"
          aria-label={`Play ${file.name}`}
        />
      ) : (
        <button className="text-button" onClick={load}>
          ▶ Play recording
        </button>
      )}
      {error !== null && <ErrorBox error={error} />}
    </div>
  );
}

export function LeadDetail() {
  const { id } = useParams();
  const { session } = useAuth();
  const q = useData<Lead>(`/leads/${id}`);
  const [historyPage, setHistoryPage] = useState(1);
  const hist = useData<History>(
    `/leads/${id}/history?page=${historyPage}`,
    !!q.data,
  );
  const defs = useData<Definition[]>("/definitions");
  const dir = useDirectory();
  const [tab, setTab] = useState("Activity");
  const [dialog, setDialog] = useState("");
  const [note, setNote] = useState("");
  const [editingNote, setEditingNote] = useState<{
    id: string;
    text: string;
  } | null>(null);
  const [error, setError] = useState<unknown>(null);
  const action = useAction();
  const nav = useNavigate();
  function act(fn: () => Promise<unknown>) {
    setError(null);
    void action(fn).catch(setError);
  }
  return (
    <>
      <Link className="back-link" to="/app/leads">
        <ArrowLeft size={15} />
        Back to leads
      </Link>
      <QueryNotice query={defs} />
      <QueryNotice query={dir} />
      <Load query={q}>
        {(lead) => (
          <>
            <PageHeading
              eyebrow="LEAD WORKSPACE"
              title={lead.name}
              description={`${lead.phone}${lead.city ? " · " + lead.city : ""}${lead.state ? ", " + lead.state : ""}`}
              actions={
                <>
                  <Button variant="secondary" onClick={() => setDialog("edit")}>
                    Edit details
                  </Button>
                  <Button
                    disabled={lead.dnd}
                    onClick={() => setDialog("outcome")}
                  >
                    <Phone size={17} />
                    Log a conversation
                  </Button>
                </>
              }
            />
            {lead.dnd && (
              <div className="notice">
                <ShieldAlert size={18} />
                Do not disturb is enabled. Contact actions are unavailable.
              </div>
            )}
            <div className="lead-detail-grid">
              <aside>
                <Panel>
                  <div className="lead-profile">
                    <span className="lead-avatar large-avatar">
                      {lead.name.slice(0, 2).toUpperCase()}
                    </span>
                    <Badge value={lead.status} />
                    <h2>{lead.name}</h2>
                    <p>
                      {lead.source} · {dateTime(lead.created_at)}
                    </p>
                    <a
                      className={`button secondary ${lead.dnd ? "disabled" : ""}`}
                      href={lead.dnd ? undefined : `tel:${lead.phone}`}
                      aria-disabled={lead.dnd}
                    >
                      <Phone size={16} />
                      Open dialer
                    </a>
                  </div>
                  <dl className="detail-list">
                    <div>
                      <dt>Lead owner</dt>
                      <dd>{lead.owner_name}</dd>
                    </div>
                    <div>
                      <dt>Pipeline</dt>
                      <dd>
                        {defs.data?.find(
                          (d) => d.kind === "stage" && d.key === lead.stage,
                        )?.label || lead.stage}
                      </dd>
                    </div>
                    <div>
                      <dt>Last contact</dt>
                      <dd>{dateTime(lead.last_contact)}</dd>
                    </div>
                    <div>
                      <dt>Next follow-up</dt>
                      <dd>{dateTime(lead.follow_up)}</dd>
                    </div>
                    <div>
                      <dt>
                        {session?.organization?.settings.industry ===
                        "real_estate"
                          ? "Property category"
                          : "Primary category"}
                      </dt>
                      <dd>
                        {defs.data?.find(
                          (d) =>
                            d.kind === "category" && d.key === lead.category,
                        )?.label ||
                          lead.category ||
                          "Not set"}
                      </dd>
                    </div>
                    <div>
                      <dt>Property / project interests</dt>
                      <dd>{lead.interests.join(", ") || "Not recorded"}</dd>
                    </div>
                    {Object.entries({ ...lead.details, ...lead.custom }).map(
                      ([key, value]) => (
                        <div key={key}>
                          <dt>
                            {defs.data?.find(
                              (d) => d.kind === "field" && d.key === key,
                            )?.label || key.replaceAll("_", " ")}
                          </dt>
                          <dd>{String(value)}</dd>
                        </div>
                      ),
                    )}
                  </dl>
                  <div className="profile-actions">
                    <Button
                      variant="secondary"
                      onClick={() => setDialog("assign")}
                    >
                      <UserRound size={15} />
                      {["telecaller", "field_executive"].includes(
                        session?.role || "",
                      )
                        ? "Hand to manager"
                        : "Assign lead"}
                    </Button>
                    {!["telecaller", "field_executive"].includes(
                      session?.role || "",
                    ) && (
                      <>
                        <Button
                          variant="secondary"
                          onClick={() => setDialog("merge")}
                        >
                          <GitMerge size={15} />
                          Merge duplicate
                        </Button>
                        <Button
                          variant="danger-quiet"
                          onClick={() => setDialog("delete")}
                        >
                          <Trash2 size={15} />
                          Delete lead
                        </Button>
                      </>
                    )}
                  </div>
                </Panel>
                <Panel
                  title="Lead score"
                  description="Points reflect saved details and activity. Your team records customer-confirmed interests."
                  action={
                    <button
                      className="text-button"
                      onClick={() => setDialog("interests")}
                    >
                      {lead.interests.length
                        ? "Edit interests"
                        : "Add interests"}
                    </button>
                  }
                >
                  <div className={`score-number ${lead.score.band}`}>
                    {lead.score.value}
                    <span>/ 100 · {lead.score.band}</span>
                  </div>
                  <dl className="detail-list score-factors">
                    {Object.entries(lead.score.factors).map(([key, value]) => (
                      <div key={key}>
                        <dt>{key}</dt>
                        <dd>+{value}</dd>
                      </div>
                    ))}
                  </dl>
                </Panel>
              </aside>
              <div>
                <LeadFieldWork key={lead.id} lead={lead} />
                <Panel>
                  <div className="detail-tabs">
                    {[
                      "Activity",
                      "Property brief",
                      "Notes",
                      "Calls",
                      "Tasks",
                      "Files",
                    ].map((t) => (
                      <button
                        className={t === tab ? "active" : ""}
                        onClick={() => {
                          setTab(t);
                          setHistoryPage(1);
                        }}
                        key={t}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                  {tab === "Property brief" && id && <BuyerBrief leadId={id} />}
                  {lead.notes && tab === "Activity" && (
                    <div className="initial-note">
                      <span className="eyebrow">LEAD NOTES</span>
                      <p>{lead.notes}</p>
                    </div>
                  )}
                  {lead.lost_reason && tab === "Activity" && (
                    <div className="initial-note">
                      <span className="eyebrow">LOST DEAL REASON</span>
                      <p>{lead.lost_reason}</p>
                    </div>
                  )}
                  {tab === "Notes" && (
                    <form
                      className="note-form"
                      onSubmit={(e) => {
                        e.preventDefault();
                        act(() =>
                          send(`/leads/${id}/notes`, { text: note }).then(() =>
                            setNote(""),
                          ),
                        );
                      }}
                    >
                      <label className="field">
                        <span>Add a note</span>
                        <textarea
                          placeholder="Capture the useful details…"
                          value={note}
                          onChange={(e) => setNote(e.target.value)}
                          required
                          maxLength={10000}
                        />
                      </label>
                      <Button disabled={!note.trim()}>
                        <Plus size={15} />
                        Add note
                      </Button>
                    </form>
                  )}
                  {tab === "Files" && (
                    <div className="file-upload">
                      <label className="button secondary">
                        <Upload size={16} />
                        Attach private file
                        <input
                          type="file"
                          className="visually-hidden"
                          accept=".pdf,.png,.jpg,.jpeg,.webp,.mp3,.m4a,.wav,.ogg,.flac"
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) {
                              const form = new FormData();
                              form.set("file", file);
                              act(() =>
                                api(`/leads/${id}/files`, {
                                  method: "POST",
                                  body: form,
                                }),
                              );
                            }
                          }}
                        />
                      </label>
                      <small>
                        Up to 10 MiB · PDFs, images and supported audio
                      </small>
                    </div>
                  )}
                  {error !== null && <ErrorBox error={error} />}
                  <Load query={hist}>
                    {(h) => (
                      <div className="history-content">
                        {tab === "Activity" &&
                          (h.activity.length ? (
                            <div className="timeline">
                              {h.activity.map((a) => (
                                <article key={a.id}>
                                  <span className="timeline-dot">
                                    <HistoryIcon size={14} />
                                  </span>
                                  <div>
                                    <strong>{a.summary}</strong>
                                    <p>
                                      {h.people[a.actor_id || ""] || "System"} ·{" "}
                                      {dateTime(a.created_at)}
                                    </p>
                                    {Object.keys(a.details).length > 0 && (
                                      <details>
                                        <summary>View details</summary>
                                        <pre>
                                          {JSON.stringify(a.details, null, 2)}
                                        </pre>
                                      </details>
                                    )}
                                  </div>
                                </article>
                              ))}
                            </div>
                          ) : (
                            <Empty
                              title="A fresh start"
                              description="Changes and conversations will appear here."
                            />
                          ))}
                        {tab === "Notes" &&
                          (h.notes.length ? (
                            h.notes.map((n) => (
                              <article className="note-card" key={n.id}>
                                <div>
                                  <strong>
                                    {h.people[n.author_id] || "Team member"}
                                  </strong>
                                  <small>{dateTime(n.created_at)}</small>
                                </div>
                                <p>{n.text}</p>
                                {(n.author_id === session?.user.id ||
                                  session?.role === "admin") && (
                                  <div className="inline-actions">
                                    <button onClick={() => setEditingNote(n)}>
                                      Edit
                                    </button>
                                    <button
                                      onClick={() =>
                                        act(() =>
                                          api(`/leads/${id}/notes/${n.id}`, {
                                            method: "DELETE",
                                          }),
                                        )
                                      }
                                    >
                                      Remove
                                    </button>
                                  </div>
                                )}
                              </article>
                            ))
                          ) : (
                            <Empty
                              title="No notes yet"
                              description="Add context that will help the next conversation."
                            />
                          ))}
                        {tab === "Calls" && (
                          <>
                            <h3 className="subheading">
                              Manual business outcomes
                            </h3>
                            {h.manual_calls.length ? (
                              h.manual_calls.map((c) => (
                                <article className="call-card" key={c.id}>
                                  <div>
                                    <Badge value={c.outcome} />
                                    <span>
                                      {duration(c.duration)} declared
                                      {c.phone_call_id
                                        ? " · linked device call"
                                        : ""}
                                    </span>
                                    <small>{dateTime(c.created_at)}</small>
                                  </div>
                                  <p>{c.notes || "No notes added."}</p>
                                  <small>
                                    {h.people[c.user_id] || "Team member"}
                                    {Number(c.order_value) > 0
                                      ? ` · ${money(c.order_value)}`
                                      : ""}
                                  </small>
                                </article>
                              ))
                            ) : (
                              <Empty title="No manual outcomes" />
                            )}
                            <h3 className="subheading">
                              Device-observed phone calls
                            </h3>
                            {h.phone_calls.length ? (
                              h.phone_calls.map((c) => (
                                <article className="call-card" key={c.id}>
                                  <div>
                                    <strong>
                                      {c.direction} · {c.result}
                                    </strong>
                                    <span>{duration(c.duration)} observed</span>
                                    <small>{dateTime(c.started_at)}</small>
                                  </div>
                                  <RecordingBadge value={c.recording_state} />
                                  {c.recordings.map((f) => (
                                    <AudioFile key={f.id} file={f} />
                                  ))}
                                </article>
                              ))
                            ) : (
                              <Empty
                                title="No synchronized phone calls"
                                description="Call metadata will appear when an authorized device client syncs it."
                              />
                            )}
                          </>
                        )}
                        {tab === "Tasks" && (
                          <>
                            <Button
                              variant="secondary"
                              onClick={() => nav("/app/tasks?lead_id=" + id)}
                            >
                              <Plus size={15} />
                              Create a task
                            </Button>
                            {h.tasks.length ? (
                              h.tasks
                                .filter(
                                  (t) =>
                                    !["telecaller", "field_executive"].includes(
                                      session?.role || "",
                                    ) || t.owner_id === session?.user.id,
                                )
                                .map((t) => (
                                  <Link
                                    className="task-row"
                                    to="/app/tasks"
                                    key={t.id}
                                  >
                                    <CalendarClock size={18} />
                                    <span>
                                      <strong>{t.title}</strong>
                                      <small>{dateTime(t.due_at)}</small>
                                    </span>
                                    <Badge value={t.state} />
                                  </Link>
                                ))
                            ) : (
                              <Empty title="No tasks linked yet" />
                            )}
                          </>
                        )}
                        {tab === "Files" &&
                          (h.files.length ? (
                            h.files.map((f) => (
                              <article className="file-row" key={f.id}>
                                <File size={22} />
                                <div>
                                  <strong>{f.name}</strong>
                                  <small>
                                    {Math.ceil(f.size / 1024)} KB ·{" "}
                                    {dateTime(f.created_at)}
                                  </small>
                                  {f.mime.startsWith("audio/") && (
                                    <AudioFile file={f} />
                                  )}
                                </div>
                                <button
                                  aria-label={`Download ${f.name}`}
                                  className="icon-button"
                                  onClick={() =>
                                    void download(
                                      `/files/${f.id}`,
                                      f.name,
                                    ).catch(setError)
                                  }
                                >
                                  <Download size={18} />
                                </button>
                                {(!["telecaller", "field_executive"].includes(
                                  session?.role || "",
                                ) ||
                                  (!f.phone_call_id &&
                                    !f.mime.startsWith("audio/"))) &&
                                  (f.author_id === session?.user.id ||
                                    session?.role === "admin") && (
                                    <button
                                      className="icon-button"
                                      aria-label={`Remove ${f.name}`}
                                      onClick={() =>
                                        act(() =>
                                          api(`/files/${f.id}`, {
                                            method: "DELETE",
                                          }),
                                        )
                                      }
                                    >
                                      <Trash2 size={16} />
                                    </button>
                                  )}
                              </article>
                            ))
                          ) : (
                            <Empty
                              title="Keep the context together"
                              description="Private lead documents and recordings appear here."
                            />
                          ))}
                        <div
                          className="pagination"
                          aria-label="History pagination"
                        >
                          <Button
                            variant="secondary"
                            disabled={historyPage === 1}
                            onClick={() => setHistoryPage(historyPage - 1)}
                          >
                            Newer
                          </Button>
                          <span>
                            Page {historyPage} of{" "}
                            {Math.max(
                              1,
                              Math.ceil(
                                Math.max(
                                  ...(tab === "Calls"
                                    ? ["manual_calls", "phone_calls"]
                                    : [
                                        (
                                          {
                                            Activity: "activity",
                                            Notes: "notes",
                                            Tasks: "tasks",
                                            Files: "files",
                                          } as Record<string, string>
                                        )[tab],
                                      ]
                                  ).map((key) => h.pagination.totals[key] || 0),
                                ) / h.pagination.size,
                              ),
                            )}
                          </span>
                          <Button
                            variant="secondary"
                            disabled={
                              !(
                                tab === "Calls"
                                  ? ["manual_calls", "phone_calls"]
                                  : [
                                      (
                                        {
                                          Activity: "activity",
                                          Notes: "notes",
                                          Tasks: "tasks",
                                          Files: "files",
                                        } as Record<string, string>
                                      )[tab],
                                    ]
                              ).some(
                                (key) =>
                                  (h.pagination.totals[key] || 0) >
                                  historyPage * h.pagination.size,
                              )
                            }
                            onClick={() => setHistoryPage(historyPage + 1)}
                          >
                            Older
                          </Button>
                        </div>
                      </div>
                    )}
                  </Load>
                </Panel>
              </div>
            </div>
            {dialog === "interests" && q.data && (
              <FormDialog
                title="Customer interests"
                description="Record what the customer has told your team. Saving any interests adds 15 score points; clearing them removes those points."
                fields={[interestsField]}
                initial={{ interests: q.data.interests.join("\n") }}
                onClose={() => setDialog("")}
                submitLabel="Save interests"
                onSubmit={(values) =>
                  action(() =>
                    send(
                      `/leads/${id}`,
                      { interests: interestValues(values.interests) },
                      "PATCH",
                    ),
                  )
                }
              />
            )}
            {dialog === "edit" && (
              <LeadForm lead={lead} onClose={() => setDialog("")} />
            )}
            {dialog === "outcome" && (
              <OutcomeDialog lead={lead} onClose={() => setDialog("")} />
            )}
            {dialog === "assign" && (
              <FormDialog
                title="Choose the next owner"
                dependencies={[dir]}
                fields={[
                  {
                    name: "owner_id",
                    label: "Active team member",
                    required: true,
                    options: (dir.data || [])
                      .filter((u) =>
                        ["telecaller", "field_executive"].includes(
                          session?.role || "",
                        )
                          ? u.role === "manager"
                          : ["manager", "telecaller"].includes(u.role),
                      )
                      .map((u) => ({
                        value: u.id,
                        label: u.name + " · " + u.role,
                      })),
                  },
                ]}
                onClose={() => setDialog("")}
                onSubmit={(v) =>
                  action(() =>
                    send("/leads/assign", {
                      lead_ids: [id],
                      owner_id: v.owner_id,
                    }),
                  )
                }
              />
            )}
            {dialog === "merge" && (
              <FormDialog
                title="Merge into this lead"
                description="The primary name and phone are preserved. Notes, files, calls, tasks and assignment history move to this lead."
                fields={[
                  {
                    name: "duplicate_id",
                    label: "Duplicate lead",
                    required: true,
                    wide: true,
                    render: (value, set) => (
                      <LeadPicker
                        label="Duplicate lead"
                        required
                        value={String(value || "")}
                        onChange={set}
                        excludeId={id}
                      />
                    ),
                  },
                ]}
                onClose={() => setDialog("")}
                submitLabel="Merge records"
                onSubmit={(v) =>
                  action(() =>
                    api(`/leads/${id}/merge/${v.duplicate_id}`, {
                      method: "POST",
                    }),
                  )
                }
              />
            )}
            {dialog === "delete" && (
              <FormDialog
                title={`Delete ${lead.name}?`}
                description="This lead will leave active queues. Its history is retained for recovery."
                fields={[
                  {
                    name: "confirmation",
                    label: `Type “${lead.name}” to confirm`,
                    required: true,
                  },
                ]}
                onClose={() => setDialog("")}
                submitLabel="Delete lead"
                onSubmit={(v) =>
                  action(() =>
                    api(
                      `/leads/${id}?confirmation=${encodeURIComponent(String(v.confirmation))}`,
                      { method: "DELETE" },
                    ),
                  ).then(() => nav("/app/leads"))
                }
              />
            )}
            {editingNote && (
              <FormDialog
                title="Edit note"
                fields={[
                  {
                    name: "text",
                    label: "Note",
                    type: "textarea",
                    required: true,
                    wide: true,
                  },
                ]}
                initial={{ text: editingNote.text }}
                onClose={() => setEditingNote(null)}
                onSubmit={(v) =>
                  action(() =>
                    send(
                      `/leads/${id}/notes/${editingNote.id}`,
                      { text: v.text },
                      "PUT",
                    ),
                  )
                }
              />
            )}
          </>
        )}
      </Load>
    </>
  );
}
