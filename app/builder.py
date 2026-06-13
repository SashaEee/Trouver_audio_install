"""Custom voice-pack builder for Roomtone.

Turns a user's own clips (recording / upload / typed text) into the exact
format r2567r expects (MP3 16 kHz mono ~16 kbps, files ``./NNN.mp3`` in a flat
gzip tar), starting from the official Russian base so untouched events keep
their stock voice. Hosts the result on GitHub so the robot can fetch it.
"""
import os
import io
import json
import base64
import hashlib
import tarfile
import subprocess
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.join(HERE, "..", "media", "off")      # official RU mp3s (./NNN.mp3)
UPLOAD_DIR = os.path.join(HERE, "data", "uploads")       # per-event custom mp3s
BUILD_DIR = os.path.join(HERE, "data", "build")

MAX_CLIP_SEC = 15          # cap a single line so a whole song can't sneak in
RU_VOICE = "Milena"        # macOS built-in ru_RU voice

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(BUILD_DIR, exist_ok=True)


class BuildError(Exception):
    pass


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise BuildError((r.stderr or r.stdout or " ".join(cmd))[-300:])


def _encode(src_path, dst_path, start=None, dur=None):
    """Re-encode any audio/video source into the robot's line format."""
    cmd = ["ffmpeg", "-y"]
    if start:
        cmd += ["-ss", str(float(start))]
    cmd += ["-i", src_path]
    clip = float(dur) if dur else MAX_CLIP_SEC
    clip = max(0.3, min(clip, MAX_CLIP_SEC))
    cmd += ["-t", str(clip),
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-ar", "16000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "16k",
            "-map_metadata", "-1", dst_path]
    _run(cmd)


def event_mp3_path(eid):
    return os.path.join(UPLOAD_DIR, f"{eid}.mp3")


def make_from_file(eid, src_path, start=None, dur=None):
    """Convert an uploaded audio/video file into the line for *eid*."""
    dst = event_mp3_path(eid)
    _encode(src_path, dst, start=start, dur=dur)
    return _probe(dst)


def make_from_text(eid, text, voice=RU_VOICE):
    """Speak *text* with a macOS voice, then encode it as the line for *eid*."""
    text = (text or "").strip()
    if not text:
        raise BuildError("пустой текст")
    aiff = os.path.join(UPLOAD_DIR, f"_{eid}.aiff")
    try:
        _run(["say", "-v", voice, "-o", aiff, text])
        dst = event_mp3_path(eid)
        _encode(aiff, dst)
    finally:
        if os.path.exists(aiff):
            os.remove(aiff)
    return _probe(event_mp3_path(eid))


def remove(eid):
    p = event_mp3_path(eid)
    if os.path.exists(p):
        os.remove(p)


def _probe(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "json", path], capture_output=True, text=True).stdout
        dur = float(json.loads(out)["format"]["duration"])
    except Exception:
        dur = None
    return {"size": os.path.getsize(path), "duration": dur}


def build_pack(edits):
    """Build official RU base + per-event overrides into a tar.gz.

    *edits* is an iterable of event ids that have a file in UPLOAD_DIR.
    Returns (tar_bytes, md5, size).
    """
    base = {f[:-4]: os.path.join(BASE_DIR, f)
            for f in os.listdir(BASE_DIR) if f.endswith(".mp3")}
    files = dict(base)
    for eid in edits:
        p = event_mp3_path(eid)
        if os.path.isfile(p):
            files[eid] = p
    if not files:
        raise BuildError("нет файлов для сборки")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for eid in sorted(files):
            tf.add(files[eid], arcname=f"./{eid}.mp3")
    raw = buf.getvalue()
    return raw, hashlib.md5(raw).hexdigest(), len(raw)


# ---- GitHub hosting (token from env GH_TOKEN; never persisted in code) -------
_API = "https://api.github.com"


def _gh(method, path, body=None):
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise BuildError("нет GitHub-токена для размещения пака (GH_TOKEN)")
    url = path if path.startswith("http") else _API + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "roomtone")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.loads(r.read() or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or "null")


def host_pack(raw, md5, repo=os.environ.get("GH_REPO", "vac-voice")):
    """Upload tar bytes to a public GitHub repo, return a robot-reachable raw URL.

    Content-addressed filename: identical content reuses the URL, changed
    content gets a fresh one (so the robot never fetches a stale cached file).
    """
    st, me = _gh("GET", "/user")
    if st != 200:
        raise BuildError(f"GitHub: токен не принят [{st}]")
    owner = me["login"]

    st, _ = _gh("GET", f"/repos/{owner}/{repo}")
    if st == 404:
        st, r = _gh("POST", "/user/repos",
                    {"name": repo, "private": False, "auto_init": True,
                     "description": "vacuum voice packs"})
        if st not in (200, 201):
            raise BuildError(f"GitHub: не создать репозиторий [{st}]")

    name = f"my_{md5}.tar.gz"
    cdn = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{name}"
    st, info = _gh("GET", f"/repos/{owner}/{repo}/contents/{name}")
    if st == 200 and isinstance(info, dict) and "sha" in info:
        return cdn  # already hosted with identical content
    body = {"message": f"add {name}", "content": base64.b64encode(raw).decode(),
            "branch": "main"}
    st, r = _gh("PUT", f"/repos/{owner}/{repo}/contents/{name}", body)
    if st not in (200, 201):
        raise BuildError(f"GitHub: загрузка не удалась [{st}]")
    return cdn
