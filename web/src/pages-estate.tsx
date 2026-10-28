import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  Bath,
  BedDouble,
  Building2,
  CalendarDays,
  Download,
  MapPin,
  Plus,
  Ruler,
  Search,
  Upload,
} from "lucide-react";
import { api, download, params, send } from "./api";
import { PrivateLogo, useAction, useAuth, useData, useDirectory } from "./main";
import { LeadPicker } from "./pages-leads";
import type { Property, Requirement, Visit, Booking } from "./estate-types";
import {
  Badge,
  Button,
  Dialog,
  Empty,
  ErrorBox,
  Fields,
  FormDialog,
  Load,
  PageHeading,
  Panel,
  QueryNotice,
  Stat,
  Table,
  dateTime,
  money,
  options,
  type Field,
  type Values,
} from "./ui";

export const propertyTypes = [
  "apartment",
  "villa",
  "plot",
  "office",
  "retail",
  "warehouse",
  "other",
];
const hasBedrooms = (type: string) => ["apartment", "villa"].includes(type);
const hasBathrooms = (type: string) => type !== "plot";
const possessionLabel = (type: string, listing: string) =>
  listing === "rent"
    ? "Available from"
    : type === "plot"
      ? "Plot handover"
      : "Possession / handover";
const split = (value: string | boolean | undefined) =>
  String(value || "")
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
const initialValues = (data: object): Values =>
  Object.fromEntries(
    Object.entries(data).map(([k, v]) => [
      k,
      v == null
        ? ""
        : Array.isArray(v)
          ? v.join(", ")
          : typeof v === "boolean"
            ? v
            : String(v),
    ]),
  );
const localTime = (iso: string) => {
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
};

export function PropertyPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const [search, setSearch] = useState("");
  const q = useData<{ items: Property[] }>(
    "/properties?" + params({ q: search, status: "available" }),
  );
  const chosen = useData<Property>("/properties/" + value, !!value);
  const items = q.data?.items || [];
  return (
    <label className="field">
      <span>Property *</span>
      <input
        aria-label="Search available properties"
        placeholder="Search property, reference or project"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <QueryNotice query={q} />
      <select
        aria-label="Property"
        required
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">Choose a property</option>
        {value && !items.some((p) => p.id === value) && (
          <option value={value}>
            {chosen.data
              ? `${chosen.data.reference} · ${chosen.data.title}`
              : chosen.isPending
                ? "Loading selected property…"
                : "Selected property unavailable — choose another"}
          </option>
        )}
        {items.map((p) => (
          <option key={p.id} value={p.id}>
            {p.reference} · {p.title}
          </option>
        ))}
      </select>
      <small>
        Search to find more inventory. Only available properties can be reserved
        or scheduled.
      </small>
    </label>
  );
}

function PropertyCard({ property: p }: { property: Property }) {
  const photo = p.files.find((f) => f.mime.startsWith("image/"));
  return (
    <article className="estate-card">
      <Link
        to={"/app/properties/" + p.id}
        className={"property-photo " + (photo ? "" : "property-placeholder")}
        aria-label={"View " + p.title}
      >
        {photo ? (
          <PrivateLogo id={photo.id} alt={p.title} />
        ) : (
          <>
            <Building2 size={42} strokeWidth={1} />
            <span>{p.project || p.property_type}</span>
          </>
        )}
        <span className="property-reference">{p.reference}</span>
      </Link>
      <div className="estate-card-body">
        <div className="estate-line">
          <Badge value={p.status} />
          <small>{p.listing_type === "rent" ? "FOR RENT" : "FOR SALE"}</small>
        </div>
        <h3>
          <Link to={"/app/properties/" + p.id}>{p.title}</Link>
        </h3>
        <p className="estate-location">
          <MapPin size={14} />
          {[p.locality, p.city].filter(Boolean).join(", ")}
        </p>
        <div className="estate-specs">
          {hasBedrooms(p.property_type) && p.bedrooms !== null && (
            <span>
              <BedDouble size={15} />
              {p.bedrooms} beds
            </span>
          )}
          <span>
            <Ruler size={15} />
            {Number(p.area_sqft).toLocaleString("en-IN")} sq ft
          </span>
        </div>
        <div className="estate-price">
          <strong>{money(p.price)}</strong>
          {p.listing_type === "rent" && <small>/ month</small>}
          <Link to={"/app/properties/" + p.id} aria-label={"Open " + p.title}>
            <ArrowRight size={20} />
          </Link>
        </div>
      </div>
    </article>
  );
}

