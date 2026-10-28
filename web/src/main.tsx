import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Link,
  Navigate,
  NavLink,
  Outlet,
  Route,
  Routes,
  useNavigate,
  useLocation,
} from "react-router-dom";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Building2,
  CalendarDays,
  Check,
  CheckCheck,
  ChevronRight,
  Clock3,
  Download,
  FileClock,
  FolderArchive,
  GitBranch,
  LayoutDashboard,
  Compass,
  Layers3,
  CircleUserRound,
  LogOut,
  Menu,
  Phone,
  Plus,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Target,
  Users,
  X,
  Zap,
} from "lucide-react";
import {
  ApiError,
  api,
  download,
  params,
  refreshSession,
  send,
  setSession,
} from "./api";
import type {
  Analytics,
  Directory,
  PublicConfig,
  Session,
  SavedView,
} from "./types";
import {
  Badge,
  Button,
  Empty,
  ErrorBox,
  FormDialog,
  QueryNotice,
  Load,
  MiniBar,
  PageHeading,
  Panel,
  Stat,
  Table,
  dateTime,
  duration,
  money,
} from "./ui";
import { LeadDetail, LeadsPage } from "./pages-leads";
import { FieldWorkPage } from "./pages-field";
import { DashboardPage } from "./pages-dashboard";
import { CallbackAlerts } from "./callback-alerts";
import { HourlyCallChart } from "./hourly-call-chart";
import {
  AttendancePage,
  ApprovalsPage,
  CallsPage,
  PayrollPage,
  TasksPage,
  TeamPage,
} from "./pages-work";
import {
  AuditPage,
  AutomationsPage,
  BackupsPage,
  IntegrationsPage,
  SecurityPage,
  SettingsPage,
} from "./pages-admin";
import {
  BookingsPage,
  EstateOverview,
  PropertiesPage,
  PropertyDetailPage,
  SiteVisitsPage,
} from "./pages-estate";
import {
  CompanyBillingPage,
  PaymentReviewsPage,
  PlatformBillingPage,
  SuperAdminPage,
} from "./pages-billing";
import "@fontsource/dm-sans/400.css";
import "@fontsource/dm-sans/500.css";
import "@fontsource/dm-sans/600.css";
import "@fontsource/dm-sans/700.css";
import "@fontsource/manrope/500.css";
import "@fontsource/manrope/600.css";
import "@fontsource/manrope/700.css";
import "./style.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 15000, refetchOnWindowFocus: true },
  },
});
const Auth = createContext<{
  session: Session | null;
  ready: boolean;
  error: unknown;
  retry: () => void;
}>({
  session: null,
  ready: false,
  error: null,
  retry: () => {},
});
export const useAuth = () => useContext(Auth);
export function useData<T>(path: string, enabled = true) {
  const { session } = useAuth();
  return useQuery<T, Error>({
    queryKey: [session?.organization?.id, session?.user.id, path],
    queryFn: ({ signal }) => api<T>(path, { signal }),
    enabled: enabled && !!session,
    refetchInterval: path.split("?")[0].endsWith("/history")
      ? 5000
      : ["/billing", "/platform/billing"].includes(path)
        ? 15000
        : ["/automations", "/integrations"].includes(path)
          ? 10000
          : [
                "/notifications",
                "/notifications/inbox",
                "/health",
                "/dashboard",
              ].includes(path.split("?")[0])
            ? 30000
            : false,
  });
}
export function useAction() {
  const qc = useQueryClient();
  return async <T,>(action: () => Promise<T>) => {
    const r = await action();
    void qc.invalidateQueries();
    return r;
  };
}
export function useDirectory() {
  return useData<Directory[]>("/directory");
}
export function PrivateLogo({
  id,
  alt,
  path,
}: {
  id: string;
  alt: string;
  path?: string;
}) {
  const image = useData<Blob>(path || "/files/" + id);
  const [url, setUrl] = useState("");
  useEffect(() => {
    if (!image.data) return;
    const value = URL.createObjectURL(image.data);
    setUrl(value);
    return () => URL.revokeObjectURL(value);
  }, [image.data]);
  return image.isError ? (
    <span>Logo unavailable</span>
  ) : url ? (
    <img src={url} alt={alt} />
  ) : (
    <span aria-label="Loading logo">…</span>
  );
}
function AuthProvider({ children }: { children: ReactNode }) {
  const [session, set] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<unknown>(null);
  function retry() {
    setReady(false);
    setError(null);
    void refreshSession()
      .catch((failure: unknown) => {
        if (failure instanceof ApiError && failure.status === 401)
          setSession(null);
        else setError(failure);
      })
      .finally(() => setReady(true));
  }
  const previous = useRef("");
  useEffect(() => {
    const listener = (e: Event) => {
      const s = (e as CustomEvent<Session | null>).detail;
      const key = `${s?.user.id}:${s?.organization?.id}:${s?.role}`;
      if (key !== previous.current) {
        queryClient.removeQueries({
          predicate: (query) => query.queryKey[0] !== "public",
        });
        previous.current = key;
      }
      setError(null);
      set(s);
    };
    window.addEventListener("crm-session", listener);
    retry();
    return () => window.removeEventListener("crm-session", listener);
  }, []);
  return (
    <Auth.Provider value={{ session, ready, error, retry }}>
      {children}
    </Auth.Provider>
  );
}
export function Mark({ small = false }: { small?: boolean }) {
  return (
    <span className={`brand-mark ${small ? "small" : ""}`} aria-hidden="true">
      <img src="/brand/viacrm-symbol.svg" width="40" height="40" alt="" />
    </span>
  );
}
function BrandName({ name }: { name: string }) {
  return name.toLowerCase() === "viacrm" ? (
    <span className="viacrm-wordmark">
      Via<span>CRM</span>
    </span>
  ) : (
    <>{name}</>
  );
}
function usePublicConfig() {
  return useQuery({
    queryKey: ["public"],
    queryFn: () => api<PublicConfig>("/public"),
  });
}
function PublicSite() {
  const q = usePublicConfig();
  const config = q.data;
  useEffect(() => {
    document.title = `${config?.brand || "ViaCRM"} — Every lead. A way forward.`;
  }, [config?.brand]);
  const [preview, setPreview] = useState("Pipeline");
  const [menu, setMenu] = useState(false);
  const services = [
    {
      icon: Target,
      title: "Buyers, with a clear next step",
      text: "Capture enquiries, record budget and location preferences, and find matching available properties.",
    },
    {
      icon: Phone,
      title: "A better calling workflow",
      text: "Focused queues, useful outcomes and follow-ups your team can act on.",
    },
    {
      icon: BarChart3,
      title: "Your property portfolio, connected",
      text: "Manage sale and rental inventory, project details, property photos and private brochures.",
    },
    {
      icon: CalendarDays,
      title: "Site visits that move decisions",
      text: "Schedule visits, avoid agent clashes and capture customer feedback before the next conversation.",
    },
    {
      icon: SlidersHorizontal,
      title: "Made for your business",
      text: "Shape roles, fields, categories and branding around your actual process.",
    },
    {
      icon: GitBranch,
      title: "Bookings, from reservation to close",
      text: "Keep unit availability, booking stages, agreed value and commissions connected to the customer.",
    },
  ];
  return (
    <div className="marketing">
      <nav className="public-nav">
        <Link className="brand" to="/">
          <Mark />
          <BrandName name={config?.brand || "ViaCRM"} />
        </Link>
        <button
          className="icon-button mobile-only"
          aria-label="Toggle navigation"
          onClick={() => setMenu(!menu)}
        >
          {menu ? <X /> : <Menu />}
        </button>
        <div className={menu ? "public-links open" : "public-links"}>
          <a href="#services" onClick={() => setMenu(false)}>
            What we build
          </a>
          <a href="#process" onClick={() => setMenu(false)}>
            Our process
          </a>
          <a href="#questions" onClick={() => setMenu(false)}>
            FAQs
          </a>
          <Link to="/login" className="login-link">
            Customer login <ArrowUpRight size={16} />
          </Link>
          <a className="button" href="#contact">
            Let’s talk <ArrowRight size={16} />
          </a>
        </div>
      </nav>
      <main>
        <section className="hero">
          <div className="hero-copy">
            <div className="pill">
              <span />A REAL ESTATE WORKSPACE, BUILT FOR YOUR TEAM
            </div>
            <h1>
              One workspace.
              <br />
              <em>Every opportunity.</em>
            </h1>
            <p>
              Bring buyers, properties and site visits together. A real estate
              CRM for your agency, with your identity and a clear path from
              enquiry to booking.
            </p>
            <div className="hero-actions">
              <a className="button large" href="#contact">
                Start your company workspace <ArrowUpRight size={19} />
              </a>
              <a className="text-button" href="#services">
                Explore the platform <ArrowRight size={16} />
              </a>
            </div>
            <div className="hero-note">
              <ShieldCheck size={17} />
              Your process. Your identity. Room to grow.
            </div>
          </div>
          <div className="hero-visual">
            <div className="visual-note">
              <span className="tiny-star">✦</span> THE BIG PICTURE. THE RIGHT
              NEXT MOVE.
            </div>
            <div className="preview-window">
              <div className="preview-top">
                <span className="window-dots">● ● ●</span>
                <span>
                  {(config?.brand || "ViaCRM").toUpperCase()} / WORKSPACE
                  PREVIEW
                </span>
                <span>↗</span>
              </div>
              <div className="preview-body">
                <aside>
                  <Mark small />
                  <LayoutDashboard size={18} />
                  <Users size={18} />
                  <Phone size={18} />
                  <BarChart3 size={18} />
                  <Settings2 size={18} />
                </aside>
                <div className="preview-main">
                  <div className="preview-heading">
                    <div>
                      <small>WORKSPACE / OVERVIEW</small>
                      <h3>Your day, in perspective.</h3>
                    </div>
                    <span className="preview-avatar">A</span>
                  </div>
                  <div className="preview-tabs">
                    {["Pipeline", "Team activity"].map((t) => (
                      <button
                        key={t}
                        className={preview === t ? "active" : ""}
                        onClick={() => setPreview(t)}
                      >
                        {t}
                      </button>
                    ))}
                    <span>Illustrative preview</span>
                  </div>
                  <div className="preview-stats">
                    <div>
                      <small>Active opportunities</small>
                      <strong>{preview === "Pipeline" ? "24" : "8"}</strong>
                      <span>Every next step, in view</span>
                    </div>
                    <div>
                      <small>
                        {preview === "Pipeline"
                          ? "Follow-ups today"
                          : "Tasks completed"}
                      </small>
                      <strong>{preview === "Pipeline" ? "06" : "12"}</strong>
                      <span>Keep the momentum</span>
                    </div>
                  </div>
                  <div className="preview-columns">
                    {["New enquiry", "In conversation", "Next step"].map(
                      (label, i) => (
                        <div key={label}>
                          <h4>
                            <span
                              style={{
                                background: ["#5276e8", "#bd8a45", "#318270"][
                                  i
                                ],
                              }}
                            />
                            {label}
                          </h4>
                          <div className="mini-lead">
                            <span className="mini-initial">
                              {["AC", "BL", "NS"][i]}
                            </span>
                            <strong>
                              {
                                [
                                  "Alpine & Co.",
                                  "Brightside Labs",
                                  "Northstar Studio",
                                ][i]
                              }
                            </strong>
                            <small>
                              {
                                [
                                  "Website enquiry",
                                  "Discovery scheduled",
                                  "Proposal review",
                                ][i]
                              }
                            </small>
                            <div>
                              <span>Example lead</span>
                              <ArrowUpRight size={13} />
                            </div>
                          </div>
                          {i === 0 && (
                            <div className="mini-lead ghost">
                              <span />
                              <span />
                              <span />
                            </div>
                          )}
                        </div>
                      ),
                    )}
                  </div>
                </div>
              </div>
            </div>
            <div className="floating-note">
              <span>
                <CheckCheck size={20} />
              </span>
              <div>
                <strong>Clarity is a competitive advantage.</strong>
                <small>Keep the work connected. Keep moving forward.</small>
              </div>
            </div>
          </div>
        </section>
        <div className="industry-strip">
          <span>BUILT FOR THE WAY YOU WORK</span>
          <p>Real estate agencies</p>
          <i />
          <p>Developers</p>
          <i />
          <p>Channel partners</p>
          <i />
          <p>Property consultants</p>
          <i />
          <p>Growing teams</p>
        </div>
        <section className="public-section" id="services">
          <div className="section-intro">
            <div>
              <div className="eyebrow">LESS FRICTION. MORE FOCUS.</div>
              <h2>
                Good software should
                <br />
                fit the business.
              </h2>
            </div>
            <p>
              Your processes have their own rhythm. We turn them into a
              considered, useful workspace that gives your team room to do their
              best work.
            </p>
          </div>
          <div className="service-grid">
            {services.map((s) => (
              <article key={s.title}>
                <s.icon size={25} />
                <h3>{s.title}</h3>
                <p>{s.text}</p>
              </article>
            ))}
          </div>
        </section>
        <section className="process-section" id="process">
          <div className="eyebrow">A COLLABORATIVE PROCESS</div>
          <h2>From the first enquiry to the keys.</h2>
          <div className="process-grid">
            {[
              [
                "01",
                "Capture the enquiry",
                "Bring enquiries into your company workspace and assign each customer to the right team member.",
              ],
              [
                "02",
                "Find the right fit",
                "Record the customer's confirmed budget, preferred locations and property needs. Match them with available inventory.",
              ],
              [
                "03",
                "Open the door",
                "Schedule site visits, coordinate the team and save customer feedback with the enquiry.",
              ],
              [
                "04",
                "Bring it home",
                "Record reservations and bookings. Keep availability and agreed commercial terms in one place.",
              ],
            ].map(([n, t, p]) => (
              <article key={n}>
                <span>{n}</span>
                <h3>{t}</h3>
                <p>{p}</p>
              </article>
            ))}
          </div>
        </section>
        <section className="public-section custom-section">
          <div>
            <div className="eyebrow">YOUR BUSINESS, IN THE DETAILS</div>
            <h2>
              Make it feel like
              <br />
              your own.
            </h2>
            <p>
              Start with what matters today. Agree the right features for your
              project, then shape the workspace around them.
            </p>
          </div>
          <div className="custom-tags">
            {[
              "Your branding",
              "Your lead stages",
              "Your roles & permissions",
              "Your data fields",
              "Your automations",
              "Your reports",
              "Your integrations",
            ].map((x) => (
              <span key={x}>
                <Check size={17} />
                {x}
              </span>
            ))}
          </div>
        </section>
        <section className="public-section faq-section" id="questions">
          <div>
            <div className="eyebrow">A FEW GOOD QUESTIONS</div>
            <h2>Before we begin.</h2>
          </div>
          <div>
            {[
              [
                "How does a company subscription work?",
                "Your super admin creates your company's workspace and publishes subscription plans. Choose a plan, pay using the provided QR and submit the transaction reference. The super admin verifies receipt before activating the subscription.",
              ],
              [
                "Can you tailor our existing workflow?",
                "Yes. Discovery starts with how your team works today, what needs to change and which parts should stay familiar.",
              ],
              [
                "How long does implementation take?",
                "The timeline depends on the agreed scope, integrations, data migration and review process. We define milestones in your proposal.",
              ],
              [
                "Can you connect our existing tools?",
                "We assess API access, permissions and provider constraints before including an integration in your project scope.",
              ],
              [
                "What happens after launch?",
                "We agree training, handoff, maintenance and ongoing support as part of your project.",
              ],
            ].map(([t, p]) => (
              <details key={t}>
                <summary>
                  {t}
                  <Plus size={18} />
                </summary>
                <p>{p}</p>
              </details>
            ))}
          </div>
        </section>
        <section className="contact-section" id="contact">
          <span className="eyebrow">LET’S MAKE WORK FLOW</span>
          <h2>
            Tell us how your business works.
            <br />
            We’ll take it from there.
          </h2>
          <p>A conversation is the first step towards a CRM that fits.</p>
          {q.isError ? (
            <ErrorBox error={q.error} retry={() => void q.refetch()} />
          ) : !config ? (
            <p>Loading contact information…</p>
          ) : config.contact_configured ? (
            <div className="hero-actions">
              {config.phone && (
                <a className="button light large" href={`tel:${config.phone}`}>
                  Book a discovery call <Phone size={18} />
                </a>
              )}
              {config.email && (
                <a
                  className="button outline-light large"
                  href={`mailto:${config.email}`}
                >
                  Email your requirements <ArrowUpRight size={18} />
                </a>
              )}
            </div>
          ) : (
            <div className="setup-notice">
              Contact details are being configured. Existing customers can{" "}
              <Link to="/login">sign in here</Link>.
            </div>
          )}
        </section>
      </main>
      <footer className="public-footer">
        <Link className="brand" to="/">
          <Mark />
          <BrandName name={config?.brand || "ViaCRM"} />
        </Link>
        <p>Every lead. A way forward.</p>
        <Link to="/login">
          Existing customer login <ArrowUpRight size={15} />
        </Link>
        <span>
          © {new Date().getFullYear()} {config?.brand || "ViaCRM"}
        </span>
      </footer>
    </div>
  );
}

