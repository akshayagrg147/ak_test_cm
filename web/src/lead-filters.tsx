import { useId, useState } from "react";
import { Download, Filter, Search, X } from "lucide-react";
import type { Definition, Role } from "./types";
import { Button, Dialog, QueryNotice, type QueryDependency } from "./ui";

type Values = Record<string, string>;
type Choice = { value: string; label: string };
type Member = { id: string; name: string };
export const leadFilterKeys = [
  "q",
  "status",
  "source",
  "owner_id",
  "callback",
  "city",
  "state",
  "category",
  "interest",
  "stage",
  "dnd",
  "reported_by",
  "reason",
  "from_date",
  "to_date",
];
export const leadStatusChoices: Choice[] = [
  { value: "new", label: "New enquiry" },
  { value: "follow-up", label: "Follow-up needed" },
  { value: "not-picked", label: "Call not answered" },
  { value: "converted", label: "Converted / won" },
  { value: "lost", label: "Lost" },
];
export const leadSourceChoices: Choice[] = [
  ["manual", "Manual entry"],
  ["website", "Website"],
  ["referral", "Referral"],
  ["indiamart", "IndiaMART"],
  ["justdial", "Justdial"],
  ["tradeindia", "TradeIndia"],
  ["99acres", "99acres"],
  ["magicbricks", "Magicbricks"],
  ["housing", "Housing"],
  ["walk-in", "Walk-in"],
  ["property-expo", "Property exhibition"],
  ["broker", "Broker"],
].map(([value, label]) => ({ value, label }));
const followups = [
  { value: "overdue", label: "Overdue follow-ups" },
  { value: "upcoming", label: "Upcoming follow-ups" },
  { value: "stale", label: "Not contacted in 48 hours" },
];
const contactChoices = [
  { value: "false", label: "Contact allowed" },
  { value: "true", label: "Do not contact" },
];
const choiceLabel = (choices: Choice[], value: string) =>
  choices.find((choice) => choice.value === value)?.label || value;
const activeValues = (values: Values) =>
  Object.fromEntries(
    leadFilterKeys
      .filter((key) => !!values[key])
      .map((key) => [key, values[key]]),
  );
const validDate = (value?: string) => {
  const date = value ? new Date(value) : null;
  return date && !Number.isNaN(date.getTime()) ? date : null;
};
const dayString = (date: Date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
const dayBoundary = (value: string, followingDay = false) => {
  if (!value) return "";
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day + (followingDay ? 1 : 0)).toISOString();
};
const midnight = (value?: string) => {
  const date = validDate(value);
  return (
    !value ||
    (!!date &&
      date.getHours() === 0 &&
      date.getMinutes() === 0 &&
      date.getSeconds() === 0 &&
      date.getMilliseconds() === 0)
  );
};
const wholeDays = (values: Values) =>
  midnight(values.from_date) && midnight(values.to_date);
const dateInput = (value?: string, inclusiveEnd = false) => {
  const date = validDate(value);
  if (!date) return "";
  if (inclusiveEnd) date.setTime(date.getTime() - 1);
  return dayString(date);
};
export function normalizeLeadFilter(key: string, raw: string | boolean) {
  const value = String(raw);
  if (
    !["from_date", "to_date"].includes(key) ||
    !/^\d{4}-\d{2}-\d{2}$/.test(value)
  )
    return value;
  const boundary = dayBoundary(value);
  return dateInput(boundary) === value ? boundary : value;
}
const timeInput = (value?: string) => {
  const date = validDate(value);
  return date
    ? new Date(date.getTime() - date.getTimezoneOffset() * 60000)
        .toISOString()
        .slice(0, 16)
    : "";
};
const readableDate = (value: string, time = false, inclusiveEnd = false) => {
  const date = validDate(value);
  if (!date) return "Invalid date";
  if (inclusiveEnd) date.setTime(date.getTime() - 1);
  return date.toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
    ...(time ? ({ hour: "2-digit", minute: "2-digit" } as const) : {}),
  });
};

