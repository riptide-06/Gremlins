"""Run installed SA3 with pre-quantization headroom, leaving its installation intact."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sa3-root', type=Path, default=Path(os.environ.get('SA3_ROOT', '~/Code/sa3/stable-audio-3/optimized/mlx')), help='Installed SA3 optimized/mlx directory')
    args = parser.parse_args()
    engine_path = args.sa3_root.expanduser().resolve() / 'scripts/sa3_mlx.py'
    if not engine_path.is_file():
        parser.error(f'SA3 engine missing: {engine_path}; set --sa3-root or SA3_ROOT')
    spec = importlib.util.spec_from_file_location('sa3_engine', engine_path)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    original_save = engine.save_wav

    def save_with_headroom(path, audio, sample_rate=44100):
        peak = float(engine.np.abs(audio).max())
        gain = min(1.0, 0.8 / max(peak, 1e-12))
        original_save(path, audio * gain, sample_rate)
        Path(path).with_suffix('.headroom.json').write_text(json.dumps({'preGainPeak': peak, 'linearGainBeforePCM': gain, 'targetPeak': .8, 'purpose': 'Avoid upstream hard clipping before PCM conversion'}, indent=2) + '\n')

    engine.save_wav = save_with_headroom
    provenance = Path(__file__).resolve().parent / 'public/audio/music-provenance.json'
    data = json.loads(provenance.read_text())
    sys.argv = [str(engine_path)] + data['command'][1:]
    engine.main()
    data['preQuantizationHeadroomWrapper'] = str(Path(__file__).resolve())
    data['engineSource'] = str(engine_path)
    provenance.write_text(json.dumps(data, indent=2) + '\n')

if __name__ == '__main__':
    main()
