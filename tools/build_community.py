#!/usr/bin/env python3
"""Convert a Dreame/Valetudo-numbered voice pack into r2567r format.

Uses work/bridge_r2567r_to_dreame.json (r2567r id -> Dreame number) to place
each source line on the right r2567r event, starting from the official RU base
so unmapped events keep a sensible Russian voice. Output is MP3 16 kHz mono
./NNN.mp3, exactly what the robot expects.

Usage:
  python build_community.py <pack_dir> <out_tar> [--fill] [--ext ogg]
    <pack_dir>  dir with Dreame-numbered files (e.g. 7.ogg, 45.ogg)
    --fill      also cover bridge-less events with leftover clips
                (for language-neutral packs like R2D2 -> full coverage)
"""
import os
import sys
import json
import hashlib
import tarfile
import argparse
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
OFF = os.path.join(ROOT, "work", os.environ.get("BASE", "off"))
BRIDGE = os.path.join(ROOT, "work", "bridge_r2567r_to_dreame.json")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(" ".join(cmd[:3]) + " … : " + (r.stderr or "")[-200:])


_BR = os.environ.get("BR", "16k")  # audio bitrate; lower = smaller pack = more reliable robot download


def encode(src, dst):
    run(["ffmpeg", "-y", "-i", src,
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
         "-ar", "16000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", _BR,
         "-map_metadata", "-1", dst])


def src_for(pack_dir, num, ext):
    for e in (ext, "ogg", "wav", "mp3", "opus"):
        p = os.path.join(pack_dir, f"{num}.{e}")
        if os.path.isfile(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pack_dir")
    ap.add_argument("out_tar")
    ap.add_argument("--fill", action="store_true")
    ap.add_argument("--ext", default="ogg")
    a = ap.parse_args()

    bridge = {k: v for k, v in json.load(open(BRIDGE)).items() if not k.startswith("_")}
    base = {f[:-4]: os.path.join(OFF, f) for f in os.listdir(OFF) if f.endswith(".mp3")}

    work = os.path.join(ROOT, "work", "community_build")
    os.makedirs(work, exist_ok=True)
    files = dict(base)            # start from RU base
    used_nums = set()
    voiced = 0

    # 1) bridge-mapped events
    for eid, num in bridge.items():
        src = src_for(a.pack_dir, num, a.ext)
        if not src:
            continue
        dst = os.path.join(work, f"{eid}.mp3")
        encode(src, dst)
        files[eid] = dst
        used_nums.add(str(num))
        voiced += 1

    # 2) optional fill for language-neutral packs -> cover every base event
    if a.fill:
        avail = sorted((f for f in os.listdir(a.pack_dir)
                        if f.rsplit(".", 1)[-1] in ("ogg", "wav", "mp3", "opus")),
                       key=lambda x: int("".join(c for c in x if c.isdigit()) or 0))
        leftover = [f for f in avail if f.rsplit(".", 1)[0] not in used_nums]
        li = 0
        for eid in sorted(base):
            if eid in bridge:
                continue
            if not leftover:
                break
            src = os.path.join(a.pack_dir, leftover[li % len(leftover)])
            li += 1
            dst = os.path.join(work, f"{eid}.mp3")
            encode(src, dst)
            files[eid] = dst
            voiced += 1

    # 3) tar exactly like the official pack
    with tarfile.open(a.out_tar, "w:gz") as tf:
        for eid in sorted(files):
            tf.add(files[eid], arcname=f"./{eid}.mp3")
    raw = open(a.out_tar, "rb").read()
    md5 = hashlib.md5(raw).hexdigest()
    print(f"[+] {a.out_tar}: {len(files)} files, {voiced} voiced by pack, "
          f"size={len(raw)} md5={md5}")
    print(f"MD5={md5}\nSIZE={len(raw)}")


if __name__ == "__main__":
    main()