function Select({
  label,
  value,
  choices,
  all,
  onChange,
  hint,
  disabled = false,
  missingLabel,
}: {
  label: string;
  value: string;
  choices: Choice[];
  all: string;
  onChange: (value: string) => void;
  hint?: string;
  disabled?: boolean;
  missingLabel?: string;
}) {
  const hintId = useId();
  return (
    <label className="field">
      <span>{label}</span>
      <select
        aria-label={label}
        aria-describedby={hint ? hintId : undefined}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
      >
        <option value="">{all}</option>
        {value && !choices.some((choice) => choice.value === value) && (
          <option value={value}>
            {missingLabel || `Saved selection: ${value}`}
          </option>
        )}
        {choices.map((choice) => (
          <option key={choice.value} value={choice.value}>
            {choice.label}
          </option>
        ))}
      </select>
      {hint && <small id={hintId}>{hint}</small>}
    </label>
  );
}
function Text({
  label,
  value,
  onChange,
  hint,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  hint?: string;
}) {
  const hintId = useId();
  return (
    <label className="field">
      <span>{label}</span>
      <input
        aria-label={label}
        aria-describedby={hint ? hintId : undefined}
        value={value}
        maxLength={160}
        onChange={(e) => onChange(e.target.value)}
      />
      {hint && <small id={hintId}>{hint}</small>}
    </label>
  );
}

