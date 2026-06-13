# Add your own pack

There are two ways: **inside the app** (easiest) or **from the command line** (for whole packs).

## A) In the web UI — per‑line

Open any event → choose a method:

- **Text → voice** — type what the robot should say (offline TTS).
- **Record** — capture your own voice from the mic.
- **File** — drop in any audio/video; the first 15 s are used.

Hit **Build & install** and the app builds `official base + your lines`, hosts it, and installs it.
Hosting your *custom* pack needs a GitHub token:

```bash
echo 'export GH_TOKEN=ghp_xxx' > secret.env   # a fine‑grained PAT with repo contents:write
echo 'export GH_REPO=my-vac-packs' >> secret.env
```

## B) From the command line — whole community pack

### Valetudo‑numbered pack (`N.ogg`, 0–187)

```bash
BR=8k python tools/build_community.py <pack_dir> packs/mypack.tar.gz --ext ogg
# add --fill for language‑neutral packs (droid/beeps) to cover every event
```

### Any other layout

Write a `{r2567r_id: source_filename}` JSON, then:

```bash
BR=8k python tools/build_mapped.py <pack_dir> mymap.json packs/mypack.tar.gz
```

`BASE=off_8k` selects the small base (smaller pack = more reliable install).

### Host it & register it

```bash
GH_TOKEN=ghp_xxx GH_REPO=Trouver_audio_install python tools/gh_host.py packs/mypack.tar.gz
# prints RAW_URL / MD5 / SIZE
```

Add an entry to `LIBRARY` in `app/server.py`:

```python
{"id": "XX", "name": "My pack", "kind": "community", "coverage": 80,
 "url": "<RAW_URL>", "md5": "<MD5>", "size": <SIZE>, "tag": "fun"},
```

Then PR it back so others get it too. 🙌
