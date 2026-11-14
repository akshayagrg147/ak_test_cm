"""Understands an incoming message: intent, FAQ topic, and any lead details.

Uses Claude (claude-opus-5-5) with structured output when ANTHROPIC_API_KEY is set;
otherwise (or on any API error) falls back to keyword rules, so the bot never goes silent.
Claude never writes replies — only this JSON.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

log = logging.getLogger("brain")

Intent = Literal[
    "interested",      # wants demo / price / details / how to start
    "question",        # asks about a feature (faq_topic set) without clear buying intent
    "greeting",
    "answer",          # is answering the question we just asked
    "not_interested",
    "pause",           # "baad mein", "abhi nahi" while collecting
    "opt_out",         # stop messaging me
    "opt_in",          # START after opting out
    "human",           # wants a real person / complaint / something the bot can't handle
    "thanks",          # thanks / praise / emoji only
    "off_topic",       # spam, unrelated
]
Topic = Literal[
    "features", "enquiry", "matching", "followup", "inventory", "site_visit",
    "booking", "customize", "who_for", "pricing", "access", "whatsapp", "data_safety", "excel",
    "unknown", "none",
]


class Details(BaseModel):
    name: Optional[str] = None
    whatsapp: Optional[str] = Field(None, description="10-digit Indian mobile, digits only")
    team_size: Optional[str] = None
    lead_sources: Optional[str] = Field(None, description="where their leads come from: portals, IndiaMART, ads, walk-in")
    current_tool: Optional[str] = Field(None, description="where they keep leads today: Excel, diary, WhatsApp, a CRM")
    demo_time: Optional[str] = None


class Understanding(BaseModel):
    intent: Intent
    faq_topic: Topic = "none"
    details: Details = Field(default_factory=Details)


SYSTEM = """You read Instagram DMs and comments sent to ViaCRM (@viacrm91), a real estate CRM SaaS for Indian \
agencies, developers, channel partners and sales teams. Messages are in Hindi, Hinglish or English.
Classify the message and extract lead details. You do NOT write replies.

ViaCRM features (the only things the bot can answer about):
- enquiry: enquiry capture and assignment to agents
- matching: buyer-property matching by budget and location
- followup: follow-up queues and reminders
- inventory: sale/rental inventory with brochures
- site_visit: clash-free site-visit scheduling
- booking: bookings with unit availability and commissions
- customize: custom branding, stages, roles, reports
- features: "what does it do / details / features" in general
- who_for: who it is for
- pricing: price, cost, plans, kitna
- access: link, login, trial, app download, how to get it
- whatsapp: does it connect / integrate / sync with WhatsApp
- data_safety: is my data safe, secure, private, who can see it, hacking
- excel: "Excel se kaam chal raha hai", why switch from Excel/sheets/diary
If they ask something not covered (integrations, mobile app specifics, data import, refunds, a complaint…) \
use faq_topic "unknown" and intent "human".

