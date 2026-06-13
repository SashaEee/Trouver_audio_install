# How it works

## The pack format (what the robot wants)

`trouver.vacuum.r2567r` (and its Dreame siblings) play a voice pack that is:

- a **flat gzip tarball**, entries named `./NNN.mp3` (zero‑padded 3‑digit + leading `./`),
- each file **MP3, 16 kHz, mono, ~8–16 kbps**.

`NNN` is an **event id** — 003 = startup, 006 = start cleaning, 045 = "I'm here", and so on. The
full meaning table lives in [`app/data/r2567r_events.json`](../app/data/r2567r_events.json) (built
by transcribing the official pack).

## Installing over the cloud (no root)

Login is an OAuth2 password grant against the brand's cloud (`*.iot.trouver-tech.com`, region‑
prefixed). The pack is then installed with a MiOT `set_property` call:

```
siid 7 / piid 4  ←  {"id": "<pack>", "url": "<https url>", "md5": "<md5>", "size": <bytes>}
```

The robot downloads the tarball itself, so **the URL must return HTTP 200 with no redirect** and be
reachable from the robot's network. `piid 1` = volume, `piid 2` = active pack, `piid 3` = status
(`{"id","progress","state"}`). RoboVoice polls `piid 3` for honest progress and retries on `fail`.

> On `r2567r`, installing **auto‑activates**, and there's a **single custom‑pack slot** — installing
> a new community pack replaces the previous one. Stock RU/EN always stay available.

## The bridge (why re‑mapping is needed)

Community packs are numbered for **Roborock/Valetudo** or **mihome**, not for `r2567r`. So RoboVoice
maps **meaning → meaning**:

```
r2567r event  ──(meaning)──►  canonical Dreame sound_list number  ──►  source file
```

`app/data/bridge_r2567r_to_dreame.json` holds that bridge (~81 events), built once and reused for
any Dreame/Valetudo‑numbered pack.

## Four community pack layouts handled

| Layout | Example | Mapper |
|---|---|---|
| Valetudo `N.ogg` (0–187) | `7.ogg` | bridge (direct) |
| mihome "tens" `NN.mp3` | `010.mp3`, `580.mp3` | functional lines + comedy fill |
| `event_variant` | `12_4.mp3` | event group → r2567r |
| Named files | `39sound_I_am_here.mp3` | name → r2567r |

`tools/build_community.py` handles Valetudo‑numbered packs; `tools/build_mapped.py` takes an explicit
`{r2567r_id: source_file}` map for the rest.

## Reliability: keep packs small

The robot's downloader is routed through China and reaches `raw.githubusercontent.com` only
intermittently — large files drop near 100%. Packs are encoded at **8 kbps** (6 kbps for the biggest)
onto an 8 kbps base so every pack lands at **~290–640 KB**, which installs first‑try in practice.
(jsDelivr / other CDNs were tested and are **not** reachable from the robot.)
