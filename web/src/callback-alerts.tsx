import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Bell,
  CalendarClock,
  PhoneCall,
  RefreshCw,
  UserRound,
  X,
} from "lucide-react";
import { useData } from "./main";
import { ErrorBox, Load } from "./ui";
import "./callback-alerts.css";

interface AlertItem {
  id: string;
  kind: "callback" | "task" | "handoff" | "first_contact";
  title: string;
  description: string;
  owner_name: string;
  url: string;
  due_at: string;
}
export interface AlertInbox {
  items: AlertItem[];
  counts: { callbacks: number; other: number; all: number };
  total: number;
  page: number;
  pages: number;
  page_size: number;
  timezone: string;
  as_of: string;
}

export function CallbackAlerts() {
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState<"all" | "callbacks">("all");
  const [page, setPage] = useState(1);
  const [position, setPosition] = useState({ top: 68, left: 12 });
  const button = useRef<HTMLButtonElement>(null);
  const anchor = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const id = useId();
  const location = useLocation();
  const query = useData<AlertInbox>(
    `/notifications/inbox?category=${category}&page=${page}`,
  );
  const refetch = query.refetch;
  const callbackCount = query.data?.counts.callbacks || 0;
  useEffect(() => setOpen(false), [location.pathname]);
  useEffect(() => {
    if (open) void refetch();
  }, [open, refetch]);
  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const bounds = button.current?.getBoundingClientRect();
      if (!bounds) return;
      const width = Math.min(420, window.innerWidth - 24);
      setPosition({
        top: bounds.bottom + 8,
        left: Math.max(
          12,
          Math.min(bounds.right - width, window.innerWidth - width - 12),
        ),
      });
    };
    place();
    heading.current?.focus();
    const outside = (event: PointerEvent) => {
      if (!anchor.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        button.current?.focus();
      }
    };
    const scroll = (event: Event) => {
      if (event.target === document || event.target === window) setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    window.addEventListener("keydown", escape);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", scroll, true);
    return () => {
      document.removeEventListener("pointerdown", outside);
      window.removeEventListener("keydown", escape);
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", scroll, true);
    };
  }, [open]);
  return (
    <div className="callback-alert-anchor" ref={anchor}>
      <button
        ref={button}
        className={`icon-button callback-alert-bell ${callbackCount ? "has-overdue" : ""}`}
        aria-label={
          query.isError
            ? "Notifications ! Alerts unavailable"
            : callbackCount
              ? `Notifications ${callbackCount > 99 ? "99+" : callbackCount} overdue callbacks${callbackCount > 99 ? ` (${callbackCount} total)` : ""}`
              : "Notifications"
        }
        aria-describedby={`${id}-status`}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? `${id}-panel` : undefined}
        onClick={() => {
          if (!open) {
            setCategory("all");
            setPage(1);
          }
          setOpen(!open);
        }}
      >
        <Bell size={21} />
        {query.isError ? (
          <span className="callback-alert-count unavailable" aria-hidden="true">
            !
          </span>
        ) : callbackCount ? (
          <span className="callback-alert-count" aria-hidden="true">
            {callbackCount > 99 ? "99+" : callbackCount}
          </span>
        ) : (
          !!query.data?.counts.other && (
            <i className="callback-alert-other-dot" aria-hidden="true" />
          )
        )}
      </button>
      <span id={`${id}-status`} className="visually-hidden" aria-live="polite">
        {query.isError
          ? "Alerts could not be refreshed"
          : query.isPending
            ? "Checking callback alerts"
            : `${callbackCount} overdue callbacks; ${query.data?.counts.other || 0} other alerts`}
      </span>
      {open && (
        <div
          ref={panel}
          id={`${id}-panel`}
          role="dialog"
          aria-labelledby={`${id}-title`}
          className="callback-alert-panel"
          style={{
            top: position.top,
            left: position.left,
            maxHeight: `calc(100dvh - ${position.top + 12}px)`,
          }}
        >
          <header>
            <div>
              <h2 ref={heading} tabIndex={-1} id={`${id}-title`}>
                Alerts & reminders
              </h2>
              <p>
                {query.isError
                  ? "Please refresh to check your alerts."
                  : query.isPending
                    ? "Checking your next steps…"
                    : callbackCount
                      ? `${callbackCount} ${callbackCount === 1 ? "callback needs" : "callbacks need"} attention`
                      : "No callbacks overdue"}
              </p>
            </div>
            <button
              className="icon-button"
              aria-label="Refresh alerts"
              disabled={query.isFetching}
              onClick={() => void refetch()}
            >
              <RefreshCw size={17} />
            </button>
            <button
              className="icon-button"
              aria-label="Close alerts"
              onClick={() => {
                setOpen(false);
                button.current?.focus();
              }}
            >
              <X size={20} />
            </button>
          </header>
          <div className="callback-alert-filters" aria-label="Alert type">
            {(["all", "callbacks"] as const).map((value) => (
              <button
                key={value}
                aria-pressed={category === value}
                onClick={() => {
                  setCategory(value);
                  setPage(1);
                }}
              >
                {value === "all" ? "All alerts" : "Overdue callbacks"}
                {query.data && (
                  <span>
                    {value === "all"
                      ? query.data.counts.all
                      : query.data.counts.callbacks}
                  </span>
                )}
              </button>
            ))}
          </div>
          {query.isError ? (
            <ErrorBox error={query.error} retry={() => void refetch()} />
          ) : (
            <Load query={query}>
              {(data) => (
                <>
                  {data.items.length ? (
                    <div className="callback-alert-list">
                      {data.items.map((item) => {
                        const Icon =
                          item.kind === "callback"
                            ? PhoneCall
                            : item.kind === "first_contact"
                              ? UserRound
                              : CalendarClock;
                        return (
                          <Link
                            key={item.id}
                            to={item.url}
                            className={
                              item.kind === "callback" ? "overdue" : ""
                            }
                            onClick={() => setOpen(false)}
                          >
                            <span
                              className="callback-alert-icon"
                              aria-hidden="true"
                            >
                              <Icon size={19} />
                            </span>
                            <span className="callback-alert-content">
                              <strong>{item.title}</strong>
                              <span>{item.description}</span>
                              <small>
                                {item.owner_name === "Unassigned"
                                  ? "Unassigned"
                                  : `Assigned to ${item.owner_name}`}
                              </small>
                              <small>
                                {item.kind === "handoff"
                                  ? "Added "
                                  : item.kind === "first_contact"
                                    ? "Awaiting contact since "
                                    : "Due "}
                                {new Intl.DateTimeFormat("en-IN", {
                                  dateStyle: "medium",
                                  timeStyle: "short",
                                  timeZone: data.timezone,
                                }).format(new Date(item.due_at))}
                              </small>
                              {item.kind === "callback" && (
                                <b>{overdueText(item.due_at, data.as_of)}</b>
                              )}
                            </span>
                          </Link>
                        );
                      })}
                    </div>
                  ) : query.isFetching ? (
                    <p role="status" className="callback-alert-help">
                      Checking for new reminders…
                    </p>
                  ) : (
                    <div className="callback-alert-empty">
                      <Bell size={27} aria-hidden="true" />
                      <strong>
                        {category === "callbacks"
                          ? "No overdue callbacks"
                          : "You're all caught up"}
                      </strong>
                      <p>
                        {category === "callbacks"
                          ? "Callbacks appear here when their scheduled time passes."
                          : "New reminders will appear here when something needs attention."}
                      </p>
                    </div>
                  )}
                  {data.total > 0 && (
                    <div className="callback-alert-pagination">
                      <span>
                        {(data.page - 1) * data.page_size + 1}–
                        {Math.min(data.page * data.page_size, data.total)} of{" "}
                        {data.total}
                      </span>
                      <button
                        disabled={data.page <= 1 || query.isFetching}
                        onClick={() => setPage(data.page - 1)}
                      >
                        Previous
                      </button>
                      <button
                        disabled={data.page >= data.pages || query.isFetching}
                        onClick={() => setPage(data.page + 1)}
                      >
                        Next
                      </button>
                    </div>
                  )}
                  <p className="callback-alert-help">
                    Callback alerts clear after you save a call result or move
                    the callback to a future time. Complete callback tasks in
                    Planner, or update field follow-ups in Field work.
                  </p>
                  <small className="callback-alert-zone">
                    Times shown in {data.timezone} · Updates every 30 seconds
                    while this CRM tab is active
                  </small>
                </>
              )}
            </Load>
          )}
        </div>
      )}
    </div>
  );
}

function overdueText(due: string, asOf: string) {
  const minutes = Math.max(
    0,
    Math.floor((Date.parse(asOf) - Date.parse(due)) / 60000),
  );
  if (minutes < 1) return "Due now";
  const count =
    minutes >= 1440
      ? Math.floor(minutes / 1440)
      : minutes >= 60
        ? Math.floor(minutes / 60)
        : minutes;
  const unit = minutes >= 1440 ? "day" : minutes >= 60 ? "hour" : "minute";
  return `${count} ${unit}${count === 1 ? "" : "s"} overdue`;
}
