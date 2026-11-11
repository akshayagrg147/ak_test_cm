import { Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Circle,
  Clock3,
  ShieldCheck,
} from "lucide-react";
import { useAuth, useData } from "./main";
import type {
  CompanyProfile,
  OnboardingData,
  PaymentReadiness,
  Subscription,
} from "./estate-types";
import "./onboarding.css";

/** Company profile fields in display order, shared by progress counts and missing-field hints. */
export const profileFieldLabels: Record<keyof CompanyProfile, string> = {
  contact_name: "contact person",
  email: "email",
  phone: "contact phone",
  city: "city",
  state: "state",
  address: "address",
  website: "website",
  rera_number: "RERA number",
  gst_number: "GST number",
};

export function profileProgress(profile: CompanyProfile | undefined) {
  const keys = Object.keys(profileFieldLabels) as (keyof CompanyProfile)[];
  const missing = keys.filter((key) => !String(profile?.[key] || "").trim());
  return { filled: keys.length - missing.length, total: keys.length, missing };
}

export function missingProfileText(missing: string[]) {
  return missing
    .map((key) => profileFieldLabels[key as keyof CompanyProfile] || key)
    .join(", ");
}

export const ENDING_SOON_DAYS = 7;

/** Plain-language subscription timing for trials and plans that are ending or have ended. */
export function subscriptionTiming(sub: Subscription | null | undefined) {
  if (!sub || typeof sub.days_left !== "number") return null;
  const trial = sub.status === "trial";
  const noun = trial ? "trial" : "plan";
  if (sub.effective_status === "expired")
    return {
      tone: "expired" as const,
      short: "Expired",
      title: `Your ${noun} ended on ${sub.ends_on}`,
    };
  if (!["trial", "active"].includes(sub.effective_status)) return null;
  const days = sub.days_left;
  const short =
    days === 0 ? "Ends today" : days === 1 ? "1 day left" : `${days} days left`;
  return {
    tone: days <= ENDING_SOON_DAYS ? ("soon" as const) : ("ok" as const),
    short,
    title:
      days === 0
        ? `Your ${noun} ends today`
        : `Your ${noun} ends in ${days === 1 ? "1 day" : days + " days"}`,
  };
}

/** Countdown shown to a company administrator while a trial or plan is close to ending. */
export function TrialNotice({
  subscription,
  payments,
  showAction = true,
}: {
  subscription: Subscription | null | undefined;
  payments?: PaymentReadiness;
  showAction?: boolean;
}) {
  const timing = subscriptionTiming(subscription);
  if (!timing || timing.tone === "ok") return null;
  const canPay = payments ? payments.ready : true;
  return (
    <div
      className={`crm-trial-notice ${timing.tone}`}
      role={timing.tone === "expired" ? "alert" : "status"}
    >
      {timing.tone === "expired" ? (
        <AlertTriangle size={22} aria-hidden="true" />
      ) : (
        <Clock3 size={22} aria-hidden="true" />
      )}
      <div>
        <strong>{timing.title}</strong>
        <p>
          {canPay
            ? `Choose a plan to keep your team working without interruption. Ends ${subscription?.ends_on}.`
            : `Paid plans are still being set up by your ViaCRM provider. Contact them to extend access. Ends ${subscription?.ends_on}.`}
        </p>
      </div>
      {showAction && canPay && (
        <Link className="button" to="/app/billing">
          Choose a plan
          <ArrowRight size={16} />
        </Link>
      )}
    </div>
  );
}

interface Step {
  key: string;
  done: boolean;
  title: string;
  detail: string;
  to: string;
  cta: string;
}

