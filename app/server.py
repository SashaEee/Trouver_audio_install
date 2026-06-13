"""Roomtone backend — Flask. Real Trouver/Dreame cloud auth, no password storage."""
import os
import re
import json
import secrets
import tempfile

from flask import Flask, request, jsonify, session, send_from_directory, send_file, abort

from dreame_client import DreameCloud, CloudError, AuthError, BRANDS, REGIONS
import events as ev
import builder

HERE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=os.path.join(HERE, "static"), static_url_path="")
app.secret_key = os.environ.get("ROOMTONE_SECRET", secrets.token_hex(16))
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB upload ceiling

# server-side session store: sid -> {"cloud": <to_session dict>, "edits": {...}}
STORE = {}

# ready-made packs the robot can install (host must be reachable by the robot)
LIBRARY = [
    {"id": "RU", "name": "Штатный русский", "kind": "official", "coverage": 116,
     "url": "https://oss.iot.dreame.tech/dreame-product/resources/f5755224d0f0ea11233d3758a6fb590d",
     "md5": "f5755224d0f0ea11233d3758a6fb590d", "size": 662094, "tag": "official"},
    {"id": "EN", "name": "English (стоковый)", "kind": "official", "coverage": 116,
     "url": "https://oss.iot.dreame.tech/dreame-product/resources/4ff3cd22ef6a3ae45dcc88e791e3d29a",
     "md5": "4ff3cd22ef6a3ae45dcc88e791e3d29a", "size": 551443, "tag": "official"},
    {"id": "MX", "name": "Максим — нецензурный", "kind": "community", "coverage": 65,
     "url": "https://raw.githubusercontent.com/SashaEee/Trouver_audio_install/main/packs/maxim_full.tar.gz",
     "md5": "826b3de2731432d7a2075d4574b36134", "size": 648531, "tag": "18+"},
    {"id": "SW", "name": "Звёздные войны — R2-D2", "kind": "community", "coverage": 116,
     "url": "https://raw.githubusercontent.com/SashaEee/Trouver_audio_install/main/packs/starwars_r2d2.tar.gz",
     "md5": "9014c6f0c0dc6cbd1df3020b52ea5274", "size": 283176, "tag": "дроид"},
    {"id": "GL", "name": "GLaDOS — Portal", "kind": "community", "coverage": 79,
     "url": "https://raw.githubusercontent.com/SashaEee/Trouver_audio_install/main/packs/glados.tar.gz",
     "md5": "32a61328ad74d16cb521ca02807b540c", "size": 290628, "tag": "EN"},
    {"id": "KZ", "name": "Домовёнок Кузя", "kind": "community", "coverage": 57,
     "url": "https://raw.githubusercontent.com/SashaEee/Trouver_audio_install/main/packs/kuzya.tar.gz",
     "md5": "42e9f59128e80658957d75e3d91bcf04", "size": 380678, "tag": "сказка"},
    {"id": "K3", "name": "Кузя (вариант 3)", "kind": "community", "coverage": 70,
     "url": "https://raw.githubusercontent.com/SashaEee/Trouver_audio_install/main/packs/kuzya3.tar.gz",
     "md5": "03874fa9cc248629bf61fbf3c93743de", "size": 506135, "tag": "сказка"},
    {"id": "BT", "name": "Супер ботаник", "kind": "community", "coverage": 57,
     "url": "https://raw.githubusercontent.com/SashaEee/Trouver_audio_install/main/packs/botanik.tar.gz",
     "md5": "0654865dd343e27d20b87283b1188928", "size": 338718, "tag": "18+"},
    {"id": "GA", "name": "Дерзкая Галя", "kind": "community", "coverage": 81,
     "url": "https://raw.githubusercontent.com/SashaEee/Trouver_audio_install/main/packs/galya.tar.gz",
     "md5": "d2c9cbd485a4f203bb7c6eb418a5b089", "size": 416310, "tag": "18+"},
    {"id": "RM", "name": "Рик и Морти", "kind": "community", "coverage": 34,
     "url": "https://raw.githubusercontent.com/SashaEee/Trouver_audio_install/main/packs/rickmorty.tar.gz",
     "md5": "65b11ebdcd5f75d6ab647be7ae16ca96", "size": 406795, "tag": "18+"},
    {"id": "EL", "name": "Элеонора", "kind": "community", "coverage": 34,
     "url": "https://raw.githubusercontent.com/SashaEee/Trouver_audio_install/main/packs/eleonora.tar.gz",
     "md5": "f23480e805f2950fae47c49658026179", "size": 442807, "tag": "голос"},
    {"id": "DB", "name": "Добкин", "kind": "community", "coverage": 23,
     "url": "https://raw.githubusercontent.com/SashaEee/Trouver_audio_install/main/packs/dobkin.tar.gz",
     "md5": "2f8ec687ce40286a4a34f9984d4513cb", "size": 336898, "tag": "голос"},
    {"id": "SV", "name": "Советские фильмы", "kind": "community", "coverage": 94,
     "url": "https://raw.githubusercontent.com/SashaEee/Trouver_audio_install/main/packs/sovet.tar.gz",
     "md5": "88dce38c3b75007dc4cb210b8bca60fb", "size": 577978, "tag": "кино"},
    {"id": "MU", "name": "Кузя + Винни + Остров", "kind": "community", "coverage": 94,
     "url": "https://raw.githubusercontent.com/SashaEee/Trouver_audio_install/main/packs/multi.tar.gz",
     "md5": "f6ff5386aae0930fae5349cc0dbb0f67", "size": 635741, "tag": "сборник"},
    {"id": "AL", "name": "Алиса", "kind": "community", "coverage": 13,
     "url": "https://raw.githubusercontent.com/SashaEee/Trouver_audio_install/main/packs/alice_ru.tar.gz",
     "md5": "1ac3664599c347cfcf570d896a7f1479", "size": 339642, "tag": "голос"},
    {"id": "WC", "name": "Warcraft", "kind": "community", "coverage": 20,
     "url": "https://raw.githubusercontent.com/SashaEee/Trouver_audio_install/main/packs/warcraft.tar.gz",
     "md5": "f1401ff2d4ce0d23d090425af4d2ca9b", "size": 348993, "tag": "игра"},
]
_LIB = {p["id"]: p for p in LIBRARY}

