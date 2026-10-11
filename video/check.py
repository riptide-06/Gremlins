# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Verify delivery format and extract a timestamped contact sheet."""
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'out'
VIDEO = OUT / 'campus-cubbies.mp4'
manifest = json.loads((ROOT / 'public/manifest.json').read_text())
duration = manifest['durationInFrames'] / manifest['fps']
probe = json.loads(subprocess.check_output([
    'ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(VIDEO)
]))
video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
audio = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
assert (video['width'], video['height']) == (1920, 1080), video
assert video['avg_frame_rate'] == '30/1', video
assert int(video['nb_frames']) == manifest['durationInFrames'], video
assert abs(float(probe['format']['duration']) - duration) < 0.1, probe['format']
assert any(s['codec_type'] == 'subtitle' for s in probe['streams'])
times = [round(s['startSec'] + s['durationSec'] * fraction, 1) for s in manifest['scenes'] for fraction in (.25, .8)]
sheet = Image.new('RGB', (1280, len(manifest['scenes']) * 390), '#eeeae1')
draw = ImageDraw.Draw(sheet)
hashes = set()
for index, time in enumerate(times):
    frame = OUT / f'frame-{time:05.1f}.jpg'
    subprocess.run([
        'ffmpeg', '-v', 'error', '-y', '-ss', str(time), '-i', str(VIDEO),
        '-frames:v', '1', '-vf', 'scale=640:360', str(frame)
    ], check=True)
    image = Image.open(frame).convert('RGB')
    hashes.add(image.tobytes())
    x, y = (index % 2) * 640, (index // 2) * 390
    sheet.paste(image, (x, y))
    draw.text((x + 14, y + 367), f'{time:.1f}s', fill='#193c2c')
assert len(hashes) == len(times), 'Duplicate sampled frames: inspect render.'
sheet.save(OUT / 'contact-sheet.jpg', quality=90)
report = {
    'durationSec': float(probe['format']['duration']),
    'dimensions': [video['width'], video['height']],
    'fps': video['avg_frame_rate'],
    'frames': int(video['nb_frames']),
    'videoCodec': video['codec_name'],
    'audioCodec': audio['codec_name'],
    'subtitleTrack': True,
    'distinctSamples': len(hashes),
    'captionTiming': 'Phrase estimates within measured takes',
}
(OUT / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
