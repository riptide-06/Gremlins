#!/usr/bin/env python3
"""Local, reproducible Campus Cubbies audio. No third-party Python dependencies."""
import argparse
import array
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import shutil
import wave

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'public/audio'
ARCHIVE = ROOT / 'versions/60s/public'
MODELS = Path(os.environ.get('AUDIOCPP_MODELS', '~/Code/bbb-artifact-tour/audio.cpp/models')).expanduser()
SA3_ROOT = Path(os.environ.get('SA3_ROOT', '~/Code/sa3/stable-audio-3/optimized/mlx')).expanduser()
SA3_PYTHON = os.environ.get('SA3_PYTHON')
REUSE_ARCHIVE = True
SAMPLE = 'Campus Cubbies brings campus knowledge to your own agent. Ordinary files become useful context, ready when you ask.'
SELECTED_SEEDS = {'06': 6706, '08': 6208}
CAST = [
    ('A', 'Warm peer', 1101, 'A young adult woman with a warm, clear mid-register American English voice. Friendly, grounded and intelligent, like a helpful graduate student. Conversational documentary narration, natural brisk pace, crisp diction, gently curious. No sales pitch or exaggerated enthusiasm.'),
    ('B', 'Quiet assurance', 2202, 'An adult man with a soft resonant baritone American English voice, warm and lightly textured. Calm assurance and understated curiosity, explaining a useful idea to a colleague. Natural brisk conversational pace, clear diction, no theatrical delivery or advertising cadence.'),
    ('C', 'Bright guide', 3303, 'An adult woman with a clear warm alto voice and a light British English accent. Thoughtful, inviting, quietly confident documentary guide. Nimble conversational pace and precise consonants, restrained expressive lift, never posh or promotional.'),
    ('D', 'Thoughtful builder', 4404, 'An adult man with a warm mid-range voice and a light Indian English accent. Curious, approachable and assured, like a thoughtful campus researcher sharing something practical. Brisk natural speech, clear articulation, gentle optimism, no announcer cadence.'),
]

def run(cmd):
    print(' '.join(map(str, cmd)), flush=True)
    subprocess.run(list(map(str, cmd)), check=True)

def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

