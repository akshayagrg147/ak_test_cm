"""Every message the bot can send. Nothing else is ever sent.
# Texts APPROVED by Akshay on 2026-11-10. Re-confirm with him before changing any customer-facing text.

The LLM only *understands* messages (intent + details); it never writes replies.
So this file is the complete list of texts Akshay approves before go-live.
Never put the ViaCRM website URL / IP in here.
"""

# ---------- Opening / general ----------
GREETING = (
    "Namaste 🙏 ViaCRM mein aapka swagat hai!\n"
    "Hum real estate agencies, developers aur channel partners ke liye CRM banate hain — "
    "enquiries, follow-ups, site visits aur bookings sab ek jagah.\n\n"
    "Free demo chahiye to bas *demo* likhiye. Koi sawaal ho to pooch lijiye 😊"
)

THANKS_REPLY = "Thank you 🙏 Kabhi bhi demo chahiye ho to *demo* likh dijiye."

NOT_INTERESTED = "Koi baat nahi 🙏 Jab bhi zarurat ho, yahan message kar dijiye. All the best!"

OFF_TOPIC = (
    "Main ViaCRM ka assistant hoon 🙂 CRM, demo ya features ke baare mein kuch bhi poochiye. "
    "Team se seedhi baat karni ho to *team* likhiye."
)

# ---------- FAQ answers (only from the real feature list) ----------
FAQ = {
    "features": (
        "ViaCRM mein ye sab milta hai 👇\n"
        "• Enquiry capture + team mein auto-assign\n"
        "• Buyer ko budget/location ke hisaab se property matching\n"
        "• Follow-up queue aur reminders\n"
        "• Sale/rental inventory, brochures ke saath\n"
        "• Site visit scheduling (koi clash nahi)\n"
        "• Bookings, unit availability aur commissions\n"
        "• Apni branding, stages, roles aur reports"
    ),
    "enquiry": (
        "Har enquiry ek jagah capture hoti hai aur sahi agent ko assign ho jaati hai — "
        "koi lead miss nahi hoti 📥"
    ),
    "matching": (
        "Buyer ka budget aur location daalte hi ViaCRM matching properties dikha deta hai 🏠 "
        "Agent ko list dhoondhni nahi padti."
    ),
    "followup": (
        "Har lead ki follow-up queue banti hai aur time par reminder aata hai ⏰ "
        "\"Call karna bhool gaya\" wali problem khatam."
    ),
    "inventory": (
        "Sale aur rental dono inventory ek jagah rakhiye, brochures ke saath 📂 "
        "Client ko turant share kar sakte hain."
    ),
    "site_visit": (
        "Site visits schedule kijiye bina kisi clash ke 📅 "
        "Ek hi time par do visits double-book nahi honge."
    ),
    "booking": (
        "Bookings, unit availability aur commissions — sab track hota hai 💼 "
        "Kaunsa unit available hai, ek nazar mein dikh jaata hai."
    ),
    "customize": (
        "Apni company ki branding, apne pipeline stages, team roles aur reports — "
        "sab aapke hisaab se set hota hai ⚙️"
    ),
    "who_for": (
        "ViaCRM real estate agencies, developers, channel partners aur sales teams ke liye hai 🏢 "
        "Chhoti team ho ya badi, dono ke liye chalta hai."
    ),
    "pricing": (
        "Pricing aapki team size aur zarurat par depend karti hai 💰 "
        "Demo call par team aapko exact quote bata degi."
    ),
    "access": (
        "Access ke liye hamari team aapko khud call/WhatsApp karke setup karwa degi 📞 "
        "Bas demo ke liye 2 minute ki details de dijiye."
    ),
}

DEMO_CTA = "Free demo chahiye to *demo* likhiye 🙂"

