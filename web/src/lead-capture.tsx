import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  Copy,
  Globe2,
  KeyRound,
  Link2,
  Megaphone,
} from "lucide-react";
import { api, send } from "./api";
import { useAction, useData } from "./main";
import { Badge, Button, ErrorBox, Load, Table, dateTime } from "./ui";
import "./lead-capture.css";

interface CaptureChannel {
  channel: "website" | "google-ads";
  label: string;
  configured: boolean;
  enabled: boolean;
  endpoint: string;
  last_received: string | null;
}
export interface LeadCaptureData {
  auto_assign: boolean;
  telecallers: number;
  form: { enabled: boolean; url: string; last_received: string | null };
  channels: CaptureChannel[];
  recent: {
    id: string;
    channel: string;
    state: string;
    imported: number;
    duplicates: number;
    invalid: number;
    error: string;
    created_at: string;
  }[];
  captured_7d: Record<string, number>;
  key?: string;
}

const channelNames: Record<string, string> = {
  "website-form": "Enquiry form",
  website: "Website integration",
  "google-ads": "Google Ads",
};

function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="capture-copy">
      <span>{label}</span>
      <div>
        <code>{value}</code>
        <button
          type="button"
          className="text-button"
          aria-label={`Copy ${label.toLowerCase()}`}
          onClick={() =>
            void navigator.clipboard
              ?.writeText(value)
              .then(() => {
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              })
              .catch(() => setCopied(false))
          }
        >
          {copied ? <CheckCircle2 size={15} /> : <Copy size={15} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}