const propertyFields: Field[] = [
  {
    name: "property_type",
    label: "Property type",
    options: options(propertyTypes),
    required: true,
    defaultValue: "apartment",
  },
  {
    name: "listing_type",
    label: "Listing type",
    options: options(["sale", "rent"]),
    required: true,
    defaultValue: "sale",
  },
  { name: "title", label: "Property title", required: true, maxLength: 180 },
  {
    name: "reference",
    label: "Inventory reference",
    required: true,
    hint: "Unique unit code, e.g. ORCHARD-A1204",
    maxLength: 60,
  },
  { name: "city", label: "City", required: true, maxLength: 100 },
  { name: "locality", label: "Locality", maxLength: 120 },
  { name: "address", label: "Property address", wide: true, maxLength: 500 },
  {
    name: "price",
    label: "Asking price (₹)",
    type: "number",
    min: "0.01",
    step: "0.01",
    required: true,
  },
  {
    name: "area_sqft",
    label: "Area (sq ft)",
    type: "number",
    min: "0.01",
    step: "0.01",
    required: true,
  },
  {
    name: "bedrooms",
    label: "Bedrooms",
    type: "number",
    min: "0",
    max: "50",
    step: "1",
  },
  {
    name: "bathrooms",
    label: "Bathrooms",
    type: "number",
    min: "0",
    max: "50",
    step: "1",
  },
  {
    name: "possession",
    label: "Possession / handover",
    hint: "For example: Ready to move or December 2027",
    maxLength: 80,
  },
  {
    name: "amenities",
    label: "Amenities",
    hint: "Separate with commas, e.g. Parking, Lift, Security",
    wide: true,
  },
  {
    name: "status",
    label: "Availability",
    options: options(["available", "off-market"]),
    required: true,
    defaultValue: "available",
  },
  {
    name: "description",
    label: "Description",
    type: "textarea",
    wide: true,
    maxLength: 10000,
  },
];
const projectFields: Field[] = [
  { name: "project", label: "Project / building", maxLength: 160 },
  { name: "developer", label: "Developer / owner", maxLength: 160 },
  {
    name: "rera_number",
    label: "Project RERA number",
    hint: "Optional. Enter only if you have a project registration reference.",
    maxLength: 100,
  },
];
const amenityHints: Record<string, string> = {
  apartment: "Parking, Lift, Security",
  villa: "Private garden, Terrace, Parking",
  plot: "Road access, Boundary wall, Corner plot",
  office: "Meeting room, Power backup, Parking",
  retail: "Street frontage, Ground floor, Storage",
  warehouse: "Loading area, Truck access, Power connection",
  other: "Parking, Security",
};

function PropertyForm({
  item,
  close,
}: {
  item: Property | true;
  close: () => void;
}) {
  const action = useAction();
  const [values, setValues] = useState<Values>(() => {
    const initial = item === true ? {} : initialValues(item);
    return Object.fromEntries(
      [...propertyFields, ...projectFields].map((f) => [
        f.name,
        initial[f.name] ?? f.defaultValue ?? "",
      ]),
    );
  });
  const [projectOpen, setProjectOpen] = useState(
    item !== true && !!(item.project || item.developer || item.rera_number),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const type = String(values.property_type),
    listing = String(values.listing_type);
  const fields = propertyFields
    .filter((f) =>
      f.name === "bedrooms"
        ? hasBedrooms(type)
        : f.name !== "bathrooms" || hasBathrooms(type),
    )
    .map((f) => {
      if (f.name === "bathrooms" && !hasBedrooms(type))
        return { ...f, label: "Washrooms" };
      if (f.name === "price")
        return {
          ...f,
          label: listing === "rent" ? "Monthly rent (₹)" : "Asking price (₹)",
        };
      if (f.name === "area_sqft" && type === "plot")
        return { ...f, label: "Plot area (sq ft)" };
      if (f.name === "possession")
        return {
          ...f,
          label: possessionLabel(type, listing),
          hint:
            listing === "rent"
              ? "For example: Immediately or December 2027"
              : type === "plot"
                ? "For example: Ready for possession or December 2027"
                : f.hint,
        };
      if (f.name === "amenities")
        return {
          ...f,
          hint: "Separate with commas, e.g. " + amenityHints[type],
        };
      return f;
    });
  const set = (name: string, value: string | boolean) =>
    setValues((previous) => ({
      ...previous,
      [name]: value,
      ...(name === "property_type"
        ? {
            bedrooms: hasBedrooms(String(value)) ? previous.bedrooms : "",
            bathrooms: hasBathrooms(String(value)) ? previous.bathrooms : "",
          }
        : {}),
    }));
  return (
    <Dialog
      title={item === true ? "Add a property" : "Edit property"}
      description="Choose the property and listing type first. The details below will adjust to your selection."
      onClose={() => {
        if (!busy) close();
      }}
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (busy) return;
          setBusy(true);
          setError(null);
          try {
            await action(() =>
              send(
                item === true ? "/properties" : "/properties/" + item.id,
                {
                  ...values,
                  amenities: split(values.amenities),
                  bedrooms:
                    hasBedrooms(type) && values.bedrooms !== ""
                      ? Number(values.bedrooms)
                      : null,
                  bathrooms:
                    hasBathrooms(type) && values.bathrooms !== ""
                      ? Number(values.bathrooms)
                      : null,
                },
                item === true ? "POST" : "PUT",
              ),
            );
            close();
          } catch (e) {
            setError(e);
          } finally {
            setBusy(false);
          }
        }}
      >
        <fieldset
          className="dialog-content property-form-fields"
          disabled={busy}
        >
          <Fields fields={fields} values={values} set={set} />
          <details
            className="property-project-fields"
            open={projectOpen}
            onToggle={(e) => setProjectOpen(e.currentTarget.open)}
          >
            <summary>Project / owner details (optional)</summary>
            <p>Add a building, owner or project reference when relevant.</p>
            <Fields fields={projectFields} values={values} set={set} />
          </details>
        </fieldset>
        {error !== null && <ErrorBox error={error} />}
        <footer>
          <Button
            type="button"
            variant="secondary"
            disabled={busy}
            onClick={close}
          >
            Cancel
          </Button>
          <Button disabled={busy}>{busy ? "Saving…" : "Save property"}</Button>
        </footer>
      </form>
    </Dialog>
  );
}

