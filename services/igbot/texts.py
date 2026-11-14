"""Every message the bot can send. Nothing else is ever sent.
# Texts APPROVED by Akshay on 2026-11-10.
# 2026-11-14 sales-playbook update (qualifying questions, WhatsApp handoff, new FAQs, prices):
# APPROVED by Akshay on 2026-11-14 ("Texts approved"). Re-confirm with him before changing any customer-facing text.

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
    # Prices confirmed by Akshay on 14 Nov 2026 (sales playbook §3)
    "pricing": (
        "Pehle *14 din bilkul free trial* hai 💰 Koi payment nahi, saare features.\n"
        "Uske baad ₹399/user/mahina, ya ₹3,999/user/saal (≈ 2 mahine free).\n"
        "🎁 Founding Dealer offer, sirf pehle 20 companies: *₹249/user/mahina*, 12 mahine ke liye lock.\n"
        "Kam se kam 2 users. Setup aur data import free.\n"
        "Ek portal lead ₹200–500 ki padti hai. Mahine mein 3–4 leads bhi bach gayin to paisa wasool 🙂"
    ),
    "access": (
        "14 din ka free trial hai, setup hum karte hain 🙌 "
        "Aap apni Excel/Google Sheet bhejiye, hum leads ViaCRM mein daal ke login bhej denge."
    ),
    "whatsapp": (
        "Abhi WhatsApp ka direct connection nahi hai 🙏 Client se baat WhatsApp pe hi kariye. "
        "ViaCRM mein bas note aur next follow-up date daal dijiye, taaki koi client bhoole nahi. "
        "Telecallers ke Android phone se calls aur recording ViaCRM mein sync ho jaati hai 📞"
    ),
    "data_safety": (
        "Bilkul sahi sawaal 👍 Aapka data India mein (AWS Mumbai) server par rehta hai, password login ke saath, "
        "aur sirf aapki company dekh sakti hai.\n"
        "• Telecaller sirf apni assigned leads dekhta hai\n"
        "• Kisi agent ko hataya to uska access turant band\n"
        "• Optional 2-step login (authenticator app) bhi hai\n"
        "• Data kabhi bhi Excel mein export kar sakte hain, aap kahin bandhe nahi"
    ),
    "excel": (
        "Excel mein data rehta hai, par Excel subah yaad nahi dilata ki aaj kisko call karna hai, "
        "na batata hai ki telecaller ne call kiya ya nahi 📋\n"
        "Apni Excel bhejiye, hum *free* mein ViaCRM mein daal denge. 14 din dono saath chalaiye, khud farak dekhiye."
    ),
}


DEMO_CTA = "Free demo chahiye to *demo* likhiye 🙂"

# ---------- Lead collection ----------
# Shown once, when someone first shows interest. Says WHY we ask.
START_COLLECT = (
    "ViaCRM mein interest dikhane ke liye shukriya 🙏 "
    "Bas 3 chhoti cheezein bata dijiye, taaki aapke kaam ke hisaab se sahi demo bhejein. "
    "(Ye sirf demo ke liye hai.)"
)

ASK = {
    "name": "Pehle aapka naam?",
    "team_size": "1️⃣ Aapki team mein kitne log hain? (telecaller / site visit wale, jaise 3, 8, 15)",
    "lead_sources": "2️⃣ Leads kahan se aati hain? (99acres/MagicBricks, IndiaMART, Justdial, FB ads, walk-in…)",
    "current_tool": "3️⃣ Abhi leads kahan rakhte ho? (Excel, diary, WhatsApp, koi aur CRM)",
}

RETRY = {
    "name": "Sirf aapka naam likh dijiye 🙂",
    "team_size": "Team mein lagbhag kitne log hain? Sirf number likh dijiye 🙂",
    "lead_sources": "Jaise 99acres, MagicBricks, IndiaMART, Justdial, FB ads ya walk-in? Ya *skip* likhiye.",
    "current_tool": "Excel, diary, WhatsApp ya koi CRM? Ya *skip* likh dijiye.",
}

# Re-ask after answering a question mid-flow
BACK_TO_FLOW = "Demo ke liye — {question}"

# {wa_link} = https://wa.me/<Akshay's WhatsApp Business number>?text=DEMO
LEAD_DONE = (
    "Shukriya {name} ji 🙏 Sab note kar liya!\n"
    "Demo video aur free trial ke liye bas is link par WhatsApp kijiye, *DEMO* pehle se likha hoga 👇\n"
    "{wa_link}\n"
    "Wahan 3 minute ka demo video bhejenge aur aapke sawaalon ka jawab denge."
)
# Used if no WhatsApp number is set yet
LEAD_DONE_NO_WA = (
    "Shukriya {name} ji 🙏 Sab note kar liya!\n"
    "Hamari team jaldi yahin DM mein demo video bhejegi. Kuch aur poochna ho to yahin likhiye."
)

ALREADY_DONE = (
    "Aapki details pehle se hamare paas hain ✅ Demo ke liye is link par WhatsApp kijiye 👇\n{wa_link}"
)
ALREADY_DONE_NO_WA = (
    "Aapki details pehle se hamare paas hain ✅ Team jaldi demo video bhejegi. "
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
COMMENT_PUBLIC_DONE = "@{username} ji, aapki details hamare paas hain, DM check kijiye 📩"

# Private reply (DM) sent from a comment. Instagram allows one per comment.
COMMENT_PRIVATE_OPENER = (
    "Namaste 🙏 Aapne ViaCRM ki post par comment kiya tha, isliye message kar rahe hain.\n"
    "{answer}\n\n"
    "Free demo chahiye to yahan *demo* reply kijiye. "
    "Message nahi chahiye to *STOP* likhiye."
)
# Private reply when the comment itself asks for a demo (e.g. "DEMO"): start the 3 questions right away.
COMMENT_PRIVATE_DEMO = (
    "Namaste 🙏 Aapne ViaCRM ki post par *DEMO* comment kiya tha, isliye message kar rahe hain.\n"
    "{start}\n\n{question}\n\n"
    "Message nahi chahiye to *STOP* likhiye."
)
COMMENT_DEFAULT_ANSWER = (
    "ViaCRM real estate teams ke liye CRM hai — enquiries, follow-ups, site visits aur bookings ek jagah."
)

# ---------- Notifications to Akshay (not sent to customers) ----------
NOTIFY_LEAD = "🟢 Naya ViaCRM lead: {name} | IG @{username} | team {team_size} | leads from: {lead_sources} | kept in: {current_tool}"
NOTIFY_HANDOFF = "🟠 IG par human chahiye: @{username} — \"{text}\""