function Login() {
  const { session, ready } = useAuth();
  const config = usePublicConfig();
  const brand = config.data?.brand || "ViaCRM";
  useEffect(() => {
    document.title = `${brand} · Sign in`;
  }, [brand]);
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [challenge, setChallenge] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  if (ready && session) return <Navigate to="/app" replace />;
  return (
    <div className="login-page">
      <div className="login-story">
        <Link className="brand" to="/">
          <Mark />
          <BrandName name={brand} />
        </Link>
        <div>
          <div className="eyebrow">WELCOME TO YOUR NEXT CHAPTER</div>
          <h1>
            Great work.
            <br />
            <span>All connected.</span>
          </h1>
          <p>
            A place for every opportunity.
            <br />A clear next move for everyone.
          </p>
          <div className="login-art" aria-hidden="true">
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <div className="orbit orbit-three" />
            <span className="orbit-center">
              <Mark />
            </span>
            <div className="orbit-label">
              <Layers3 size={19} /> One connected workspace
            </div>
          </div>
        </div>
        <small>{brand.toUpperCase()} / EVERY LEAD. A WAY FORWARD.</small>
      </div>
      <main className="login-form">
        <Link to="/" className="back-link">
          ← Back to website
        </Link>
        <div>
          <div className="eyebrow">YOUR WORKSPACE AWAITS</div>
          <h1>{challenge ? "One more step." : "Welcome back."}</h1>
          <p>
            {challenge
              ? "Enter the six-digit code from your authenticator."
              : "Sign in to pick up where you left off."}
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setBusy(true);
              setError(null);
              void send<Session>("/auth/login", {
                phone,
                password,
                ...(challenge ? { challenge, code } : {}),
              })
                .then((r) => {
                  if (r.challenge_required) {
                    setChallenge(r.challenge || "");
                  } else setSession(r);
                })
                .catch(setError)
                .finally(() => setBusy(false));
            }}
          >
            <label className="field">
              <span>Phone number</span>
              <input
                autoComplete="username"
                type="tel"
                placeholder="+91 98765 43210"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required
                disabled={!!challenge}
              />
              <small>
                Include your country code for international numbers.
              </small>
            </label>
            <label className="field">
              <span>Password</span>
              <input
                autoComplete="current-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={!!challenge}
              />
            </label>
            {challenge && (
              <label className="field">
                <span>Authenticator code</span>
                <input
                  autoFocus
                  inputMode="numeric"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  required
                  autoComplete="one-time-code"
                />
              </label>
            )}
            {error !== null && <ErrorBox error={error} />}
            <Button disabled={busy}>
              {busy
                ? "Signing in…"
                : challenge
                  ? "Verify & sign in"
                  : "Sign in to your workspace"}
              <ArrowRight size={18} />
            </Button>
            {challenge && (
              <Button
                variant="secondary"
                type="button"
                onClick={() => {
                  setChallenge("");
                  setCode("");
                }}
              >
                Use a different account
              </Button>
            )}
          </form>
          <div className="login-help">
            <ShieldCheck size={18} />
            <p>
              Accounts are provided by your administrator.
              <br />
              For access or a password reset, contact your team.
            </p>
          </div>
        </div>
        <small>Secure access · Organization-specific permissions</small>
      </main>
    </div>
  );
}

