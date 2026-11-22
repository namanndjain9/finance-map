"""Original background music, synthesised with numpy (no samples, no licences needed).

A calm, optimistic loop at 92 BPM in C major: I - V - vi - IV pads, a soft plucked arpeggio,
a round bass note per bar and a gentle pulse, with a little echo. Written as 16-bit stereo WAV.
"""

import wave
from pathlib import Path

import numpy as np

SR = 44_100
BPM = 92
BEAT = 60 / BPM
BAR = 4 * BEAT

# (root midi, chord tones as midi) for C, G, Am, F
CHORDS = [
    (48, [60, 64, 67, 72]),
    (43, [59, 62, 67, 71]),
    (45, [60, 64, 69, 72]),
    (41, [60, 65, 69, 72]),
]


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def tone(freq: float, seconds: float, harmonics=(1.0, 0.35, 0.12), detune: float = 0.0) -> np.ndarray:
    t = np.arange(int(seconds * SR)) / SR
    out = np.zeros_like(t)
    for k, amp in enumerate(harmonics, start=1):
        out += amp * np.sin(2 * np.pi * freq * k * (1 + detune) * t)
    return out


def envelope(n: int, attack: float, release: float) -> np.ndarray:
    env = np.ones(n)
    a, r = min(n, int(attack * SR)), min(n, int(release * SR))
    if a:
        env[:a] = np.linspace(0, 1, a)
    if r:
        env[-r:] *= np.linspace(1, 0, r)
    return env


def add(buf: np.ndarray, start: float, sig: np.ndarray) -> None:
    i = int(start * SR)
    j = min(len(buf), i + len(sig))
    if i < len(buf):
        buf[i:j] += sig[: j - i]


def render(seconds: float, path: Path) -> Path:
    n = int((seconds + 2) * SR)
    left, right = np.zeros(n), np.zeros(n)
    rng = np.random.default_rng(7)
    bars = int(seconds / BAR) + 2
    for b in range(bars):
        t0 = b * BAR
        root, notes = CHORDS[b % len(CHORDS)]
        # pad: detuned pair per note, slow swell, panned slightly apart
        for i, m in enumerate(notes[:3]):
            sig = tone(hz(m), BAR + 0.6, (1.0, 0.18), detune=0.0025) + tone(hz(m), BAR + 0.6, (1.0, 0.18), detune=-0.0025)
            sig *= envelope(len(sig), 0.9, 0.9) * 0.05
            pan = 0.35 + 0.15 * i
            add(left, t0, sig * (1 - pan))
            add(right, t0, sig * pan)
        # bass
        sig = tone(hz(root), BAR, (1.0, 0.25)) * envelope(int(BAR * SR), 0.05, 0.6) * 0.11
        add(left, t0, sig)
        add(right, t0, sig)
        # arpeggio: eighth notes, plucked
        pattern = [0, 1, 2, 3, 2, 1, 2, 3]
        for k, idx in enumerate(pattern):
            if b == 0 and k < 4:
                continue  # ease in
            m = notes[idx] + 12
            dur = 0.6
            tt = np.arange(int(dur * SR)) / SR
            sig = tone(hz(m), dur, (1.0, 0.3, 0.08)) * np.exp(-tt * 7) * envelope(len(tt), 0.004, 0.05)
            sig *= 0.035 * (0.85 + 0.3 * rng.random())
            pan = 0.3 + 0.4 * (k % 2)
            add(left, t0 + k * BEAT / 2, sig * (1 - pan))
            add(right, t0 + k * BEAT / 2, sig * pan)
        # soft pulse on beats 1 and 3
        for beat in (0, 2):
            dur = 0.35
            tt = np.arange(int(dur * SR)) / SR
            freq = 55 + 60 * np.exp(-tt * 30)
            sig = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-tt * 12) * 0.09
            add(left, t0 + beat * BEAT, sig)
            add(right, t0 + beat * BEAT, sig)

    # echo (dotted eighth), a touch of space
    delay = int(0.75 * BEAT * SR)
    for ch, other in ((left, right), (right, left)):
        wet = np.zeros_like(ch)
        wet[delay:] = other[:-delay] * 0.22
        ch += wet

    out = np.stack([left, right], axis=1)[: int(seconds * SR)]
    fade_in, fade_out = int(1.5 * SR), int(3.0 * SR)
    out[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
    out[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None]
    out /= max(1e-9, np.abs(out).max()) / 0.89
    pcm = (out * 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path


if __name__ == "__main__":
    print(render(30, Path("demo/.work/music_preview.wav")))
