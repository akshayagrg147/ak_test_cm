import { useEffect, useState } from "react";
import { Copy, MessageCircle, MessageSquareText, Plus } from "lucide-react";
import { api, params, send } from "./api";
import { useAction, useData } from "./main";
import { whatsappLink, whatsappNumber } from "./whatsapp";
import type { Property } from "./estate-types";
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
  type Field,
} from "./ui";

/**
 * Message templates for WhatsApp click-to-chat and SMS links. ViaCRM renders text and
 * logs that a chat was opened; the user presses Send in their own app.
 */
export interface MessageTemplate {
  id: string;
  name: string;
  body: string;
  purpose: string;
  active: boolean;
  sort_order: number;
  updated_at: string;
}
interface TemplateList {
  items: MessageTemplate[];
  placeholders: string[];
}
const purposes = [
  ["any", "Any"],
  ["new_lead", "New lead"],
  ["follow_up", "Follow-up"],
  ["site_visit", "Site visit"],
  ["property", "Property"],
];
const purposeLabel = (v: string) => purposes.find(([k]) => k === v)?.[1] || v;
const LONG_URL = 1800;

export function MessageTemplatesPage() {
  const q = useData<TemplateList>("/message-templates");
  const action = useAction();
  const [editing, setEditing] = useState<MessageTemplate | true | null>(null);
  const [removing, setRemoving] = useState<MessageTemplate | null>(null);
  const fields: Field[] = [
    { name: "name", label: "Template name", required: true, maxLength: 60 },
    {
      name: "purpose",
      label: "Use for",
      options: purposes.map(([value, label]) => ({ value, label })),
      defaultValue: "any",
    },
    {
      name: "body",
      label: "Message text",
      type: "textarea",
      required: true,
      maxLength: 1000,
      wide: true,
      hint:
        "Placeholders: " +
        (q.data?.placeholders || []).map((p) => `{{${p}}}`).join(", "),
    },
    { name: "active", label: "Active", type: "checkbox", defaultValue: true },
  ];
  return (
    <>
      <PageHeading
        eyebrow="STUDIO · MESSAGES"
        title="Message templates"
        description="Ready messages your team opens in WhatsApp or SMS from a lead. Names, property and visit details are filled in; the user still presses Send in their own app."
        actions={
          <Button onClick={() => setEditing(true)}>
            <Plus size={17} />
            Add template
          </Button>
        }
      />
      <Panel>
        <Load query={q}>
          {(d) =>
            d.items.length ? (
              <ul className="template-list">
                {d.items.map((t) => (
                  <li key={t.id}>
                    <div>
                      <strong>{t.name}</strong>
                      <span>
                        {purposeLabel(t.purpose)}
                        {!t.active && " · inactive"}
                      </span>
                    </div>
                    <p className="preserve-lines">{t.body}</p>
                    <div className="inline-actions">
                      {!t.active && <Badge value="inactive" />}
                      <Button
                        variant="secondary"
                        onClick={() => setEditing(t)}
                        aria-label={"Edit " + t.name}
                      >
                        Edit
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() => setRemoving(t)}
                        aria-label={"Delete " + t.name}
                      >
                        Delete
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty
                title="No templates yet"
                description="Add a message such as a site visit confirmation. Use placeholders like {{first_name}} and {{visit_time}}."
              />
            )
          }
        </Load>
      </Panel>
      {editing && (
        <FormDialog
          title={editing === true ? "Add a message template" : "Edit template"}
          description="Up to 1,000 characters. Unknown placeholders are rejected so customers never see {{…}} text."
          fields={fields}
          initial={
            editing === true
              ? {}
              : {
                  name: editing.name,
                  purpose: editing.purpose,
                  body: editing.body,
                  active: editing.active,
                }
          }
          onClose={() => setEditing(null)}
          onSubmit={(v) =>
            action(() =>
              send(
                editing === true
                  ? "/message-templates"
                  : "/message-templates/" + editing.id,
                {
                  name: v.name,
                  purpose: v.purpose || "any",
                  body: v.body,
                  active: !!v.active,
                  sort_order: editing === true ? 0 : editing.sort_order,
                },
                editing === true ? "POST" : "PUT",
              ),
            ).then(() => setEditing(null))
          }
        />
      )}
      {removing && (
        <FormDialog
          title={`Delete “${removing.name}”?`}
          description="If notes already used this template it is hidden instead, so lead history stays intact."
          fields={[]}
          submitLabel="Delete template"
          onClose={() => setRemoving(null)}
          onSubmit={() =>
            action(() =>
              api("/message-templates/" + removing.id, { method: "DELETE" }),
            ).then(() => setRemoving(null))
          }
        />
      )}
    </>
  );
}

interface Rendered {
  text: string;
  missing: string[];
  truncated: boolean;
  template_name: string;
}

/** Pick a template, optionally a property, edit the server-rendered text, then open WhatsApp or SMS. */
export function TemplateMessageDialog({
  lead,
  close,
}: {
  lead: { id: string; name: string; phone: string };
  close: () => void;
}) {
  const action = useAction();
  const templates = useData<TemplateList>("/message-templates");
  const matches = useData<{ items: Property[] }>(
    `/leads/${lead.id}/property-matches`,
  );
  const [search, setSearch] = useState("");
  const found = useData<{ items: Property[] }>(
    "/properties?" + params({ q: search, status: "available" }),
    search.trim().length > 1,
  );
  const [templateId, setTemplateId] = useState("");
  const [propertyId, setPropertyId] = useState("");
  const [text, setText] = useState("");
  const [missing, setMissing] = useState<string[]>([]);
  const [truncated, setTruncated] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!templateId) return;
    let live = true;
    setError(null);
    send<Rendered>(`/leads/${lead.id}/template-render`, {
      template_id: templateId,
      ...(propertyId ? { property_id: propertyId } : {}),
    })
      .then((r) => {
        if (!live) return;
        setText(r.text);
        setMissing(r.missing);
        setTruncated(r.truncated);
        setName(r.template_name);
      })
      .catch((e) => {
        if (!live) return;
        setError(e);
        setText("");
      });
    return () => {
      live = false;
    };
  }, [lead.id, templateId, propertyId]);
  const wa = text ? whatsappLink(lead.phone, text) : null;
  const number = whatsappNumber(lead.phone);
  const sms =
    text && number ? `sms:+${number}?body=${encodeURIComponent(text)}` : null;
  const log = (channel: "whatsapp" | "sms") =>
    void action(() =>
      send(`/leads/${lead.id}/message-log`, {
        channel,
        template_id: templateId || null,
        text: text.slice(0, 1000),
      }),
    ).catch(setError);
  const options = [
    ...(matches.data?.items || []).map((p) => ({ p, group: "Matching" })),
    ...(found.data?.items || [])
      .filter((p) => !matches.data?.items.some((m) => m.id === p.id))
      .map((p) => ({ p, group: "Search results" })),
  ];
  const active = templates.data?.items.filter((t) => t.active) || [];
  return (
    <Dialog
      title="Message with a template"
      description={`Opens your own WhatsApp or SMS app with this text for ${lead.name}. ViaCRM does not send it.`}
      onClose={close}
    >
      <div className="dialog-content template-dialog">
        <label className="field wide">
          <span>Template</span>
          <select
            aria-label="Template"
            value={templateId}
            onChange={(e) => setTemplateId(e.target.value)}
          >
            <option value="">Choose a template…</option>
            {active.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} · {purposeLabel(t.purpose)}
              </option>
            ))}
          </select>
          {templates.data && !active.length && (
            <small>
              Ask an admin to add templates in Studio → Message templates.
            </small>
          )}
        </label>
        <label className="field">
          <span>Find a property (optional)</span>
          <input
            aria-label="Search properties for the message"
            placeholder="Project, property or reference"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <label className="field">
          <span>Property</span>
          <select
            aria-label="Property for the message"
            value={propertyId}
            onChange={(e) => setPropertyId(e.target.value)}
          >
            <option value="">No property</option>
            {options.map(({ p, group }) => (
              <option key={p.id} value={p.id}>
                {group === "Matching" ? "★ " : ""}
                {p.reference} · {p.title}
              </option>
            ))}
          </select>
          <small>★ marks properties matching this client’s brief.</small>
        </label>
        <label className="field wide">
          <span>Message preview (you can edit it)</span>
          <textarea
            aria-label="Message preview"
            rows={6}
            maxLength={1000}
            value={text}
            disabled={!templateId}
            onChange={(e) => setText(e.target.value)}
          />
          {missing.length > 0 && (
            <small role="status">
              Some details were empty: {missing.join(", ").replace(/_/g, " ")}.
            </small>
          )}
          {truncated && (
            <small role="status">
              The filled-in message was over 1,000 characters and was shortened.
            </small>
          )}
          {wa && wa.length > LONG_URL && (
            <small role="status">
              This message is long; some phones may cut it off.
            </small>
          )}
        </label>
        {!number && (
          <p className="muted-note">
            This phone number can’t open WhatsApp or SMS. Use Copy text instead.
          </p>
        )}
      </div>
      {error !== null && <ErrorBox error={error} />}
      <footer>
        <Button variant="secondary" onClick={close}>
          Close
        </Button>
        <Button
          variant="secondary"
          disabled={!text}
          onClick={() =>
            void navigator.clipboard
              ?.writeText(text)
              .then(() => setCopied(true))
              .catch(() => setCopied(false))
          }
        >
          <Copy size={16} />
          {copied ? "Copied" : "Copy text"}
        </Button>
        {sms ? (
          <a className="button secondary" href={sms} onClick={() => log("sms")}>
            <MessageSquareText size={16} />
            Open SMS
          </a>
        ) : (
          <Button variant="secondary" disabled>
            <MessageSquareText size={16} />
            Open SMS
          </Button>
        )}
        {wa ? (
          <a
            className="button whatsapp-button"
            href={wa}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => log("whatsapp")}
            aria-label={`Open WhatsApp with ${name || "this"} message`}
          >
            <MessageCircle size={16} />
            Open WhatsApp
          </a>
        ) : (
          <Button disabled>
            <MessageCircle size={16} />
            Open WhatsApp
          </Button>
        )}
      </footer>
    </Dialog>
  );
}
