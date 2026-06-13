#!/usr/bin/env python3
"""Upload a file to a public GitHub repo and print its raw URL.

Token read from env GH_TOKEN (never hard-coded). Creates the repo if missing,
creates-or-updates the file via the Contents API (handles binary via base64).
"""
import os
import sys
import json
import base64
import hashlib
import urllib.request

TOKEN = os.environ["GH_TOKEN"]
REPO = os.environ.get("GH_REPO", "vac-voice")
LOCAL = sys.argv[1] if len(sys.argv) > 1 else "work/leather_bastards.tar.gz"
REMOTE = os.path.basename(LOCAL)
API = "https://api.github.com"


def api(method, path, body=None):
    url = path if path.startswith("http") else API + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "vac-voice-uploader")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or "null")


def main():
    st, me = api("GET", "/user")
    if st != 200:
        print(f"[!] token check failed [{st}]: {me}")
        sys.exit(1)
    owner = me["login"]
    print(f"[+] authenticated as {owner}")

    # ensure repo exists
    st, _ = api("GET", f"/repos/{owner}/{REPO}")
    if st == 404:
        st, r = api("POST", "/user/repos",
                    {"name": REPO, "private": False, "auto_init": True,
                     "description": "vacuum voice packs"})
        if st not in (200, 201):
            print(f"[!] repo create failed [{st}]: {r}")
            sys.exit(1)
        print(f"[+] created public repo {owner}/{REPO}")
    else:
        print(f"[+] repo {owner}/{REPO} already exists")

    raw = open(LOCAL, "rb").read()
    md5 = hashlib.md5(raw).hexdigest()
    content_b64 = base64.b64encode(raw).decode()

    # need existing sha to update
    st, info = api("GET", f"/repos/{owner}/{REPO}/contents/{REMOTE}")
    body = {"message": f"add {REMOTE}", "content": content_b64, "branch": "main"}
    if st == 200 and isinstance(info, dict) and "sha" in info:
        body["sha"] = info["sha"]
    st, r = api("PUT", f"/repos/{owner}/{REPO}/contents/{REMOTE}", body)
    if st not in (200, 201):
        print(f"[!] upload failed [{st}]: {r}")
        sys.exit(1)

    raw_url = f"https://raw.githubusercontent.com/{owner}/{REPO}/main/{REMOTE}"
    print(f"[+] uploaded {REMOTE} ({len(raw)} bytes, md5 {md5})")
    print(f"RAW_URL={raw_url}")
    print(f"MD5={md5}")
    print(f"SIZE={len(raw)}")


if __name__ == "__main__":
    main()