/** Company administrator settings for website, enquiry-form and Google Ads lead capture. */
export function LeadCapturePanel() {
  const q = useData<LeadCaptureData>("/lead-capture");
  const [error, setError] = useState<unknown>(null),
    [revealed, setRevealed] = useState<{ channel: string; key: string } | null>(
      null,
    ),
    [busy, setBusy] = useState(""),
    [assign, setAssign] = useState<boolean | null>(null),
    action = useAction();
  // Show the chosen setting immediately; clear it once the saved value arrives.
  useEffect(() => {
    if (assign !== null && q.data?.auto_assign === assign) setAssign(null);
  }, [assign, q.data?.auto_assign]);
  function run<T>(name: string, task: () => Promise<T>) {
    setError(null);
    setBusy(name);
    return action(task)
      .catch((e) => {
        setError(e);
        return null;
      })
      .finally(() => setBusy(""));
  }
  return (
    <section
      className="panel lead-capture"
      aria-labelledby="lead-capture-title"
    >
      <div className="panel-heading">
        <div>
          <h2 id="lead-capture-title">Lead capture</h2>
          <p>
            Bring enquiries in automatically. Repeat enquiries from the same
            phone join the existing lead, and new enquiries alert your team
            until someone calls.
          </p>
        </div>
      </div>
      {error !== null && <ErrorBox error={error} />}
      <Load query={q}>
        {(d) => {
          const website = d.channels.find((c) => c.channel === "website");
          const google = d.channels.find((c) => c.channel === "google-ads");
          const total = Object.values(d.captured_7d).reduce(
            (sum, n) => sum + n,
            0,
          );
          return (
            <>
              <div className="capture-assign">
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={assign ?? d.auto_assign}
                    disabled={busy === "assign"}
                    onChange={(e) => {
                      const value = e.target.checked;
                      setAssign(value);
                      void run("assign", () =>
                        send("/lead-capture", { auto_assign: value }, "PUT"),
                      ).then((r) => {
                        if (r === null) setAssign(null);
                      });
                    }}
                  />
                  <span>
                    <strong>Assign new enquiries automatically</strong>
                    <small>
                      {d.telecallers
                        ? `Round-robin across ${d.telecallers} active telecaller${d.telecallers === 1 ? "" : "s"}.`
                        : "No active telecallers yet. Enquiries stay unassigned until you add one."}
                    </small>
                  </span>
                </label>
                <p className="capture-week">
                  <strong>{total}</strong> enquir{total === 1 ? "y" : "ies"}{" "}
                  captured in the last 7 days
                </p>
              </div>
              <div className="capture-grid">
                <article className="capture-card">
                  <header>
                    <Link2 size={20} aria-hidden="true" />
                    <h3>Enquiry form link</h3>
                    <Badge
                      value={d.form.enabled ? "active" : "inactive"}
                      label={d.form.enabled ? "on" : "off"}
                    />
                  </header>
                  <p>
                    A ready-made form your clients can open from your website,
                    social profiles, ads or messages. No website changes needed.
                  </p>
                  {d.form.enabled && d.form.url && (
                    <CopyField label="Form link" value={d.form.url} />
                  )}
                  <p className="muted capture-last">
                    Last enquiry: {dateTime(d.form.last_received)}
                  </p>
                  <div className="capture-actions">
                    <Button
                      variant={d.form.enabled ? "secondary" : ""}
                      disabled={busy === "form"}
                      onClick={() =>
                        void run("form", () =>
                          send(
                            "/lead-capture",
                            { form_enabled: !d.form.enabled },
                            "PUT",
                          ),
                        )
                      }
                    >
                      {d.form.enabled ? "Turn off form" : "Turn on form"}
                    </Button>
                    {d.form.enabled && (
                      <>
                        <a
                          className="button secondary"
                          href={d.form.url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Open form
                        </a>
                        <button
                          className="text-button"
                          disabled={busy === "link"}
                          onClick={() =>
                            void run("link", () =>
                              api("/lead-capture/form/new-link", {
                                method: "POST",
                              }),
                            )
                          }
                        >
                          Replace link
                        </button>
                      </>
                    )}
                  </div>
                </article>
                {[website, google].map(
                  (channel) =>
                    channel && (
                      <article className="capture-card" key={channel.channel}>
                        <header>
                          {channel.channel === "website" ? (
                            <Globe2 size={20} aria-hidden="true" />
                          ) : (
                            <Megaphone size={20} aria-hidden="true" />
                          )}
                          <h3>{channel.label}</h3>
                          <Badge
                            value={channel.enabled ? "active" : "inactive"}
                            label={channel.enabled ? "on" : "off"}
                          />
                        </header>
                        <p>
                          {channel.channel === "website"
                            ? "For your website developer, landing-page builder or Zapier/Make: send each enquiry as JSON with name and phone. Email, city, budget, project and message are kept in the lead notes."
                            : "In Google Ads, open your lead form, choose webhook delivery, then paste this URL and key. Use “Send test data” to check the connection."}
                        </p>
                        <CopyField
                          label="Webhook URL"
                          value={channel.endpoint}
                        />
                        {revealed?.channel === channel.channel && (
                          <div className="capture-key" role="status">
                            <CopyField
                              label={
                                channel.channel === "website"
                                  ? "X-Webhook-Token header"
                                  : "Key"
                              }
                              value={revealed.key}
                            />
                            <small>
                              Copy this key now. For security it won't be shown
                              again; generate a new key if you lose it.
                            </small>
                          </div>
                        )}
                        <p className="muted capture-last">
                          Last delivery: {dateTime(channel.last_received)}
                        </p>
                        <div className="capture-actions">
                          <Button
                            variant={channel.enabled ? "secondary" : ""}
                            disabled={busy === channel.channel}
                            onClick={() =>
                              void run(channel.channel, () =>
                                api<LeadCaptureData>(
                                  `/lead-capture/${channel.channel}/key`,
                                  { method: "POST" },
                                ),
                              ).then((r) => {
                                if (r?.key)
                                  setRevealed({
                                    channel: channel.channel,
                                    key: r.key,
                                  });
                              })
                            }
                          >
                            <KeyRound size={16} />
                            {channel.configured
                              ? "Generate new key"
                              : "Turn on and get key"}
                          </Button>
                          {channel.enabled && (
                            <button
                              className="text-button"
                              disabled={busy === channel.channel + "-off"}
                              onClick={() =>
                                void run(channel.channel + "-off", () =>
                                  api(`/lead-capture/${channel.channel}/key`, {
                                    method: "DELETE",
                                  }),
                                ).then(() => setRevealed(null))
                              }
                            >
                              Turn off
                            </button>
                          )}
                        </div>
                        {channel.channel === "website" && (
                          <details>
                            <summary>Example request</summary>
                            <pre className="endpoint-code">{`POST ${channel.endpoint}
X-Webhook-Token: <your key>
Content-Type: application/json

{"id": "your-unique-id", "name": "Riya Sharma",
 "phone": "+919876543210", "email": "riya@example.com",
 "city": "Pune", "budget": "80 lakh", "project": "Lake View",
 "message": "Looking for a 2 BHK"}`}</pre>
                          </details>
                        )}
                      </article>
                    ),
                )}
              </div>
              {d.recent.length > 0 && (
                <Table
                  headers={[
                    "When",
                    "Channel",
                    "State",
                    "Added or updated",
                    "Duplicates",
                    "Invalid",
                  ]}
                >
                  {d.recent.map((r) => (
                    <tr key={r.id}>
                      <td>{dateTime(r.created_at)}</td>
                      <td>{channelNames[r.channel] || r.channel}</td>
                      <td>
                        <Badge
                          value={r.state === "test" ? "pending" : r.state}
                          label={r.state === "test" ? "test received" : r.state}
                        />
                      </td>
                      <td>{r.imported}</td>
                      <td>{r.duplicates}</td>
                      <td>{r.invalid}</td>
                    </tr>
                  ))}
                </Table>
              )}
            </>
          );
        }}
      </Load>
    </section>
  );
}

const purposes = [
  ["", "Choose one (optional)"],
  ["buy", "Buy a property"],
  ["rent", "Rent a property"],
  ["sell", "Sell my property"],
  ["invest", "Invest"],
];

/** Public, same-origin enquiry form shared by a company. No sign-in required. */
export function EnquiryPage() {
  const { formId = "" } = useParams();
  const details = useQuery<{ company: string; real_estate: boolean }, Error>({
    // "public" keys survive the cache reset that runs when no one is signed in.
    queryKey: ["public", "enquiry", formId],
    queryFn: () => api(`/public/enquiry/${encodeURIComponent(formId)}`),
    retry: false,
  });
  const [values, setValues] = useState<Record<string, string>>({
    name: "",
    phone: "",
    email: "",
    city: "",
    purpose: "",
    budget: "",
    message: "",
    website: "",
  });
  const [consent, setConsent] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(null),
    [sent, setSent] = useState(false);
  const field = (name: string) => ({
    value: values[name],
    onChange: (
      e: React.ChangeEvent<
        HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
      >,
    ) => setValues((v) => ({ ...v, [name]: e.target.value })),
  });
  return (
    <main className="enquiry-page">
      <div className="enquiry-card">
        {details.isPending ? (
          <p role="status">Loading the enquiry form…</p>
        ) : details.isError ? (
          <div>
            <h1>This form isn't available</h1>
            <p>
              The link may have been replaced or turned off. Please contact the
              company directly.
            </p>
          </div>
        ) : sent ? (
          <div role="status">
            <CheckCircle2 size={36} aria-hidden="true" />
            <h1>Thank you!</h1>
            <p>
              {details.data.company} has your enquiry and will contact you soon.
            </p>
          </div>
        ) : (
          <>
            <div className="eyebrow">ENQUIRY</div>
            <h1>{details.data.company}</h1>
            <p>
              Share a few details and the team will call you back.{" "}
              <small>Fields marked * are required.</small>
            </p>
            {error !== null && <ErrorBox error={error} />}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setBusy(true);
                setError(null);
                void send(`/public/enquiry/${encodeURIComponent(formId)}`, {
                  ...values,
                  consent,
                })
                  .then(() => setSent(true))
                  .catch(setError)
                  .finally(() => setBusy(false));
              }}
            >
              <label className="field">
                <span>Your name *</span>
                <input
                  autoComplete="name"
                  required
                  minLength={2}
                  maxLength={160}
                  {...field("name")}
                />
              </label>
              <label className="field">
                <span>Mobile number *</span>
                <input
                  type="tel"
                  autoComplete="tel"
                  required
                  minLength={6}
                  maxLength={30}
                  placeholder="+91 98765 43210"
                  {...field("phone")}
                />
              </label>
              <label className="field">
                <span>Email</span>
                <input
                  type="email"
                  autoComplete="email"
                  maxLength={160}
                  {...field("email")}
                />
              </label>
              <label className="field">
                <span>City</span>
                <input
                  autoComplete="address-level2"
                  maxLength={100}
                  {...field("city")}
                />
              </label>
              {details.data.real_estate && (
                <>
                  <label className="field">
                    <span>I want to</span>
                    <select {...field("purpose")}>
                      {purposes.map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span>Budget</span>
                    <input
                      maxLength={60}
                      placeholder="e.g. 80 lakh"
                      {...field("budget")}
                    />
                  </label>
                </>
              )}
              <label className="field">
                <span>Message</span>
                <textarea rows={3} maxLength={2000} {...field("message")} />
              </label>
              <label className="enquiry-honeypot" aria-hidden="true">
                Leave this empty
                <input tabIndex={-1} autoComplete="off" {...field("website")} />
              </label>
              <label className="check-row">
                <input
                  type="checkbox"
                  required
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                />
                <span>
                  I agree to be contacted by {details.data.company} by phone
                  about this enquiry. *
                </span>
              </label>
              <Button type="submit" disabled={busy}>
                {busy ? "Sending…" : "Send enquiry"}
              </Button>
            </form>
          </>
        )}
      </div>
      <p className="enquiry-footer">Secure enquiry form powered by ViaCRM</p>
    </main>
  );
}