Intent rules:
- interested: wants a demo, price, details, "kaise milega", "interested", "DM", "info".
- question: asks about a specific feature without asking for demo/price.
- answer: the bot just asked for a detail (see expected_field) and the message gives it.
- pause: "baad mein", "abhi nahi", "later" while details are being collected.
- not_interested: clearly not interested.
- opt_out: stop / unsubscribe / "message mat karo" / "band karo".
- opt_in: "START" after opting out.
- human: asks for a person, call from team, or angry/complaint, or unanswerable question.
- thanks: thanks, praise, emoji-only, "nice".
- off_topic: spam, promotions, unrelated.
Extract any details present anywhere in the message (name, 10-digit whatsapp digits only, team size, \
lead_sources such as 99acres/MagicBricks/IndiaMART/Justdial/FB ads/walk-in, current_tool = where they keep leads \
today such as Excel/diary/WhatsApp/other CRM). Leave unknown fields null. \
If expected_field is "current_tool" or "lead_sources" and they say skip/nahi, set that field to "skip". \
When expected_field is "current_tool", an answer like "Excel" or "WhatsApp" is an answer, not a question."""


class _LLM:
    def __init__(self):
        self.client = None
        if os.getenv("ANTHROPIC_API_KEY"):
            import anthropic
            self.client = anthropic.Anthropic()
        self.model = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")

    def understand(self, text: str, expected_field: str | None, source: str) -> Understanding | None:
        if not self.client:
            return None
        user = f"source: {source}\nexpected_field: {expected_field or 'none'}\nmessage: {text}"
        try:
            resp = self.client.beta.messages.parse(
                model=self.model,
                max_tokens=2000,
                system=SYSTEM,
                output_config={"effort": "low"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                messages=[{"role": "user", "content": user}],
                output_format=Understanding,
            )
            if resp.stop_reason == "refusal" or resp.parsed_output is None:
                return None
            return resp.parsed_output
        except Exception as e:  # never let the LLM take the bot down
            log.warning("LLM failed, using rules: %s", e)
            return None


_llm: _LLM | None = None


def llm() -> _LLM:
    global _llm
    if _llm is None:
        _llm = _LLM()
    return _llm


# ---------------- keyword fallback ----------------
def _has(t: str, words) -> bool:
    return any(re.search(rf"(?<![a-z]){w}(?![a-z])", t) for w in words)


PHONE_RE = re.compile(r"(?:\+?91[\s-]?|0)?([6-9]\d{4}[\s-]?\d{5})")

TOPIC_WORDS = [
    ("whatsapp", [r"whatsapp (se|ke saath|ke sath|integration|integrate|sync|connect)\w*", r"whatsapp (pe|par) (chalta|kaam)",
                  r"(connect|integrate|sync)\w* (with |to )?whatsapp"]),
    ("data_safety", ["safe", "secure", "security", "hack", "hacked", "privacy", "private", "data chori", "surakshit",
                     "data kaun", "data kahan", "data leak"]),
    ("excel", [r"excel (se|me|mein|pe|hi) (kaam|chal)\w*", r"(sheet|diary|register) (se|me|mein) (kaam|chal)\w*",
               r"excel (kaafi|kafi|theek|thik)", "excel hi"]),
    ("pricing", ["price", "pricing", "cost", "kitna", "kitne ka", "rate", "charges", "plan", "plans", "fees", "mehenga",
                 "mehnga", "costly", "expensive", "कीमत", "कितना", "प्राइस"]),
    ("access", ["link", "login", "trial", "download", "app", "website", "kaise milega", "kahan milega"]),
    ("matching", ["match", "matching", "budget", "location"]),
    ("followup", ["follow", "followup", "follow-up", "reminder", "remind"]),
    ("site_visit", ["site visit", "visit", "schedule"]),
    ("booking", ["booking", "bookings", "unit", "units", "commission", "commissions"]),
    ("inventory", ["inventory", "brochure", "brochures", "rental", "listing", "listings"]),
    ("enquiry", ["enquiry", "enquiries", "inquiry", "lead", "leads", "assign"]),
    ("customize", ["branding", "brand", "custom", "stages", "roles", "report", "reports"]),
    ("who_for", ["kiske liye", "who is it for", "broker", "builder", "developer", "channel partner"]),
    ("features", ["details", "detail", "features", "feature", "info", "kya hai", "kya karta", "batao", "jankari", "जानकारी"]),
]


def rules(text: str, expected_field: str | None) -> Understanding:
    t = text.lower().strip()
    d = Details()
    m = PHONE_RE.search(text)
    if m:
        d.whatsapp = re.sub(r"\D", "", m.group(1))

    if re.fullmatch(r"start", t):
        return Understanding(intent="opt_in")
    if _has(t, ["stop", "unsubscribe", "message mat karo", "msg mat karo", "band karo", "mat bhejo", "no more messages"]):
        return Understanding(intent="opt_out")
    if _has(t, ["team", "human", "insaan", "real person", "call me", "call karo", "baat karni", "complaint", "manager", "delete my data", "data delete"]) and not d.whatsapp and expected_field is None:
        return Understanding(intent="human", faq_topic="unknown")

    if _has(t, ["follow for follow", "f4f", "follow back", "collab", "promotion", "dm for promo", "check my profile"]):
        return Understanding(intent="off_topic")

    topic = "none"
    for name, words in TOPIC_WORDS:
        if _has(t, words):
            topic = name
            break

    if expected_field:
        if _has(t, ["baad mein", "later", "abhi nahi", "not now", "busy"]):
            return Understanding(intent="pause")
        if "?" in t and not d.whatsapp:  # a question in the middle of the flow
            return Understanding(intent="question", faq_topic=topic if topic != "none" else "unknown")
        # answering the question we asked
        if expected_field == "whatsapp":
            return Understanding(intent="answer", details=d)
        if expected_field == "team_size":
            n = re.search(r"\d+", t)
            if n:
                d.team_size = n.group(0)
            return Understanding(intent="answer", details=d)
        if expected_field in ("current_tool", "lead_sources"):
            v = "skip" if _has(t, ["skip", "nahi", "no", "nothing", "pata nahi"]) else text.strip()[:120]
            setattr(d, expected_field, v)
            return Understanding(intent="answer", details=d)
        if expected_field == "demo_time":
            d.demo_time = text.strip()[:80]
            return Understanding(intent="answer", details=d)
        if expected_field == "name":
            nm = re.sub(r"(?i)^(my name is|mera naam|naam|main|i am|i'm|this is)\s*", "", text.strip())
            nm = re.sub(r"(?i)\s*(hai|hoon|hu|here)\.?$", "", nm).strip(" .,!")
            if 1 <= len(nm.split()) <= 4 and not re.search(r"\d|\?", nm):
                d.name = nm.title()
            return Understanding(intent="answer", details=d)

    if _has(t, ["not interested", "interest nahi", "nahi chahiye", "no thanks", "zarurat nahi"]):
        return Understanding(intent="not_interested")
    if _has(t, ["demo", "interested", "intrested", "dm", "chahiye", "want", "price", "kitna", "pricing", "kaise milega", "details", "info", "डेमो"]):
        return Understanding(intent="interested", faq_topic=topic, details=d)
    if topic != "none":
        return Understanding(intent="question", faq_topic=topic, details=d)
    if _has(t, ["hi", "hello", "hey", "namaste", "namaskar", "hii", "helo", "नमस्ते"]):
        return Understanding(intent="greeting")
    if _has(t, ["thanks", "thank you", "thanku", "nice", "great", "awesome", "superb", "badhiya", "mast", "shukriya", "dhanyavad"]) or not re.search(r"[a-zऀ-ॿ0-9]", t):
        return Understanding(intent="thanks")
    if "?" in t:
        return Understanding(intent="human", faq_topic="unknown")
    return Understanding(intent="off_topic")


def understand(text: str, expected_field: str | None = None, source: str = "dm") -> tuple[Understanding, str]:
    """Returns (understanding, engine) where engine is 'claude' or 'rules'."""
    u = llm().understand(text, expected_field, source)
    if u is not None:
        return u, "claude"
    return rules(text, expected_field), "rules"