# ---------- Lead collection ----------
# Shown once, when someone first shows interest. Says WHY we ask.
START_COLLECT = (
    "Badhiya! 🙌 Free demo set karne ke liye bas 5 chhoti details chahiye, "
    "taaki hamari team aapko sahi time par call kar sake. "
    "(Ye sirf demo ke liye use hongi.)"
)

ASK = {
    "name": "Aapka naam kya hai?",
    "whatsapp": "Aapka WhatsApp number? (10 digit) 📱",
    "team_size": "Aapki team mein kitne log hain? (jaise 3, 10, 25)",
    "current_tool": "Abhi leads kaise manage karte hain? (Excel, register, koi aur CRM…) — na batana ho to *skip* likhiye",
    "demo_time": "Demo call ke liye kaunsa time theek rahega? (jaise kal 5 baje, Saturday subah)",
}

RETRY = {
    "name": "Sirf aapka naam likh dijiye 🙂",
    "whatsapp": "Ye number sahi nahi lag raha 🤔 10 digit ka mobile number bhejiye, jaise 98XXXXXXXX",
    "team_size": "Team mein lagbhag kitne log hain? Sirf number likh dijiye 🙂",
    "current_tool": "Excel, register, WhatsApp ya koi CRM? Ya *skip* likh dijiye.",
    "demo_time": "Koi bhi din aur time bata dijiye, jaise \"kal 5 baje\" 🙂",
}

# Re-ask after answering a question mid-flow
BACK_TO_FLOW = "Demo ke liye — {question}"

LEAD_DONE = (
    "Shukriya {name} ji 🙏 Aapki demo request mil gayi!\n"
    "Hamari team aapko *{demo_time}* WhatsApp/call karegi.\n"
    "Kuch aur poochna ho to yahin likhiye."
)

ALREADY_DONE = (
    "Aapki demo request pehle se hamare paas hai ✅ Team jaldi contact karegi. "
    "Kuch badalna ho to *team* likhiye."
)

COLLECT_PAUSED = (
    "Theek hai 👍 Jab ready hon, *demo* likh dijiye — wahin se aage badhenge."
)

# ---------- Handoff / opt-out ----------
HANDOFF = (
    "Main ye hamari team ko bhej raha hoon 🙏 Ek team member jaldi yahin jawab dega."
)

OPT_OUT = (
    "Theek hai, ab aapko automatic messages nahi aayenge 🙏 "
    "Dobara baat karni ho to *START* likhiye."
)

OPT_IN = "Welcome back 🙏 Free demo chahiye to *demo* likhiye, ya koi bhi sawaal poochiye 😊"

# ---------- Comments ----------
# Public reply under the post/Reel (short, never contains details)
COMMENT_PUBLIC_INTERESTED = "@{username} aapko DM kiya hai 📩"
COMMENT_PUBLIC_THANKS = "@{username} Thank you 🙏"
COMMENT_PUBLIC_RECENT = "@{username} DM check kijiye 📩"  # we already DMed them in the last 24h
COMMENT_PUBLIC_DONE = "@{username} ji, aapki demo request hamare paas hai — team jaldi contact karegi 🙏"

# Private reply (DM) sent from a comment. Instagram allows one per comment.
COMMENT_PRIVATE_OPENER = (
    "Namaste 🙏 Aapne ViaCRM ki post par comment kiya tha, isliye message kar rahe hain.\n"
    "{answer}\n\n"
    "Free demo chahiye to yahan *demo* reply kijiye. "
    "Message nahi chahiye to *STOP* likhiye."
)
COMMENT_DEFAULT_ANSWER = (
    "ViaCRM real estate teams ke liye CRM hai — enquiries, follow-ups, site visits aur bookings ek jagah."
)

# ---------- Notifications to Akshay (not sent to customers) ----------
NOTIFY_LEAD = "🟢 Naya ViaCRM demo lead: {name} | {whatsapp} | team {team_size} | tool: {current_tool} | time: {demo_time} | IG @{username}"
NOTIFY_HANDOFF = "🟠 IG par human chahiye: @{username} — \"{text}\""
