"""Small admin tool.

  .venv/bin/python cli.py leads            list saved leads
  .venv/bin/python cli.py paused           chats handed to a human (bot is silent there)
  .venv/bin/python cli.py resume IGSID     give a chat back to the bot
  .venv/bin/python cli.py refresh-token    renew the 60-day Instagram token in .env
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
import os  # noqa: E402

import store  # noqa: E402

cmd = sys.argv[1] if len(sys.argv) > 1 else ""
if cmd == "leads":
    for l in store.leads():
        g = lambda k: str(l.get(k) or "-")
        print(f"{l['id']:>3}  {g('name'):<20} @{g('username'):<20} team {g('team_size'):<4} from: {g('lead_sources'):<25} kept in: {g('current_tool')}")
elif cmd == "paused":
    for p in store.paused():
        print(p["igsid"], "@" + (p["username"] or "?"))
elif cmd == "resume" and len(sys.argv) > 2:
    store.set_state(sys.argv[2], "new")
    print("bot resumed for", sys.argv[2])
elif cmd == "refresh-token":
    url = "https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=" + os.environ["IG_ACCESS_TOKEN"]
    tok = json.loads(urllib.request.urlopen(url).read())["access_token"]
    env = Path(".env")
    env.write_text(re.sub(r"(?m)^IG_ACCESS_TOKEN=.*$", "IG_ACCESS_TOKEN=" + tok, env.read_text()))
    print("token refreshed in .env (valid ~60 more days)")
else:
    print(__doc__)
