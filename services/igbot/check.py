"""Read-only check of the Instagram token in .env (never prints the token).
  .venv/bin/python check.py
"""
import json, os, urllib.request, urllib.error
from dotenv import load_dotenv
load_dotenv()
tok, ig = os.environ.get("IG_ACCESS_TOKEN", ""), os.environ.get("IG_USER_ID", "")
ver = os.getenv("GRAPH_VERSION", "v24.0")
if not tok:
    raise SystemExit("IG_ACCESS_TOKEN is empty in .env")
for host in ("graph.facebook.com", "graph.instagram.com"):
    url = f"https://{host}/{ver}/{ig}?fields=id,username"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    try:
        print(host, "OK", json.loads(urllib.request.urlopen(req, timeout=15).read()))
    except urllib.error.HTTPError as e:
        print(host, "ERR", e.code, json.loads(e.read()).get("error", {}).get("message"))
