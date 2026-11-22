"""Build the demo video end to end:  .\\.venv\\Scripts\\python.exe -m demo.make  [--ai] [--keep-server]

1. narration clips (edge-tts)          -> demo/.work/voice/
2. own server on :8001 (not your :8000) -> real app, AI off unless --ai
3. recordings (Playwright, 1920x1080)  -> intro card, app walkthrough, outro card
4. original background music (numpy)   -> demo/.work/music.wav
5. ffmpeg mix                          -> demo/out/finance-map-demo.mp4 (+ .srt, + captioned copy)
"""

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import yaml

from demo import music, voice
from demo.record import record_app, record_card

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
WORK = DEMO / ".work"
OUT = DEMO / "out"
PORT = 8001
INTRO_LEAD, OUTRO_LEAD = 0.7, 0.8  # seconds of picture before the voice starts on each card
FADE = 0.4
SCENE_TAIL = 1.0   # seconds a scene may run on after its narration before it gets sped up
MAX_SPEEDUP = 3.0  # never fast-forward a scene more than this


def log(msg: str) -> None:
    print(f"[demo] {msg}", flush=True)


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def ensure_frontend() -> None:
    if not (ROOT / "web" / "dist" / "index.html").is_file():
        log("building the frontend (web/dist is missing)")
        subprocess.run("npm run build", cwd=ROOT / "web", shell=True, check=True)


def start_server(ai: bool) -> subprocess.Popen:
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", PORT)) == 0:
            raise SystemExit(f"port {PORT} is busy; stop whatever is running there first")
    env = dict(os.environ, LOG_LEVEL="WARNING")
    if not ai:
        env["GEMINI_API_KEY"] = ""  # deterministic demo: tiers 0-2 and the plain-summary story
        env["GOOGLE_API_KEY"] = ""
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.api:app", "--port", str(PORT)],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 180
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/status", timeout=2):
                return proc
        except OSError:
            if proc.poll() is not None:
                raise SystemExit("the demo server exited during startup; try running uvicorn by hand")
            time.sleep(1)
    proc.terminate()
    raise SystemExit("the demo server did not come up within 3 minutes")


def to_segment(video: Path, start: float, seconds: float, out: Path, target: float | None = None,
               fade_in: bool = True, fade_out: bool = True) -> Path:
    """Cut [start, start+seconds) from a recording; squeeze it to `target` seconds if given."""
    target = target or seconds
    filters = []
    if target < seconds - 0.05:
        filters.append(f"setpts=PTS*{target / seconds:.5f}")
    filters.append("fps=30,scale=1920:1080,format=yuv420p")
    if fade_in:
        filters.append(f"fade=t=in:st=0:d={FADE}")
    if fade_out:
        filters.append(f"fade=t=out:st={target - FADE:.3f}:d={FADE}")
    run([
        "ffmpeg", "-y", "-ss", f"{start:.3f}", "-t", f"{seconds:.3f}", "-i", str(video), "-t", f"{target:.3f}",
        "-vf", ",".join(filters), "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "16", str(out),
    ])
    return out