/** Getting-started checklist for company administrators, built from real workspace counts. */
export function SetupChecklist({ realEstate }: { realEstate: boolean }) {
  const { session } = useAuth();
  const admin = session?.role === "admin";
  const q = useData<OnboardingData>("/onboarding", admin);
  if (!admin || !q.data) return null;
  const d = q.data;
  const subscribed = d.subscription?.effective_status === "active";
  const steps: Step[] = [
    {
      key: "profile",
      done: d.profile.filled === d.profile.total,
      title: "Complete your company profile",
      detail:
        d.profile.filled === d.profile.total
          ? "All company details are recorded."
          : `${d.profile.filled} of ${d.profile.total} details added. Missing: ${missingProfileText(d.profile.missing)}.`,
      to: "/app/settings",
      cta: "Edit profile",
    },
    {
      key: "telecaller",
      done: d.telecallers > 0,
      title: "Add a telecaller",
      detail:
        d.telecallers > 0
          ? `${d.telecallers} active telecaller${d.telecallers === 1 ? "" : "s"} can receive leads.`
          : "Telecallers receive distributed leads and sync calls from the Android app.",
      to: "/app/team",
      cta: "Add team member",
    },
    ...(realEstate
      ? [
          {
            key: "property",
            done: d.properties > 0,
            title: "Add your first property",
            detail:
              d.properties > 0
                ? `${d.properties} propert${d.properties === 1 ? "y" : "ies"} in your portfolio.`
                : "Listings let your team match buyers and schedule site visits.",
            to: "/app/properties",
            cta: "Add property",
          },
        ]
      : []),
    {
      key: "leads",
      done: d.leads > 0,
      title: "Add or import leads",
      detail:
        d.leads > 0
          ? `${d.leads} lead${d.leads === 1 ? "" : "s"} in your workspace.`
          : "Add enquiries one by one or import a spreadsheet.",
      to: "/app/leads",
      cta: "Go to leads",
    },
    {
      key: "capture",
      done: d.capture,
      title: "Start capturing enquiries",
      detail: d.capture
        ? "New enquiries arrive automatically and alert your team."
        : "Turn on your enquiry form link or connect your website or Google Ads.",
      to: "/app/integrations",
      cta: "Set up lead capture",
    },
    {
      key: "plan",
      done: subscribed,
      title: "Choose a subscription plan",
      detail: subscribed
        ? `${d.subscription?.plan_name} is active until ${d.subscription?.ends_on}.`
        : d.payments.ready
          ? "Pick a plan before your trial ends."
          : "Paid plans are being set up by your ViaCRM provider.",
      to: "/app/billing",
      cta: "View plans",
    },
  ];
  const complete = steps.filter((step) => step.done).length;
  if (complete === steps.length)
    return <TrialNotice subscription={d.subscription} payments={d.payments} />;
  return (
    <section
      className="panel crm-setup-checklist"
      aria-labelledby="setup-checklist-title"
    >
      <div className="panel-heading">
        <div>
          <h2 id="setup-checklist-title">Get your workspace ready</h2>
          <p>
            {complete} of {steps.length} steps complete. Each step updates
            automatically as your team works.
          </p>
        </div>
        <span
          className="crm-setup-meter"
          role="progressbar"
          aria-label="Setup progress"
          aria-valuemin={0}
          aria-valuemax={steps.length}
          aria-valuenow={complete}
        >
          <i style={{ width: `${(complete / steps.length) * 100}%` }} />
        </span>
      </div>
      <TrialNotice subscription={d.subscription} payments={d.payments} />
      <ol className="crm-setup-steps">
        {steps.map((step) => (
          <li key={step.key} className={step.done ? "done" : ""}>
            {step.done ? (
              <CheckCircle2 size={20} aria-hidden="true" />
            ) : (
              <Circle size={20} aria-hidden="true" />
            )}
            <div>
              <strong>
                {step.title}
                <span className="visually-hidden">
                  {step.done ? " (done)" : " (to do)"}
                </span>
              </strong>
              <p>{step.detail}</p>
            </div>
            {!step.done && (
              <Link className="button secondary" to={step.to}>
                {step.cta}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

/** Explains why companies cannot pay yet and what the super admin should set up. */
export function PaymentsNotReadyNotice({
  payments,
  linkToBilling = false,
}: {
  payments: PaymentReadiness;
  linkToBilling?: boolean;
}) {
  if (payments.ready) return null;
  const missing = [
    !payments.plans && "publish at least one active subscription plan",
    !payments.upi_ready &&
      !payments.cod_ready &&
      "upload your payment QR with a payee name, or turn on cash collection",
  ].filter(Boolean);
  return (
    <div className="crm-trial-notice soon" role="status">
      <AlertTriangle size={22} aria-hidden="true" />
      <div>
        <strong>Companies can't pay you yet</strong>
        <p>To accept subscription payments, {missing.join(" and ")}.</p>
      </div>
      {linkToBilling && (
        <Link className="button secondary" to="/app/platform/billing">
          Set up payments
        </Link>
      )}
    </div>
  );
}

/** Encourages the platform owner to protect the super-admin account with an authenticator. */
export function TwoFactorNotice() {
  const { session } = useAuth();
  if (!session || session.role !== "owner" || session.user.totp_enabled)
    return null;
  return (
    <div className="crm-trial-notice security" role="status">
      <ShieldCheck size={22} aria-hidden="true" />
      <div>
        <strong>Protect your super admin account</strong>
        <p>
          This account controls every company and payment. Turn on an
          authenticator app so a password alone can't sign in.
        </p>
      </div>
      <Link className="button secondary" to="/app/security">
        Set up authenticator
      </Link>
    </div>
  );
}