MY_ID = "MY"  # the user's own pack (official RU base + their replacements)


def _sid():
    return session.get("sid")


def _cloud():
    sid = _sid()
    if not sid or sid not in STORE:
        return None
    return DreameCloud.from_session(STORE[sid]["cloud"])


def _save(cloud):
    STORE[_sid()]["cloud"] = cloud.to_session()


def _edits():
    """Per-session map eid -> {kind, label, size, duration}."""
    return STORE[_sid()].setdefault("edits", {})


def _custom():
    """Last built custom pack info for this session, or None."""
    return STORE[_sid()].get("custom")


def _known_event_ids(c, did):
    dev = next((x for x in c.devices if x["did"] == str(did)), None)
    model = dev["model"] if dev else "trouver.vacuum.r2567r"
    return model, {it["id"] for it in ev.build_events(model)}


def need_auth():
    return jsonify({"error": "not_authenticated"}), 401


@app.post("/api/login")
def login():
    d = request.get_json(force=True, silent=True) or {}
    email = (d.get("email") or "").strip()
    password = d.get("password") or ""
    brand = d.get("brand", "trouver")
    region = d.get("region", "ru")
    if not email or not password:
        return jsonify({"error": "email и пароль обязательны"}), 400
    if brand not in BRANDS or region not in REGIONS:
        return jsonify({"error": "неизвестный бренд/регион"}), 400
    try:
        c = DreameCloud(brand, region)
        c.login(email, password)
        devices = c.get_devices()
    except AuthError as e:
        return jsonify({"error": f"вход не удался: {e}"}), 401
    except CloudError as e:
        return jsonify({"error": f"облако: {e}"}), 502
    sid = secrets.token_hex(16)
    session["sid"] = sid
    session.permanent = True
    STORE[sid] = {"cloud": c.to_session(), "edits": {}}
    return jsonify({"ok": True, "brand": brand, "region": region, "devices": devices})


