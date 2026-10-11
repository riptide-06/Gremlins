# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///
"""Mix the approved scene takes and make captions, then mux the silent render.

Run: uv run video/finish.py [--video video/out/picture.mp4]
Caption phrase timings are proportional estimates within each measured take.
"""
import argparse
import json
import re
import subprocess
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent


def run(args):
    subprocess.run(args, check=True)


def stamp(seconds):
    ms = round(seconds * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--video', type=Path)
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'public/manifest.json').read_text())
    out = ROOT / 'out'
    out.mkdir(exist_ok=True)
    rate = 48000
    total_seconds = manifest['durationInFrames'] / manifest['fps']
    samples = round(total_seconds * rate)
    voice = np.zeros((samples, 2), dtype=np.float64)
    duck = np.ones(samples)
    captions = []

    def decode(path):
        raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-ar', str(rate), '-ac', '2', '-f', 'f32le', '-'])
        return np.frombuffer(raw, dtype='<f4').reshape(-1, 2).astype(np.float64)

    for index, scene in enumerate(manifest['scenes']):
        path = ROOT / 'public' / scene['audio']
        start = scene['audioStartSec']
        duration = scene['audioDurationSec']
        if start < scene['startSec'] or start + duration > scene['startSec'] + scene['durationSec']:
            raise ValueError(f"Narration outside scene: {scene['id']}")
        take = decode(path)
        rms = np.sqrt(np.mean(take ** 2))
        take *= 10 ** (-20 / 20) / max(rms, 1e-8)
        at = round(start * rate)
        voice[at:at + len(take)] += take
        begin, end = max(0, at - round(.15 * rate)), min(samples, at + len(take) + round(.25 * rate))
        duck[begin:end] = .4
        ramp = round(.15 * rate)
        if begin >= ramp:
            duck[begin-ramp:begin] = np.minimum(duck[begin-ramp:begin], np.linspace(1, .4, ramp))
        if end + ramp <= samples:
            duck[end:end+ramp] = np.minimum(duck[end:end+ramp], np.linspace(.4, 1, ramp))
        text = scene['text'].replace('U C S C', 'UCSC').replace('A two A', 'A2A')
        words = text.split()
        groups = []
        current = []
        for word in words:
            current.append(word)
            if len(current) >= 9 or (len(current) >= 4 and re.search(r'[.!?:]$', word)):
                groups.append(current)
                current = []
        if current:
            groups.append(current)
        used = 0
        for group in groups:
            begin = start + duration * used / len(words)
            used += len(group)
            end = start + duration * used / len(words)
            captions.append(f'{len(captions)+1}\n{stamp(begin)} --> {stamp(end)}\n{" ".join(group)}\n')
    music = decode(ROOT / 'public/audio/music.wav')[:samples]
    music = np.pad(music, ((0, samples-len(music)), (0, 0)))
    music *= 10 ** (-27 / 20) / max(np.sqrt(np.mean(music ** 2)), 1e-8)
    duck[:rate] *= np.linspace(0, 1, rate)
    duck[-3*rate:] *= np.linspace(1, 0, 3*rate)
    mix = voice + music * duck[:, None]
    mix *= min(1, .89 / max(np.abs(mix).max(), 1e-8))
    with wave.open(str(out / 'soundtrack.wav'), 'wb') as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes((mix * 32767).astype('<i2').tobytes())
    (out/'campus-cubbies.srt').write_text('\n'.join(captions))
    if args.video:
        run(['ffmpeg', '-y', '-i', str(args.video), '-i', str(out/'soundtrack.wav'), '-i', str(out/'campus-cubbies.srt'), '-map', '0:v:0', '-map', '1:a:0', '-map', '2:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-c:s', 'mov_text', '-metadata:s:s:0', 'language=eng', '-t', str(total_seconds), '-movflags', '+faststart', str(out/'campus-cubbies.mp4')])


if __name__ == '__main__':
    main()
