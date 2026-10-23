#!/usr/bin/env python3
""""Watch" a competitor video (Instagram reel, TikTok, YouTube, Facebook, or a local file):
download it, transcribe the speech, and make contact-sheet images of the frames, so Claude can
read what is said and look at what is shown without anyone playing the video.

  python3 watch_video.py https://www.tiktok.com/@user/video/123 --out videos/tt-user-123
  python3 watch_video.py https://www.instagram.com/reel/ABC/ --cookies ~/Downloads/ig-cookies.txt --out videos/ig-abc
  python3 watch_video.py ad-video.mp4 --out videos/ad1 --every 2

Output folder gets: video.<ext>, info.json (caption, uploader, views, likes when available),
transcript.txt, grid_01.jpg ... (8 frames per sheet), summary.txt (caption + stats + transcript).
Then ask Claude to read summary.txt and view grid_01.jpg.

Needs (not Python standard library, install once):
  brew install yt-dlp ffmpeg
  pip3 install mlx-whisper        (Apple Silicon Macs; fastest)
  or pip3 install openai-whisper  (any machine; slower)
Instagram needs a logged-in cookies file: plain yt-dlp hits the login wall. Export cookies.txt for
instagram.com from a browser where you are logged in (a "cookies.txt" browser extension), or try
--cookies-from-browser chrome / safari / firefox. Keep the cookies file private (chmod 600) and
delete it when done; it is a login. Free: no API credits.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys


def run(cmd, **kw):
    print("$", " ".join(cmd))
    return subprocess.run(cmd, **kw)


def need(tool, hint):
    if not shutil.which(tool):
        sys.exit(f"Missing '{tool}'. Install it: {hint}")


def download(url, out, cookies=None, browser=None):
    need("yt-dlp", "brew install yt-dlp")
    cmd = ["yt-dlp", "--no-update", "--write-info-json", "-f", "mp4/best", "-o", os.path.join(out, "video.%(ext)s")]
    if cookies:
        cmd += ["--cookies", os.path.expanduser(cookies)]
    if browser:
        cmd += ["--cookies-from-browser", browser]
    r = run(cmd + [url])
    if r.returncode != 0:
        sys.exit("Download failed. For Instagram this is almost always the login wall: pass --cookies <file>.")
    vids = [f for f in glob.glob(os.path.join(out, "video.*")) if not f.endswith(".json")]
    info = glob.glob(os.path.join(out, "video*.info.json"))
    if info:
        os.replace(info[0], os.path.join(out, "info.json"))
    return vids[0]


def transcribe(video, out, model, language=None):
    need("ffmpeg", "brew install ffmpeg")
    wav = os.path.join(out, "audio.wav")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000", wav])
    if not os.path.exists(wav):
        return "(no audio track)"
    if shutil.which("mlx_whisper"):
        cmd = ["mlx_whisper", wav, "--model", model, "-f", "txt", "-o", out]
    elif shutil.which("whisper"):
        cmd = ["whisper", wav, "--model", "turbo", "--output_format", "txt", "--output_dir", out]
    else:
        return "(no transcript: install mlx-whisper or openai-whisper)"
    if language:
        cmd += ["--language", language]
    run(cmd)
    txt = os.path.join(out, "audio.txt")
    if os.path.exists(txt):
        os.replace(txt, os.path.join(out, "transcript.txt"))
        os.remove(wav)
        with open(os.path.join(out, "transcript.txt"), encoding="utf-8") as fh:
            return fh.read().strip()
    return "(transcription failed)"


def frames(video, out, every):
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", video,
         "-vf", f"fps=1/{every},scale=360:-1,tile=4x2", os.path.join(out, "grid_%02d.jpg")])
    return sorted(glob.glob(os.path.join(out, "grid_*.jpg")))


def main():
    ap = argparse.ArgumentParser(description="Download + transcribe + frame-grid a video (free).",
                                 epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="video URL or local video file")
    ap.add_argument("--out", required=True, help="output folder, e.g. videos/ig-brand-reel1")
    ap.add_argument("--cookies", help="cookies.txt file (needed for Instagram)")
    ap.add_argument("--cookies-from-browser", dest="browser", help="chrome, safari, firefox (may not work for Arc)")
    ap.add_argument("--every", type=float, default=4, help="seconds between frames (default 4; use 1-2 for short ads)")
    ap.add_argument("--model", default="mlx-community/whisper-large-v3-turbo", help="mlx_whisper model")
    ap.add_argument("--language", help="force language code, e.g. bg, de (default: auto-detect)")
    ap.add_argument("--no-transcript", action="store_true")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    if os.path.exists(a.source):
        video = a.source
    else:
        existing = [f for f in glob.glob(os.path.join(a.out, "video.*")) if not f.endswith(".json")]
        video = existing[0] if existing else download(a.source, a.out, a.cookies, a.browser)
    need("ffmpeg", "brew install ffmpeg")
    transcript = "(skipped)" if a.no_transcript else transcribe(video, a.out, a.model, a.language)
    grids = frames(video, a.out, a.every)

    info = {}
    if os.path.exists(os.path.join(a.out, "info.json")):
        with open(os.path.join(a.out, "info.json"), encoding="utf-8") as fh:
            info = json.load(fh)
    keys = ["webpage_url", "uploader", "channel", "upload_date", "duration", "view_count", "like_count", "comment_count"]
    lines = [f"{k}: {info.get(k)}" for k in keys if info.get(k) is not None]
    lines += ["", "CAPTION:", (info.get("description") or info.get("title") or "-").strip(),
              "", "TRANSCRIPT:", transcript, "", "FRAME SHEETS (8 frames each, every %ss):" % a.every] + grids
    with open(os.path.join(a.out, "summary.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"done: {os.path.join(a.out, 'summary.txt')} + {len(grids)} frame sheet(s)")


if __name__ == "__main__":
    main()