def measure(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()

def tts(requests, kind, directory):
    if not requests:
        return
    directory.mkdir(parents=True, exist_ok=True)
    request_path = directory / 'requests.json'
    save(request_path, {'requests': requests})
    model = MODELS / f'Qwen3-TTS-12Hz-1.7B-{kind}-GGUF'
    run(['audiocpp', '--task', 'vdes' if kind == 'VoiceDesign' else 'tts', '--family', 'qwen3_tts', '--model', model, '--backend', 'metal', '--request-sequence', request_path, '--out-dir', directory, '--metrics'])

def auditions():
    tts([{'id': f'audition-{key}', 'seed': seed, 'text': SAMPLE, 'instruct': direction} for key, name, seed, direction in CAST], 'VoiceDesign', OUT / 'auditions')
    save_casting()

def save_casting():
    path = OUT / 'casting.json'
    casting = json.loads(path.read_text()) if path.exists() else {}
    casting.pop('provisional', None)
    casting.update(status='APPROVED: user explicitly selected candidate B', selected='B', reason='User cast choice after four auditions: Quiet assurance.', engine='audiocpp qwen3_tts Metal', model=str(MODELS / 'Qwen3-TTS-12Hz-1.7B-VoiceDesign-GGUF'), reference_transcript=SAMPLE, candidates=[{'id': key, 'name': name, 'seed': seed, 'instruct': direction, 'audio': f'auditions/audition-{key}.wav'} for key, name, seed, direction in CAST])
    save(path, casting)

def ensure_reference():
    ref = OUT / 'auditions/audition-B.wav'
    if not ref.is_file():
        key, _, seed, direction = next(candidate for candidate in CAST if candidate[0] == 'B')
        tts([{'id': f'audition-{key}', 'seed': seed, 'text': SAMPLE, 'instruct': direction}], 'VoiceDesign', ref.parent)
    save_casting()
    return ref

def reel():
    parts = []
    for key, name, _, _ in CAST:
        label = OUT / 'auditions' / f'label-{key}.aiff'
        run(['say', '-v', 'Samantha', '-o', label, f'Candidate {key}. {name}.'])
        part = label.with_suffix('.wav')
        run(['ffmpeg', '-y', '-v', 'error', '-i', label, '-ar', '24000', '-ac', '1', part])
        parts += [part, OUT / 'auditions' / f'audition-{key}.wav']
    with wave.open(str(OUT / 'audition-reel.wav'), 'wb') as target:
        target.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
        for part in parts:
            with wave.open(str(part)) as source:
                assert source.getparams()[:3] == (1, 2, 24000)
                target.writeframes(source.readframes(source.getnframes()))
            target.writeframes(b'\0\0' * 18000)

def script_scenes():
    script = (ROOT / 'script.md').read_text()
    fps = int(re.search(r'(\d+) fps', script)[1])
    matches = re.findall(r'^## (\d+) · .+ · (\d+)–(\d+) seconds\nNarration: (.+)$', script, re.M)
    scenes = [{'id': key, 'startSec': int(start), 'durationSec': int(end)-int(start), 'text': text} for key, start, end, text in matches]
    assert scenes and scenes[0]['startSec'] == 0
    for index, scene in enumerate(scenes):
        assert scene['id'] == f'{index+1:02}' and scene['durationSec'] > 0
        if index:
            assert scenes[index-1]['startSec'] + scenes[index-1]['durationSec'] == scene['startSec']
    return fps, scenes

def reuse_sources():
    if not REUSE_ARCHIVE or not (ARCHIVE / 'manifest.json').is_file() or not (ARCHIVE / 'audio/timing-verification.json').is_file():
        return {}
    old = json.loads((ARCHIVE / 'manifest.json').read_text())
    timing_ids = {s['id'] for s in json.loads((ARCHIVE / 'audio/timing-verification.json').read_text())}
    return {s['text']: s for s in old['scenes'] if s['id'] in timing_ids and all(p.is_file() for p in [ARCHIVE / s['audio'], ARCHIVE / 'audio/raw' / f"{s['id']}.wav", ARCHIVE / 'audio/raw' / f"{s['id']}-trimmed.wav"])}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def narration():
    _, scenes = script_scenes()
    old = reuse_sources()
    ref = ensure_reference()
    (OUT / 'raw').mkdir(parents=True, exist_ok=True)
    requests, provenance = [], []
    for scene in scenes:
        key, text = scene['id'], scene['text']
        if text in old:
            source = old[text]
            for src, dst in [(ARCHIVE / source['audio'], OUT / f'{key}.wav'), (ARCHIVE / 'audio/raw' / f"{source['id']}.wav", OUT / 'raw' / f'{key}.wav')]:
                shutil.copy2(src, dst)
            provenance.append({'id': key, 'method': 'exact-text approved take reuse', 'sourceId': source['id'], 'source': str(ARCHIVE / source['audio']), 'sha256': digest(OUT / f'{key}.wav'), 'text': text})
        else:
            spoken = text.replace('permissioned', 'permission’d') if key == '06' else text
            request = {'id': key, 'seed': SELECTED_SEEDS.get(key, 6100 + int(key)), 'voice_ref': str(ref), 'reference_text': SAMPLE, 'text': spoken}
            requests.append(request)
            provenance.append({'id': key, 'method': 'approved B reference synthesis', 'canonicalText': text, 'request': request})
    tts(requests, 'Base', OUT / 'raw')
    save(OUT / 'narration-provenance.json', {'status': 'APPROVED candidate B: explicitly selected by user', 'reference_audio': str(ref), 'reference_sha256': digest(ref), 'reference_transcript': SAMPLE, 'model': str(MODELS / 'Qwen3-TTS-12Hz-1.7B-Base-GGUF'), 'script_sha256': digest(ROOT / 'script.md'), 'scenes': provenance})

def finish():
    fps, source_scenes = script_scenes()
    provenance = json.loads((OUT / 'narration-provenance.json').read_text())
    if provenance['script_sha256'] != digest(ROOT / 'script.md'):
        raise RuntimeError('Script changed: run narration before finish.')
    # Use the decision recorded by narration, not the current archive availability.
    reused = {s['id']: s for s in provenance['scenes'] if s['method'] == 'exact-text approved take reuse'}
    old_timing = {s['id']: s for s in json.loads((ARCHIVE / 'audio/timing-verification.json').read_text())} if reused else {}
    scenes, verification = [], []
    for scene in source_scenes:
        key, text, duration = scene['id'], scene['text'], scene['durationSec']
        raw = OUT / 'raw' / f'{key}.wav'
        trimmed = OUT / 'raw' / f'{key}-trimmed.wav'
        dest = OUT / f'{key}.wav'
        available = duration - .65
        if key in reused:
            source = reused[key]
            if digest(dest) != source['sha256']:
                raise RuntimeError(f'Scene {key}: reused delivered take changed; run narration again.')
            shutil.copy2(ARCHIVE / 'audio/raw' / f"{source['sourceId']}-trimmed.wav", trimmed)
            timing = dict(old_timing[source['sourceId']])
            timing.update(id=key, reusedFrom=source['sourceId'])
        else:
            run(['ffmpeg', '-y', '-v', 'error', '-i', raw, '-af', 'silenceremove=start_periods=1:start_duration=0.02:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_duration=0.02:start_threshold=-45dB,areverse', trimmed])
            rate = max(1, measure(trimmed) / (available - .03))
            if rate > 1.15:
                raise RuntimeError(f'Scene {key} needs a new take or reviewed script/timing: {measure(trimmed):.3f}s into {available}s; rate {rate:.3f} exceeds 1.15. No selected-take pause cuts are applied. Change its seed in SELECTED_SEEDS, then rerun narration and finish.')
            run(['ffmpeg', '-y', '-v', 'error', '-i', trimmed, '-af', f'atempo={rate:.8f},afade=t=in:d=0.008,areverse,afade=t=in:d=0.015,areverse', dest])
            timing = {'id': key, 'rawDurationSec': measure(raw), 'trimmedDurationSec': measure(trimmed), 'pauseRemovedSec': 0, 'tempoFactor': rate}
        actual = measure(dest)
        assert actual <= available
        scenes.append({**scene, 'durationInFrames': duration*fps, 'audio': f'audio/{key}.wav', 'audioStartSec': scene['startSec'] + .35, 'audioDurationSec': actual})
        verification.append({**timing, 'durationSec': actual, 'tailSec': duration - .35 - actual})
    save(ROOT / 'public/manifest.json', {'fps': fps, 'durationInFrames': sum(s['durationInFrames'] for s in scenes), 'scenes': scenes})
    save(OUT / 'timing-verification.json', verification)
    for scene in provenance['scenes']:
        scene['rawSha256'] = digest(OUT / 'raw' / f"{scene['id']}.wav")
        scene['deliveredSha256'] = digest(OUT / f"{scene['id']}.wav")
        scene['processing'] = next(t for t in verification if t['id'] == scene['id'])
        scene.pop('pauseEditTrimmedSourceSec', None)
    save(OUT / 'narration-provenance.json', provenance)
    print(json.dumps(verification, indent=2))

def music():
    _, scenes = script_scenes()
    seconds = sum(s['durationSec'] for s in scenes)
    prompt = 'Instrumental warm minimal electronic and acoustic underscore, gentle steady pulse at 100 BPM, soft felt piano, delicate plucked acoustic strings, muted rounded synth bass, airy subtle pads, restrained tiny percussion. Curious and thoughtful opening, gradually quietly uplifting, gentle harmonic lift midway, intimate human scale, unobtrusive background under documentary narration, sparse arrangement, clean production, soft resolved ending. No vocals.'
    cmd = [str(SA3_ROOT / 'sa3'), '--prompt', prompt, '--negative-prompt', 'vocals, singing, speech, choir, bombastic trailer, epic drums, aggressive percussion, distorted', '--cfg', '2', '--dit', 'medium', '--decoder', 'same-l', '--seconds', str(seconds), '--seed', '101160', '--steps', '8', '--out', str(OUT / 'music.wav')]
    save(OUT / 'music-provenance.json', {'engine': 'Stable Audio 3 MLX', 'model': 'medium', 'decoder': 'same-l', 'seed': 101160, 'command': cmd, 'prompt': prompt, 'durationSec': seconds, 'data_provenance': 'SA3 licensed AudioSparx and CC Freesound training data per engine documentation.'})
    run([Path(SA3_PYTHON).expanduser() if SA3_PYTHON else SA3_ROOT / '.venv/bin/python', ROOT / 'sa3_headroom.py', '--sa3-root', SA3_ROOT])
    provenance = json.loads((OUT / 'music-provenance.json').read_text())
    provenance.update(sha256=digest(OUT / 'music.wav'), headroom=json.loads((OUT / 'music.headroom.json').read_text()))
    save(OUT / 'music-provenance.json', provenance)

def verify():
    manifest = json.loads((ROOT / 'public/manifest.json').read_text())
    fps, scenes = script_scenes()
    seconds = sum(s['durationSec'] for s in scenes)
    assert manifest['fps'] == fps and manifest['durationInFrames'] == seconds*fps
    assert sum(s['durationInFrames'] for s in manifest['scenes']) == seconds*fps
    assert len(manifest['scenes']) == len(scenes)
    for actual, expected in zip(manifest['scenes'], scenes):
        assert all(actual[k] == v for k, v in expected.items())
    provenance = json.loads((OUT / 'narration-provenance.json').read_text())
    for scene in provenance['scenes']:
        if scene['method'] == 'exact-text approved take reuse':
            assert digest(OUT / f"{scene['id']}.wav") == scene['sha256']
    files = [OUT / f"{s['id']}.wav" for s in scenes] + [OUT / 'music.wav']
    if (OUT / 'audition-reel.wav').exists():
        files.append(OUT / 'audition-reel.wav')
    report = []
    for path in files:
        with wave.open(str(path)) as audio:
            assert audio.getsampwidth() == 2
            samples = array.array('h', audio.readframes(audio.getnframes()))
            peak = max(map(abs, samples)) / 32768
            clipped = sum(abs(s) >= 32767 for s in samples)
            report.append({'file': path.name, 'sampleRate': audio.getframerate(), 'channels': audio.getnchannels(), 'durationSec': audio.getnframes() / audio.getframerate(), 'peak': peak, 'clippedSamples': clipped, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
            assert peak > .001
            assert clipped == 0, path
    assert measure(OUT / 'music.wav') == seconds
    for scene in manifest['scenes']:
        assert scene['audioDurationSec'] == measure(ROOT / 'public' / scene['audio'])
        assert abs(scene['audioStartSec'] - scene['startSec'] - .35) < 1e-9
        assert scene['audioStartSec'] + scene['audioDurationSec'] <= scene['startSec'] + scene['durationSec'] - .3
    save(OUT / 'technical-verification.json', report)
    print(json.dumps(report, indent=2))

def asr():
    _, scenes = script_scenes()
    paths = [OUT / f"{s['id']}.wav" for s in scenes]
    run(['uvx', 'parakeet-mlx', '--output-dir', OUT / 'asr', '--output-format', 'json', *paths])
    def normalize(text):
        text = text.lower().replace('’', "'")
        text = re.sub(r'\bu\s*c\s*s\s*c\b', 'ucsc', text)
        text = re.sub(r'\ba\s*(?:two|2|to)\s*a\b', 'a2a', text)
        text = re.sub(r'\bbay\s*leaf\b', 'bayleaf', text)
        text = re.sub(r"\bcubby's\b", 'cubbies', text)
        text = re.sub(r'\bmycubby\b', 'my cubby', text)
        return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text)
    report = []
    for scene in scenes:
        heard = json.loads((OUT / 'asr' / f"{scene['id']}.json").read_text())['text']
        expected, actual = normalize(scene['text']), normalize(heard)
        changes = [{'expected': expected[i:j], 'heard': actual[k:l]} for op, i, j, k, l in difflib.SequenceMatcher(None, expected, actual).get_opcodes() if op != 'equal']
        report.append({'id': scene['id'], 'expected': scene['text'], 'heard': heard, 'normalizedMatch': not changes, 'differences': changes, 'audioSha256': digest(OUT / f"{scene['id']}.wav")})
    save(OUT / 'asr-verification.json', {'engine': 'local Parakeet MLX tdt-0.6b-v3', 'normalization': "Case/punctuation, UCSC letter spacing, A two A / A2A, BayLeaf and My Cubby spacing, homophonic Cubby's / Cubbies", 'scenes': report})
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['auditions', 'reel', 'narration', 'finish', 'music', 'verify', 'asr'])
    parser.add_argument('--models', type=Path, default=MODELS, help='Qwen model parent directory (or AUDIOCPP_MODELS)')
    parser.add_argument('--sa3-root', type=Path, default=SA3_ROOT, help='SA3 optimized/mlx directory (or SA3_ROOT)')
    parser.add_argument('--sa3-python', default=SA3_PYTHON, help='SA3 Python interpreter (or SA3_PYTHON); default: SA3_ROOT/.venv/bin/python')
    parser.add_argument('--no-reuse', action='store_true', help='Synthesize every scene even if versions/60s is available')
    args = parser.parse_args()
    MODELS, SA3_ROOT = args.models.expanduser().resolve(), args.sa3_root.expanduser().resolve()
    SA3_PYTHON, REUSE_ARCHIVE = args.sa3_python, not args.no_reuse
    OUT.mkdir(parents=True, exist_ok=True)
    globals()[args.stage]()
