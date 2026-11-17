import { useEffect, useState } from "react";
import { Copy, Link2, MessageCircle, RefreshCw } from "lucide-react";
import { api, send } from "./api";
import { useAction, useAuth, useData } from "./main";
import type { Property } from "./estate-types";
import { Button, ErrorBox, Load, Panel, dateTime, money } from "./ui";

/** Public share link for one property. The buyer opens it without logging in. */
interface ShareState {
  enabled: boolean;
  url: string | null;
  photo_file_ids: string[] | null;
  doc_file_ids: string[];
  show_rera: boolean;
  contact_mode: "sharer" | "company";
  views: number;
  last_viewed_at: string | null;
  available: boolean;
  can_manage: boolean;
  callers_can_share: boolean;
  photos: { id: string; name: string }[];
  documents: { id: string; name: string }[];
}

export function shareMessage(p: Property, url: string) {
  return `${p.title}, ${[p.locality, p.city].filter(Boolean).join(", ")}, ${money(p.price)}: ${url}`;
}

export function PropertyShareCard({ property }: { property: Property }) {
  const { session } = useAuth();
  const q = useData<ShareState>(`/properties/${property.id}/share`);
  const action = useAction();
  const [error, setError] = useState<unknown>(null);
  const [copied, setCopied] = useState(false);
  const [choose, setChoose] = useState(false);
  const [photos, setPhotos] = useState<string[]>([]);
  const [docs, setDocs] = useState<string[]>([]);
  const [rera, setRera] = useState(true);
  const [mode, setMode] = useState<"sharer" | "company">("sharer");
  const data = q.data;
  useEffect(() => {
    if (!data) return;
    setChoose(data.photo_file_ids !== null);
    setPhotos(data.photo_file_ids || data.photos.map((f) => f.id));
    setDocs(data.doc_file_ids);
    setRera(data.show_rera);
    setMode(data.contact_mode);
  }, [data]);
  const run = (fn: () => Promise<unknown>) =>
    void action(fn)
      .then(() => setError(null))
      .catch(setError);
  const save = () =>
    run(() =>
      send(
        `/properties/${property.id}/share`,
        {
          photo_file_ids: choose ? photos : null,
          doc_file_ids: docs,
          show_rera: rera,
          contact_mode: mode,
        },
        "PUT",
      ),
    );
  const toggle = (list: string[], id: string, on: boolean) =>
    on ? [...new Set([...list, id])] : list.filter((v) => v !== id);
  return (
    <div id="share" className="share-card">
      <Panel
        title="Share"
        description="A public page buyers open without logging in: photos, price, size, location and your contact. Address, owner details and internal references stay private."
      >
        <Load query={q}>
          {(s) => (
            <>
              {s.enabled && s.url ? (
                <>
                  <label className="field wide">
                    <span>Public link</span>
                    <input readOnly value={s.url} aria-label="Public link" />
                  </label>
                  <p className="muted-note">
                    {s.views
                      ? `Opened ${s.views} ${s.views === 1 ? "time" : "times"}, last ${dateTime(s.last_viewed_at)}`
                      : "Not opened yet"}
                  </p>
                  <div className="inline-actions share-actions">
                    <Button
                      variant="secondary"
                      onClick={() =>
                        void navigator.clipboard
                          ?.writeText(s.url || "")
                          .then(() => setCopied(true))
                      }
                    >
                      <Copy size={16} />
                      {copied ? "Copied" : "Copy link"}
                    </Button>
                    <a
                      className="button whatsapp-button"
                      href={`https://wa.me/?text=${encodeURIComponent(shareMessage(property, s.url))}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <MessageCircle size={16} />
                      WhatsApp
                    </a>
                    {s.can_manage && (
                      <>
                        <Button
                          variant="secondary"
                          onClick={() =>
                            run(() =>
                              api(`/properties/${property.id}/share/replace`, {
                                method: "POST",
                              }),
                            )
                          }
                        >
                          <RefreshCw size={16} />
                          Replace link
                        </Button>
                        <Button
                          variant="secondary"
                          onClick={() =>
                            run(() =>
                              api(`/properties/${property.id}/share`, {
                                method: "DELETE",
                              }),
                            )
                          }
                        >
                          Turn off
                        </Button>
                      </>
                    )}
                  </div>
                </>
              ) : (
                <p className="muted-note">
                  {!s.available
                    ? "Only available properties can be shared."
                    : s.can_manage
                      ? "Sharing is off. Turn it on to get a link."
                      : "Sharing is off. Ask an admin or manager to turn it on."}
                </p>
              )}
              {s.can_manage && s.available && (
                <fieldset className="share-options">
                  <legend>What buyers see</legend>
                  <label className="check-field">
                    <input
                      type="checkbox"
                      checked={!choose}
                      onChange={(e) => setChoose(!e.target.checked)}
                    />
                    All property photos
                  </label>
                  {choose &&
                    s.photos.map((f) => (
                      <label key={f.id} className="check-field">
                        <input
                          type="checkbox"
                          checked={photos.includes(f.id)}
                          onChange={(e) =>
                            setPhotos(toggle(photos, f.id, e.target.checked))
                          }
                        />
                        {f.name}
                      </label>
                    ))}
                  {s.documents.length > 0 && (
                    <p className="muted-note">
                      PDFs stay private unless ticked:
                    </p>
                  )}
                  {s.documents.map((f) => (
                    <label key={f.id} className="check-field">
                      <input
                        type="checkbox"
                        checked={docs.includes(f.id)}
                        onChange={(e) =>
                          setDocs(toggle(docs, f.id, e.target.checked))
                        }
                      />
                      Public PDF: {f.name}
                    </label>
                  ))}
                  <label className="check-field">
                    <input
                      type="checkbox"
                      checked={rera}
                      onChange={(e) => setRera(e.target.checked)}
                    />
                    Show RERA number
                  </label>
                  <label className="field">
                    <span>Contact shown to buyers</span>
                    <select
                      aria-label="Contact shown to buyers"
                      value={mode}
                      onChange={(e) =>
                        setMode(e.target.value as "sharer" | "company")
                      }
                    >
                      <option value="sharer">
                        The person who turned sharing on
                      </option>
                      <option value="company">
                        Always the company contact
                      </option>
                    </select>
                  </label>
                  <Button onClick={save}>
                    <Link2 size={16} />
                    {s.enabled ? "Save sharing options" : "Turn on sharing"}
                  </Button>
                </fieldset>
              )}
              {session?.role === "admin" && (
                <label className="check-field share-callers">
                  <input
                    type="checkbox"
                    checked={s.callers_can_share}
                    onChange={(e) =>
                      run(() =>
                        send(
                          "/property-share-settings",
                          { callers_can_share: e.target.checked },
                          "PUT",
                        ),
                      )
                    }
                  />
                  Let telecallers make properties public (company-wide)
                </label>
              )}
              {error !== null && <ErrorBox error={error} />}
            </>
          )}
        </Load>
      </Panel>
    </div>
  );
}