@app.post("/api/logout")
def logout():
    sid = _sid()
    if sid and sid in STORE:
        for eid in STORE[sid].get("edits", {}):
            builder.remove(eid)
        STORE.pop(sid, None)
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/session")
def whoami():
    c = _cloud()
    if not c:
        return need_auth()
    return jsonify({"ok": True, "brand": c.brand, "region": c.region, "devices": c.devices})


@app.get("/api/state")
def state():
    c = _cloud()
    if not c:
        return need_auth()
    did = request.args.get("did")
    try:
        st = c.voice_state(did)
        _save(c)
        return jsonify(st)
    except CloudError as e:
        return jsonify({"error": str(e)}), 502


@app.get("/api/library")
def library():
    packs = list(LIBRARY)
    cust = _custom() if _sid() in STORE else None
    if cust:
        packs.insert(0, {"id": MY_ID, "name": "Моя озвучка", "kind": "custom",
                         "coverage": cust.get("coverage", 0), "tag": "своя"})
    return jsonify({"packs": packs})


@app.get("/api/events")
def list_events():
    c = _cloud()
    if not c:
        return need_auth()
    did = request.args.get("did")
    dev = next((x for x in c.devices if x["did"] == str(did)), None)
    model = dev["model"] if dev else "trouver.vacuum.r2567r"
    items = ev.build_events(model)
    maxim_ids = ev.load_maxim_ids()
    active = None
    try:
        active = c.voice_state(did).get("active")
        _save(c)
    except CloudError:
        pass
    edits = _edits()
    cov = _covered_ids(active, maxim_ids)
    for it in items:
        if it["id"] in edits:
            it["source"] = "custom"
            it["custom"] = edits[it["id"]]
        elif active not in (None, "RU", "EN", "MY") and (cov is None or it["id"] in cov):
            it["source"] = "pack"
        else:
            it["source"] = "stock"
    counts = {}
    for it in items:
        counts[it["source"]] = counts.get(it["source"], 0) + 1
    return jsonify({"model": model, "active": active, "events": items,
                    "categories": ev.CATEGORY_LABELS, "counts": counts})


@app.post("/api/volume")
def volume():
    c = _cloud()
    if not c:
        return need_auth()
    d = request.get_json(force=True, silent=True) or {}
    try:
        c.set_volume(d.get("did"), d.get("level", 80))
        _save(c)
        return jsonify({"ok": True})
    except CloudError as e:
        return jsonify({"error": str(e)}), 502


@app.post("/api/activate")
def activate():
    c = _cloud()
    if not c:
        return need_auth()
    d = request.get_json(force=True, silent=True) or {}
    try:
        c.activate(d.get("did"), d.get("id"))
        _save(c)
        return jsonify({"ok": True})
    except CloudError as e:
        return jsonify({"error": str(e)}), 502


@app.post("/api/install")
def install():
    c = _cloud()
    if not c:
        return need_auth()
    d = request.get_json(force=True, silent=True) or {}
    pid = d.get("id")
    pack = _LIB.get(pid)
    if pid == MY_ID and _custom():
        cu = _custom()
        url, md5, size = cu["url"], cu["md5"], cu["size"]
    elif pack:
        url, md5, size = pack["url"], pack["md5"], pack["size"]
    else:
        url, md5, size = d.get("url"), d.get("md5"), d.get("size")
    if not (url and md5 and size):
        return jsonify({"error": "нужны url/md5/size или известный пак"}), 400
    try:
        res = c.install(d.get("did"), pid, url, md5, size)
        _save(c)
        return jsonify({"ok": True, "result": res})
    except CloudError as e:
        return jsonify({"error": str(e)}), 502


# ---- custom audio: build your own lines ------------------------------------
def _guard_eid(c, did, eid):
    eid = re.sub(r"[^0-9A-Za-z]", "", eid or "")
    model, ids = _known_event_ids(c, did)
    if eid not in ids:
        abort(400, "неизвестное событие")
    return eid


