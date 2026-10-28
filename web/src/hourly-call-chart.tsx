import { useState } from "react";
import "./hourly-call-chart.css";

function hourLabel(hour: number) {
  return `${hour % 12 || 12} ${hour < 12 ? "AM" : "PM"}`;
}
function hourRange(hour: number) {
  return `${hourLabel(hour)} – ${hourLabel((hour + 1) % 24)}`;
}

export function HourlyCallChart({
  items,
  timezone,
}: {
  items: { hour: number; calls: number }[];
  timezone: string;
}) {
  const [selectedHour, setSelectedHour] = useState<number | null>(null);
  const total = items.reduce((sum, item) => sum + item.calls, 0);
  const peak = items.reduce(
    (best, item) => (item.calls > (best?.calls || 0) ? item : best),
    null as (typeof items)[number] | null,
  );
  const ceiling = Math.max(Math.ceil((peak?.calls || 0) / 2) * 2, 2);
  const selected = items.find((item) => item.hour === selectedHour) || peak;
  return (
    <figure className="call-hourly" aria-label="Calls by hour">
      <figcaption className="call-hourly-caption">
        <strong>
          {total.toLocaleString()} {total === 1 ? "call" : "calls"}
        </strong>
        <span>By time of day · {timezone}</span>
      </figcaption>
      {total ? (
        <>
          <p className="call-hourly-instruction">
            Select an hour to see its total. Each bar combines that hour across
            the selected dates.
          </p>
          <div className="call-hourly-layout">
            <div className="call-hourly-axis" aria-hidden="true">
              <span>{ceiling.toLocaleString()}</span>
              <span>{(ceiling / 2).toLocaleString()}</span>
              <span>0</span>
            </div>
            <div
              className="call-hourly-scroll"
              tabIndex={0}
              role="region"
              aria-label="Hourly calls chart; scroll sideways to see all 24 hours"
            >
              <div className="call-hourly-columns">
                {items.map(({ hour, calls }) => {
                  const height = (calls / ceiling) * 140;
                  return (
                    <button
                      type="button"
                      className="call-hourly-column"
                      key={hour}
                      title={`${hourRange(hour)}: ${calls.toLocaleString()} ${calls === 1 ? "call" : "calls"}`}
                      aria-pressed={selected?.hour === hour}
                      onClick={() => setSelectedHour(hour)}
                    >
                      <span className="call-hourly-label">
                        {hourLabel(hour)}{" "}
                      </span>
                      <span className="call-hourly-well">
                        <strong style={{ bottom: height + 6 }}>
                          {calls.toLocaleString()}
                        </strong>
                        <span className="visually-hidden">
                          {" "}
                          {calls === 1 ? "call" : "calls"}
                        </span>
                        <i
                          className="call-hourly-bar"
                          style={{ height }}
                          aria-hidden="true"
                        />
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
          <p className="call-hourly-scroll-hint">
            Scroll sideways to see all 24 hours. You can also use the hourly
            data table below.
          </p>
          {selected && (
            <p className="call-hourly-selection" aria-live="polite">
              <strong>
                {selectedHour === null ? "Busiest hour: " : ""}
                {hourRange(selected.hour)} · {selected.calls.toLocaleString()}{" "}
                {selected.calls === 1 ? "call" : "calls"}
              </strong>
              <span>
                {selected.calls
                  ? "Total across the selected report dates."
                  : "No calls recorded for this hour."}
              </span>
            </p>
          )}
        </>
      ) : (
        <div className="call-hourly-empty">
          <strong>No calls in this period</strong>
          <p>Change the report dates or team member to check other activity.</p>
        </div>
      )}
      <details className="call-hourly-data">
        <summary>View hourly data</summary>
        <div
          className="call-hourly-table"
          tabIndex={0}
          role="region"
          aria-label="Scrollable hourly call counts"
        >
          <table>
            <caption>Hourly call counts · {timezone}</caption>
            <thead>
              <tr>
                <th scope="col">Hour</th>
                <th scope="col">Calls</th>
              </tr>
            </thead>
            <tbody>
              {items.map(({ hour, calls }) => (
                <tr key={hour}>
                  <th scope="row">{hourRange(hour)}</th>
                  <td>{calls.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <p className="call-hourly-definition">
        Phone calls use their start time; manual calls use the time they were
        saved. Adding a result to a synced call does not count it again.
      </p>
    </figure>
  );
}
