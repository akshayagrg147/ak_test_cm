import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  Building2,
  CalendarDays,
  CheckCheck,
  Clock3,
  Headset,
  Phone,
  Plus,
  RefreshCw,
  Target,
  Users,
} from "lucide-react";
import { params } from "./api";
import { useAuth, useData } from "./main";
import { DistributionChart, TrendChart, chartColors } from "./charts";
import { leadSourceChoices, leadStatusChoices } from "./lead-filters";
import type { DashboardData, Directory, Task } from "./types";
import type { Visit } from "./estate-types";
import {
  Badge,
  Button,
  Empty,
  Load,
  PageHeading,
  Panel,
  QueryNotice,
  Stat,
  money,
} from "./ui";
import "./dashboard.css";

interface EstateSummary {
  available: number;
  inventory: number;
  reserved: number;
  booked_value: string;
  commission: string;
  booking_count: number;
  visits: Visit[];
}
const periodLabels: Record<number, string> = {
  1: "Today",
  7: "Last 7 days",
  30: "Last 30 days",
};

export function DashboardPage() {
  const { session } = useAuth();
  const [days, setDays] = useState(7);
  const [owner, setOwner] = useState("");
  const personal = ["telecaller", "field_executive"].includes(
    session?.role || "",
  );
  const field = session?.role === "field_executive";
  const realEstate = session?.organization?.settings.industry === "real_estate";
  const directory = useData<Directory[]>("/directory", !personal);
  const q = useData<DashboardData>(
    "/dashboard?" + params({ days, owner_id: personal ? "" : owner }),
  );
  const tasks = useData<Task[]>(
    "/tasks?" +
      params({
        state: "open",
        owner_id: personal || !owner ? session?.user.id : owner,
      }),
  );
  const estate = useData<EstateSummary>("/real-estate/overview", realEstate);
  const selectedName = directory.data?.find((item) => item.id === owner)?.name;
  const name = session?.user.name.split(" ")[0] || "there";
  const refreshing =
    q.isFetching || tasks.isFetching || (realEstate && estate.isFetching);
  return (
    <div className={`crm-dashboard ${personal ? "personal" : "management"}`}>
      <PageHeading
        eyebrow={`${field ? "FIELD WORKSPACE" : personal ? "YOUR CALLING WORKSPACE" : "BUSINESS OVERVIEW"} · WELCOME, ${name.toUpperCase()}`}
        title={
          field
            ? "Your field work, in focus."
            : personal
              ? "Your calling day, made simple."
              : "Your real estate business, in focus."
        }
        description={
          personal
            ? "Your clients, conversations and next steps. All in one clear view."
            : "Know where your team stands and what needs your attention next."
        }
        actions={
          <>
            <Button
              variant="secondary"
              disabled={refreshing}
              onClick={() =>
                void Promise.all([
                  q.refetch(),
                  tasks.refetch(),
                  ...(realEstate ? [estate.refetch()] : []),
                ])
              }
            >
              <RefreshCw size={16} className={refreshing ? "spin" : ""} />
              Refresh
            </Button>
            <Link className="button" to="/app/leads?create=1">
              <Plus size={17} />
              Add a lead
            </Link>
          </>
        }
      />
      <div className="crm-dashboard-filters">
        <div className="crm-period" aria-label="Dashboard period">
          {[1, 7, 30].map((value) => (
            <button
              key={value}
              aria-pressed={days === value}
              onClick={() => setDays(value)}
            >
              {periodLabels[value]}
            </button>
          ))}
        </div>
        {!personal && (
          <label className="crm-team-filter">
            <Users size={17} aria-hidden="true" />
            <span className="visually-hidden">Dashboard team member</span>
            <select
              aria-label="Dashboard team member"
              value={owner}
              onChange={(event) => setOwner(event.target.value)}
            >
              <option value="">Entire team</option>
              {directory.data?.map((member) => (
                <option key={member.id} value={member.id}>
                  {member.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <span className="crm-range-note">
          {q.data?.timezone ||
            session?.organization?.settings.workplace?.timezone ||
            "Asia/Kolkata"}{" "}
          · Today is in progress
        </span>
      </div>
      {!personal && <QueryNotice query={directory} />}
      <Load query={q}>
        {(data) => (
          <>
            <div className="crm-dashboard-stats stats-grid">
              <Stat
                label={personal ? "My assigned clients" : "New enquiries"}
                value={
                  personal
                    ? data.metrics.visible_leads.toLocaleString()
                    : data.metrics.leads.toLocaleString()
                }
                icon={<Users size={20} />}
                detail={
                  personal
                    ? `${data.metrics.leads} added in this period`
                    : `${data.metrics.prior_leads} in the previous equal period`
                }
                accent
              />
              <Stat
                label={personal ? "My calls logged" : "Team calls logged"}
                value={data.metrics.calls.toLocaleString()}
                icon={<Phone size={20} />}
                detail={`${periodLabels[days]} · synced and manual calls`}
              />
              <Stat
                label={personal ? "My talk time" : "Converted leads"}
                value={
                  personal
                    ? talkTime(data.metrics.talk_seconds)
                    : data.metrics.converted.toLocaleString()
                }
                icon={personal ? <Headset size={20} /> : <Target size={20} />}
                detail={
                  personal
                    ? `${talkTime(data.metrics.observed_seconds)} synced · ${talkTime(data.metrics.declared_seconds)} manual`
                    : `${data.metrics.conversion_rate}% of enquiries added in this period`
                }
              />
              <Stat
                label="Follow-ups overdue"
                value={data.metrics.actionable_overdue.toLocaleString()}
                icon={<Clock3 size={20} />}
                detail="Current open clients awaiting a callback"
              />
            </div>
            <section className="crm-priority-banner" aria-label="Next priority">
              <span className="crm-priority-symbol">
                <CheckCheck size={24} />
              </span>
              <div>
                <h2>
                  {data.metrics.actionable_overdue
                    ? `${data.metrics.actionable_overdue} follow-up${data.metrics.actionable_overdue === 1 ? " needs" : "s need"} a next step`
                    : "Make your next conversation count"}
                </h2>
                <p>
                  {personal
                    ? `${data.metrics.needs_first_contact} open client${data.metrics.needs_first_contact === 1 ? " is" : "s are"} waiting for a first conversation.`
                    : `${data.metrics.needs_first_contact} open clients need first contact. ${data.metrics.unassigned} of this period's enquiries are unassigned.`}
                </p>
              </div>
              <a href="#priority-clients">
                Review priority clients <ArrowRight size={17} />
              </a>
            </section>
            <div className="crm-insight-grid">
              <Panel
                className="crm-trend-panel"
                title={
                  personal ? "Your activity" : "Enquiry & calling activity"
                }
                description={`${periodLabels[days]}${selectedName ? " · " + selectedName : ""}. New enquiries and calls recorded over time.`}
                action={
                  <span className="crm-live-label">
                    <i />
                    Actual CRM activity
                  </span>
                }
              >
                <TrendChart key={`${days}-${owner}`} items={data.trend} />
              </Panel>
              <Panel
                title={personal ? "Your call outcomes" : "Enquiry sources"}
                description={
                  personal
                    ? "Device results and standalone manual calls in this period."
                    : "Where this period's new clients came from."
                }
              >
                <DistributionChart
                  label={
                    personal
                      ? "Call outcome distribution"
                      : "Enquiry source distribution"
                  }
                  unit={personal ? "calls" : "enquiries"}
                  items={
                    personal
                      ? Object.entries(data.call_results).map(
                          ([key, value]) => ({
                            label:
                              (
                                {
                                  answered: "Answered",
                                  missed: "Missed",
                                  rejected: "Rejected",
                                  unknown: "Unknown result",
                                  manual: "Manual calls",
                                } as Record<string, string>
                              )[key] || key,
                            value,
                          }),
                        )
                      : sourceItems(data.sources)
                  }
                />
                <Link
                  className="crm-panel-link"
                  to={personal ? "/app/phone-calls" : "/app/leads"}
                >
                  {personal ? "View call history" : "Explore enquiries"}
                  <ArrowUpRight size={16} />
                </Link>
              </Panel>
            </div>
            <div className="crm-work-grid">
              <Panel
                className="crm-priority-panel"
                title="Priority clients"
                description="Current open clients needing follow-up or first contact. Closed and do-not-contact clients are excluded."
                action={
                  <Link className="text-button" to="/app/leads">
                    All clients <ArrowUpRight size={16} />
                  </Link>
                }
              >
                <div id="priority-clients" className="crm-priority-list">
                  {data.priority.length ? (
                    data.priority.map(({ lead, reason }) => (
                      <Link
                        className="crm-client-row"
                        key={lead.id}
                        to={`/app/leads/${lead.id}`}
                      >
                        <span className="crm-client-avatar" aria-hidden="true">
                          {lead.name.slice(0, 2).toUpperCase()}
                        </span>
                        <span className="crm-client-name">
                          <strong>{lead.name}</strong>
                          <small>
                            {lead.phone}
                            {lead.city ? ` · ${lead.city}` : ""}
                          </small>
                        </span>
                        <span className={`crm-client-reason ${reason}`}>
                          <strong>
                            {reason === "overdue"
                              ? "Overdue follow-up"
                              : reason === "due_today"
                                ? "Follow up today"
                                : "First conversation"}
                          </strong>
                          <small>
                            {lead.follow_up && reason !== "first_contact"
                              ? workTime(lead.follow_up, data.timezone)
                              : "Review requirements"}
                          </small>
                        </span>
                        <ArrowRight size={17} aria-hidden="true" />
                      </Link>
                    ))
                  ) : (
                    <Empty
                      title="No priority clients right now"
                      description="New open enquiries and due follow-ups will appear here."
                    />
                  )}
                </div>
                {data.priority_total > data.priority.length && (
                  <p className="crm-list-footnote">
                    Showing {data.priority.length} of {data.priority_total}{" "}
                    clients needing attention. Open All clients to review more.
                  </p>
                )}
              </Panel>
              <Panel
                title={
                  owner && !personal
                    ? `${selectedName || "Team member"}'s next tasks`
                    : "Your next tasks"
                }
                description="Open tasks, ordered by due time. The Planner shows the full list."
                action={
                  <Link className="text-button" to="/app/tasks">
                    Planner <ArrowUpRight size={16} />
                  </Link>
                }
              >
                <Load query={tasks}>
                  {(items) =>
                    items.length ? (
                      <div className="crm-task-list">
                        {items.slice(0, 4).map((item) => (
                          <Link
                            key={item.id}
                            to={
                              item.field_handoff_id && item.lead_id
                                ? `/app/leads/${item.lead_id}`
                                : "/app/tasks"
                            }
                          >
                            <span className="crm-task-icon">
                              <CalendarDays size={18} />
                            </span>
                            <span>
                              <strong>{item.title}</strong>
                              <small>
                                {workTime(item.due_at, data.timezone)}
                              </small>
                              {item.field_handoff_id && (
                                <small>Field follow-up</small>
                              )}
                            </span>
                            <ArrowUpRight size={15} />
                          </Link>
                        ))}
                      </div>
                    ) : (
                      <Empty
                        title="No open tasks"
                        description="Create a task in the Planner to keep the next step in view."
                      />
                    )
                  }
                </Load>
              </Panel>
            </div>
            <div className="crm-insight-grid crm-secondary-insights">
              <Panel
                title={
                  personal ? "Your client pipeline" : "Pipeline at a glance"
                }
                description="Current stages of enquiries added in the selected period. Each client appears in one stage."
              >
                {data.metrics.leads ? (
                  <div className="crm-stage-list">
                    {data.pipeline.map((stage, index) => (
                      <Link
                        key={stage.key}
                        to={
                          "/app/leads?" +
                          params({
                            stage: stage.key,
                            owner_id: owner,
                            from_date: data.from_date,
                            to_date: data.to_date,
                          })
                        }
                      >
                        <span>
                          <strong>{stage.label}</strong>
                          <b>{stage.count}</b>
                        </span>
                        <span className="crm-bar-track" aria-hidden="true">
                          <i
                            style={{
                              width: `${(stage.count / data.metrics.leads) * 100}%`,
                              background:
                                chartColors[index % chartColors.length],
                            }}
                          />
                        </span>
                      </Link>
                    ))}
                  </div>
                ) : (
                  <Empty
                    title="No new enquiries in this period"
                    description="Choose a wider period or add a client to see the pipeline."
                  />
                )}
                <p className="crm-list-footnote">
                  Lead status:{" "}
                  {Object.entries(data.statuses)
                    .map(
                      ([key, count]) =>
                        `${leadStatusChoices.find((item) => item.value === key)?.label || key} ${count}`,
                    )
                    .join(" · ") || "No enquiries"}
                </p>
              </Panel>
              {personal ? (
                <Panel
                  title="Your daily shortcuts"
                  description="A direct route to the work you use most."
                >
                  <QuickLinks field={field} />
                </Panel>
              ) : (
                <Panel
                  title="Team calling activity"
                  description="Top five team members by logged calls in this period."
                  action={
                    <Link className="text-button" to="/app/reports">
                      Full report <ArrowUpRight size={16} />
                    </Link>
                  }
                >
                  {data.leaderboard.length ? (
                    <div className="crm-team-list">
                      {data.leaderboard.slice(0, 5).map((member, index) => (
                        <div key={member.user_id}>
                          <span className="crm-team-rank">{index + 1}</span>
                          <span className="crm-team-name">
                            <strong>{member.name}</strong>
                            <small>{member.minutes} talk minutes</small>
                            <span className="crm-bar-track" aria-hidden="true">
                              <i
                                style={{
                                  width: `${(member.calls / Math.max(...data.leaderboard.map((m) => m.calls), 1)) * 100}%`,
                                }}
                              />
                            </span>
                          </span>
                          <strong>
                            {member.calls}
                            <small>calls</small>
                          </strong>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <Empty
                      title="No calls logged in this period"
                      description="Synced and standalone manual calls appear here after they are recorded."
                    />
                  )}
                </Panel>
              )}
            </div>
            {realEstate && (
              <div className="crm-estate-grid">
                <Panel
                  title={
                    personal
                      ? "Your upcoming site visits"
                      : "Upcoming site visits"
                  }
                  description="Current schedule, independent of the chart period."
                  action={
                    <Link className="text-button" to="/app/site-visits">
                      View visits <ArrowUpRight size={16} />
                    </Link>
                  }
                >
                  <Load query={estate}>
                    {(d) =>
                      d.visits.length ? (
                        <div className="crm-task-list">
                          {d.visits.slice(0, 4).map((visit) => (
                            <Link
                              key={visit.id}
                              to={`/app/leads/${visit.lead_id}`}
                            >
                              <span className="crm-task-icon">
                                <Building2 size={18} />
                              </span>
                              <span>
                                <strong>{visit.lead_name}</strong>
                                <small>{visit.property_title}</small>
                                <small>
                                  {workTime(visit.starts_at, data.timezone)} ·{" "}
                                  {visit.assignee_name}
                                </small>
                              </span>
                              <Badge value={visit.status} />
                            </Link>
                          ))}
                        </div>
                      ) : (
                        <Empty
                          title="No upcoming visits"
                          description="When a client agrees to a visit, arrange it from their profile."
                        />
                      )
                    }
                  </Load>
                </Panel>
                <Panel
                  title="Property workspace"
                  description={
                    personal
                      ? "Find an available property and prepare for the client conversation."
                      : "Live company portfolio. Booking figures below include all non-cancelled bookings."
                  }
                >
                  <Load query={estate}>
                    {(d) => (
                      <>
                        <div className="crm-property-summary">
                          <span className="crm-property-icon">
                            <Building2 size={28} />
                          </span>
                          <div>
                            <strong>
                              {d.available}
                              <span> / {d.inventory}</span>
                            </strong>
                            <p>properties available</p>
                          </div>
                        </div>
                        {!personal && (
                          <dl className="crm-property-values">
                            <div>
                              <dt>Booking value</dt>
                              <dd>{money(d.booked_value)}</dd>
                            </div>
                            <div>
                              <dt>Reserved properties</dt>
                              <dd>{d.reserved}</dd>
                            </div>
                          </dl>
                        )}
                        <Link className="crm-panel-link" to="/app/properties">
                          Browse properties <ArrowRight size={16} />
                        </Link>
                      </>
                    )}
                  </Load>
                </Panel>
              </div>
            )}
          </>
        )}
      </Load>
      <p className="crm-dashboard-note">
        Charts use the selected period. Priority clients, tasks and visits show
        current work.{" "}
        {personal
          ? "You see only clients and activity available to your account."
          : "Choose a team member to filter enquiry and call charts; property figures remain company-wide."}
      </p>
    </div>
  );
}

function sourceItems(sources: Record<string, number>) {
  const sorted = Object.entries(sources).sort((a, b) => b[1] - a[1]);
  const result = sorted.slice(0, 4).map(([key, value]) => ({
    label: leadSourceChoices.find((item) => item.value === key)?.label || key,
    value,
  }));
  if (sorted.length > 4)
    result.push({
      label: "Other sources",
      value: sorted.slice(4).reduce((sum, [, value]) => sum + value, 0),
    });
  return result;
}
function QuickLinks({ field }: { field: boolean }) {
  return (
    <div className="crm-quick-links">
      {[
        {
          to: "/app/leads",
          icon: Users,
          title: "My clients",
          text: "Review requirements and plan the next call",
        },
        {
          to: "/app/phone-calls",
          icon: Phone,
          title: "Call history",
          text: "Calls, remarks and available recordings",
        },
        {
          to: "/app/field-work",
          icon: Building2,
          title: field ? "My field work" : "Visits & handoffs",
          text: field
            ? "Accept visits and record the next step"
            : "Coordinate confirmed client visits",
        },
      ].map(({ to, icon: Icon, title, text }) => (
        <Link key={to} to={to}>
          <span className="crm-task-icon">
            <Icon size={20} />
          </span>
          <span>
            <strong>{title}</strong>
            <small>{text}</small>
          </span>
          <ArrowUpRight size={17} />
        </Link>
      ))}
    </div>
  );
}
function talkTime(seconds: number) {
  const hours = Math.floor(seconds / 3600),
    minutes = Math.floor((seconds % 3600) / 60);
  const remainder = seconds % 60;
  return hours
    ? `${hours}h ${minutes}m`
    : minutes
      ? `${minutes}m${remainder ? ` ${remainder}s` : ""}`
      : `${seconds}s`;
}
function workTime(value: string, zone: string) {
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: zone,
  }).format(new Date(value));
}
