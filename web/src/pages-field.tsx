import { useState } from "react";
import { Link } from "react-router-dom";
import {
  CalendarDays,
  Check,
  MapPin,
  Phone,
  Plus,
  RefreshCw,
  UserRound,
} from "lucide-react";
import { params, send } from "./api";
import { useAction, useAuth, useData, useDirectory } from "./main";
import { LeadPicker } from "./pages-leads";
import { PropertyPicker } from "./pages-estate";
import type { FieldHandoff } from "./estate-types";
import type { Lead } from "./types";
import {
  Badge,
  Button,
  Empty,
  ErrorBox,
  FormDialog,
  Load,
  PageHeading,
  Panel,
  Stat,
  dateTime,
  type Field,
} from "./ui";

const active = (item: FieldHandoff) =>
  item.current && !["closed", "cancelled"].includes(item.status);
const statuses = [
  ["active", "Active work"],
  ["pending", "Awaiting acceptance"],
  ["accepted", "Visit arranged"],
  ["follow_up", "Follow-up needed"],
  ["ready_for_booking", "Ready for booking"],
  ["closed", "Closed"],
  ["cancelled", "Cancelled"],
];
const label = (value: string) =>
  statuses.find(([key]) => key === value)?.[1] || value;
const localTime = (value: string) => {
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
};
interface WorkData {
  items: FieldHandoff[];
  total: number;
  summary: Record<string, number>;
}