export function PropertiesPage() {
  const { session } = useAuth();
  const [f, setF] = useState<Record<string, string>>({});
  const [page, setPage] = useState(1),
    [adding, setAdding] = useState(false);
  const q = useData<{ items: Property[]; total: number }>(
    "/properties?" + params({ ...f, page }),
  );
  const filter = (k: string, v: string) => {
    setF((old) => ({ ...old, [k]: v }));
    setPage(1);
  };
  return (
    <>
      <PageHeading
        eyebrow="YOUR PROPERTY PORTFOLIO"
        title="A place for every possibility."
        description="Keep sale and rental inventory, project details and brochures in one place."
        actions={
          !["telecaller", "field_executive"].includes(session?.role || "") && (
            <Button onClick={() => setAdding(true)}>
              <Plus size={17} />
              Add property
            </Button>
          )
        }
      />
      <div className="filter-row estate-filters">
        <div className="search-field">
          <Search size={16} />
          <input
            aria-label="Search inventory"
            placeholder="Project, property or reference"
            value={f.q || ""}
            onChange={(e) => filter("q", e.target.value)}
          />
        </div>
        <select
          aria-label="Inventory availability"
          value={f.status || ""}
          onChange={(e) => filter("status", e.target.value)}
        >
          <option value="">All availability</option>
          {["available", "reserved", "sold", "leased", "off-market"].map(
            (v) => (
              <option key={v}>{v}</option>
            ),
          )}
        </select>
        <select
          aria-label="Inventory type"
          value={f.property_type || ""}
          onChange={(e) => filter("property_type", e.target.value)}
        >
          <option value="">All property types</option>
          {propertyTypes.map((v) => (
            <option key={v}>{v}</option>
          ))}
        </select>
        <select
          aria-label="Sale or rent"
          value={f.listing_type || ""}
          onChange={(e) => filter("listing_type", e.target.value)}
        >
          <option value="">Sale & rent</option>
          <option value="sale">For sale</option>
          <option value="rent">For rent</option>
        </select>
        <input
          aria-label="Inventory city"
          placeholder="City"
          value={f.city || ""}
          onChange={(e) => filter("city", e.target.value)}
        />
        <input
          aria-label="Maximum asking price"
          placeholder="Max price / rent (₹)"
          type="number"
          min="0"
          value={f.max_price || ""}
          onChange={(e) => filter("max_price", e.target.value)}
        />
      </div>
      <Load query={q}>
        {(data) =>
          data.items.length ? (
            <>
              <div className="estate-grid">
                {data.items.map((p) => (
                  <PropertyCard key={p.id} property={p} />
                ))}
              </div>
              <Pager
                total={data.total}
                page={page}
                size={24}
                setPage={setPage}
              />
            </>
          ) : (
            <Empty
              title="Your next listing starts here"
              description="Add a property or adjust your filters to find available inventory."
            />
          )
        }
      </Load>
      {adding && <PropertyForm item={true} close={() => setAdding(false)} />}
    </>
  );
}

