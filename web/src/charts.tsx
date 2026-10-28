import { useId, useState } from "react";

export const chartColors = [
  "#3659d9",
  "#178873",
  "#b57829",
  "#8a60b5",
  "#65748c",
  "#bf5578",
];
export interface ChartItem {
  label: string;
  value: number;
  color?: string;
}

export function DistributionChart({
  items,
  label,
  unit = "leads",
}: {
  items: ChartItem[];
  label: string;
  unit?: string;
}) {
  const positive = items.filter((item) => item.value > 0);
  const total = positive.reduce((sum, item) => sum + item.value, 0);
  let percent = 0;
  const gradient = positive
    .map((item, index) => {
      const start = percent;
      percent += (item.value / total) * 100;
      return `${item.color || chartColors[index % chartColors.length]} ${start}% ${percent}%`;
    })
    .join(",");
  return (
    <div className="crm-distribution" aria-label={label}>
      <div
        className="crm-donut"
        role="img"
        aria-label={`${total} ${unit}. ${positive.map((item) => `${item.label}: ${item.value}`).join("; ") || "No data yet"}`}
        style={{
          background: total ? `conic-gradient(${gradient})` : "#e8ecf3",
        }}
      >
        <div>
          <strong>{total.toLocaleString()}</strong>
          <span>{unit}</span>
        </div>
      </div>
      {positive.length ? (
        <ul className="crm-chart-legend">
          {positive.map((item, index) => (
            <li key={item.label}>
              <i
                aria-hidden="true"
                style={{
                  background:
                    item.color || chartColors[index % chartColors.length],
                }}
              />
              <span>{item.label}</span>
              <strong>{item.value.toLocaleString()}</strong>
            </li>
          ))}
        </ul>
      ) : (
        <p className="crm-chart-empty">
          No {unit} in this period. Your chart will appear as activity is
          recorded.
        </p>
      )}
    </div>
  );
}

export function TrendChart({
  items,
}: {
  items: { key: string; label: string; leads: number; calls: number }[];
}) {
  const [series, setSeries] = useState<"calls" | "leads">("calls");
  const id = useId().replaceAll(":", "");
  const values = items.map((item) => item[series]);
  const total = values.reduce((a, b) => a + b, 0);
  const top = Math.max(Math.ceil(Math.max(...values, 1) / 4) * 4, 4);
  const points = values.map((value, index) => [
    items.length === 1 ? 340 : 10 + (index / (items.length - 1)) * 660,
    190 - (value / top) * 175,
  ]);
  const line = points
    .map(([x, y], index) => `${index ? "L" : "M"}${x},${y}`)
    .join(" ");
  const area = points.length
    ? `${line} L${points.at(-1)![0]},190 L${points[0][0]},190 Z`
    : "";
  const labels = [
    ...new Set([0, Math.floor((items.length - 1) / 2), items.length - 1]),
  ];
  return (
    <div className="crm-trend">
      <div className="crm-trend-toolbar">
        <div>
          <strong>{total.toLocaleString()}</strong>
          <span>{series === "calls" ? "calls logged" : "new enquiries"}</span>
        </div>
        <div className="crm-toggle" aria-label="Chart measure">
          {(["calls", "leads"] as const).map((value) => (
            <button
              key={value}
              aria-pressed={series === value}
              onClick={() => setSeries(value)}
            >
              {value === "calls" ? "Calls" : "Enquiries"}
            </button>
          ))}
        </div>
      </div>
      <div className="crm-trend-plot">
        <div className="crm-y-labels" aria-hidden="true">
          <span>{top}</span>
          <span>{top / 2}</span>
          <span>0</span>
        </div>
        <svg
          viewBox="0 0 680 210"
          preserveAspectRatio="none"
          role="img"
          aria-labelledby={`trend-${id}`}
        >
          <title id={`trend-${id}`}>
            {series === "calls" ? "Call activity" : "New enquiries"}: {total} in
            this period. Open chart data below for exact values.
          </title>
          <defs>
            <linearGradient id={`fill-${id}`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#3659d9" stopOpacity=".19" />
              <stop offset="100%" stopColor="#3659d9" stopOpacity=".015" />
            </linearGradient>
          </defs>
          {[15, 102.5, 190].map((y) => (
            <line
              key={y}
              x1="0"
              x2="680"
              y1={y}
              y2={y}
              stroke="#e8ecf4"
              strokeDasharray="4 6"
              vectorEffect="non-scaling-stroke"
            />
          ))}
          {!!total && <path d={area} fill={`url(#fill-${id})`} />}
          <path
            d={line}
            stroke="#3659d9"
            strokeWidth="3"
            fill="none"
            vectorEffect="non-scaling-stroke"
            strokeLinejoin="round"
          />
          {points.map(([x, y], index) => (
            <circle
              key={items[index].key}
              cx={x}
              cy={y}
              r="4"
              fill="white"
              stroke="#3659d9"
              strokeWidth="2"
              vectorEffect="non-scaling-stroke"
            >
              <title>
                {items[index].label}: {values[index]} {series}
              </title>
            </circle>
          ))}
        </svg>
      </div>
      <div className="crm-x-labels" aria-hidden="true">
        {labels.map((index) => (
          <span key={index}>{items[index]?.label}</span>
        ))}
      </div>
      {!total && (
        <p className="crm-chart-empty">
          No {series === "calls" ? "calls logged" : "new enquiries"} in this
          period.
        </p>
      )}
      <details className="crm-chart-data">
        <summary>View chart data</summary>
        <div
          className="crm-chart-table"
          tabIndex={0}
          role="region"
          aria-label="Scrollable chart values"
        >
          <table>
            <caption>Activity in the selected period</caption>
            <thead>
              <tr>
                <th scope="col">Date / local hour</th>
                <th scope="col">Calls</th>
                <th scope="col">New enquiries</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.key}>
                  <th scope="row">{item.label}</th>
                  <td>{item.calls}</td>
                  <td>{item.leads}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