@app.post("/api/tts")
def tts():
    c = _cloud()
    if not c:
        return need_auth()
    d = request.get_json(force=True, silent=True) or {}
    eid = _guard_eid(c, d.get("did"), d.get("eid"))
    text = (d.get("text") or "").strip()
    if not text:
        return jsonify({"error": "введите текст"}), 400
    try:
        info = builder.make_from_text(eid, text, voice=d.get("voice") or builder.RU_VOICE)
    except builder.BuildError as e:
        return jsonify({"error": str(e)}), 400
    _edits()[eid] = {"kind": "tts", "label": text[:60], "size": info["size"],
                     "duration": info.get("duration")}
    return jsonify({"ok": True, **info})


@app.post("/api/upload")
def upload():
    c = _cloud()
    if not c:
        return need_auth()
    eid = _guard_eid(c, request.form.get("did"), request.form.get("eid"))
    f = request.files.get("audio")
    if not f:
        return jsonify({"error": "нет файла"}), 400
    start = request.form.get("start") or None
    dur = request.form.get("dur") or None
    suffix = os.path.splitext(f.filename or "")[1][:8] or ".bin"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        f.save(tmp.name)
        tmp.close()
        info = builder.make_from_file(eid, tmp.name, start=start, dur=dur)
    except builder.BuildError as e:
        return jsonify({"error": f"не получилось обработать аудио: {e}"}), 400
    finally:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)
    label = (f.filename or "запись")[:60]
    _edits()[eid] = {"kind": "file", "label": label, "size": info["size"],
                     "duration": info.get("duration")}
    return jsonify({"ok": True, **info})


@app.post("/api/remove")
def remove_edit():
    c = _cloud()
    if not c:
        return need_auth()
    d = request.get_json(force=True, silent=True) or {}
    eid = _guard_eid(c, d.get("did"), d.get("eid"))
    builder.remove(eid)
    _edits().pop(eid, None)
    return jsonify({"ok": True})


@app.post("/api/build_install")
def build_install():
    c = _cloud()
    if not c:
        return need_auth()
    d = request.get_json(force=True, silent=True) or {}
    did = d.get("did")
    edits = _edits()
    if not edits:
        return jsonify({"error": "нет своих фраз — сначала запишите хотя бы одну"}), 400
    try:
        raw, md5, size = builder.build_pack(edits.keys())
        url = builder.host_pack(raw, md5)
    except builder.BuildError as e:
        return jsonify({"error": str(e)}), 502
    STORE[_sid()]["custom"] = {"url": url, "md5": md5, "size": size,
                               "coverage": len(edits)}
    try:
        res = c.install(did, MY_ID, url, md5, size)
        _save(c)
        return jsonify({"ok": True, "id": MY_ID, "url": url, "md5": md5,
                        "size": size, "result": res})
    except CloudError as e:
        return jsonify({"error": str(e)}), 502


_WORK = os.path.join(HERE, "..", "media")
DATA = os.path.join(HERE, "data")
_AUDIO_DIRS = {
    "stock": os.path.join(_WORK, "off"),
    "pack": os.path.join(_WORK, "maxim_out"),
    "custom": os.path.join(HERE, "data", "uploads"),
}

# per-pack audio for auditioning a pack before installing it
_PACK_DIRS = {
    "RU": os.path.join(_WORK, "off"),
    "EN": os.path.join(_WORK, "en_out"),
    "MX": os.path.join(_WORK, "maxim_out"),
    "SW": os.path.join(_WORK, "sw_out"),
    "GL": os.path.join(_WORK, "glados_out"),
    "KZ": os.path.join(_WORK, "KZ_out"),
    "K3": os.path.join(_WORK, "K3_out"),
    "BT": os.path.join(_WORK, "BT_out"),
    "GA": os.path.join(_WORK, "GA_out"),
    "RM": os.path.join(_WORK, "RM_out"),
    "EL": os.path.join(_WORK, "EL_out"),
    "DB": os.path.join(_WORK, "DB_out"),
    "SV": os.path.join(_WORK, "SV_out"),
    "MU": os.path.join(_WORK, "MU_out"),
    "AL": os.path.join(_WORK, "AL_out"),
    "WC": os.path.join(_WORK, "WC_out"),
}
_RU_BASE = os.path.join(_WORK, "off")