export function PropertyDetailPage() {
  const { id } = useParams(),
    { session } = useAuth();
  const q = useData<Property>("/properties/" + id),
    action = useAction();
  const [edit, setEdit] = useState(false),
    [archive, setArchive] = useState(false),
    [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false);
  const canEdit = !["telecaller", "field_executive"].includes(
    session?.role || "",
  );
  return (
    <>
      <Link className="back-link" to="/app/properties">
        ← Property inventory
      </Link>
      <Load query={q}>
        {(p) => (
          <>
            <PageHeading
              eyebrow={
                p.reference +
                " · " +
                (p.listing_type === "rent" ? "FOR RENT" : "FOR SALE")
              }
              title={p.title}
              description={[p.project, p.locality, p.city]
                .filter(Boolean)
                .join(" · ")}
              actions={
                canEdit && (
                  <Button
                    variant="secondary"
                    disabled={["reserved", "sold", "leased"].includes(p.status)}
                    onClick={() => setEdit(true)}
                  >
                    Edit property
                  </Button>
                )
              }
            />
            {error !== null && <ErrorBox error={error} />}
            <div className="estate-detail-grid">
              <Panel className="estate-property-info">
                <div className="estate-detail-price">
                  <div>
                    <small>
                      Asking{" "}
                      {p.listing_type === "rent" ? "monthly rent" : "price"}
                    </small>
                    <h2>{money(p.price)}</h2>
                  </div>
                  <Badge value={p.status} />
                </div>
                <div className="estate-specs large">
                  <span>
                    <Ruler size={19} />
                    {Number(p.area_sqft).toLocaleString("en-IN")} sq ft
                  </span>
                  {hasBedrooms(p.property_type) && p.bedrooms !== null && (
                    <span>
                      <BedDouble size={19} />
                      {p.bedrooms} bedrooms
                    </span>
                  )}
                  {hasBathrooms(p.property_type) && p.bathrooms !== null && (
                    <span>
                      <Bath size={19} />
                      {p.bathrooms}{" "}
                      {hasBedrooms(p.property_type) ? "bathrooms" : "washrooms"}
                    </span>
                  )}
                </div>
                <dl className="detail-list">
                  <div>
                    <dt>Property type</dt>
                    <dd>{p.property_type}</dd>
                  </div>
                  <div>
                    <dt>Developer / owner</dt>
                    <dd>{p.developer || "Not recorded"}</dd>
                  </div>
                  <div>
                    <dt>{possessionLabel(p.property_type, p.listing_type)}</dt>
                    <dd>{p.possession || "Not recorded"}</dd>
                  </div>
                  {p.rera_number && (
                    <div>
                      <dt>RERA number</dt>
                      <dd>{p.rera_number}</dd>
                    </div>
                  )}
                  <div>
                    <dt>Address</dt>
                    <dd>{p.address || "Not recorded"}</dd>
                  </div>
                </dl>
                <p className="preserve-lines">
                  {p.description ||
                    "Add a description to help the sales team present this property."}
                </p>
                <div className="estate-amenities">
                  {p.amenities.map((a, i) => (
                    <span key={i}>{a}</span>
                  ))}
                </div>
                {canEdit && (
                  <Button variant="secondary" onClick={() => setArchive(true)}>
                    Archive property
                  </Button>
                )}
              </Panel>
              <Panel
                title="Photos & brochures"
                description="Private to your company workspace."
              >
                {canEdit && (
                  <label className="button secondary file-upload">
                    <Upload size={16} />
                    {busy ? "Uploading…" : "Add photo or PDF"}
                    <input
                      type="file"
                      accept="image/png,image/jpeg,image/webp,application/pdf"
                      disabled={busy}
                      className="visually-hidden"
                      aria-label="Upload property file"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        e.target.value = "";
                        if (!file) return;
                        const body = new FormData();
                        body.set("file", file);
                        setBusy(true);
                        void action(() =>
                          api("/properties/" + id + "/files", {
                            method: "POST",
                            body,
                          }),
                        )
                          .catch(setError)
                          .finally(() => setBusy(false));
                      }}
                    />
                  </label>
                )}
                <div className="property-files">
                  {p.files.map((f) => (
                    <div key={f.id} className="property-file">
                      {f.mime.startsWith("image/") && (
                        <PrivateLogo id={f.id} alt={f.name} />
                      )}
                      <span>{f.name}</span>
                      <button
                        className="text-button"
                        onClick={() =>
                          void download("/files/" + f.id, f.name).catch(
                            setError,
                          )
                        }
                      >
                        <Download size={15} />
                        Download
                      </button>
                    </div>
                  ))}
                </div>
                {!p.files.length && (
                  <Empty
                    title="No property files yet"
                    description="Add property photos, a floor plan or a PDF brochure."
                  />
                )}
              </Panel>
            </div>
            {edit && <PropertyForm item={p} close={() => setEdit(false)} />}
            {archive && (
              <FormDialog
                title="Archive this property?"
                description="Existing history is retained. Resolve active bookings and visits first."
                fields={[]}
                submitLabel="Archive property"
                onClose={() => setArchive(false)}
                onSubmit={() =>
                  action(() =>
                    api("/properties/" + p.id, { method: "DELETE" }),
                  ).then(() => {
                    window.location.assign("/app/properties");
                  })
                }
              />
            )}
          </>
        )}
      </Load>
    </>
  );
}

