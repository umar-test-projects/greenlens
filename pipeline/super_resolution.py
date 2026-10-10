"""Optional visual-only Real-ESRGAN x4. Never modifies measurement data."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
import cv2
import numpy as np

MODEL = 'RealESRGAN_x4plus'
WEIGHTS_URL = 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth'


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def infer(bgr, weights, device, tile):
    # Optional packages are imported only when enhancement is requested.
    import torch
    from basicsr.archs.rrdbnet_arch import RRDBNet
    from realesrgan import RealESRGANer
    if device == 'auto':
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    if device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable; use --device cpu or auto')
    torch.manual_seed(0)
    if device == 'cuda':
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
    network = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                      num_block=23, num_grow_ch=32, scale=4)
    engine = RealESRGANer(scale=4, model_path=str(weights), model=network,
                         tile=tile, tile_pad=10, pre_pad=0, half=False,
                         device=torch.device(device))
    with torch.inference_mode():
        output, _ = engine.enhance(bgr, outscale=4)
    return output, {'device': device, 'precision': 'float32', 'seed': 0,
                    'versions': {p: version(p) for p in ('torch','torchvision','basicsr','realesrgan','numpy','opencv-python')}}


def build(root, weights, device='auto', tile=128):
    directory = Path(root) / 'public/data'
    source = directory / 'satellite-rgb.png'
    metadata_path = directory / 'imagery.json'
    metadata = json.loads(metadata_path.read_text())
    metadata.pop('superResolvedImage', None)
    record = {'status': 'fallback', 'model': MODEL, 'scale': 4,
              'displayOnly': True, 'generatedDetail': True, 'requestedDevice': device,
              'nativeResolutionM': metadata['resolutionM'],
              'label': 'AI-generated detail (visual only); spatial resolution unchanged',
              'weightsSource': WEIGHTS_URL, 'sourceImage': metadata['image'],
              'sourceSha256': sha256(source), 'sceneId': metadata.get('sceneId'),
              'createdAt': datetime.now(timezone.utc).isoformat(),
              'parameters': {'tile': tile, 'tilePad': 10, 'prePad': 0, 'outscale': 4}}
    output_path = directory / 'satellite-sr.png'
    try:
        weights = Path(weights)
        if not weights.is_file():
            raise FileNotFoundError('Local model weights unavailable')
        record['weightsSha256'] = sha256(weights)
        image = cv2.imread(str(source))
        if image is None:
            raise RuntimeError('Source image unreadable')
        output, runtime = infer(image, weights, device, tile)
        if output.shape != (image.shape[0]*4, image.shape[1]*4, 3) or output.dtype != np.uint8:
            raise RuntimeError('Model returned invalid x4 RGB output')
        temporary = directory / 'satellite-sr.tmp.png'
        if not cv2.imwrite(str(temporary), output):
            raise RuntimeError('Could not save generated image')
        temporary.replace(output_path)
        record.update(runtime)
        record.update(status='ready', outputSha256=sha256(output_path),
                      sourceDimensions=[image.shape[1],image.shape[0]],
                      outputDimensions=[output.shape[1],output.shape[0]])
        metadata['superResolvedImage'] = '/data/satellite-sr.png'
    except Exception as error:
        record['reason'] = f'{type(error).__name__}: {error}'
        output_path.unlink(missing_ok=True)
        (directory/'satellite-sr.tmp.png').unlink(missing_ok=True)
        print('Super-resolution unavailable; original retained:', record['reason'])
    metadata['superResolution'] = record
    temporary_metadata = metadata_path.with_suffix('.tmp')
    temporary_metadata.write_text(json.dumps(metadata, indent=2))
    temporary_metadata.replace(metadata_path)
    return record


def options():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--super-resolution', action='store_true', help='Generate visual-only AI detail')
    parser.add_argument('--weights', type=Path, default=Path(__file__).resolve().parents[1]/'weights'/f'{MODEL}.pth')
    parser.add_argument('--device', choices=['auto','cpu','cuda'], default='auto')
    parser.add_argument('--tile', type=int, default=128)
    args = parser.parse_args()
    if args.tile < 0:
        parser.error('--tile must be nonnegative (0 disables tiling)')
    return args


if __name__ == '__main__':
    args = options()
    if args.super_resolution:
        build(Path(__file__).resolve().parents[1], args.weights, args.device, args.tile)