def _load_ids(path, frommap=False):
    try:
        d = json.load(open(os.path.join(DATA, path)))
        return {k for k in d if not k.startswith("_")}
    except Exception:
        return set()


# r2567r event ids each community pack actually voices (for the dictionary coloring)
_BRIDGE_IDS = _load_ids("bridge_r2567r_to_dreame.json")
_PACK_IDS = {
    "RM": _load_ids("map_s4_roborock.json"), "EL": _load_ids("map_s4_roborock.json"),
    "DB": _load_ids("map_s4_dobkin.json"), "WC": _load_ids("map_s4_dobkin.json"),
    "SV": _load_ids("map_SV.json"), "MU": _load_ids("map_MU.json"), "AL": _load_ids("map_AL.json"),
}


def _covered_ids(active, maxim_ids):
    """Which r2567r events the active pack voices. None = all of them."""
    if active == "MX":
        return maxim_ids
    if active == "SW":                              # language-neutral, full coverage
        return None
    if active in ("GL", "KZ", "K3", "BT", "GA"):    # bridge (Valetudo-numbered) packs
        return _BRIDGE_IDS
    if active in _PACK_IDS:
        return _PACK_IDS[active]
    return set()

# lines users actually recognise, in the order they'd hear them
_SIGNATURE = ["003", "006", "010", "045", "011", "012", "008", "090"]


@app.get("/api/audio/<src>/<eid>")
def audio(src, eid):
    base = _AUDIO_DIRS.get(src)
    eid = re.sub(r"[^0-9A-Za-z_]", "", eid)
    if not base or not eid:
        abort(404)
    path = os.path.join(base, f"{eid}.mp3")
    if not os.path.isfile(path):
        abort(404)
    return send_file(path, mimetype="audio/mpeg")


@app.get("/api/packaudio/<pid>/<eid>")
def packaudio(pid, eid):
    eid = re.sub(r"[^0-9A-Za-z_]", "", eid)
    if not eid:
        abort(404)
    if pid == MY_ID:
        base = os.path.join(HERE, "data", "uploads")
    else:
        base = _PACK_DIRS.get(pid)
    if not base:
        abort(404)
    path = os.path.join(base, f"{eid}.mp3")
    if not os.path.isfile(path):  # not overridden by this pack -> RU base line
        path = os.path.join(_RU_BASE, f"{eid}.mp3")
    if not os.path.isfile(path):
        abort(404)
    return send_file(path, mimetype="audio/mpeg")


@app.get("/api/preview/<pid>")
def preview(pid):
    """Signature lines to audition a pack, with their meanings."""
    c = _cloud()
    if not c:
        return need_auth()
    titles = {it["id"]: it["title"] for it in ev.build_events("trouver.vacuum.r2567r")}
    if pid == MY_ID:
        ids = list(_edits().keys())[:8]
    elif pid == "MX":
        mids = ev.load_maxim_ids()
        ids = [i for i in _SIGNATURE if i in mids] or [i for i in sorted(mids)][:6]
    else:
        ids = list(_SIGNATURE)
    base = _PACK_DIRS.get(pid) if pid != MY_ID else os.path.join(HERE, "data", "uploads")
    items = []
    for eid in ids:
        if base and (os.path.isfile(os.path.join(base, f"{eid}.mp3"))
                     or os.path.isfile(os.path.join(_RU_BASE, f"{eid}.mp3"))):
            items.append({"eid": eid, "title": titles.get(eid, f"Событие {eid}")})
    return jsonify({"id": pid, "items": items[:8]})


@app.get("/")
def root():
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"),
            port=int(os.environ.get("PORT", "8765")), debug=False)