export function LeadFilters({
  values,
  onChange,
  members = [],
  definitions = [],
  definitionsQuery,
  role,
  lost,
  total,
  loading,
  failed = false,
  onExport,
  realEstate,
}: {
  values: Values;
  onChange: (values: Values) => void;
  members?: Member[];
  definitions?: Definition[];
  definitionsQuery?: QueryDependency;
  role: Role;
  lost: boolean;
  total?: number;
  loading: boolean;
  failed?: boolean;
  onExport: () => void;
  realEstate: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Values>({});
  const [period, setPeriod] = useState("any");
  const [dateError, setDateError] = useState("");
  const definitionsUnavailable =
    !!definitionsQuery &&
    definitionsQuery.data === undefined &&
    (definitionsQuery.isPending || definitionsQuery.isError);
  const active = activeValues(values);
  if (lost) delete active.status;
  const commonKeys = ["q", "status", "source", "owner_id"];
  const extraCount =
    Object.keys(active).filter(
      (key) =>
        !commonKeys.includes(key) && !["from_date", "to_date"].includes(key),
    ).length + (values.from_date || values.to_date ? 1 : 0);
  const memberChoices = members.map((member) => ({
    value: member.id,
    label: member.name,
  }));
  const categoryLabels = definitions
    .filter((definition) => definition.kind === "category")
    .map((definition) => ({ value: definition.key, label: definition.label }));
  const categories = definitions
    .filter((definition) => definition.kind === "category" && definition.active)
    .map((definition) => ({ value: definition.key, label: definition.label }));
  const stages = definitions
    .filter((definition) => definition.kind === "stage")
    .map((definition) => ({ value: definition.key, label: definition.label }));
  const update = (key: string, value: string) =>
    onChange({ ...values, [key]: value });
  const reset = () => onChange({});
  const set = (key: string, value: string) =>
    setDraft((current) => ({ ...current, [key]: value }));
  function edit() {
    setDraft(activeValues(values));
    setPeriod(
      values.from_date || values.to_date
        ? wholeDays(values)
          ? "custom"
          : "exact"
        : "any",
    );
    setDateError("");
    setOpen(true);
  }
  function preset(value: string) {
    setPeriod(value);
    setDateError("");
    if (value === "exact") return;
    if (value === "any") {
      setDraft((current) => ({ ...current, from_date: "", to_date: "" }));
      return;
    }
    if (value === "custom") {
      setDraft((current) => ({
        ...current,
        from_date: current.from_date
          ? dayBoundary(dateInput(current.from_date))
          : "",
        to_date: current.to_date
          ? dayBoundary(
              dateInput(current.to_date, midnight(current.to_date)),
              true,
            )
          : "",
      }));
      return;
    }
    const today = new Date(),
      start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    if (value === "week") start.setDate(start.getDate() - 6);
    if (value === "month") start.setDate(1);
    setDraft((current) => ({
      ...current,
      from_date: dayBoundary(dayString(start)),
      to_date: dayBoundary(dayString(today), true),
    }));
  }
  const chips: { key: string; label: string; remove: string[] }[] =
    Object.entries(active)
      .filter(([key]) => !["from_date", "to_date"].includes(key))
      .map(([key, value]) => {
        const labels: Record<string, string> = {
          q: `Search: ${value}`,
          status: `Status: ${choiceLabel(leadStatusChoices, value)}`,
          source: `Source: ${choiceLabel(leadSourceChoices, value)}`,
          owner_id: `Assigned to: ${value === "unassigned" ? "Unassigned" : memberChoices.find((member) => member.value === value)?.label || "Unavailable member"}`,
          callback: `Follow-up: ${choiceLabel(followups, value)}`,
          city: `City: ${value}`,
          state: `State: ${value}`,
          category: `Category: ${choiceLabel(categoryLabels, value)}`,
          stage: `Sales stage: ${choiceLabel(stages, value)}`,
          interest: `Interest: ${value}`,
          dnd: `Contact preference: ${choiceLabel(contactChoices, value)}`,
          reported_by: `Marked lost by: ${memberChoices.find((member) => member.value === value)?.label || "Unavailable member"}`,
          reason: `Lost reason: ${value}`,
        };
        return { key, label: labels[key], remove: [key] };
      });
  if (values.from_date || values.to_date) {
    const days = wholeDays(values);
    chips.push({
      key: "dates",
      label: `Added: ${values.from_date ? `from ${readableDate(values.from_date, !days)}` : ""}${values.from_date && values.to_date ? " " : ""}${values.to_date ? `${days ? "through" : "before"} ${readableDate(values.to_date, !days, days)}` : " onwards"}`,
      remove: ["from_date", "to_date"],
    });
  }
  return (
    <>
      <div className="table-toolbar lead-filter-toolbar">
        <label className="field lead-filter-search">
          <span>Find a lead</span>
          <div className="search-field">
            <Search size={17} />
            <input
              aria-label="Search lead list"
              placeholder="Name, phone number or city"
              value={values.q || ""}
              onChange={(e) => update("q", e.target.value)}
            />
          </div>
        </label>
        {!lost && (
          <Select
            label="Lead status"
            value={values.status || ""}
            all="All statuses"
            choices={leadStatusChoices}
            onChange={(value) => update("status", value)}
          />
        )}
        <Select
          label="Lead source"
          value={values.source || ""}
          all="All sources"
          choices={leadSourceChoices}
          onChange={(value) => update("source", value)}
        />
        {!["telecaller", "field_executive"].includes(role) && (
          <Select
            label="Assigned to"
            missingLabel="Unavailable team member (saved filter)"
            value={values.owner_id || ""}
            all="Anyone on the team"
            choices={[
              { value: "unassigned", label: "Unassigned" },
              ...memberChoices,
            ]}
            onChange={(value) => update("owner_id", value)}
          />
        )}
        <Button
          type="button"
          variant="secondary"
          aria-haspopup="dialog"
          onClick={edit}
        >
          <Filter size={16} />
          More filters
          {extraCount > 0 && <span className="filter-count">{extraCount}</span>}
        </Button>
        <button
          className="icon-button"
          aria-label="Export filtered leads"
          title="Download the leads matching these filters"
          onClick={onExport}
        >
          <Download size={18} />
        </button>
      </div>
      <div className="lead-filter-summary">
        <p role="status" aria-live="polite">
          {failed
            ? "Unable to load results. Your filters are kept."
            : loading
              ? "Updating leads…"
              : `${total ?? 0} ${total === 1 ? "lead" : "leads"} ${chips.length ? `${total === 1 ? "matches" : "match"} your filters` : lost ? "in lost deals" : "in this workspace"}`}
        </p>
        {chips.length > 0 && (
          <button className="text-button" onClick={reset}>
            Clear all filters
          </button>
        )}
        {chips.length > 0 && (
          <div
            className="applied-lead-filters"
            aria-label="Active lead filters"
          >
            {chips.map((chip) => (
              <button
                key={chip.key}
                aria-label={`Remove filter: ${chip.label}`}
                onClick={() => {
                  const next = { ...values };
                  chip.remove.forEach((key) => delete next[key]);
                  onChange(next);
                }}
              >
                {chip.label}
                <X size={14} />
              </button>
            ))}
            <small>Leads must match all selected filters.</small>
          </div>
        )}
      </div>
      {open && (
        <Dialog
          title="Filter leads"
          description="Choose filters, then select Apply filters to update your list."
          onClose={() => setOpen(false)}
        >
          <form
            onSubmit={(event) => {
              event.preventDefault();
              const start = validDate(draft.from_date),
                end = validDate(draft.to_date);
              if (
                (draft.from_date && !start) ||
                (draft.to_date && !end) ||
                (start && end && start >= end)
              ) {
                setDateError(
                  "Choose an end date on or after the start date. For exact times, the end must be later.",
                );
                return;
              }
              onChange(
                Object.fromEntries(
                  Object.entries(activeValues(draft)).map(([key, value]) => [
                    key,
                    value.trim(),
                  ]),
                ),
              );
              setOpen(false);
            }}
          >
            <div className="dialog-content lead-filter-dialog">
              {definitionsQuery && (
                <QueryNotice query={definitionsQuery} loading />
              )}
              <section>
                <h3>Follow-up & contact</h3>
                <div className="form-grid">
                  <Select
                    label="Follow-up timing"
                    value={draft.callback || ""}
                    all="Any follow-up time"
                    choices={followups}
                    onChange={(value) => set("callback", value)}
                    hint="Not contacted in 48 hours means no first contact recorded and the lead was added over 48 hours ago."
                  />
                  <Select
                    label="Contact preference"
                    value={draft.dnd || ""}
                    all="All contact preferences"
                    choices={contactChoices}
                    onChange={(value) => set("dnd", value)}
                    hint="Do not contact means the customer has opted out."
                  />
                </div>
              </section>
              <section>
                <h3>Location & requirements</h3>
                <div className="form-grid">
                  <Text
                    label="City"
                    value={draft.city || ""}
                    onChange={(value) => set("city", value)}
                    hint="Full city name, e.g. Panipat. Capital letters do not matter."
                  />
                  <Text
                    label="State / region"
                    value={draft.state || ""}
                    onChange={(value) => set("state", value)}
                  />
                  <Select
                    label={realEstate ? "Property category" : "Lead category"}
                    value={draft.category || ""}
                    all={
                      definitionsUnavailable
                        ? definitionsQuery?.isError
                          ? "Categories unavailable"
                          : "Loading categories…"
                        : "All categories"
                    }
                    choices={categories}
                    disabled={definitionsUnavailable}
                    missingLabel={
                      definitionsUnavailable
                        ? `Saved category: ${draft.category || ""}`
                        : `${choiceLabel(categoryLabels, draft.category || "")} (previous category)`
                    }
                    onChange={(value) => set("category", value)}
                    hint="Matches the saved category or a recorded category interest."
                  />
                  <Text
                    label="Property / project interest"
                    value={draft.interest || ""}
                    onChange={(value) => set("interest", value)}
                    hint="Search what the customer asked for, e.g. a project name. Part of the name is enough."
                  />
                  <Select
                    label="Sales stage"
                    value={draft.stage || ""}
                    all={
                      definitionsUnavailable
                        ? definitionsQuery?.isError
                          ? "Sales stages unavailable"
                          : "Loading sales stages…"
                        : "All sales stages"
                    }
                    choices={stages}
                    disabled={definitionsUnavailable}
                    onChange={(value) => set("stage", value)}
                    hint="Your team's progress steps, separate from the lead's call status."
                  />
                </div>
              </section>
              <section>
                <h3>When was the lead added?</h3>
                <div className="form-grid">
                  <label className="field wide">
                    <span>Lead added</span>
                    <select
                      aria-label="Lead added"
                      value={period}
                      onChange={(e) => preset(e.target.value)}
                    >
                      <option value="any">Any date</option>
                      <option value="today">Today</option>
                      <option value="week">Last 7 days</option>
                      <option value="month">This month</option>
                      <option value="custom">Choose dates</option>
                      <option value="exact">Exact date and time</option>
                    </select>
                    <small>
                      Dates use your browser's local time. Saved filters keep
                      the selected dates.
                    </small>
                  </label>
                  {period !== "any" &&
                    (period === "exact" ? (
                      <>
                        <label className="field">
                          <span>Added from (time)</span>
                          <input
                            aria-label="Added from (time)"
                            type="datetime-local"
                            value={timeInput(draft.from_date)}
                            onChange={(e) =>
                              set(
                                "from_date",
                                e.target.value
                                  ? new Date(e.target.value).toISOString()
                                  : "",
                              )
                            }
                          />
                        </label>
                        <label className="field">
                          <span>Added before (time)</span>
                          <input
                            aria-label="Added before (time)"
                            type="datetime-local"
                            value={timeInput(draft.to_date)}
                            onChange={(e) =>
                              set(
                                "to_date",
                                e.target.value
                                  ? new Date(e.target.value).toISOString()
                                  : "",
                              )
                            }
                          />
                          <small>This end time is excluded.</small>
                        </label>
                      </>
                    ) : (
                      <>
                        <label className="field">
                          <span>Added from date</span>
                          <input
                            aria-label="Added from date"
                            type="date"
                            value={dateInput(draft.from_date)}
                            onChange={(e) => {
                              setPeriod("custom");
                              set("from_date", dayBoundary(e.target.value));
                            }}
                          />
                        </label>
                        <label className="field">
                          <span>Added through date</span>
                          <input
                            aria-label="Added through date"
                            type="date"
                            value={dateInput(draft.to_date, true)}
                            onChange={(e) => {
                              setPeriod("custom");
                              set("to_date", dayBoundary(e.target.value, true));
                            }}
                          />
                          <small>Includes the whole final day.</small>
                        </label>
                      </>
                    ))}
                </div>
                {dateError && (
                  <p role="alert" className="filter-date-error">
                    {dateError}
                  </p>
                )}
              </section>
              {(lost ||
                draft.status === "lost" ||
                draft.reason ||
                draft.reported_by) && (
                <section>
                  <h3>Lost lead details</h3>
                  <div className="form-grid">
                    <Text
                      label="Lost reason contains"
                      value={draft.reason || ""}
                      onChange={(value) => set("reason", value)}
                    />
                    <Select
                      label="Marked lost by"
                      missingLabel="Unavailable team member (saved filter)"
                      value={draft.reported_by || ""}
                      all="Anyone on the team"
                      choices={memberChoices}
                      onChange={(value) => set("reported_by", value)}
                    />
                  </div>
                </section>
              )}
            </div>
            <footer className="lead-filter-footer">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setDraft({
                    ...(lost ? { status: "lost" } : {}),
                    q: draft.q || "",
                    source: draft.source || "",
                    owner_id: draft.owner_id || "",
                    ...(!lost && draft.status ? { status: draft.status } : {}),
                  });
                  setPeriod("any");
                  setDateError("");
                }}
              >
                Reset more filters
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button>Apply filters</Button>
            </footer>
          </form>
        </Dialog>
      )}
    </>
  );
}
