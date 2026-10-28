import { useState } from "react";
import { Link } from "react-router-dom";
import { Download, ShieldCheck } from "lucide-react";
import { download, send } from "./api";
import { useAction, useData } from "./main";
import type { PayRow } from "./types";
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
  type Field,
} from "./ui";

interface PayData {
  month: string;
  timezone: string;
  as_of: string;
  items: PayRow[];
  policy: string;
  totals: {
    estimated_pay: string;
    office_seconds: string;
    call_seconds: string;
    pending_hours: string;
  };
}
const method = (row: PayRow) =>
  row.pay_basis === "office_calls" ? "Office + calling" : "Approved work hours";
function time(value: string | number) {
  const seconds = Math.max(0, Math.floor(Number(value) || 0));
  return `${Math.floor(seconds / 3600)}h ${String(Math.floor((seconds % 3600) / 60)).padStart(2, "0")}m${seconds % 60 ? ` ${seconds % 60}s` : ""}`;
}
function thisMonth() {
  const day = new Date();
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}`;
}

function PaySettings({ row, onClose }: { row: PayRow; onClose: () => void }) {
  const [basis, setBasis] = useState(row.pay_basis);
  const action = useAction();
  const fields: Field[] = [
    {
      name: "pay_basis",
      label: "Calculate salary using",
      wide: true,
      render: (value, set) => (
        <label className="field">
          <span>Calculate salary using</span>
          <select
            aria-label="Calculate salary using"
            value={String(value)}
            onChange={(event) => {
              set(event.target.value);
              setBasis(event.target.value as PayRow["pay_basis"]);
            }}
          >
            <option value="work">Approved work hours</option>
            <option value="office_calls">
              Office + calling — separate rates
            </option>
          </select>
        </label>
      ),
    },
    {
      name: "hourly_rate",
      label:
        basis === "office_calls" ? "Office hourly rate (₹)" : "Hourly rate (₹)",
      type: "number",
      min: "0",
      max: "1000000",
      step: ".01",
      required: true,
    },
    ...(basis === "office_calls"
      ? [
          {
            name: "call_hourly_rate",
            label: "Calling hourly rate (₹)",
            type: "number",
            min: ".01",
            max: "1000000",
            step: ".01",
            required: true,
          },
        ]
      : []),
    {
      name: "daily_target",
      label: "Daily target hours",
      type: "number",
      min: ".01",
      max: "24",
      step: ".01",
      required: true,
      hint: "For target tracking. Salary uses the eligible time actually recorded.",
    },
  ];
  return (
    <FormDialog
      title={`Pay settings · ${row.name}`}
      description="Rates apply to every month. Existing estimates update when you change a rate."
      fields={fields}
      initial={{
        hourly_rate: row.hourly_rate,
        daily_target: row.daily_target,
        pay_basis: row.pay_basis,
        call_hourly_rate: row.call_hourly_rate,
      }}
      onClose={onClose}
      onSubmit={(values) =>
        action(() =>
          send(
            `/payroll/profiles/${row.user_id}`,
            {
              ...values,
              call_hourly_rate: values.call_hourly_rate ?? row.call_hourly_rate,
            },
            "PUT",
          ),
        )
      }
    >
      <div className="payroll-settings-help">
        {basis === "office_calls" ? (
          <>
            <strong>Each hour is counted once.</strong>
            <p>
              8 approved office hours including 2 call hours become 6 office
              hours + 2 call hours, each at its own rate. Calls outside office
              hours also use the calling rate.
            </p>
            <p>
              Office pay needs approved check-in/check-out attendance. Calling
              pay uses synced answered calls; manual time and conversation
              entries do not add office or calling hours.
            </p>
          </>
        ) : (
          <p>
            Pay uses approved work hours from attendance or manual time. Synced
            calling time is displayed for reference.
          </p>
        )}
      </div>
    </FormDialog>
  );
}

function Calculation({ row }: { row: PayRow }) {
  return (
    <div className="pay-calculation">
      <div>
        <span>
          {row.pay_basis === "office_calls"
            ? "Non-call office time"
            : "Approved work"}
          <small>
            {row.pay_basis === "office_calls"
              ? time(row.non_call_office_seconds)
              : `${row.base_paid_hours} hours`}{" "}
            × {money(row.hourly_rate)} / hour
          </small>
        </span>
        <strong>{money(row.base_pay)}</strong>
      </div>
      {row.pay_basis === "office_calls" && (
        <div>
          <span>
            Calling time
            <small>
              {time(row.call_seconds)} × {money(row.call_hourly_rate)} / hour
            </small>
          </span>
          <strong>{money(row.call_pay)}</strong>
        </div>
      )}
      <div className="pay-calculation-total">
        <span>Estimated salary</span>
        <strong>{money(row.estimated_pay)}</strong>
      </div>
    </div>
  );
}

function Breakdown({
  row,
  data,
  onClose,
}: {
  row: PayRow;
  data: PayData;
  onClose: () => void;
}) {
  return (
    <Dialog
      title={`Salary breakdown · ${row.name}`}
      description={`${data.month} · ${data.timezone} · ${method(row)}`}
      onClose={onClose}
    >
      <div className="dialog-content payroll-breakdown">
        <Calculation row={row} />
        <dl className="payroll-facts">
          <div>
            <dt>Office attendance recorded</dt>
            <dd>{time(row.office_seconds)}</dd>
          </div>
          <div>
            <dt>Approved office attendance</dt>
            <dd>{time(row.approved_office_seconds)}</dd>
          </div>
          <div>
            <dt>Office time awaiting approval</dt>
            <dd>{time(row.pending_office_seconds)}</dd>
          </div>
          <div>
            <dt>Synced answered-call time</dt>
            <dd>{time(row.call_seconds)}</dd>
          </div>
          <div>
            <dt>Calls during approved office time</dt>
            <dd>{time(row.calls_during_office_seconds)}</dd>
          </div>
          <div>
            <dt>Calls outside approved office time</dt>
            <dd>{time(row.calls_outside_office_seconds)}</dd>
          </div>
          <div>
            <dt>Approved work ledger</dt>
            <dd>{row.approved_hours} h</dd>
          </div>
          <div>
            <dt>Work awaiting review</dt>
            <dd>{row.pending_hours} h</dd>
          </div>
          <div>
            <dt>Manually entered call duration</dt>
            <dd>
              {time(row.declared_call_seconds)}{" "}
              <small>Reference only; excluded from calling pay</small>
            </dd>
          </div>
          <div>
            <dt>Monthly work target</dt>
            <dd>
              {row.target_hours} h{" "}
              <small>{row.approved_leave_days} approved leave days</small>
            </dd>
          </div>
        </dl>
        {row.open_attendance > 0 && (
          <p className="notice">
            Attendance is still open. Close the session, then approve its time
            before it contributes to office pay.
          </p>
        )}
        <h3>Daily time breakdown</h3>
        {row.daily.length ? (
          <Table
            label="Daily salary time breakdown"
            headers={[
              "Day",
              "Office recorded",
              "Office approved",
              "Call time",
              "Calls inside office",
              "Non-call office",
              "Approved work",
            ]}
          >
            {row.daily.map((day) => (
              <tr key={day.day}>
                <td>{day.day}</td>
                <td>{time(day.office_seconds)}</td>
                <td>{time(day.approved_office_seconds)}</td>
                <td>{time(day.call_seconds)}</td>
                <td>{time(day.calls_during_office_seconds)}</td>
                <td>{time(day.non_call_office_seconds)}</td>
                <td>{day.approved_work_hours} h</td>
              </tr>
            ))}
          </Table>
        ) : (
          <p className="help-text">
            No attendance, work entries or answered calls in this month.
          </p>
        )}
        <p className="help-text">
          Call time uses phone-reported start and duration. Placement around
          office boundaries is approximate. Overlapping call records count once.
          Manual call durations and recordings do not add calling pay.
        </p>
        <p className="help-text">
          Updated {dateTime(data.as_of)}. Late call syncing and attendance
          approvals can change this estimate.
        </p>
      </div>
      <footer>
        <Button onClick={onClose}>Close</Button>
      </footer>
    </Dialog>
  );
}

export function PayrollPage() {
  const [month, setMonth] = useState(thisMonth());
  const [search, setSearch] = useState("");
  const [edit, setEdit] = useState<PayRow | null>(null);
  const [detail, setDetail] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const query = useData<PayData>(`/payroll?month=${month}`);
  return (
    <>
      <PageHeading
        eyebrow="TIME YOU CAN ACCOUNT FOR"
        title="Payroll estimates"
        description="Office attendance, calling time and a clear salary calculation for every employee."
        actions={
          <Button
            variant="secondary"
            onClick={() =>
              void download(
                `/payroll/export?month=${month}`,
                "payroll-estimate.csv",
              ).catch(setError)
            }
          >
            <Download size={16} />
            Export estimate
          </Button>
        }
      />
      <div className="filter-row payroll-filters">
        <label className="field">
          <span>Salary month</span>
          <input
            aria-label="Payroll month"
            type="month"
            value={month}
            onChange={(event) => {
              setMonth(event.target.value || thisMonth());
              setDetail(null);
            }}
          />
        </label>
        <label className="field">
          <span>Find an employee</span>
          <input
            aria-label="Search payroll employees"
            placeholder="Employee name"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <Badge value="admin only" />
      </div>
      {error !== null && <ErrorBox error={error} />}
      <Load query={query}>
        {(data) => (
          <>
            <div className="stats-grid">
              <Stat
                label="Estimated team salary"
                value={money(data.totals.estimated_pay)}
                detail="From each employee's selected pay method"
                accent
              />
              <Stat
                label="Office attendance"
                value={time(data.totals.office_seconds)}
                detail="Recorded time, including hours awaiting approval"
              />
              <Stat
                label="Synced calling time"
                value={time(data.totals.call_seconds)}
                detail="Answered calls; overlapping records count once"
              />
              <Stat
                label="Work awaiting review"
                value={`${Number(data.totals.pending_hours).toFixed(2)} h`}
                detail="Pending work does not add office pay"
              />
            </div>
            <div className="notice payroll-source-note">
              <ShieldCheck size={20} />
              <p>
                Employees check in and out through{" "}
                <Link to="/app/attendance">Attendance</Link>. Review office time
                in <Link to="/app/approvals">Requests & approvals</Link>.
                Calling time comes from synced answered phone calls, even when
                no recording is uploaded.
              </p>
            </div>
            <Panel
              title="Employee estimates"
              description="Choose Office + calling in Edit rate to pay non-call office time and calling time at separate hourly rates."
            >
              {data.items.filter((row) =>
                row.name
                  .toLocaleLowerCase()
                  .includes(search.trim().toLocaleLowerCase()),
              ).length ? (
                <Table
                  headers={[
                    "Employee",
                    "Office attendance",
                    "Calling time",
                    "Pay method",
                    "Pay breakdown",
                    "Estimated salary",
                    "Actions",
                  ]}
                >
                  {data.items
                    .filter((row) =>
                      row.name
                        .toLocaleLowerCase()
                        .includes(search.trim().toLocaleLowerCase()),
                    )
                    .map((row) => (
                      <tr key={row.user_id}>
                        <td>
                          <strong>{row.name}</strong>
                          {!row.active && (
                            <small className="block muted">
                              Inactive employee
                            </small>
                          )}
                        </td>
                        <td>
                          <strong>{time(row.office_seconds)}</strong>
                          <small className="block muted">
                            {time(row.approved_office_seconds)} approved
                          </small>
                          {Number(row.pending_office_seconds) > 0 && (
                            <small className="block muted">
                              {time(row.pending_office_seconds)} awaiting
                              approval
                            </small>
                          )}
                          {row.open_attendance > 0 && (
                            <small className="block muted">
                              Check-out pending
                            </small>
                          )}
                        </td>
                        <td>
                          <strong>{time(row.call_seconds)}</strong>
                          <small className="block muted">
                            {row.answered_call_records} answered call records
                          </small>
                        </td>
                        <td>
                          {method(row)}
                          <small className="block muted">
                            {row.approved_hours} h approved work
                          </small>
                        </td>
                        <td>
                          <span className="block">
                            {row.pay_basis === "office_calls"
                              ? "Office"
                              : "Work"}
                            : {money(row.base_pay)}
                          </span>
                          {row.pay_basis === "office_calls" && (
                            <span className="block">
                              Calling: {money(row.call_pay)}
                            </span>
                          )}
                          <small className="block muted">
                            {money(row.hourly_rate)} / h
                            {row.pay_basis === "office_calls"
                              ? ` office · ${money(row.call_hourly_rate)} / h calling`
                              : ""}
                          </small>
                        </td>
                        <td>
                          <strong>{money(row.estimated_pay)}</strong>
                        </td>
                        <td>
                          <div className="payroll-row-actions">
                            <button
                              className="text-button"
                              onClick={() => setDetail(row.user_id)}
                            >
                              View breakdown
                            </button>
                            <button
                              className="text-button"
                              onClick={() => setEdit(row)}
                            >
                              Edit rate
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                </Table>
              ) : (
                <Empty
                  title="No employees match"
                  description="Try a different employee name."
                  action={
                    <Button variant="secondary" onClick={() => setSearch("")}>
                      Clear search
                    </Button>
                  }
                />
              )}
            </Panel>
            <div className="policy-box">
              <ShieldCheck size={22} />
              <div>
                <h3>How salary is calculated</h3>
                <p>
                  Office + calling: 8 approved office hours including 2 call
                  hours = 6 office hours × office rate + 2 call hours × calling
                  rate. Calls outside approved office time also use the calling
                  rate.
                </p>
                <p>
                  Approved work hours: existing attendance/manual-work approval
                  rules apply. Manual call durations do not count as paid call
                  time. Tax, statutory deductions and commissions are not
                  calculated here.
                </p>
                <details>
                  <summary>Time sources and calculation details</summary>
                  <p>{data.policy}</p>
                  <p>
                    {data.timezone} · Updated {dateTime(data.as_of)}. These are
                    live estimates.
                  </p>
                </details>
              </div>
            </div>
            {detail && data.items.some((row) => row.user_id === detail) && (
              <Breakdown
                row={data.items.find((row) => row.user_id === detail)!}
                data={data}
                onClose={() => setDetail(null)}
              />
            )}
          </>
        )}
      </Load>
      {edit && (
        <PaySettings
          key={edit.user_id}
          row={edit}
          onClose={() => setEdit(null)}
        />
      )}
    </>
  );
}