export function BuyerBrief({ leadId }: { leadId: string }) {
  const q = useData<Requirement | null>(`/leads/${leadId}/requirements`),
    matches = useData<{ items: Property[]; criteria_saved: boolean }>(
      `/leads/${leadId}/property-matches`,
    );
  const [editing, setEditing] = useState(false),
    [visit, setVisit] = useState<string | null>(null),
    action = useAction();
  const fields: Field[] = [
    {
      name: "purpose",
      label: "Customer intent",
      options: options(["buy", "rent", "invest"]),
      required: true,
      defaultValue: "buy",
    },
    { name: "city", label: "Preferred city", maxLength: 100 },
    {
      name: "budget_min",
      label: "Minimum budget (₹)",
      type: "number",
      min: "0",
      step: "0.01",
      required: true,
      defaultValue: "0",
    },
    {
      name: "budget_max",
      label: "Maximum budget (₹)",
      type: "number",
      min: "0",
      step: "0.01",
      hint: "Monthly budget for rentals. Leave blank if not confirmed.",
    },
    {
      name: "localities",
      label: "Preferred localities",
      hint: "Separate with commas",
    },
    {
      name: "property_types",
      label: "Property types",
      wide: true,
      render: (value, set) => (
        <fieldset className="property-type-choices">
          <legend>Property types</legend>
          {propertyTypes.map((type) => (
            <label key={type}>
              <input
                type="checkbox"
                checked={split(value).includes(type)}
                onChange={(event) =>
                  set(
                    (event.target.checked
                      ? [...split(value), type]
                      : split(value).filter((v) => v !== type)
                    ).join(", "),
                  )
                }
              />
              <span>{type}</span>
            </label>
          ))}
        </fieldset>
      ),
    },
    {
      name: "bedrooms",
      label: "Bedrooms required",
      type: "number",
      min: "0",
      max: "50",
      step: "1",
    },
    { name: "timeline", label: "Purchase / move timeline", maxLength: 100 },
    {
      name: "financing",
      label: "Financing",
      options: options([
        "undecided",
        "self-funded",
        "loan-required",
        "loan-approved",
      ]),
      required: true,
      defaultValue: "undecided",
    },
    {
      name: "notes",
      label: "Customer requirements",
      type: "textarea",
      wide: true,
      maxLength: 4000,
    },
  ];
  return (
    <div className="buyer-brief">
      <div className="estate-section-heading">
        <div>
          <h3>Property brief</h3>
          <p>
            Record what the customer tells you. Matches use these saved
            criteria.
          </p>
        </div>
        <Button variant="secondary" onClick={() => setEditing(true)}>
          {q.data ? "Edit requirements" : "Add requirements"}
        </Button>
      </div>
      <Load query={q}>
        {(r) =>
          r ? (
            <dl className="brief-grid">
              <div>
                <dt>Intent</dt>
                <dd>{r.purpose}</dd>
              </div>
              <div>
                <dt>Budget{r.purpose === "rent" ? " / month" : ""}</dt>
                <dd>
                  {money(r.budget_min)} –{" "}
                  {r.budget_max === null
                    ? "Not confirmed"
                    : money(r.budget_max)}
                </dd>
              </div>
              <div>
                <dt>Location</dt>
                <dd>
                  {[r.city, ...r.localities].filter(Boolean).join(", ") ||
                    "Not confirmed"}
                </dd>
              </div>
              <div>
                <dt>Timeline</dt>
                <dd>{r.timeline || "Not confirmed"}</dd>
              </div>
              <div>
                <dt>Financing</dt>
                <dd>{r.financing}</dd>
              </div>
              <div>
                <dt>Type / bedrooms</dt>
                <dd>
                  {r.property_types.join(", ") || "Any type"}
                  {r.bedrooms !== null ? " · " + r.bedrooms + " beds" : ""}
                </dd>
              </div>
              <div className="wide">
                <dt>Notes</dt>
                <dd>{r.notes || "No additional notes"}</dd>
              </div>
            </dl>
          ) : (
            <Empty
              title="Understand the buyer first"
              description="Save budget, preferred locations and property type to find matching inventory."
            />
          )
        }
      </Load>
      <h3 className="subheading">Matching available properties</h3>
      <Load query={matches}>
        {(m) =>
          m.items.length ? (
            <div className="match-list">
              {m.items.map((p) => (
                <article key={p.id}>
                  <div>
                    <Link className="strong" to={"/app/properties/" + p.id}>
                      {p.title}
                    </Link>
                    <small className="block muted">
                      {p.reference} · {p.locality}, {p.city} · {money(p.price)}
                    </small>
                  </div>
                  <Button variant="secondary" onClick={() => setVisit(p.id)}>
                    Schedule visit
                  </Button>
                </article>
              ))}
            </div>
          ) : (
            <p className="help-text">
              {m.criteria_saved
                ? "No available properties match all saved criteria. Review the requirements or add inventory."
                : "Add the customer's requirements to see matching properties."}
            </p>
          )
        }
      </Load>
      {editing && (
        <FormDialog
          title="Customer property requirements"
          description="Enter customer-confirmed information. Leave unconfirmed details blank."
          fields={fields}
          dependencies={[q]}
          initial={q.data ? initialValues(q.data) : {}}
          onClose={() => setEditing(false)}
          onSubmit={(v) =>
            action(() =>
              send(
                `/leads/${leadId}/requirements`,
                {
                  ...v,
                  localities: split(v.localities),
                  property_types: split(v.property_types),
                  budget_max: v.budget_max === "" ? null : v.budget_max,
                  bedrooms: v.bedrooms === "" ? null : Number(v.bedrooms),
                },
                "PUT",
              ),
            )
          }
        />
      )}
      {visit && (
        <VisitForm
          close={() => setVisit(null)}
          leadId={leadId}
          propertyId={visit}
        />
      )}
    </div>
  );
}