const navAreas = [
  {
    id: "home",
    label: "Home",
    icon: Compass,
    description: "Your daily perspective",
    items: [
      { path: "overview", label: "Overview", icon: LayoutDashboard },
      { path: "tasks", label: "Planner", icon: CalendarDays },
      { path: "phone-calls", label: "Conversations", icon: Phone },
    ],
  },
  {
    id: "sales",
    label: "Sales",
    icon: Layers3,
    description: "Relationships that move forward",
    items: [
      { path: "leads", label: "Leads", icon: Users },
      {
        path: "lost",
        label: "Closed opportunities",
        icon: FolderArchive,
        roles: ["admin", "manager"],
      },
    ],
  },
  {
    id: "property",
    label: "Property",
    icon: Building2,
    description: "From enquiry to the keys",
    items: [
      { path: "properties", label: "Inventory", icon: Building2 },
      { path: "site-visits", label: "Site visits", icon: CalendarDays },
      { path: "field-work", label: "Field work", icon: Users, estate: true },
      {
        path: "bookings",
        label: "Bookings",
        icon: Check,
        roles: ["admin", "manager"],
      },
    ],
  },
  {
    id: "people",
    label: "People",
    icon: Users,
    description: "A connected team",
    items: [
      { path: "attendance", label: "Attendance", icon: Clock3 },
      { path: "approvals", label: "Requests & approvals", icon: FileClock },
      {
        path: "team",
        label: "Team directory",
        icon: Users,
        roles: ["admin", "manager"],
      },
      {
        path: "payroll",
        label: "Payroll estimates",
        icon: Building2,
        roles: ["admin"],
      },
    ],
  },
  {
    id: "insights",
    label: "Insights",
    icon: BarChart3,
    description: "Decisions with perspective",
    items: [{ path: "reports", label: "Reports", icon: BarChart3 }],
  },
  {
    id: "studio",
    label: "Studio",
    icon: SlidersHorizontal,
    description: "Make the workspace yours",
    items: [
      {
        path: "automations",
        label: "Workflows",
        icon: Zap,
        roles: ["admin", "manager"],
      },
      {
        path: "integrations",
        label: "Connections",
        icon: GitBranch,
        roles: ["admin", "manager"],
      },
      {
        path: "audit",
        label: "Audit log",
        icon: Activity,
        roles: ["admin", "manager"],
      },
      {
        path: "backups",
        label: "Data snapshots",
        icon: FolderArchive,
        roles: ["admin"],
      },
      {
        path: "settings",
        label: "Workspace profile",
        icon: Settings2,
        roles: ["admin"],
      },
      {
        path: "billing",
        label: "Subscription",
        icon: Building2,
        roles: ["admin"],
      },
      { path: "security", label: "Account & security", icon: ShieldCheck },
    ],
  },
];
function Guard({ roles, children }: { roles?: string[]; children: ReactNode }) {
  const { session, ready, error, retry } = useAuth();
  if (!ready)
    return <div className="page-loading">Opening your workspace…</div>;
  if (error)
    return (
      <div className="page-loading">
        <ErrorBox error={error} retry={retry} />
      </div>
    );
  if (!session) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(session.role))
    return (
      <Empty
        title="This workspace needs a different role"
        description="Your administrator controls access to this area."
      />
    );
  return <>{children}</>;
}
function Shell() {
  const { session } = useAuth();
  const [shellError, setShellError] = useState<unknown>(null);
  const [menu, setMenu] = useState(false);
  const [search, setSearch] = useState("");
  const [returning, setReturning] = useState(false);
  const nav = useNavigate();
  const location = useLocation();
  const menuButton = useRef<HTMLButtonElement>(null);
  const rail = useRef<HTMLElement>(null);
  const menuWasOpen = useRef(false);
  const sectionNavigation = useRef<HTMLElement>(null);
  const publicConfig = usePublicConfig();
  const sessionData = useData<Session>("/auth/me");
  const s = sessionData.data || session!;
  const health = useData<{ worker: string }>("/health", s.role === "admin");
  const areas = navAreas.map((area) => ({
    ...area,
    items: area.items.filter(
      (item) =>
        (!("roles" in item) || item.roles?.includes(s.role)) &&
        (!("estate" in item) ||
          s.organization?.settings.industry === "real_estate"),
    ),
  }));
  const activeArea =
    areas.find((area) =>
      area.items.some(
        (item) =>
          location.pathname === `/app/${item.path}` ||
          location.pathname.startsWith(`/app/${item.path}/`),
      ),
    ) || areas[0];
  const brand =
    s.organization?.settings.brand_name || publicConfig.data?.brand || "ViaCRM";
  useEffect(() => {
    document.title = `${brand} · ${s.role === "owner" ? "Platform" : activeArea.label}`;
  }, [brand, s.role, activeArea.label]);
  useEffect(() => {
    window.scrollTo(0, 0);
    const revealActive = () => {
      const section = sectionNavigation.current;
      const current = section?.querySelector<HTMLElement>(
        '[aria-current="page"]',
      );
      if (!section || !current) return;
      const bounds = section.getBoundingClientRect();
      const active = current.getBoundingClientRect();
      if (active.right > bounds.right)
        section.scrollLeft += active.right - bounds.right + 12;
      else if (active.left < bounds.left)
        section.scrollLeft -= bounds.left - active.left + 12;
    };
    revealActive();
    window.addEventListener("resize", revealActive);
    return () => window.removeEventListener("resize", revealActive);
  }, [location.pathname, s.role]);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 768px)");
    const closeOnDesktop = () => {
      if (!media.matches) setMenu(false);
    };
    media.addEventListener("change", closeOnDesktop);
    return () => media.removeEventListener("change", closeOnDesktop);
  }, []);
  useEffect(() => {
    if (menu) rail.current?.querySelector<HTMLAnchorElement>("nav a")?.focus();
    else if (menuWasOpen.current) menuButton.current?.focus();
    menuWasOpen.current = menu;
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMenu(false);
      }
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [menu]);
  return (
    <div className="app-shell">
      <a className="skip-link" href="#workspace-main">
        Skip to workspace
      </a>
      {menu && (
        <button
          aria-label="Close navigation"
          className="nav-backdrop"
          onClick={() => setMenu(false)}
        />
      )}
      <aside
        id="work-areas"
        ref={rail}
        className={`workspace-rail ${menu ? "open" : ""}`}
      >
        <Link
          className="rail-brand"
          aria-label={`${brand} home`}
          to="/app"
          onClick={() => setMenu(false)}
        >
          <Mark />
        </Link>
        <button
          className="icon-button rail-close mobile-only"
          aria-label="Close work areas"
          onClick={() => {
            setMenu(false);
          }}
        >
          <X size={20} />
        </button>
        <nav aria-label="Work areas">
          {s.role === "owner" ? (
            <Link
              to="/app/platform"
              className="area-link active"
              aria-current="true"
              onClick={() => setMenu(false)}
            >
              <Building2 size={22} />
              <span>Super admin</span>
            </Link>
          ) : (
            areas.map((area) => (
              <Link
                key={area.id}
                to={`/app/${area.items[0].path}`}
                className={`area-link ${activeArea.id === area.id ? "active" : ""}`}
                aria-current={activeArea.id === area.id ? "true" : undefined}
                onClick={() => setMenu(false)}
              >
                <area.icon size={22} />
                <span>{area.label}</span>
              </Link>
            ))
          )}
        </nav>
        <div className="rail-bottom">
          <span className="rail-edition">V / 01</span>
          <Link
            className="rail-profile"
            to="/app/security"
            onClick={() => setMenu(false)}
          >
            {s.user.name
              .split(" ")
              .map((v) => v[0])
              .slice(0, 2)
              .join("")}
            <span className="visually-hidden">
              {" "}
              — Account for {s.user.name}
            </span>
          </Link>
        </div>
      </aside>
      <div className="app-body" inert={menu || undefined}>
        <header className="topbar">
          <button
            ref={menuButton}
            className="icon-button mobile-only"
            onClick={() => setMenu(true)}
            aria-label="Open navigation"
            aria-expanded={menu}
            aria-controls="work-areas"
          >
            <Menu />
          </button>
          <div className="workspace-identity">
            <span className="product-wordmark">
              <span className="product-name" title={brand}>
                <BrandName name={brand} />
              </span>
              <span>workspace</span>
            </span>
            <span className="identity-divider" />
            <span className="workspace-initial">
              {s.organization?.settings.logo_id ? (
                <PrivateLogo
                  id={s.organization.settings.logo_id}
                  alt={`${s.organization.name} logo`}
                />
              ) : (
                s.organization?.name[0] || "P"
              )}
            </span>
            <div>
              <strong>{s.organization?.name || "Platform workspace"}</strong>
              <small>
                {s.role === "owner"
                  ? "Organization management"
                  : `${s.role.replaceAll("_", " ")} access`}
              </small>
            </div>
          </div>
          {s.role !== "owner" && (
            <form
              className="command-search"
              onSubmit={(e) => {
                e.preventDefault();
                nav(`/app/leads?q=${encodeURIComponent(search)}`);
              }}
            >
              <Search size={18} />
              <input
                placeholder="Search your leads…"
                aria-label="Search leads"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <kbd>↵</kbd>
            </form>
          )}
          <div className="topbar-right">
            <span className="workspace-date">
              {new Intl.DateTimeFormat("en-IN", {
                day: "numeric",
                month: "short",
                year: "numeric",
              }).format(new Date())}
            </span>
            {s.role !== "owner" && (
              <CallbackAlerts key={`${s.organization?.id}-${s.user.id}`} />
            )}
            <Link
              className="topbar-profile"
              to="/app/security"
              aria-label={`Account for ${s.user.name}`}
            >
              <CircleUserRound size={20} />
              <span>{s.user.name.split(" ")[0]}</span>
            </Link>
            <button
              className="icon-button"
              aria-label="Sign out"
              onClick={() =>
                void api("/auth/logout", { method: "POST" })
                  .then(() => setSession(null))
                  .catch(setShellError)
              }
            >
              <LogOut size={18} />
            </button>
          </div>
        </header>
        <div className="context-bar">
          <div className="context-caption">
            <span>{s.role === "owner" ? "Platform" : activeArea.label}</span>
            <small>
              {s.role === "owner"
                ? "Companies, subscriptions and payments"
                : activeArea.description}
            </small>
          </div>
          <nav ref={sectionNavigation} aria-label="Section navigation">
            {s.role === "owner" ? (
              <>
                <NavLink to="/app/platform" end>
                  <Building2 size={15} />
                  Companies
                </NavLink>
                <NavLink to="/app/platform/billing">
                  <Settings2 size={15} />
                  Plans & payments
                </NavLink>
                <NavLink to="/app/platform/payments">
                  <ShieldCheck size={15} />
                  Payment verification
                </NavLink>
              </>
            ) : (
              activeArea.items.map((item) => (
                <NavLink key={item.path} to={`/app/${item.path}`}>
                  <item.icon size={15} />
                  {item.label}
                </NavLink>
              ))
            )}
          </nav>
        </div>
        <QueryNotice query={sessionData} />
        <QueryNotice query={health} />
        <QueryNotice query={publicConfig} />
        {shellError !== null && <ErrorBox error={shellError} />}
        {s.acting_as && (
          <div
            className="support-banner member-login-banner"
            role="region"
            aria-label="Member login"
          >
            <ShieldCheck size={18} />
            <div>
              <strong>Signed in as {s.user.name}</strong>
              <span>
                Opened by {s.acting_as.administrator.name} · Expires{" "}
                {dateTime(s.acting_as.until)}. Changes are recorded with your
                administrator identity.
              </span>
            </div>
            <button
              disabled={returning}
              onClick={() => {
                setReturning(true);
                setShellError(null);
                void api<Session>("/auth/login-as/exit", { method: "POST" })
                  .then((restored) => {
                    setSession(restored);
                    nav(
                      restored.role === "owner" ? "/app/platform" : "/app/team",
                    );
                  })
                  .catch(setShellError)
                  .finally(() => setReturning(false));
              }}
            >
              {returning ? "Returning…" : "Return to my account"}
            </button>
          </div>
        )}
        {s.support && !s.acting_as && (
          <div className="support-banner">
            <ShieldCheck size={17} />
            <span>
              Support access · {s.organization?.name} · expires{" "}
              {dateTime(s.support_until)}
            </span>
            <button
              onClick={() =>
                void api<Session>("/auth/support/exit", {
                  method: "POST",
                }).then((s) => {
                  setSession(s);
                  nav("/app/platform");
                })
              }
            >
              Exit support
            </button>
          </div>
        )}
        {health.data?.worker === "offline" && (
          <div className="worker-banner">
            Background worker is offline. Scheduled actions will catch up when
            it restarts.
          </div>
        )}
        {!navigator.onLine && (
          <div className="worker-banner">
            You’re offline. Reconnect to save changes.
          </div>
        )}
        <main id="workspace-main" className="workspace-main">
          <Outlet />
        </main>
        <footer className="app-footer">
          <span>
            <Mark small />
            Every lead. A way forward.
          </span>
          <span>
            {brand} ·{" "}
            {s.organization?.settings.workplace?.timezone || "Asia/Kolkata"}
          </span>
        </footer>
      </div>
    </div>
  );
}
function AppIndex() {
  const { session } = useAuth();
  return (
    <Navigate
      replace
      to={
        session?.role === "owner"
          ? "/app/platform"
          : session?.role === "field_executive"
            ? "/app/field-work"
            : "/app/overview"
      }
    />
  );
}
function sourceGradient(sources: Record<string, number>) {
  const colors = ["#3158d9", "#738be1", "#dbad65", "#358977", "#8f80be"];
  const total = Object.values(sources).reduce((a, b) => a + b, 0);
  let percent = 0;
  return total
    ? "conic-gradient(" +
        Object.values(sources)
          .map((value, i) => {
            const start = percent;
            percent += (value / total) * 100;
            return `${colors[i % colors.length]} ${start}% ${percent}%`;
          })
          .join(",") +
        ")"
    : "#e6e9ef";
}
function Overview({ report = false }: { report?: boolean }) {
  const { session } = useAuth();
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [owner, setOwner] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [save, setSave] = useState(false);
  const saved = useData<SavedView[]>("/saved-views");
  const action = useAction();
  const filter = {
    from_date: from ? new Date(from + "T00:00:00").toISOString() : undefined,
    to_date: to ? new Date(to + "T00:00:00").toISOString() : undefined,
    owner_id: owner,
  };
  const path = "/analytics?" + params(filter);
  const q = useData<Analytics>(path);
  const directory = useDirectory();
  return (
    <>
      <PageHeading
        eyebrow={
          report
            ? "INSIGHT INTO EVERY NEXT STEP"
            : `WELCOME BACK, ${session?.user.name.split(" ")[0].toUpperCase()}`
        }
        title={
          report ? "Reports & insights" : "Your real estate business, in focus."
        }
        description={
          report
            ? "A clearer view of your pipeline, activity and outcomes."
            : "Your buyers, properties and the next steps that move a deal forward."
        }
        actions={
          <>
            {report ? (
              <Button
                variant="secondary"
                onClick={() =>
                  void download(path + "&export=true", "analytics.csv").catch(
                    setError,
                  )
                }
              >
                <Download size={16} />
                Export report
              </Button>
            ) : (
              <Link className="button" to="/app/leads?create=1">
                <Plus size={17} />
                Add a lead
              </Link>
            )}
          </>
        }
      />
      <div className="filter-row">
        <label>
          From{" "}
          <input
            type="date"
            aria-label="Report from date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </label>
        <label>
          Until (exclusive){" "}
          <input
            type="date"
            aria-label="Report end date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </label>
        {!["telecaller", "field_executive"].includes(session?.role || "") && (
          <select
            aria-label="Report employee"
            value={owner}
            onChange={(e) => setOwner(e.target.value)}
          >
            <option value="">Entire team</option>
            {directory.data?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </select>
        )}
        <span className="filter-note">
          {!from && !to ? "Last 30 days" : "Selected period"} ·{" "}
          {q.data?.timezone || "Workplace timezone"}
        </span>
      </div>
      {report && (
        <div className="saved-views report-views">
          <span>SAVED REPORTS</span>
          {saved.data
            ?.filter((v) => v.kind === "analytics")
            .map((v) => (
              <span className="view-chip" key={v.id}>
                <button
                  onClick={() => {
                    setFrom(v.filters.from_date || "");
                    setTo(v.filters.to_date || "");
                    setOwner(v.filters.owner_id || "");
                  }}
                >
                  {v.name}
                </button>
                <button
                  aria-label={`Remove report ${v.name}`}
                  onClick={() =>
                    void action(() =>
                      api(`/saved-views/${v.id}`, { method: "DELETE" }),
                    ).catch(setError)
                  }
                >
                  <X size={12} />
                </button>
              </span>
            ))}
          <button className="text-button" onClick={() => setSave(true)}>
            + Save current report
          </button>
        </div>
      )}
      <QueryNotice query={directory} />
      <QueryNotice query={saved} />
      {!report && <EstateOverview />}
      {error !== null && <ErrorBox error={error} />}
      <Load query={q}>
        {(data) => (
          <>
            {!report && (
              <section className="focus-hub" aria-label="Workspace shortcuts">
                <div className="focus-hub-copy">
                  <span className="eyebrow">THE NEXT MOVE</span>
                  <h2>
                    Make room for
                    <br />
                    your next opportunity.
                  </h2>
                  <p>
                    {data.metrics.overdue
                      ? `${data.metrics.overdue} callbacks are overdue. Give the right conversations your attention.`
                      : "A clear view of what matters. Start with your customers or plan the day ahead."}
                  </p>
                  <Link
                    to={
                      data.metrics.overdue
                        ? "/app/leads?callback=overdue"
                        : "/app/leads"
                    }
                  >
                    Open your sales workspace <ArrowUpRight size={18} />
                  </Link>
                </div>
                <div className="focus-shortcuts">
                  <Link to="/app/tasks">
                    <span>
                      <CalendarDays size={21} />
                    </span>
                    <div>
                      <strong>Plan the day</strong>
                      <small>Tasks, priorities & calendar</small>
                    </div>
                    <ArrowUpRight size={17} />
                  </Link>
                  <Link to="/app/phone-calls">
                    <span>
                      <Phone size={21} />
                    </span>
                    <div>
                      <strong>Keep the conversation going</strong>
                      <small>Call activity & customer context</small>
                    </div>
                    <ArrowUpRight size={17} />
                  </Link>
                  <Link to="/app/reports">
                    <span>
                      <BarChart3 size={21} />
                    </span>
                    <div>
                      <strong>See the bigger picture</strong>
                      <small>Performance & team insights</small>
                    </div>
                    <ArrowUpRight size={17} />
                  </Link>
                </div>
              </section>
            )}
            <div className="stats-grid">
              <Stat
                label="Total leads"
                value={data.metrics.leads.toLocaleString()}
                detail={`${data.metrics.leads - data.metrics.prior_leads >= 0 ? "+" : ""}${data.metrics.leads - data.metrics.prior_leads} vs. previous period`}
                icon={<Users size={19} />}
                accent
              />
              <Stat
                label="Converted leads"
                value={data.metrics.converted}
                detail={`${data.metrics.conversion_rate}% of leads in this period`}
                icon={<Target size={19} />}
              />
              <Stat
                label="Recorded calls"
                value={data.metrics.calls}
                detail={`${Math.round(data.metrics.observed_seconds / 60)} device-observed minutes`}
                icon={<Phone size={19} />}
              />
              <Stat
                label="Order value"
                value={money(data.metrics.order_value)}
                detail={`Average order ${money(data.metrics.average_order_value)}`}
                icon={<ArrowUpRight size={19} />}
              />
            </div>
            <div className="attention-strip">
              <span className="attention-icon">
                <Clock3 size={20} />
              </span>
              <div>
                <strong>Your next conversations are waiting.</strong>
                <span>
                  {data.metrics.overdue} overdue callbacks ·{" "}
                  {data.metrics.upcoming} upcoming · {data.metrics.stale} need
                  first contact
                </span>
              </div>
              <Link to="/app/leads?callback=overdue">
                Open follow-ups <ArrowRight size={16} />
              </Link>
            </div>
            <div className="dashboard-grid">
              <Panel
                title="Pipeline snapshot"
                description="Lead status, for the selected creation period"
                action={
                  <Link className="text-button" to="/app/leads">
                    View leads <ChevronRight size={15} />
                  </Link>
                }
              >
                <div className="pipeline-summary">
                  <strong>{data.metrics.leads}</strong>
                  <span>leads in your pipeline</span>
                  <span className="badge neutral">
                    {data.metrics.unassigned} unassigned
                  </span>
                </div>
                {data.metrics.leads ? (
                  <MiniBar items={data.statuses} total={data.metrics.leads} />
                ) : (
                  <Empty
                    title="Your pipeline starts here"
                    description="Add your first lead to see its progress."
                  />
                )}
              </Panel>
              <Panel
                title="Where opportunities begin"
                description="Lead sources in this period"
              >
                <div className="source-ring">
                  <div
                    className="ring"
                    style={{ background: sourceGradient(data.sources) }}
                  >
                    <div>
                      <strong>{Object.keys(data.sources).length}</strong>
                      <small>sources</small>
                    </div>
                  </div>
                  <div className="source-legend">
                    {Object.entries(data.sources).map(([key, value], i) => (
                      <div key={key}>
                        <i
                          style={{
                            background: [
                              "#3158d9",
                              "#738be1",
                              "#dbad65",
                              "#358977",
                            ][i % 4],
                          }}
                        />
                        <span>{key}</span>
                        <strong>{value}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              </Panel>
              <Panel
                className="wide-panel"
                title={report ? "Hourly call activity" : "Recent opportunities"}
                description={
                  report
                    ? "Number of calls in each hour across the selected dates."
                    : "A few of the newest additions to your workspace."
                }
                action={
                  <Link
                    className="text-button"
                    to={report ? "/app/phone-calls" : "/app/leads"}
                  >
                    View all <ArrowRight size={15} />
                  </Link>
                }
              >
                {report ? (
                  <HourlyCallChart
                    items={data.hourly}
                    timezone={data.timezone}
                  />
                ) : data.latest.length ? (
                  <Table headers={["Lead", "Source", "Status", "Owner", ""]}>
                    {data.latest.map((l) => (
                      <tr key={l.id}>
                        <td>
                          <Link className="name-cell" to={`/app/leads/${l.id}`}>
                            <span className="lead-avatar">
                              {l.name.slice(0, 2).toUpperCase()}
                            </span>
                            <span>
                              <strong>{l.name}</strong>
                              <small>{l.city || "Location not added"}</small>
                            </span>
                          </Link>
                        </td>
                        <td>{l.source}</td>
                        <td>
                          <Badge value={l.status} />
                        </td>
                        <td>{l.owner_name}</td>
                        <td>
                          <Link
                            aria-label={`Open ${l.name}`}
                            className="row-arrow"
                            to={`/app/leads/${l.id}`}
                          >
                            <ArrowUpRight size={17} />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </Table>
                ) : (
                  <Empty title="No leads in this period" />
                )}
              </Panel>
            </div>
            {report && (
              <>
                <div className="stats-grid">
                  <Stat
                    label="Talk time"
                    value={`${Math.round(data.metrics.talk_seconds / 60)} min`}
                    detail={`${Math.round(data.metrics.declared_seconds / 60)} declared · ${Math.round(data.metrics.observed_seconds / 60)} observed`}
                  />
                  <Stat
                    label="Average call"
                    value={duration(data.metrics.average_call_seconds)}
                    detail="Across counted calls"
                  />
                  <Stat
                    label="Not answered"
                    value={`${data.metrics.missed_rate}%`}
                    detail="Missed, rejected and not picked"
                  />
                  <Stat
                    label="Assigned leads"
                    value={data.metrics.assigned}
                    detail={`${data.metrics.unassigned} currently unassigned`}
                  />
                </div>
                <div className="dashboard-grid">
                  <Panel title="Team activity">
                    <Table
                      label="Team activity; scroll sideways for more columns"
                      headers={[
                        "Team member",
                        "Calls",
                        "Minutes",
                        "Order value",
                      ]}
                    >
                      {data.leaderboard.map((r) => (
                        <tr key={r.user_id}>
                          <td>{r.name}</td>
                          <td>{r.calls}</td>
                          <td>{r.minutes}</td>
                          <td>{money(r.order_value)}</td>
                        </tr>
                      ))}
                    </Table>
                    {!data.leaderboard.length && (
                      <Empty title="No calls in this period" />
                    )}
                  </Panel>
                  <Panel title="City performance">
                    <Table
                      label="City performance; scroll sideways for more columns"
                      headers={["City", "Leads", "Converted", "Order value"]}
                    >
                      {data.cities.map((r) => (
                        <tr key={r.city}>
                          <td>{r.city}</td>
                          <td>{r.leads}</td>
                          <td>{r.converted}</td>
                          <td>{money(r.order_value)}</td>
                        </tr>
                      ))}
                    </Table>
                  </Panel>
                </div>
                <p className="metric-definition">{data.definitions}</p>
              </>
            )}
          </>
        )}
      </Load>
      {save && (
        <FormDialog
          title="Save this report"
          fields={[{ name: "name", label: "Report name", required: true }]}
          onClose={() => setSave(false)}
          onSubmit={(v) =>
            action(() =>
              send("/saved-views", {
                name: v.name,
                kind: "analytics",
                filters: { from_date: from, to_date: to, owner_id: owner },
              }),
            )
          }
        />
      )}
    </>
  );
}
function NotFound() {
  return (
    <Empty
      title="This page isn’t here"
      description="Use the workspace navigation to continue."
      action={
        <Link className="button" to="/app">
          Open workspace
        </Link>
      }
    />
  );
}
function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<PublicSite />} />
            <Route path="/login" element={<Login />} />
            <Route
              path="/app"
              element={
                <Guard>
                  <Shell />
                </Guard>
              }
            >
              <Route index element={<AppIndex />} />
              <Route
                path="overview"
                element={
                  <Guard
                    roles={[
                      "admin",
                      "manager",
                      "telecaller",
                      "field_executive",
                    ]}
                  >
                    <DashboardPage />
                  </Guard>
                }
              />
              <Route
                path="leads"
                element={
                  <Guard
                    roles={[
                      "admin",
                      "manager",
                      "telecaller",
                      "field_executive",
                    ]}
                  >
                    <LeadsPage />
                  </Guard>
                }
              />
              <Route path="leads/:id" element={<LeadDetail />} />
              <Route
                path="lost"
                element={
                  <Guard roles={["admin", "manager"]}>
                    <LeadsPage lost />
                  </Guard>
                }
              />
              <Route path="tasks" element={<TasksPage />} />
              <Route
                path="field-work"
                element={
                  <Guard
                    roles={[
                      "admin",
                      "manager",
                      "telecaller",
                      "field_executive",
                    ]}
                  >
                    <FieldWorkPage />
                  </Guard>
                }
              />
              <Route path="phone-calls" element={<CallsPage />} />
              <Route
                path="properties"
                element={
                  <Guard
                    roles={[
                      "admin",
                      "manager",
                      "telecaller",
                      "field_executive",
                    ]}
                  >
                    <PropertiesPage />
                  </Guard>
                }
              />
              <Route
                path="properties/:id"
                element={
                  <Guard
                    roles={[
                      "admin",
                      "manager",
                      "telecaller",
                      "field_executive",
                    ]}
                  >
                    <PropertyDetailPage />
                  </Guard>
                }
              />
              <Route
                path="site-visits"
                element={
                  <Guard
                    roles={[
                      "admin",
                      "manager",
                      "telecaller",
                      "field_executive",
                    ]}
                  >
                    <SiteVisitsPage />
                  </Guard>
                }
              />
              <Route
                path="bookings"
                element={
                  <Guard roles={["admin", "manager"]}>
                    <BookingsPage />
                  </Guard>
                }
              />
              <Route
                path="billing"
                element={
                  <Guard roles={["admin"]}>
                    <CompanyBillingPage />
                  </Guard>
                }
              />
              <Route path="reports" element={<Overview report />} />
              <Route path="attendance" element={<AttendancePage />} />
              <Route path="approvals" element={<ApprovalsPage />} />
              <Route
                path="team"
                element={
                  <Guard roles={["admin", "manager"]}>
                    <TeamPage />
                  </Guard>
                }
              />
              <Route
                path="payroll"
                element={
                  <Guard roles={["admin"]}>
                    <PayrollPage />
                  </Guard>
                }
              />
              <Route
                path="settings"
                element={
                  <Guard roles={["admin"]}>
                    <SettingsPage />
                  </Guard>
                }
              />
              <Route
                path="integrations"
                element={
                  <Guard roles={["admin", "manager"]}>
                    <IntegrationsPage />
                  </Guard>
                }
              />
              <Route
                path="automations"
                element={
                  <Guard roles={["admin", "manager"]}>
                    <AutomationsPage />
                  </Guard>
                }
              />
              <Route
                path="audit"
                element={
                  <Guard roles={["admin", "manager"]}>
                    <AuditPage />
                  </Guard>
                }
              />
              <Route
                path="backups"
                element={
                  <Guard roles={["admin"]}>
                    <BackupsPage />
                  </Guard>
                }
              />
              <Route path="security" element={<SecurityPage />} />
              <Route
                path="platform"
                element={
                  <Guard roles={["owner"]}>
                    <SuperAdminPage />
                  </Guard>
                }
              />
              <Route
                path="platform/billing"
                element={
                  <Guard roles={["owner"]}>
                    <PlatformBillingPage />
                  </Guard>
                }
              />
              <Route
                path="platform/payments"
                element={
                  <Guard roles={["owner"]}>
                    <PaymentReviewsPage />
                  </Guard>
                }
              />
              <Route path="*" element={<NotFound />} />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
