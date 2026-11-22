"""Narration: one mp3 per scene with edge-tts (Microsoft's free neural voices), plus durations.

Only the narration text from demo/script.yaml is sent to the speech service.
"""

import asyncio
import json
import re
import subprocess
from pathlib import Path


def duration_s(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


async def _speak(text: str, voice: str, rate: str, path: Path) -> None:
    import edge_tts

    attempts = 10  # the free service drops a fair share of requests ("No audio was received")
    for attempt in range(attempts):
        try:
            await edge_tts.Communicate(text, voice, rate=rate).save(str(path))
            return
        except edge_tts.exceptions.NoAudioReceived:
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(min(1.5 * (attempt + 1), 6))


def synthesize(clips: dict[str, str], voice: str, rate: str, out_dir: Path) -> dict[str, dict]:
    """clips: id -> narration text. Returns id -> {path, seconds}. Reuses a clip if text/voice are unchanged."""
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    for clip_id, text in clips.items():
        text = " ".join(text.split())
        path = out_dir / f"{clip_id}.mp3"
        stamp = out_dir / f"{clip_id}.txt"
        key = f"{voice}|{rate}|{text}"
        if not (path.is_file() and stamp.is_file() and stamp.read_text(encoding="utf-8") == key):
            asyncio.run(_speak(text, voice, rate, path))
            stamp.write_text(key, encoding="utf-8")
        result[clip_id] = {"path": path, "seconds": duration_s(path), "text": text}
    return result


def _ts(seconds: float) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def write_srt(cues: list[tuple[float, float, str]], path: Path) -> None:
    """cues: (start, seconds, text). Long narration is split by sentence, timed by length."""
    lines, n = [], 0
    for start, seconds, text in cues:
        parts = [p for p in re.split(r"(?<=[.!?])\s+", text) if p]
        total = sum(len(p) for p in parts) or 1
        t = start
        for part in parts:
            span = seconds * len(part) / total
            n += 1
            lines += [str(n), f"{_ts(t)} --> {_ts(t + span)}", part, ""]
            t += span
    path.write_text("\n".join(lines), encoding="utf-8")
