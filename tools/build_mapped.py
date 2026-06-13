#!/usr/bin/env python3
"""Build an r2567r pack from an explicit {r2567r_id: source_file} mapping.

Scheme-agnostic: whatever the source pack's naming, you give a JSON mapping
each r2567r event id to a source file (relative to pack_dir). Unmapped events
keep the official RU base. Output: MP3 16 kHz mono ./NNN.mp3 gzip-tar.

Usage: python build_mapped.py <pack_dir> <map.json> <out_tar>
"""
import os, sys, json, hashlib, tarfile, subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
OFF = os.path.join(ROOT, "work", os.environ.get("BASE", "off"))


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(" ".join(cmd[:3]) + " … : " + (r.stderr or "")[-200:])


_BR = os.environ.get("BR", "16k")  # lower bitrate = smaller pack = more reliable robot download


def encode(src, dst):
    run(["ffmpeg", "-y", "-i", src, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
         "-ar", "16000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", _BR,
         "-map_metadata", "-1", dst])


def main():
    pack_dir, map_path, out_tar = sys.argv[1], sys.argv[2], sys.argv[3]
    mapping = {k: v for k, v in json.load(open(map_path)).items() if not k.startswith("_")}
    base = {f[:-4]: os.path.join(OFF, f) for f in os.listdir(OFF) if f.endswith(".mp3")}

    work = out_tar + ".work"
    os.makedirs(work, exist_ok=True)
    files = dict(base)
    voiced, missing = 0, []
    for eid, rel in mapping.items():
        src = os.path.join(pack_dir, rel)
        if not os.path.isfile(src):
            missing.append(rel); continue
        dst = os.path.join(work, f"{eid}.mp3")
        try:
            encode(src, dst); files[eid] = dst; voiced += 1
        except Exception as e:
            missing.append(f"{rel}:{e}")

    with tarfile.open(out_tar, "w:gz") as tf:
        for eid in sorted(files):
            tf.add(files[eid], arcname=f"./{eid}.mp3")
    raw = open(out_tar, "rb").read()
    md5 = hashlib.md5(raw).hexdigest()
    print(f"[+] {os.path.basename(out_tar)}: {len(files)} files, {voiced} voiced, "
          f"size={len(raw)} md5={md5}")
    if missing:
        print(f"    missing/err ({len(missing)}): {missing[:6]}")
    print(f"MD5={md5}\nSIZE={len(raw)}\nVOICED={voiced}")


if __name__ == "__main__":
    main()