def fit_scenes(app: dict, scenes: list[dict], vo: dict) -> list[dict]:
    """Per-scene spans in the app recording, plus how long each should last in the video.

    On a busy machine the browser runs slower than planned, so a scene can outlast its narration.
    Those scenes are sped up (at most MAX_SPEEDUP x) to end shortly after the narration does.
    """
    ids = [s["id"] for s in scenes]
    bounds = [app["offsets"][i] for i in ids] + [app["seconds"]]
    spans = []
    for k, sid in enumerate(ids):
        actual = bounds[k + 1] - bounds[k]
        wanted = vo[sid]["seconds"] + SCENE_TAIL + (0.9 if k == len(ids) - 1 else 0)
        target = min(actual, max(wanted, actual / MAX_SPEEDUP))
        spans.append({"id": sid, "start": app["trim"] + bounds[k], "actual": actual, "target": target})
        log(f"  scene {sid:<10} recorded {actual:5.1f} s, narration {vo[sid]['seconds']:4.1f} s"
            + (f" -> sped up {actual / target:.2f}x" if target < actual - 0.05 else ""))
    return spans


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ai", action="store_true", help="let the demo server use Gemini (needs quota)")
    args = ap.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} is not on PATH")
    cfg = yaml.safe_load((DEMO / "script.yaml").read_text(encoding="utf-8"))
    scenes = cfg["scenes"]
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    log(f"narration with {cfg['voice']}")
    clips = {"intro": cfg["intro"]["narration"], "outro": cfg["outro"]["narration"]}
    clips |= {s["id"]: s["narration"] for s in scenes}
    vo = voice.synthesize(clips, cfg["voice"], cfg.get("rate", "+0%"), WORK / "voice")

    ensure_frontend()
    log(f"starting the demo server on :{PORT} (AI {'on' if args.ai else 'off'})")
    server = start_server(args.ai)
    videos = WORK / "video"
    shutil.rmtree(videos, ignore_errors=True)
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            intro_s = INTRO_LEAD + vo["intro"]["seconds"] + 1.0
            outro_s = OUTRO_LEAD + vo["outro"]["seconds"] + 2.2
            log("recording the intro card")
            intro = record_card(browser, "intro", intro_s, videos)
            log("recording the app walkthrough")
            app = record_app(browser, f"http://127.0.0.1:{PORT}/", scenes, vo, videos)
            log("recording the outro card")
            outro = record_card(browser, "outro", outro_s, videos)
            browser.close()
    finally:
        server.terminate()
        try:
            server.wait(10)
        except subprocess.TimeoutExpired:
            server.kill()

    log("encoding segments")
    spans = fit_scenes(app, scenes, vo)
    segs = [to_segment(intro["video"], intro["trim"], intro_s, WORK / "seg_intro.mp4")]
    starts = {"intro": INTRO_LEAD}  # where each narration clip starts in the final video
    clock = intro_s
    for k, span in enumerate(spans):
        segs.append(to_segment(app["video"], span["start"], span["actual"], WORK / f"seg_{k:02}_{span['id']}.mp4",
                               target=span["target"], fade_in=k == 0, fade_out=k == len(spans) - 1))
        starts[span["id"]] = clock + 0.15
        clock += span["target"]
    segs.append(to_segment(outro["video"], outro["trim"], outro_s, WORK / "seg_outro.mp4"))
    starts["outro"] = clock + OUTRO_LEAD
    listing = WORK / "segments.txt"
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in segs), encoding="utf-8")
    picture = WORK / "picture.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(picture)])
    total = voice.duration_s(picture)
    (WORK / "timeline.json").write_text(json.dumps(
        {"total": total, "intro": intro_s, "outro": outro_s, "scenes": spans, "voice_starts": starts},
        indent=2), encoding="utf-8")

    log("composing the music")
    track = music.render(total, WORK / "music.wav")

    log("mixing")
    order = list(starts)
    cmd = ["ffmpeg", "-y", "-i", str(picture), "-i", str(track)]
    for cid in order:
        cmd += ["-i", str(vo[cid]["path"])]
    parts = []
    for k, cid in enumerate(order):
        ms = round(starts[cid] * 1000)
        parts.append(f"[{k + 2}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{k}]")
    vol = float(cfg.get("music_volume", 0.22))
    parts.append("".join(f"[v{k}]" for k in range(len(order)))
                 + f"amix=inputs={len(order)}:normalize=0:duration=longest,apad[voice]")
    parts.append("[voice]asplit=2[vmain][vkey]")
    parts.append(f"[1:a]aresample=48000,volume={vol}[bed]")
    parts.append("[bed][vkey]sidechaincompress=threshold=0.02:ratio=6:attack=30:release=600:makeup=1[duck]")
    parts.append("[vmain][duck]amix=inputs=2:normalize=0:duration=first,"
                 f"atrim=0:{total:.3f},loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[aout]")
    final = OUT / "finance-map-demo.mp4"
    cmd += ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(final)]
    run(cmd)

    srt = OUT / "finance-map-demo.srt"
    voice.write_srt([(starts[c], vo[c]["seconds"], vo[c]["text"]) for c in order], srt)
    captioned = OUT / "finance-map-demo-captioned.mp4"
    style = "FontName=Segoe UI,FontSize=13,PrimaryColour=&H00FFFFFF,BackColour=&H99000000,BorderStyle=4,MarginV=14,MarginL=12,MarginR=135"  # keep clear of the mascot (right)
    # the subtitles filter can't take a Windows drive path, so this one runs inside demo/out
    subprocess.run(
        ["ffmpeg", "-y", "-i", final.name, "-vf", f"subtitles={srt.name}:force_style='{style}'",
         "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "copy", "-movflags", "+faststart",
         captioned.name],
        cwd=OUT, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    log(f"done: {final}  ({total:.1f} s)")
    log(f"      {captioned}")
    log(f"      {srt}")


if __name__ == "__main__":
    main()