export function VisitForm({
  close,
  leadId = "",
  propertyId = "",
  item,
}: {
  close: () => void;
  leadId?: string;
  propertyId?: string;
  item?: Visit;
}) {
  const action = useAction(),
    dir = useDirectory(),
    { session } = useAuth();
  return (
    <FormDialog
      title={item ? "Reschedule site visit" : "Schedule a site visit"}
      submitLabel="Save site visit"
      dependencies={[dir]}
      fields={[
        {
          name: "lead_id",
          label: "Buyer",
          render: (v, set) => (
            <LeadPicker
              value={String(v || "")}
              onChange={set}
              label="Buyer enquiry"
            />
          ),
        },
        {
          name: "property_id",
          label: "Property",
          render: (v, set) => (
            <PropertyPicker value={String(v || "")} onChange={set} />
          ),
        },
        {
          name: "assignee_id",
          label: "Assigned agent",
          required: true,
          options: (dir.data || [])
            .filter(
              (u) =>
                !["telecaller", "field_executive"].includes(
                  session?.role || "",
                ) || u.id === session?.user.id,
            )
            .map((u) => ({ value: u.id, label: u.name })),
        },
        {
          name: "starts_at",
          label: "Visit date & time",
          type: "datetime-local",
          required: true,
        },
        {
          name: "duration_minutes",
          label: "Duration (minutes)",
          type: "number",
          min: "15",
          max: "480",
          step: "1",
          required: true,
          defaultValue: "60",
        },
        {
          name: "notes",
          label: "Visit instructions",
          type: "textarea",
          maxLength: 4000,
          wide: true,
        },
      ]}
      initial={
        item
          ? { ...initialValues(item), starts_at: localTime(item.starts_at) }
          : {
              lead_id: leadId,
              property_id: propertyId,
              assignee_id: session?.user.id || "",
            }
      }
      onClose={close}
      onSubmit={(v) =>
        action(() =>
          send(
            item ? "/site-visits/" + item.id : "/site-visits",
            {
              lead_id: v.lead_id,
              property_id: v.property_id,
              assignee_id: v.assignee_id,
              starts_at: new Date(String(v.starts_at)).toISOString(),
              duration_minutes: Number(v.duration_minutes),
              notes: v.notes,
            },
            item ? "PUT" : "POST",
          ),
        )
      }
    />
  );
}

