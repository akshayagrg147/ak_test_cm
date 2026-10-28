import {
  useEffect,
  useId,
  useRef,
  useState,
  type CSSProperties,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  AlertCircle,
  ArrowRight,
  Check,
  ChevronRight,
  LoaderCircle,
  Plus,
  RefreshCw,
  X,
} from "lucide-react";
import type { UseQueryResult } from "@tanstack/react-query";
import { ApiError } from "./api";

export function Button({
  children,
  variant = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: string }) {
  return (
    <button className={`button ${variant}`} {...props}>
      {children}
    </button>
  );
}
export function Badge({
  value,
  label,
  title,
}: {
  value: string;
  label?: string;
  title?: string;
}) {
  return (
    <span className={`badge ${value.replaceAll(" ", "-")}`} title={title}>
      <span />
      {label || value.replaceAll("-", " ").replaceAll("_", " ")}
    </span>
  );
}
export function recordingLabel(value: string) {
  return (
    {
      attached: "Audio uploaded",
      unavailable: "No audio uploaded",
      pending: "Upload pending",
      ambiguous: "Needs review",
    }[value] || value.replaceAll("-", " ")
  );
}
export function RecordingBadge({ value }: { value: string }) {
  return (
    <Badge
      value={value}
      label={recordingLabel(value)}
      title={
        value === "unavailable"
          ? "No recording file has been uploaded to this call. Call details and audio sync separately."
          : undefined
      }
    />
  );
}
export function Empty({
  title = "Nothing here yet",
  description = "New records will appear here.",
  action,
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Plus size={23} />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}
export function ErrorBox({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  return (
    <div role="alert" className="error-box">
      <AlertCircle size={19} />
      <div>
        <strong>We couldn’t complete that request</strong>
        <p>{error instanceof Error ? error.message : String(error)}</p>
        {retry && (
          <button type="button" className="text-button" onClick={retry}>
            <RefreshCw size={14} />
            Try again
          </button>
        )}
      </div>
    </div>
  );
}
export function Load<T>({
  query,
  children,
}: {
  query: UseQueryResult<T, Error>;
  children: (data: T) => ReactNode;
}) {
  if (query.isPending)
    return (
      <div
        role="status"
        aria-live="polite"
        aria-label="Loading"
        className="skeletons"
      >
        <div />
        <div />
        <div />
      </div>
    );
  if (
    query.isError &&
    (query.data === undefined ||
      (query.error instanceof ApiError &&
        [401, 403, 404].includes(query.error.status)))
  )
    return <ErrorBox error={query.error} retry={() => void query.refetch()} />;
  return (
    <>
      {query.isError && (
        <ErrorBox error={query.error} retry={() => void query.refetch()} />
      )}
      {children(query.data as T)}
    </>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      <div className="heading-actions">{actions}</div>
    </div>
  );
}
export function Panel({
  title,
  description,
  action,
  children,
  className = "",
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {title && (
        <div className="panel-heading">
          <div>
            <h2>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
export type Values = Record<string, string | boolean>;
export interface Field {
  name: string;
  label: string;
  type?: string;
  required?: boolean;
  options?: { value: string; label: string }[];
  hint?: string;
  render?: (
    value: string | boolean | undefined,
    set: (value: string | boolean) => void,
  ) => ReactNode;
  maxLength?: number;
  min?: string;
  max?: string;
  step?: string;
  defaultValue?: string | boolean;
  wide?: boolean;
}
export function Fields({
  fields,
  values,
  set,
}: {
  fields: Field[];
  values: Values;
  set: (name: string, v: string | boolean) => void;
}) {
  return (
    <div className="form-grid">
      {fields.map((f) =>
        f.render ? (
          <div className={`field ${f.wide ? "wide" : ""}`} key={f.name}>
            {f.render(values[f.name], (value) => set(f.name, value))}
          </div>
        ) : (
          <label
            className={`field ${f.wide ? "wide" : ""} ${f.type === "checkbox" ? "check-field" : ""}`}
            key={f.name}
          >
            <span>
              {f.label}
              {f.required && (
                <span aria-hidden="true" className="required">
                  {" "}
                  *
                </span>
              )}
            </span>
            {f.type === "textarea" ? (
              <textarea
                aria-label={f.label}
                rows={4}
                maxLength={f.maxLength}
                required={f.required}
                value={String(values[f.name] ?? "")}
                onChange={(e) => set(f.name, e.target.value)}
              />
            ) : f.options ? (
              <select
                aria-label={f.label}
                required={f.required && f.type !== "checkbox"}
                value={String(values[f.name] ?? "")}
                onChange={(e) => set(f.name, e.target.value)}
              >
                {!f.required && <option value="">Select…</option>}
                {f.required && !values[f.name] && (
                  <option value="">Select…</option>
                )}
                {f.options.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                aria-label={f.label}
                type={f.type || "text"}
                required={f.required && f.type !== "checkbox"}
                min={f.min}
                max={f.max}
                step={f.step}
                maxLength={
                  f.maxLength ?? (f.type === "password" ? 200 : undefined)
                }
                autoComplete={
                  f.type === "password" ? "new-password" : undefined
                }
                checked={
                  f.type === "checkbox" ? Boolean(values[f.name]) : undefined
                }
                value={
                  f.type === "checkbox"
                    ? undefined
                    : String(values[f.name] ?? "")
                }
                onChange={(e) =>
                  set(
                    f.name,
                    f.type === "checkbox" ? e.target.checked : e.target.value,
                  )
                }
              />
            )}
            {f.hint && <small>{f.hint}</small>}
          </label>
        ),
      )}
    </div>
  );
}
export function Dialog({
  title,
  children,
  onClose,
  description,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  description?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const d = ref.current;
    const prior = document.activeElement;
    d?.showModal();
    return () => {
      d?.close();
      if (prior instanceof HTMLElement) prior.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className="dialog"
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <header>
        <div>
          <h2 id={titleId}>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        <button
          className="icon-button"
          aria-label="Close dialog"
          onClick={onClose}
        >
          <X />
        </button>
      </header>
      {children}
    </dialog>
  );
}
export interface QueryDependency {
  isPending: boolean;
  isError: boolean;
  error: Error | null;
  data?: unknown;
  refetch: () => unknown;
}
export function QueryNotice({
  query,
  loading = false,
}: {
  query: QueryDependency;
  loading?: boolean;
}) {
  if (query.isError)
    return <ErrorBox error={query.error} retry={() => void query.refetch()} />;
  if (loading && query.isPending)
    return (
      <div
        role="status"
        aria-live="polite"
        className="skeletons"
        aria-label="Loading form options"
      >
        <div />
        <div />
      </div>
    );
  return null;
}
export function FormDialog({
  title,
  fields,
  initial = {},
  submitLabel = "Save changes",
  onClose,
  onSubmit,
  description,
  children,
  dependencies = [],
}: {
  title: string;
  fields: Field[];
  initial?: Values;
  submitLabel?: string;
  onClose: () => void;
  onSubmit: (v: Values) => Promise<unknown>;
  description?: string;
  children?: ReactNode;
  dependencies?: QueryDependency[];
}) {
  const [values, setValues] = useState<Values>(() =>
    Object.fromEntries(
      fields.map((f) => [
        f.name,
        initial[f.name] ??
          f.defaultValue ??
          (f.type === "checkbox" ? false : ""),
      ]),
    ),
  );
  useEffect(() => {
    setValues((previous) => {
      const missing = fields.filter((field) => !(field.name in previous));
      return missing.length
        ? {
            ...previous,
            ...Object.fromEntries(
              missing.map((field) => [
                field.name,
                initial[field.name] ??
                  field.defaultValue ??
                  (field.type === "checkbox" ? false : ""),
              ]),
            ),
          }
        : previous;
    });
  }, [fields, initial]);
  const blocked = dependencies.some(
    (query) => query.isPending || (query.isError && query.data === undefined),
  );
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy || blocked) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit(values);
      onClose();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title={title}
      description={description}
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <form onSubmit={(e) => void submit(e)}>
        {dependencies.map((query, index) => (
          <QueryNotice key={index} query={query} loading />
        ))}
        {!blocked && (
          <Fields
            fields={fields}
            values={values}
            set={(k, v) => setValues((s) => ({ ...s, [k]: v }))}
          />
        )}
        {children}
        {error !== null && <ErrorBox error={error} />}
        <footer>
          <Button
            type="button"
            variant="secondary"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button disabled={busy || blocked}>
            {busy ? (
              <LoaderCircle className="spin" size={17} />
            ) : (
              <Check size={17} />
            )}
            {submitLabel}
          </Button>
        </footer>
      </form>
    </Dialog>
  );
}
export function Stat({
  label,
  value,
  detail,
  icon,
  accent = false,
}: {
  label: string;
  value: ReactNode;
  detail: string;
  icon?: ReactNode;
  accent?: boolean;
}) {
  return (
    <div className={`stat ${accent ? "accent" : ""}`}>
      <div className="stat-label">
        {label}
        {icon}
      </div>
      <strong
        title={
          typeof value === "string" || typeof value === "number"
            ? String(value)
            : undefined
        }
        style={
          {
            "--value-length": Math.max(String(value).length, 6),
          } as CSSProperties
        }
      >
        {value}
      </strong>
      <small>{detail}</small>
    </div>
  );
}
export function Table({
  headers,
  children,
  label,
}: {
  headers: string[];
  children: ReactNode;
  label?: string;
}) {
  return (
    <div
      className="table-wrap"
      tabIndex={label ? 0 : undefined}
      role={label ? "region" : undefined}
      aria-label={label}
    >
      <table>
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th key={i}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}
export function MiniBar({
  items,
  total,
}: {
  items: Record<string, number>;
  total?: number;
}) {
  const max = total || Math.max(...Object.values(items), 1);
  return (
    <div className="bar-list">
      {Object.entries(items).map(([label, value], i) => (
        <div key={label}>
          <div>
            <span>
              <i
                style={{
                  background: [
                    "#4269da",
                    "#7f97e5",
                    "#d2a35d",
                    "#468a7a",
                    "#a7b0c3",
                  ][i % 5],
                }}
              />
              {label.replaceAll("-", " ")}
            </span>
            <strong>{value}</strong>
          </div>
          <div className="bar-track">
            <div style={{ width: `${(value / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}
export const dateTime = (value: string | null | undefined) =>
  value
    ? new Intl.DateTimeFormat("en-IN", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value))
    : "—";
export const money = (value: string | number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(value));
export const duration = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
export const options = (values: string[]) =>
  values.map((value) => ({
    value,
    label: value.replaceAll("-", " ").replaceAll("_", " "),
  }));
export const nextIcon = <ChevronRight size={16} />;
export const arrowIcon = <ArrowRight size={17} />;