export function FieldWorkPage() {
  const { session } = useAuth();
  const [status, setStatus] = useState("active"),
    [search, setSearch] = useState(""),
    [due, setDue] = useState(""),
    [page, setPage] = useState(1),
    [adding, setAdding] = useState(false);
  const q = useData<WorkData>(
    "/field-work?" + params({ status, q: search, due, page }),
  );
  const realEstate = session?.organization?.settings.industry === "real_estate";
  return (
    <>
      <PageHeading
        eyebrow="FROM THE FIRST CALL TO THE SITE VISIT"
        title={
          session?.role === "field_executive"
            ? "Your field work"
            : "Visits & field handoffs"
        }
        description="Know who is responsible, what the client agreed to, and the next step. The caller stays involved throughout."
        actions={
          realEstate && session?.role !== "field_executive" ? (
            <Button onClick={() => setAdding(true)}>
              <Plus size={17} />
              Arrange visit & hand off
            </Button>
          ) : undefined
        }
      />
      <div className="stats-grid field-work-stats">
        <Stat
          label="Awaiting acceptance"
          value={q.data?.summary.pending || 0}
          detail="Executive confirmation needed"
        />
        <Stat
          label="Visits arranged"
          value={q.data?.summary.accepted || 0}
          detail="Accepted client handoffs"
        />
        <Stat
          label="Follow-ups"
          value={q.data?.summary.follow_up || 0}
          detail="Dated next actions"
        />
        <Stat
          label="Ready for booking"
          value={q.data?.summary.ready_for_booking || 0}
          detail="Manager review needed"
        />
      </div>
      <div className="filter-row field-work-filters">
        <label className="field">
          <span>Find a client</span>
          <input
            type="search"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Name or phone number"
          />
        </label>
        <label className="field">
          <span>Work status</span>
          <select
            aria-label="Work status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All work</option>
            {statuses.map(([value, text]) => (
              <option key={value} value={value}>
                {text}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Next step timing</span>
          <select
            aria-label="Next step timing"
            value={due}
            onChange={(e) => {
              setDue(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Any time</option>
            <option value="overdue">Overdue visits or follow-ups</option>
          </select>
        </label>
        <Button variant="secondary" onClick={() => void q.refetch()}>
          <RefreshCw size={16} />
          Refresh work
        </Button>
      </div>
      <Load query={q}>
        {(data) =>
          data.items.length ? (
            <div className="field-work-list">
              {data.items.map((item) => (
                <HandoffCard key={item.id} item={item} />
              ))}
            </div>
          ) : (
            <Empty
              title={
                search || due || status !== "active"
                  ? "No handoffs match these filters"
                  : "No active field work yet"
              }
              description={
                session?.role === "field_executive"
                  ? "Your team assigns confirmed visits here. Refresh after an assignment, or try All work to review previous cases."
                  : "Open a client, confirm their visit, and choose an active field executive. You can also arrange it here."
              }
            />
          )
        }
      </Load>
      <div className="pagination">
        <span>
          {q.data?.total || 0} handoffs · Page {page}
        </span>
        <div>
          <Button
            variant="secondary"
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <Button
            variant="secondary"
            disabled={page * 25 >= (q.data?.total || 0)}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      </div>
      {adding && <HandoffForm close={() => setAdding(false)} />}
    </>
  );
}

export function LeadFieldWork({ lead }: { lead: Lead }) {
  const { session } = useAuth();
  const enabled = session?.organization?.settings.industry === "real_estate";
  const q = useData<WorkData>(
    "/field-work?" + params({ lead_id: lead.id }),
    enabled,
  );
  const [adding, setAdding] = useState(false);
  if (!enabled) return null;
  const current = q.data?.items.find((item) => item.current);
  return (
    <Panel
      title="Visit & field executive"
      description="The field executive takes the visit and next steps. The caller keeps access for coordination."
      action={
        session?.role !== "field_executive" &&
        !q.isPending &&
        !q.isError &&
        (!current || !active(current)) ? (
          <Button variant="secondary" onClick={() => setAdding(true)}>
            <Plus size={16} />
            Arrange visit & hand off
          </Button>
        ) : undefined
      }
    >
      <Load query={q}>
        {(data) =>
          data.items.length ? (
            <HandoffCard
              item={data.items.find((item) => item.current) || data.items[0]}
              compact
            />
          ) : (
            <p className="help-text">
              When the client agrees to a property visit, choose the executive,
              meeting point and visit time here.
            </p>
          )
        }
      </Load>
      {adding && <HandoffForm lead={lead} close={() => setAdding(false)} />}
    </Panel>
  );
}

function HandoffForm({ close, lead }: { close: () => void; lead?: Lead }) {
  const dir = useDirectory(),
    action = useAction();
  const [requestId] = useState(() => crypto.randomUUID());
  return (
    <FormDialog
      title="Arrange visit & hand off"
      submitLabel="Assign field executive"
      onClose={close}
      dependencies={[dir]}
      description="Confirm the client's agreement first. The executive will receive the visit, client history and your brief. Your caller access stays in place."
      fields={[
        {
          name: "lead_id",
          label: "Client",
          render: (v, set) =>
            lead ? (
              <>
                <label className="field">
                  <span>Client</span>
                  <input readOnly value={`${lead.name} · ${lead.phone}`} />
                </label>
                <small className="muted">
                  Selected from the client profile you opened.
                </small>
              </>
            ) : (
              <LeadPicker
                required
                label="Client"
                value={String(v || "")}
                onChange={set}
              />
            ),
        },
        {
          name: "executive_id",
          label: "Field executive",
          required: true,
          options: (dir.data || [])
            .filter((u) => u.role === "field_executive")
            .map((u) => ({ value: u.id, label: u.name })),
        },
        {
          name: "property_id",
          label: "Property",
          render: (v, set) => (
            <PropertyPicker value={String(v || "")} onChange={set} />
          ),
        },
        {
          name: "starts_at",
          label: "Visit date & time",
          type: "datetime-local",
          required: true,
        },
        {
          name: "duration_minutes",
          label: "Visit duration (minutes)",
          type: "number",
          min: "15",
          max: "480",
          step: "1",
          required: true,
          defaultValue: "60",
        },
        {
          name: "meeting_point",
          label: "Meeting point",
          required: true,
          maxLength: 500,
          hint: "For example, the property gate or your office reception.",
        },
        {
          name: "brief",
          label: "Client discussion & handoff brief",
          type: "textarea",
          required: true,
          maxLength: 4000,
          wide: true,
          hint: "Record the client's requirements, budget, questions and anything the executive should prepare.",
        },
        {
          name: "client_confirmed",
          label: "The client agreed to this property visit and time",
          type: "checkbox",
          wide: true,
        },
      ]}
      initial={{ lead_id: lead?.id || "" }}
      onSubmit={(v) => {
        if (!v.client_confirmed)
          throw new Error(
            "Confirm that the client agreed to the visit and time.",
          );
        return action(() =>
          send("/field-work", {
            ...v,
            lead_id: lead?.id || v.lead_id,
            starts_at: new Date(String(v.starts_at)).toISOString(),
            duration_minutes: Number(v.duration_minutes),
            request_id: requestId,
          }),
        );
      }}
    >
      {!dir.isPending &&
        !dir.isError &&
        !dir.data?.some((u) => u.role === "field_executive") && (
          <p className="billing-notice">
            No active field executive is available. Ask your company admin to
            add someone in People → Team directory with the Field executive
            role.
          </p>
        )}
    </FormDialog>
  );
}

function HandoffCard({
  item,
  compact = false,
}: {
  item: FieldHandoff;
  compact?: boolean;
}) {
  const { session } = useAuth(),
    action = useAction();
  const [dialog, setDialog] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(null);
  const canProgress =
    session?.role === "field_executive" ||
    ["admin", "manager"].includes(session?.role || "");
  const isActive = active(item);
  const patch = (data: Record<string, unknown>) =>
    action(() =>
      send(
        "/field-work/" + item.id,
        { version: item.version, ...data },
        "PATCH",
      ),
    );
  async function accept() {
    setBusy(true);
    setError(null);
    try {
      await patch({ action: "accept" });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <article
      className={compact ? "field-work-card compact" : "field-work-card"}
    >
      <div className="field-work-card-header">
        <div>
          <small className="eyebrow">
            {item.current ? "CLIENT HANDOFF" : "PREVIOUS HANDOFF"}
          </small>
          {!compact && <h2>{item.lead_name}</h2>}
          <a href={"tel:" + item.lead_phone}>
            <Phone size={15} />
            {item.lead_phone}
          </a>
        </div>
        <Badge value={item.status} label={label(item.status)} />
      </div>
      <div className="field-work-assignment">
        <span>
          <UserRound size={16} />
          <strong>{item.executive_name}</strong> · Field executive
        </span>
        <small>Caller / coordinator: {item.coordinator_name}</small>
      </div>
      <div className="field-work-visit">
        <CalendarDays size={20} />
        <div>
          <strong>Scheduled: {dateTime(item.visit.starts_at)}</strong>
          {item.visit.actual_started_at && (
            <small>
              Client attended: {dateTime(item.visit.actual_started_at)}
            </small>
          )}
          <small>
            {item.visit.duration_minutes} minutes · {item.visit.status}
          </small>
          <Link to={"/app/properties/" + item.visit.property_id}>
            {item.visit.property_reference} · {item.visit.property_title}
          </Link>
        </div>
      </div>
      <p className="field-meeting">
        <MapPin size={17} />
        <span>
          <strong>Meet at: </strong>
          {item.meeting_point}
          {item.property_address && (
            <small className="block muted">
              Property address: {item.property_address}
            </small>
          )}
        </span>
      </p>
      <details className="field-brief" open={compact}>
        <summary>Client discussion & preparation</summary>
        <p>{item.brief}</p>
        <small className="muted">Prepared by {item.created_by_name}</small>
      </details>
      {item.status === "pending" && (
        <p className="field-next">
          Next: {item.executive_name} accepts this handoff and reviews the
          client's history.
        </p>
      )}
      {item.status === "accepted" && (
        <p className="field-next">
          Next:{" "}
          {item.visit.status === "scheduled"
            ? "Meet the client, then record the visit outcome and next step."
            : "Review the client and record the next follow-up."}
        </p>
      )}
      {item.status === "follow_up" && (
        <div
          className={
            new Date(item.follow_up_at || "").getTime() < Date.now()
              ? "field-next overdue"
              : "field-next"
          }
        >
          <strong>{item.next_action}</strong>
          <span>Due {dateTime(item.follow_up_at)}</span>
        </div>
      )}
      {item.status === "ready_for_booking" && (
        <p className="field-next">
          Next: a manager or company admin reviews the terms and creates the
          property booking.
        </p>
      )}
      {item.feedback && (
        <p className="field-feedback">
          <strong>Latest update: </strong>
          {item.feedback}
        </p>
      )}
      {error !== null && <ErrorBox error={error} />}
      <div className="field-work-actions">
        {!compact && (session?.role !== "field_executive" || item.current) && (
          <Link className="button secondary" to={"/app/leads/" + item.lead_id}>
            Open client history
          </Link>
        )}
        {isActive &&
          item.status === "pending" &&
          session?.role === "field_executive" && (
            <Button disabled={busy} onClick={() => void accept()}>
              <Check size={16} />
              {busy ? "Accepting…" : "Accept handoff"}
            </Button>
          )}
        {isActive && item.accepted_at && canProgress && (
          <Button
            onClick={() =>
              setDialog(
                item.visit.status === "scheduled"
                  ? "visit_outcome"
                  : "follow_up",
              )
            }
          >
            {item.visit.status === "scheduled"
              ? "Record visit outcome"
              : "Record follow-up"}
          </Button>
        )}
        {isActive && (
          <Button variant="secondary" onClick={() => setDialog("reschedule")}>
            Reschedule / arrange another visit
          </Button>
        )}
        {isActive && ["admin", "manager"].includes(session?.role || "") && (
          <Button variant="secondary" onClick={() => setDialog("reassign")}>
            Change executive
          </Button>
        )}
        {item.status === "ready_for_booking" &&
          ["admin", "manager"].includes(session?.role || "") && (
            <Link
              className="button"
              to={
                "/app/bookings?" +
                params({
                  lead_id: item.lead_id,
                  property_id: item.visit.property_id,
                  agent_id: item.executive_id,
                })
              }
            >
              Create booking
            </Link>
          )}
        {isActive && (
          <Button variant="danger-quiet" onClick={() => setDialog("cancel")}>
            Cancel field work
          </Button>
        )}
      </div>
      {dialog && (
        <HandoffUpdate
          item={item}
          mode={dialog}
          close={() => setDialog("")}
          save={patch}
        />
      )}
    </article>
  );
}

function HandoffUpdate({
  item,
  mode,
  close,
  save,
}: {
  item: FieldHandoff;
  mode: string;
  close: () => void;
  save: (data: Record<string, unknown>) => Promise<unknown>;
}) {
  const [step, setStep] = useState("follow_up");
  const [visitResult, setVisitResult] = useState("completed");
  const [earlyVisit, setEarlyVisit] = useState(false);
  const [version] = useState(item.version);
  const dir = useDirectory();
  const progress = ["visit_outcome", "follow_up"].includes(mode);
  const fields: Field[] = [];
  if (mode === "reassign")
    fields.push({
      name: "executive_id",
      label: "New field executive",
      required: true,
      options: (dir.data || [])
        .filter(
          (u) => u.role === "field_executive" && u.id !== item.executive_id,
        )
        .map((u) => ({ value: u.id, label: u.name })),
    });
  if (mode === "reschedule")
    fields.push(
      {
        name: "property_id",
        label: "Property",
        render: (v, set) => (
          <PropertyPicker value={String(v || "")} onChange={set} />
        ),
      },
      {
        name: "starts_at",
        label: "New visit date & time",
        type: "datetime-local",
        required: true,
      },
      {
        name: "duration_minutes",
        label: "Visit duration (minutes)",
        type: "number",
        required: true,
        min: "15",
        max: "480",
        step: "1",
      },
      {
        name: "meeting_point",
        label: "Meeting point",
        required: true,
        maxLength: 500,
      },
    );
  if (mode === "visit_outcome") {
    fields.push({
      name: "scheduled_visit",
      label: "Scheduled visit",
      wide: true,
      render: () => (
        <p className="help-text">
          Scheduled visit: {dateTime(item.visit.starts_at)}. If the client
          already attended, record the actual earlier time below.
        </p>
      ),
    });
    fields.push({
      name: "visit_status",
      label: "Visit result",
      required: true,
      render: (value, set) => (
        <label className="field">
          <span>Visit result *</span>
          <select
            required
            aria-label="Visit result"
            value={String(value || "completed")}
            onChange={(event) => {
              set(event.target.value);
              setVisitResult(event.target.value);
            }}
          >
            <option value="completed">Client attended</option>
            <option value="no-show">Client did not attend</option>
          </select>
        </label>
      ),
      defaultValue: "completed",
    });
    if (visitResult === "completed") {
      fields.push({
        name: "early_visit_confirmed",
        label: "Visit happened before the scheduled time",
        wide: true,
        render: (value, set) => (
          <label className="field check-field">
            <input
              type="checkbox"
              checked={Boolean(value)}
              onChange={(event) => {
                set(event.target.checked);
                setEarlyVisit(event.target.checked);
              }}
            />
            <span>Visit happened before the scheduled time</span>
          </label>
        ),
      });
      if (earlyVisit)
        fields.push({
          name: "actual_started_at",
          label: "Actual visit date & time",
          type: "datetime-local",
          required: true,
          hint: "Enter when the client attended. This must be in the past and before the scheduled visit. The original schedule stays in history.",
        });
    }
  }
  if (progress)
    fields.push({
      name: "next_step",
      label: "What happens next?",
      render: (value, set) => (
        <label className="field">
          <span>What happens next? *</span>
          <select
            required
            aria-label="What happens next?"
            value={String(value || "follow_up")}
            onChange={(e) => {
              set(e.target.value);
              setStep(e.target.value);
            }}
          >
            <option value="follow_up">Follow up with client</option>
            <option value="ready_for_booking">
              Ready for manager's booking review
            </option>
            <option value="closed">Close field work</option>
          </select>
        </label>
      ),
      defaultValue: "follow_up",
    });
  fields.push({
    name: "feedback",
    label: progress ? "Client feedback & discussion" : "Reason / instructions",
    type: "textarea",
    required: true,
    maxLength: 4000,
    wide: true,
  });
  if (progress && step === "follow_up")
    fields.push(
      {
        name: "next_action",
        label: "Next action",
        required: true,
        maxLength: 200,
        hint: "For example, confirm loan documents or discuss the revised price.",
      },
      {
        name: "follow_up_at",
        label: "Follow-up date & time",
        type: "datetime-local",
        required: true,
        hint: "Choose a future date and time for the next follow-up.",
      },
    );
  return (
    <FormDialog
      title={
        {
          reschedule: "Arrange the next visit",
          reassign: "Change field executive",
          visit_outcome: "Record visit outcome & next step",
          follow_up: "Record client follow-up",
          cancel: "Cancel this field handoff",
        }[mode] || "Update field work"
      }
      description={
        mode === "cancel"
          ? "The visit and linked follow-up are cancelled together. The client record and history are retained."
          : "Save the client discussion and a clear next step. A follow-up creates a dated task for the responsible executive."
      }
      onClose={close}
      submitLabel="Save field update"
      dependencies={mode === "reassign" ? [dir] : []}
      fields={fields}
      initial={{
        property_id: item.visit.property_id,
        duration_minutes: String(item.visit.duration_minutes),
        meeting_point: item.meeting_point,
        starts_at:
          new Date(item.visit.starts_at).getTime() > Date.now()
            ? localTime(item.visit.starts_at)
            : "",
        next_action: item.next_action,
        follow_up_at: item.follow_up_at ? localTime(item.follow_up_at) : "",
      }}
      onSubmit={(v) =>
        save({
          action: mode,
          feedback: v.feedback,
          version,
          ...(mode === "reassign" ? { executive_id: v.executive_id } : {}),
          ...(mode === "reschedule"
            ? {
                property_id: v.property_id,
                starts_at: new Date(String(v.starts_at)).toISOString(),
                duration_minutes: Number(v.duration_minutes),
                meeting_point: v.meeting_point,
              }
            : {}),
          ...(mode === "visit_outcome"
            ? {
                visit_status: v.visit_status,
                ...(v.visit_status === "completed" && v.early_visit_confirmed
                  ? {
                      early_visit_confirmed: true,
                      actual_started_at: new Date(
                        String(v.actual_started_at),
                      ).toISOString(),
                    }
                  : {}),
              }
            : {}),
          ...(progress
            ? {
                next_step: v.next_step,
                ...(v.next_step === "follow_up"
                  ? {
                      next_action: v.next_action,
                      follow_up_at: new Date(
                        String(v.follow_up_at),
                      ).toISOString(),
                    }
                  : {}),
              }
            : {}),
        })
      }
    >
      <p className="help-text">
        Closing field work retains the lead. Only a manager or admin can create
        a booking; booking values do not verify a bank payment.
      </p>
    </FormDialog>
  );
}