export function SiteVisitsPage() {
  const [status, setStatus] = useState(""),
    [page, setPage] = useState(1),
    [edit, setEdit] = useState<Visit | true | null>(null),
    [outcome, setOutcome] = useState<Visit | null>(null);
  const q = useData<{ items: Visit[]; total: number }>(
      "/site-visits?" + params({ status, page }),
    ),
    action = useAction();
  return (
    <>
      <PageHeading
        eyebrow="FROM INTEREST TO EXPERIENCE"
        title="Open doors. Move decisions forward."
        description="Schedule property visits, avoid agent clashes and capture customer feedback."
        actions={
          <Button onClick={() => setEdit(true)}>
            <Plus size={17} />
            Schedule visit
          </Button>
        }
      />
      <div className="filter-row">
        <select
          aria-label="Visit status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All site visits</option>
          {["scheduled", "completed", "cancelled", "no-show"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </div>
      <Load query={q}>
        {(data) =>
          data.items.length ? (
            <>
              <div className="visit-list">
                {data.items.map((v) => (
                  <article className="visit-card" key={v.id}>
                    <div className="visit-date">
                      <CalendarDays size={21} />
                      <strong>
                        {new Date(v.starts_at).toLocaleDateString("en-IN", {
                          day: "numeric",
                          month: "short",
                        })}
                      </strong>
                      <small>
                        {new Date(v.starts_at).toLocaleTimeString("en-IN", {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </small>
                    </div>
                    <div className="visit-content">
                      <div className="estate-line">
                        <Link className="strong" to={"/app/leads/" + v.lead_id}>
                          {v.lead_name}
                        </Link>
                        <Badge value={v.status} />
                      </div>
                      <Link to={"/app/properties/" + v.property_id}>
                        {v.property_reference} · {v.property_title}
                      </Link>
                      <p>
                        {v.assignee_name} · {v.duration_minutes} minutes
                      </p>
                      {v.actual_started_at && (
                        <p>Client attended: {dateTime(v.actual_started_at)}</p>
                      )}
                      {v.notes && <p className="muted">{v.notes}</p>}
                      {v.feedback && (
                        <p className="visit-feedback">{v.feedback}</p>
                      )}
                    </div>
                    {v.field_handoff_id ? (
                      <Link
                        className="button secondary"
                        to={"/app/leads/" + v.lead_id}
                      >
                        Open field handoff
                      </Link>
                    ) : (
                      v.status === "scheduled" && (
                        <div className="visit-actions">
                          <Button
                            variant="secondary"
                            onClick={() => setEdit(v)}
                          >
                            Reschedule
                          </Button>
                          <Button
                            variant="secondary"
                            onClick={() => setOutcome(v)}
                          >
                            Record outcome
                          </Button>
                        </div>
                      )
                    )}
                  </article>
                ))}
              </div>
              <Pager
                total={data.total}
                page={page}
                size={50}
                setPage={setPage}
              />
            </>
          ) : (
            <Empty
              title="No site visits here yet"
              description="Schedule a visit from a buyer's property brief or select a buyer and property here."
            />
          )
        }
      </Load>
      {edit && (
        <VisitForm
          item={edit === true ? undefined : edit}
          close={() => setEdit(null)}
        />
      )}
      {outcome && (
        <FormDialog
          title="Record site visit outcome"
          fields={[
            {
              name: "status",
              label: "Visit outcome",
              options: options(["completed", "no-show", "cancelled"]),
              required: true,
            },
            {
              name: "feedback",
              label: "Customer feedback / cancellation reason",
              type: "textarea",
              wide: true,
              maxLength: 4000,
            },
          ]}
          onClose={() => setOutcome(null)}
          onSubmit={(v) =>
            action(() => send("/site-visits/" + outcome.id, v, "PATCH"))
          }
        />
      )}
    </>
  );
}

export function BookingsPage() {
  const [sp] = useSearchParams();
  const [status, setStatus] = useState(""),
    [page, setPage] = useState(1),
    [adding, setAdding] = useState(!!sp.get("lead_id")),
    [edit, setEdit] = useState<Booking | null>(null);
  const q = useData<{ items: Booking[]; total: number }>(
      "/bookings?" + params({ status, page }),
    ),
    dir = useDirectory(),
    action = useAction();
  return (
    <>
      <PageHeading
        eyebrow="EVERY COMMITMENT, ACCOUNTED FOR"
        title="Bookings that move business."
        description="Track reservations, deal value and agreed commissions. Amounts here are records, not proof of bank receipt."
        actions={
          <Button onClick={() => setAdding(true)}>
            <Plus size={17} />
            Create booking
          </Button>
        }
      />
      <div className="filter-row">
        <select
          aria-label="Booking status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All bookings</option>
          {["reserved", "booked", "closed", "cancelled"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </div>
      <Load query={q}>
        {(data) =>
          data.items.length ? (
            <Panel>
              <Table
                headers={[
                  "Booking / customer",
                  "Property",
                  "Agent",
                  "Agreed value",
                  "Token recorded",
                  "Commission",
                  "Stage",
                ]}
              >
                {data.items.map((b) => (
                  <tr key={b.id}>
                    <td>
                      <strong>{b.reference}</strong>
                      <Link className="block" to={"/app/leads/" + b.lead_id}>
                        {b.lead_name}
                      </Link>
                      <small>{b.booked_on}</small>
                    </td>
                    <td>
                      <Link to={"/app/properties/" + b.property_id}>
                        {b.property_title}
                      </Link>
                    </td>
                    <td>{b.agent_name}</td>
                    <td>{money(b.agreed_price)}</td>
                    <td>{money(b.token_amount)}</td>
                    <td>{money(b.commission)}</td>
                    <td>
                      <Badge value={b.status} />
                      {["reserved", "booked"].includes(b.status) && (
                        <Button variant="secondary" onClick={() => setEdit(b)}>
                          Update stage
                        </Button>
                      )}
                      {b.notes && (
                        <small className="block muted">{b.notes}</small>
                      )}
                    </td>
                  </tr>
                ))}
              </Table>
              <Pager
                total={data.total}
                page={page}
                size={50}
                setPage={setPage}
              />
            </Panel>
          ) : (
            <Empty
              title="Your first booking starts with a buyer"
              description="Reserve an available property for an enquiry. Each unit can have only one live booking."
            />
          )
        }
      </Load>
      {adding && (
        <FormDialog
          title="Create a property booking"
          dependencies={[dir]}
          fields={[
            {
              name: "lead_id",
              label: "Buyer",
              render: (v, set) => (
                <LeadPicker
                  value={String(v || "")}
                  onChange={set}
                  label="Buyer enquiry"
                />
              ),
            },
            {
              name: "property_id",
              label: "Property",
              render: (v, set) => (
                <PropertyPicker value={String(v || "")} onChange={set} />
              ),
            },
            {
              name: "agent_id",
              label: "Booking agent",
              options: (dir.data || []).map((u) => ({
                value: u.id,
                label: u.name,
              })),
              required: true,
            },
            {
              name: "reference",
              label: "Booking reference",
              required: true,
              maxLength: 80,
            },
            {
              name: "agreed_price",
              label: "Agreed deal value (₹)",
              type: "number",
              min: "0.01",
              step: "0.01",
              required: true,
            },
            {
              name: "token_amount",
              label: "Token amount recorded (₹)",
              type: "number",
              min: "0",
              step: "0.01",
              required: true,
              defaultValue: "0",
            },
            {
              name: "commission",
              label: "Agreed commission (₹)",
              type: "number",
              min: "0",
              step: "0.01",
              required: true,
              defaultValue: "0",
            },
            {
              name: "booked_on",
              label: "Booking date",
              type: "date",
              required: true,
              defaultValue: new Date().toLocaleDateString("en-CA"),
            },
            {
              name: "notes",
              label: "Booking notes",
              type: "textarea",
              wide: true,
              maxLength: 4000,
            },
          ]}
          onClose={() => setAdding(false)}
          initial={{
            lead_id: sp.get("lead_id") || "",
            property_id: sp.get("property_id") || "",
            agent_id: sp.get("agent_id") || "",
          }}
          submitLabel="Reserve property"
          onSubmit={(v) => action(() => send("/bookings", v))}
        />
      )}
      {edit && (
        <FormDialog
          title={"Update booking " + edit.reference}
          description="Cancelling releases the property. Closing marks it sold or leased. Closed bookings cannot be reopened."
          fields={[
            {
              name: "status",
              label: "Next stage",
              required: true,
              options: options(
                edit.status === "reserved"
                  ? ["booked", "cancelled"]
                  : ["closed", "cancelled"],
              ),
            },
            {
              name: "notes",
              label: "Booking notes / cancellation reason",
              type: "textarea",
              wide: true,
              maxLength: 4000,
            },
          ]}
          initial={{ notes: edit.notes }}
          onClose={() => setEdit(null)}
          onSubmit={(v) =>
            action(() => send("/bookings/" + edit.id, v, "PATCH"))
          }
        />
      )}
    </>
  );
}

export function EstateOverview() {
  const q = useData<{
    available: number;
    inventory: number;
    reserved: number;
    booked_value: string;
    commission: string;
    booking_count: number;
    visits: Visit[];
  }>("/real-estate/overview");
  return (
    <Load query={q}>
      {(d) => (
        <section className="estate-overview">
          <div className="estate-section-heading">
            <div>
              <span className="eyebrow">REAL ESTATE WORKSPACE</span>
              <h2>From the first enquiry to the keys.</h2>
            </div>
            <Link className="button secondary" to="/app/properties">
              Open inventory <ArrowRight size={16} />
            </Link>
          </div>
          <div className="stats-grid">
            <Stat
              label="Available properties"
              value={d.available}
              detail={d.inventory + " listings in your portfolio"}
              accent
            />
            <Stat
              label="Reserved properties"
              value={d.reserved}
              detail="Linked to live bookings"
            />
            <Stat
              label="Booking value"
              value={money(d.booked_value)}
              detail={d.booking_count + " non-cancelled deals"}
            />
            <Stat
              label="Closed-deal commission"
              value={money(d.commission)}
              detail="Agreed amounts on closed bookings"
            />
          </div>
          <Panel
            title="Next site visits"
            action={
              <Link className="text-button" to="/app/site-visits">
                View schedule <ArrowRight size={15} />
              </Link>
            }
          >
            {d.visits.length ? (
              <div className="overview-visits">
                {d.visits.map((v) => (
                  <article key={v.id}>
                    <CalendarDays size={20} />
                    <div>
                      <Link to={"/app/leads/" + v.lead_id}>{v.lead_name}</Link>
                      <small>
                        {v.property_title} · {v.assignee_name}
                      </small>
                    </div>
                    <time>{dateTime(v.starts_at)}</time>
                  </article>
                ))}
              </div>
            ) : (
              <div className="estate-onboarding">
                <p>Turn a buyer's requirements into a property visit.</p>
                <Link className="text-button" to="/app/site-visits">
                  Schedule your first visit <ArrowRight size={15} />
                </Link>
              </div>
            )}
          </Panel>
        </section>
      )}
    </Load>
  );
}

export function Pager({
  total,
  page,
  size,
  setPage,
}: {
  total: number;
  page: number;
  size: number;
  setPage: (p: number) => void;
}) {
  return (
    <div className="pagination">
      <span>
        {total} records · Page {page}
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
          disabled={page * size >= total}
          onClick={() => setPage(page + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
