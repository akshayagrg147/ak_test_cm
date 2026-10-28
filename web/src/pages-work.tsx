import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowDownLeft,
  ArrowUpRight,
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  Download,
  List,
  MapPin,
  Plus,
  Search,
  Upload,
  UserPlus,
} from "lucide-react";
import { api, download, params, send, setSession } from "./api";
import { useAction, useAuth, useData, useDirectory } from "./main";
import { AudioFile, LeadPicker } from "./pages-leads";
import type {
  Attendance,
  PhoneCall,
  Submission,
  Task,
  User,
  Session,
} from "./types";
import {
  Badge,
  Button,
  Empty,
  ErrorBox,
  FormDialog,
  Load,
  PageHeading,
  Panel,
  QueryNotice,
  RecordingBadge,
  Stat,
  Table,
  dateTime,
  duration,
  options,
  recordingLabel,
  type Field,
  type Values,
} from "./ui";

function localInput(value: string) {
  const d = new Date(value);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}
function monthNow() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}
function nameOf(dir: { id: string; name: string }[] | undefined, id: string) {
  return dir?.find((u) => u.id === id)?.name || "Team member";
}

export function TasksPage() {
  const nav = useNavigate();
  const { session } = useAuth();
  const [sp] = useSearchParams();
  const [state, setState] = useState("open");
  const [view, setView] = useState("list");
  const [owner, setOwner] = useState("");
  const [month, setMonth] = useState(monthNow());
  const [page, setPage] = useState(1);
  const [kind, setKind] = useState("");
  const [priority, setPriority] = useState("");
  const [editing, setEditing] = useState<Task | true | null>(
    sp.get("lead_id") ? true : null,
  );
  const [error, setError] = useState<unknown>(null);
  const action = useAction();
  const dir = useDirectory();
  const q = useData<Task[]>(
    "/tasks?" +
      params({
        state,
        page,
        kind,
        priority,
        owner_id: owner,
        ...(view === "calendar"
          ? {
              from_date: new Date(month + "-01T00:00:00").toISOString(),
              to_date: new Date(
                Number(month.slice(0, 4)),
                Number(month.slice(5)),
                1,
              ).toISOString(),
            }
          : {}),
      }),
  );
  function update(t: Task, next: string) {
    void action(() =>
      send(
        `/tasks/${t.id}`,
        {
          title: t.title,
          description: t.description,
          lead_id: t.lead_id,
          owner_id: t.owner_id,
          kind: t.kind,
          priority: t.priority,
          due_at: t.due_at,
          state: next,
        },
        "PUT",
      ),
    ).catch(setError);
  }
  const fields: Field[] = [
    { name: "title", label: "Task title", required: true, wide: true },
    { name: "description", label: "Details", type: "textarea", wide: true },
    {
      name: "lead_id",
      label: "Related lead",
      wide: true,
      render: (value, set) => (
        <LeadPicker value={String(value || "")} onChange={set} />
      ),
    },
    {
      name: "owner_id",
      label: "Owner",
      required: true,
      defaultValue: ["telecaller", "field_executive"].includes(
        session?.role || "",
      )
        ? session?.user.id
        : undefined,
      options: (dir.data || [])
        .filter(
          (u) =>
            !["telecaller", "field_executive"].includes(session?.role || "") ||
            u.id === session?.user.id,
        )
        .map((u) => ({ value: u.id, label: u.name })),
    },
    {
      name: "kind",
      label: "Type",
      options: options(["callback", "task", "meeting", "reminder"]),
      defaultValue: "task",
      required: true,
    },
    {
      name: "priority",
      label: "Priority",
      options: options(["low", "normal", "high", "urgent"]),
      defaultValue: "normal",
      required: true,
    },
    {
      name: "due_at",
      label: "Due date & time",
      type: "datetime-local",
      required: true,
    },
    {
      name: "state",
      label: "State",
      options: options(["open", "completed", "cancelled"]),
      defaultValue: "open",
      required: true,
    },
  ];
  const initial: Values =
    editing && editing !== true
      ? {
          title: editing.title,
          description: editing.description,
          lead_id: editing.lead_id || "",
          owner_id: editing.owner_id,
          kind: editing.kind,
          priority: editing.priority,
          due_at: localInput(editing.due_at),
          state: editing.state,
        }
      : { lead_id: sp.get("lead_id") || "" };
  return (
    <>
      <PageHeading
        eyebrow="MAKE SPACE FOR WHAT’S NEXT"
        title="Tasks & calendar"
        description="Small next steps. Meaningful progress."
        actions={
          <Button onClick={() => setEditing(true)}>
            <Plus size={17} />
            Create task
          </Button>
        }
      />
      <div className="filter-row">
        <div className="segmented">
          <button
            className={view === "list" ? "active" : ""}
            onClick={() => {
              setView("list");
              setPage(1);
            }}
          >
            <List size={16} />
            List
          </button>
          <button
            className={view === "calendar" ? "active" : ""}
            onClick={() => {
              setView("calendar");
              setPage(1);
            }}
          >
            <CalendarDays size={16} />
            Calendar
          </button>
        </div>
        <select
          aria-label="Task state"
          value={state}
          onChange={(e) => {
            setState(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All states</option>
          {options(["open", "completed", "cancelled"]).map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <select
          aria-label="Task type"
          value={kind}
          onChange={(e) => {
            setKind(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All types</option>
          {options(["callback", "task", "meeting", "reminder"]).map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <select
          aria-label="Task priority"
          value={priority}
          onChange={(e) => {
            setPriority(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All priorities</option>
          {options(["low", "normal", "high", "urgent"]).map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        {!["telecaller", "field_executive"].includes(session?.role || "") && (
          <select
            aria-label="Task owner"
            value={owner}
            onChange={(e) => {
              setOwner(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Entire team</option>
            {dir.data?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </select>
        )}
        {view === "calendar" && (
          <input
            aria-label="Calendar month"
            type="month"
            value={month}
            onChange={(e) => {
              setMonth(e.target.value || monthNow());
              setPage(1);
            }}
          />
        )}
      </div>
      {error !== null && <ErrorBox error={error} />}
      <QueryNotice query={dir} />
      <Panel>
        <Load query={q}>
          {(tasks) =>
            !tasks.length ? (
              <Empty
                title="A little room in your day"
                description="Create a task to give the next step a time and a place."
              />
            ) : view === "list" ? (
              <Table
                headers={[
                  "",
                  "Task",
                  "Owner",
                  "Due",
                  "Priority",
                  "State",
                  "Actions",
                ]}
              >
                {tasks.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <button
                        className={`task-check ${t.state === "completed" ? "checked" : ""}`}
                        aria-label={
                          t.state === "completed"
                            ? `Reopen ${t.title}`
                            : `Complete ${t.title}`
                        }
                        disabled={!!t.field_handoff_id}
                        onClick={() =>
                          update(
                            t,
                            t.state === "completed" ? "open" : "completed",
                          )
                        }
                      >
                        <Check size={14} />
                      </button>
                    </td>
                    <td>
                      <button
                        className="text-button strong"
                        onClick={() =>
                          t.field_handoff_id
                            ? nav("/app/leads/" + t.lead_id)
                            : setEditing(t)
                        }
                      >
                        {t.title}
                      </button>
                      <small className="block muted">
                        {t.kind}
                        {t.lead_id && (
                          <>
                            {" "}
                            ·{" "}
                            <Link to={"/app/leads/" + t.lead_id}>
                              Open lead
                            </Link>
                          </>
                        )}
                      </small>
                    </td>
                    <td>{nameOf(dir.data, t.owner_id)}</td>
                    <td
                      className={
                        new Date(t.due_at) < new Date() && t.state === "open"
                          ? "overdue-text"
                          : ""
                      }
                    >
                      {dateTime(t.due_at)}
                    </td>
                    <td>
                      <Badge value={t.priority} />
                    </td>
                    <td>
                      <Badge value={t.state} />
                    </td>
                    <td>
                      {t.field_handoff_id ? (
                        <Link
                          className="text-button"
                          to={"/app/leads/" + t.lead_id}
                        >
                          Update field follow-up
                        </Link>
                      ) : (
                        <div className="inline-actions">
                          <button onClick={() => setEditing(t)}>Edit</button>
                          {t.state === "open" && (
                            <button onClick={() => update(t, "cancelled")}>
                              Cancel
                            </button>
                          )}
                          <button
                            onClick={() =>
                              void action(() =>
                                api(`/tasks/${t.id}`, { method: "DELETE" }),
                              ).catch(setError)
                            }
                          >
                            Delete
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </Table>
            ) : (
              <div className="calendar-grid">
                {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
                  <div className="calendar-weekday" key={d}>
                    {d}
                  </div>
                ))}
                {Array.from(
                  {
                    length: (new Date(month + "-01T00:00:00").getDay() + 6) % 7,
                  },
                  (_, i) => (
                    <div className="calendar-day blank" key={"blank" + i} />
                  ),
                )}
                {Array.from(
                  {
                    length: new Date(
                      Number(month.slice(0, 4)),
                      Number(month.slice(5)),
                      0,
                    ).getDate(),
                  },
                  (_, i) => {
                    const day = `${month}-${String(i + 1).padStart(2, "0")}`;
                    return (
                      <div className="calendar-day" key={day}>
                        <strong>{i + 1}</strong>
                        {tasks
                          .filter((t) => localInput(t.due_at).startsWith(day))
                          .map((t) => (
                            <button
                              key={t.id}
                              onClick={() =>
                                t.field_handoff_id
                                  ? nav("/app/leads/" + t.lead_id)
                                  : setEditing(t)
                              }
                              className={t.priority}
                            >
                              {t.title}
                            </button>
                          ))}
                      </div>
                    );
                  },
                )}
              </div>
            )
          }
        </Load>
        <div className="pagination">
          <span>
            Page {page} · {q.data?.length || 0} tasks
            {view === "calendar" ? " on this calendar page" : ""}
          </span>
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
              disabled={(q.data?.length || 0) < 100}
              onClick={() => setPage(page + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      </Panel>
      {editing && (
        <FormDialog
          title={editing === true ? "A useful next step" : "Edit task"}
          dependencies={[dir]}
          fields={fields}
          initial={initial}
          onClose={() => setEditing(null)}
          submitLabel="Save task"
          onSubmit={(v) =>
            action(() =>
              send(
                editing === true ? "/tasks" : `/tasks/${editing.id}`,
                {
                  ...v,
                  lead_id: v.lead_id || null,
                  owner_id: v.owner_id || null,
                  due_at: new Date(String(v.due_at)).toISOString(),
                },
                editing === true ? "POST" : "PUT",
              ),
            )
          }
        />
      )}
    </>
  );
}

export function AttendancePage() {
  const { session } = useAuth();
  const [month, setMonth] = useState(monthNow());
  const [team, setTeam] = useState(false);
  const [page, setPage] = useState(1);
  const [location, setLocation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [tick, setTick] = useState(Date.now());
  const action = useAction();
  const dir = useDirectory();
  const q = useData<Attendance[]>(
    "/attendance?" + params({ month, team, page }),
  );
  const own = useData<Attendance[]>("/attendance");
  const workplace = session?.organization?.settings.workplace;
  const open = own.data?.find((a) => !a.checked_out);
  useEffect(() => {
    const id = setInterval(() => setTick(Date.now()), 30000);
    return () => clearInterval(id);
  }, []);
  function checkIn() {
    setBusy(true);
    setError(null);
    setLocation("Finding your location…");
    if (!navigator.geolocation) {
      setError(
        new Error(
          "Geolocation is unavailable in this browser. Use a supported browser over HTTPS.",
        ),
      );
      setBusy(false);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation(`Location accuracy: ±${Math.round(pos.coords.accuracy)} m`);
        void action(() =>
          send("/attendance/check-in", {
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude,
            accuracy: pos.coords.accuracy,
          }),
        )
          .catch(setError)
          .finally(() => setBusy(false));
      },
      (err) => {
        setLocation("");
        setBusy(false);
        setError(
          new Error(
            err.code === 1
              ? "Location permission was denied. Allow location access in your browser settings and try again."
              : err.code === 3
                ? "Location request timed out. Move to a place with better reception and retry."
                : "Your location is unavailable. Check device location settings and retry.",
          ),
        );
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
    );
  }
  return (
    <>
      <QueryNotice query={own} />
      <QueryNotice query={dir} />
      <PageHeading
        eyebrow="PRESENT, WITH PURPOSE"
        title="Attendance"
        description="An explicit check-in. A clear record of your working day."
      />
      <div className="attendance-hero">
        <div className="attendance-status-icon">
          <MapPin size={30} />
        </div>
        <div>
          <span className="eyebrow">
            {workplace?.name || "WORKPLACE SETUP REQUIRED"}
          </span>
          <h2>{open ? "You’re checked in." : "Ready when you are."}</h2>
          <p>
            {open
              ? `Checked in ${dateTime(open.checked_in)} · ${Math.floor((Math.min(tick, new Date(open.cutoff).getTime()) - new Date(open.checked_in).getTime()) / 60000)} minutes elapsed`
              : workplace
                ? `Check in within ${workplace.radius} m of your workplace. ${workplace.timezone}.`
                : "An administrator needs to configure the workplace location before check-in."}
          </p>
          {location && <small>{location}</small>}
        </div>
        <Button
          disabled={busy || (!workplace && !open)}
          onClick={() => {
            if (open) {
              setBusy(true);
              void action(() =>
                api("/attendance/check-out", { method: "POST" }),
              )
                .catch(setError)
                .finally(() => setBusy(false));
            } else checkIn();
          }}
        >
          {busy ? "Please wait…" : open ? "Check out" : "Check in"}
          <ArrowUpRight size={18} />
        </Button>
      </div>
      {error !== null && <ErrorBox error={error} />}
      <p className="help-text">
        Check-in uses your device location and a server-calculated distance. GPS
        accuracy varies. Checking out creates eligible time for review. Open
        sessions close at workplace midnight, including after worker downtime.
      </p>
      <div className="filter-row">
        <input
          type="month"
          aria-label="Attendance month"
          value={month}
          onChange={(e) => setMonth(e.target.value || monthNow())}
        />
        {!["telecaller", "field_executive"].includes(session?.role || "") && (
          <div className="segmented">
            <button
              className={!team ? "active" : ""}
              onClick={() => {
                setTeam(false);
                setPage(1);
              }}
            >
              My attendance
            </button>
            <button
              className={team ? "active" : ""}
              onClick={() => {
                setTeam(true);
                setPage(1);
              }}
            >
              Team attendance
            </button>
          </div>
        )}
      </div>
      <Panel
        title="Attendance history"
        description="One check-in record per employee and workplace day"
      >
        <Load query={q}>
          {(records) =>
            records.length ? (
              <Table
                headers={[
                  "Day",
                  ...(team ? ["Team member"] : []),
                  "Checked in",
                  "Checked out",
                  "Duration",
                  "Closure",
                ]}
              >
                {records.map((a) => (
                  <tr key={a.id}>
                    <td>{a.day}</td>
                    {team && <td>{nameOf(dir.data, a.user_id)}</td>}
                    <td>{dateTime(a.checked_in)}</td>
                    <td>{dateTime(a.checked_out)}</td>
                    <td>
                      {a.checked_out
                        ? duration(
                            Math.max(
                              0,
                              Math.floor(
                                (new Date(a.checked_out).getTime() -
                                  new Date(a.checked_in).getTime()) /
                                  1000,
                              ),
                            ),
                          )
                        : "In progress"}
                    </td>
                    <td>
                      <Badge
                        value={
                          a.auto_closed
                            ? "midnight closure"
                            : a.checked_out
                              ? "manual checkout"
                              : "checked in"
                        }
                      />
                    </td>
                  </tr>
                ))}
              </Table>
            ) : (
              <Empty
                title="No check-ins this month"
                description="Your accepted check-ins will appear here."
              />
            )
          }
        </Load>
        <RecordsPager
          page={page}
          count={q.data?.length || 0}
          setPage={setPage}
        />
      </Panel>
    </>
  );
}

export function ApprovalsPage() {
  const { session } = useAuth();
  const [tab, setTab] = useState("time-entries");
  const [page, setPage] = useState(1);
  const [dialog, setDialog] = useState("");
  const [review, setReview] = useState<Submission | null>(null);
  const action = useAction();
  const dir = useDirectory();
  const q = useData<Submission[]>("/" + tab + "?page=" + page);
  const isAdmin = session?.role === "admin";
  const employee: Field[] = isAdmin
    ? [
        {
          name: "user_id",
          label: "Employee",
          required: true,
          options: (dir.data || [])
            .filter((u) => u.role !== "admin")
            .map((u) => ({ value: u.id, label: u.name })),
        },
      ]
    : [];
  return (
    <>
      <QueryNotice query={dir} />
      <PageHeading
        eyebrow="TIME WELL ACCOUNTED FOR"
        title="Time & leave"
        description={
          isAdmin
            ? "Review team submissions. Administrators use geofenced attendance for their own working day."
            : "Submit your work, plan your time away, and keep reviews in view."
        }
        actions={
          <>
            <Button variant="secondary" onClick={() => setDialog("leave")}>
              <CalendarDays size={16} />
              {isAdmin ? "Create employee leave" : "Request leave"}
            </Button>
            <Button onClick={() => setDialog("time")}>
              <Plus size={17} />
              {isAdmin ? "Create employee time" : "Submit time"}
            </Button>
          </>
        }
      />
      <div className="lead-tabs">
        <button
          className={tab === "time-entries" ? "active" : ""}
          onClick={() => {
            setTab("time-entries");
            setPage(1);
          }}
        >
          Work time
        </button>
        <button
          className={tab === "leave" ? "active" : ""}
          onClick={() => {
            setTab("leave");
            setPage(1);
          }}
        >
          Leave requests
        </button>
      </div>
      <Panel>
        <Load query={q}>
          {(records) =>
            records.length ? (
              <Table
                headers={[
                  "Employee",
                  tab === "leave" ? "Leave range" : "Work day",
                  tab === "leave" ? "Type" : "Hours",
                  "Details",
                  "Review state",
                  "Actions",
                ]}
              >
                {records.map((r) => (
                  <tr key={r.id}>
                    <td>{nameOf(dir.data, r.user_id)}</td>
                    <td>
                      {tab === "leave"
                        ? `${r.starts_on} → ${r.ends_on}`
                        : r.day}
                    </td>
                    <td>
                      {tab === "leave"
                        ? r.kind
                        : `${Number(r.hours).toFixed(2)} h`}
                    </td>
                    <td>
                      <span
                        className="truncate"
                        title={r.reason || r.description}
                      >
                        {r.reason || r.description}
                      </span>
                      <small className="block muted">
                        {r.source || "Leave request"}
                        {r.review_note ? " · " + r.review_note : ""}
                      </small>
                    </td>
                    <td>
                      <Badge value={r.state} />
                    </td>
                    <td>
                      {r.state === "pending" &&
                      !["telecaller", "field_executive"].includes(
                        session?.role || "",
                      ) &&
                      r.user_id !== session?.user.id &&
                      (isAdmin ||
                        ["telecaller", "field_executive"].includes(
                          dir.data?.find((u) => u.id === r.user_id)?.role || "",
                        )) ? (
                        <button
                          className="text-button"
                          onClick={() => setReview(r)}
                        >
                          Review <ChevronRight size={15} />
                        </button>
                      ) : (
                        <span className="muted">
                          {r.reviewer_id ? "Reviewed" : "Awaiting review"}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </Table>
            ) : (
              <Empty
                title="Nothing waiting here"
                description="Submitted time and leave will appear in this workspace."
              />
            )
          }
        </Load>
        <RecordsPager
          page={page}
          count={q.data?.length || 0}
          setPage={setPage}
        />
      </Panel>
      <p className="help-text">
        Only approved eligible time contributes to payroll estimates. Managers
        review telecallers and field executives; administrators review team
        submissions. Self-review is blocked on the server.
      </p>
      {dialog === "time" && (
        <FormDialog
          title="Account for your work"
          dependencies={isAdmin ? [dir] : []}
          fields={[
            ...employee,
            {
              name: "day",
              label: "Work day",
              type: "date",
              required: true,
              defaultValue: new Date().toLocaleDateString("en-CA"),
            },
            {
              name: "hours",
              label: "Hours",
              type: "number",
              step: ".0001",
              min: ".0001",
              max: "24",
              required: true,
            },
            {
              name: "category",
              label: "Category",
              required: true,
              defaultValue: "calling",
              options: options([
                "calling",
                "event",
                "training",
                "admin",
                "other",
              ]),
            },
            {
              name: "description",
              label: "What did you work on?",
              type: "textarea",
              required: true,
              wide: true,
            },
          ]}
          onClose={() => setDialog("")}
          submitLabel="Submit for review"
          onSubmit={(v) =>
            action(() => send("/time-entries", { ...v, hours: v.hours }))
          }
        />
      )}
      {dialog === "leave" && (
        <FormDialog
          title="Plan some time away"
          dependencies={isAdmin ? [dir] : []}
          fields={[
            ...employee,
            {
              name: "starts_on",
              label: "First day",
              type: "date",
              required: true,
            },
            {
              name: "ends_on",
              label: "Last day (inclusive)",
              type: "date",
              required: true,
            },
            {
              name: "kind",
              label: "Leave type",
              required: true,
              defaultValue: "planned",
              options: options([
                "casual",
                "sick",
                "planned",
                "personal",
                "other",
              ]),
            },
            {
              name: "reason",
              label: "Reason",
              type: "textarea",
              required: true,
              wide: true,
            },
          ]}
          onClose={() => setDialog("")}
          submitLabel="Submit leave request"
          onSubmit={(v) => action(() => send("/leave", v))}
        />
      )}
      {review && (
        <FormDialog
          title="Review the submission"
          description="Your decision and note will be recorded in the audit trail."
          fields={[
            {
              name: "state",
              label: "Decision",
              options: options(["approved", "rejected"]),
              required: true,
            },
            {
              name: "note",
              label: "Review note",
              type: "textarea",
              wide: true,
            },
          ]}
          onClose={() => setReview(null)}
          submitLabel="Record decision"
          onSubmit={(v) => action(() => send(`/${tab}/${review.id}/review`, v))}
        />
      )}
    </>
  );
}

export { PayrollPage } from "./payroll";

export function TeamPage() {
  const { session } = useAuth();
  const nav = useNavigate();
  const isAdmin = session?.role === "admin";
  const q = useData<User[]>("/team");
  const [edit, setEdit] = useState<User | true | null>(null);
  const [remove, setRemove] = useState<User | null>(null);
  const [reset, setReset] = useState<User | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [entering, setEntering] = useState<string | null>(null);
  const action = useAction();
  const dir = useDirectory();
  const canLoginAs = (user: User) =>
    isAdmin &&
    !session?.acting_as &&
    user.active &&
    user.id !== session?.user.id &&
    ["telecaller", "manager", "field_executive"].includes(user.role);
  async function loginAs(user: User) {
    if (entering) return;
    setEntering(user.id);
    setError(null);
    try {
      const member = await api<Session>(`/team/${user.id}/login-as`, {
        method: "POST",
      });
      setSession(member);
      nav(
        member.role === "field_executive" ? "/app/field-work" : "/app/overview",
      );
    } catch (e) {
      setError(e);
    } finally {
      setEntering(null);
    }
  }
  return (
    <>
      <QueryNotice query={dir} />
      <PageHeading
        eyebrow="GOOD WORK STARTS WITH PEOPLE"
        title="Your team"
        description="The right people, with the right access to do their work."
        actions={
          isAdmin && (
            <Button onClick={() => setEdit(true)}>
              <UserPlus size={17} />
              Add team member
            </Button>
          )
        }
      />
      {error !== null && <ErrorBox error={error} />}
      {isAdmin && (
        <p className="help-text">
          Select an active telecaller, field executive or manager's name to log
          in to their workspace. You can return to your account from the banner.
          Access and changes are recorded in the audit history.
        </p>
      )}
      <Load query={q}>
        {(users) => (
          <>
            <div className="stats-grid three">
              <Stat
                label="Team members"
                value={users.length}
                detail="Within your organization"
                accent
              />
              <Stat
                label="Active telecallers"
                value={
                  users.filter((u) => u.active && u.role === "telecaller")
                    .length
                }
                detail="Eligible for lead distribution"
              />
              <Stat
                label="Managers"
                value={
                  users.filter((u) => u.role === "manager" && u.active).length
                }
                detail="Available for lead handoffs"
              />
            </div>
            <Panel>
              <Table
                headers={[
                  "Team member",
                  "Phone",
                  "Role",
                  "Access",
                  "Joined",
                  "Actions",
                ]}
              >
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>
                      <span className="name-cell">
                        <span className="avatar">
                          {u.name.slice(0, 2).toUpperCase()}
                        </span>
                        {canLoginAs(u) ? (
                          <button
                            className="text-button member-login-name"
                            title={`Log in as ${u.name}`}
                            disabled={!!entering}
                            onClick={() => void loginAs(u)}
                          >
                            {u.name}
                          </button>
                        ) : (
                          <strong>
                            {u.name}
                            {u.id === session?.user.id ? " (you)" : ""}
                          </strong>
                        )}
                      </span>
                    </td>
                    <td>{u.phone}</td>
                    <td>
                      <Badge value={u.role} />
                    </td>
                    <td>
                      <Badge value={u.active ? "active" : "inactive"} />
                    </td>
                    <td>{dateTime(u.created_at)}</td>
                    <td>
                      <div className="inline-actions">
                        {canLoginAs(u) && (
                          <button
                            disabled={!!entering}
                            onClick={() => void loginAs(u)}
                          >
                            {entering === u.id
                              ? "Logging in…"
                              : "Log in as member"}
                          </button>
                        )}
                        {isAdmin && (
                          <button onClick={() => setEdit(u)}>Edit</button>
                        )}
                        {(isAdmin ||
                          ["telecaller", "field_executive"].includes(
                            u.role,
                          )) && (
                          <button
                            onClick={() =>
                              void action(() =>
                                send(
                                  `/team/${u.id}`,
                                  { active: !u.active },
                                  "PATCH",
                                ),
                              ).catch(setError)
                            }
                          >
                            {u.active ? "Deactivate" : "Activate"}
                          </button>
                        )}
                        {isAdmin && (
                          <>
                            <button onClick={() => setReset(u)}>
                              Reset password
                            </button>
                            <button onClick={() => setRemove(u)}>Remove</button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </Table>
            </Panel>
          </>
        )}
      </Load>
      {edit && (
        <FormDialog
          title={
            edit === true ? "Welcome someone to the team" : "Edit team member"
          }
          fields={[
            { name: "name", label: "Full name", required: true },
            ...(edit === true
              ? [
                  {
                    name: "phone",
                    label: "Login phone",
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
            {
              name: "role",
              label: "Workspace role",
              required: true,
              defaultValue: "telecaller",
              options: options([
                "admin",
                "manager",
                "telecaller",
                "field_executive",
              ]),
            },
          ]}
          initial={edit === true ? {} : { name: edit.name, role: edit.role }}
          onClose={() => setEdit(null)}
          onSubmit={(v) =>
            action(() =>
              send(
                edit === true ? "/team" : `/team/${edit.id}`,
                v,
                edit === true ? "POST" : "PATCH",
              ),
            )
          }
        />
      )}
      {reset && (
        <FormDialog
          title={`Reset ${reset.name}’s password`}
          description="Existing sessions will be revoked immediately."
          fields={[
            {
              name: "password",
              label: "New password",
              type: "password",
              required: true,
              hint: "At least 12 characters.",
            },
          ]}
          onClose={() => setReset(null)}
          onSubmit={(v) => action(() => send(`/team/${reset.id}`, v, "PATCH"))}
        />
      )}
      {remove && (
        <FormDialog
          title={`Remove ${remove.name}?`}
          dependencies={[dir]}
          description="Assigned leads must move to another active manager. Last-administrator protection is enforced."
          fields={[
            {
              name: "confirmation",
              label: `Type “${remove.name}”`,
              required: true,
            },
            {
              name: "manager_id",
              label: "Lead handoff manager",
              options: (dir.data || [])
                .filter((u) => u.role === "manager" && u.id !== remove.id)
                .map((u) => ({ value: u.id, label: u.name })),
            },
          ]}
          onClose={() => setRemove(null)}
          submitLabel="Remove member"
          onSubmit={(v) =>
            action(() =>
              api(
                `/team/${remove.id}?` +
                  params({
                    confirmation: String(v.confirmation),
                    manager_id: String(v.manager_id),
                  }),
                { method: "DELETE" },
              ),
            )
          }
        />
      )}
    </>
  );
}

export function CallsPage() {
  const { session } = useAuth();
  const [f, setF] = useState<Record<string, string>>({});
  const [page, setPage] = useState(1);
  const [error, setError] = useState<unknown>(null);
  const dir = useDirectory();
  const action = useAction();
  const q = useData<{ items: PhoneCall[]; total: number }>(
    "/phone-calls?" + params({ ...f, page }),
  );
  function filter(k: string, v: string) {
    setF((s) => ({ ...s, [k]: v }));
    setPage(1);
  }
  return (
    <>
      <PageHeading
        eyebrow="EVERY CALL, IN CONTEXT"
        title="Phone calls"
        description="Device-observed call history, separate from manual business outcomes."
      />
      <div className="filter-row">
        <div className="search-field">
          <Search size={16} />
          <input
            aria-label="Search phone calls"
            placeholder="Search number or lead"
            value={f.q || ""}
            onChange={(e) => filter("q", e.target.value)}
          />
        </div>
        {!["telecaller", "field_executive"].includes(session?.role || "") && (
          <select
            aria-label="Call employee"
            value={f.user_id || ""}
            onChange={(e) => filter("user_id", e.target.value)}
          >
            <option value="">Entire team</option>
            {dir.data?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </select>
        )}
        {[
          ["direction", ["incoming", "outgoing"]],
          ["result", ["answered", "missed", "rejected", "unknown"]],
          [
            "recording_state",
            ["attached", "unavailable", "pending", "ambiguous"],
          ],
        ].map(([key, values]) => (
          <select
            key={String(key)}
            aria-label={`Call ${key}`}
            value={f[String(key)] || ""}
            onChange={(e) => filter(String(key), e.target.value)}
          >
            <option value="">All {String(key).replace("_", " ")}s</option>
            {(values as string[]).map((v) => (
              <option key={v} value={v}>
                {key === "recording_state" ? recordingLabel(v) : v}
              </option>
            ))}
          </select>
        ))}
        <label>
          From{" "}
          <input
            aria-label="Calls from"
            type="date"
            onChange={(e) =>
              filter(
                "from_date",
                e.target.value
                  ? new Date(e.target.value + "T00:00:00").toISOString()
                  : "",
              )
            }
          />
        </label>
        <label>
          Until{" "}
          <input
            aria-label="Calls until"
            type="date"
            onChange={(e) =>
              filter(
                "to_date",
                e.target.value
                  ? new Date(e.target.value + "T00:00:00").toISOString()
                  : "",
              )
            }
          />
        </label>
      </div>
      {error !== null && <ErrorBox error={error} />}
      <QueryNotice query={dir} />
      <Panel>
        <Load query={q}>
          {(data) =>
            data.items.length ? (
              <>
                <Table
                  headers={[
                    "Lead / number",
                    "Employee",
                    "When",
                    "Direction / result",
                    "Duration",
                    "Recording",
                  ]}
                >
                  {data.items.map((c) => (
                    <tr key={c.id}>
                      <td>
                        <Link className="strong" to={"/app/leads/" + c.lead_id}>
                          {c.lead_name}
                        </Link>
                        <small className="block muted">{c.phone}</small>
                      </td>
                      <td>{c.user_name}</td>
                      <td>{dateTime(c.started_at)}</td>
                      <td>
                        <span className="call-direction">
                          {c.direction === "incoming" ? (
                            <ArrowDownLeft size={15} />
                          ) : (
                            <ArrowUpRight size={15} />
                          )}
                          {c.direction}
                        </span>
                        <Badge value={c.result} />
                      </td>
                      <td>{duration(c.duration)}</td>
                      <td>
                        <RecordingBadge value={c.recording_state} />
                        {c.recordings.map((file) => (
                          <div key={file.id}>
                            <AudioFile file={file} />
                            <button
                              className="text-button"
                              onClick={() =>
                                void download(
                                  `/files/${file.id}`,
                                  file.name,
                                ).catch(setError)
                              }
                            >
                              Download <Download size={13} />
                            </button>
                          </div>
                        ))}
                        <label className="text-button upload-recording">
                          <Upload size={13} />
                          Attach audio
                          <input
                            className="visually-hidden"
                            type="file"
                            accept="audio/*"
                            aria-label={`Attach recording to ${c.lead_name} call`}
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              if (file) {
                                const form = new FormData();
                                form.set("file", file);
                                form.set("phone_call_id", c.id);
                                void action(() =>
                                  api(`/leads/${c.lead_id}/files`, {
                                    method: "POST",
                                    body: form,
                                  }),
                                ).catch(setError);
                              }
                            }}
                          />
                        </label>
                      </td>
                    </tr>
                  ))}
                </Table>
                <div className="pagination">
                  <span>{data.total} phone calls</span>
                  <div>
                    <Button
                      variant="secondary"
                      disabled={page <= 1}
                      onClick={() => setPage(page - 1)}
                    >
                      <ChevronLeft size={16} />
                      Previous
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={page * 50 >= data.total}
                      onClick={() => setPage(page + 1)}
                    >
                      Next
                      <ChevronRight size={16} />
                    </Button>
                  </div>
                </div>
              </>
            ) : (
              <Empty
                title="No synchronized calls yet"
                description="Connect the Android companion app on your phone to sync assigned-customer calls and available built-in recordings."
              />
            )
          }
        </Load>
      </Panel>
      <p className="help-text">
        Recordings are files created by a separate dialer or authorized
        recorder. Missing recordings never hide call metadata. Private downloads
        are checked against current assignment and role.
      </p>
    </>
  );
}

function RecordsPager({
  page,
  count,
  setPage,
}: {
  page: number;
  count: number;
  setPage: (page: number) => void;
}) {
  return (
    <div className="pagination">
      <Button
        variant="secondary"
        disabled={page === 1}
        onClick={() => setPage(page - 1)}
      >
        Previous
      </Button>
      <span>Page {page}</span>
      <Button
        variant="secondary"
        disabled={count < 100}
        onClick={() => setPage(page + 1)}
      >
        Next
      </Button>
    </div>
  );
}
