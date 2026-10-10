"""Display-only contrast enhancement; preserves the source and measurement grid."""
import json
from pathlib import Path
import cv2
import numpy as np


def enhance_rgb(rgb):
    lab=cv2.cvtColor(rgb,cv2.COLOR_RGB2LAB)
    luminance=lab[:,:,0].astype(np.float32)
    low,high=np.percentile(luminance,[2,98])
    if high-low<2:
        return rgb.copy()
    stretched=np.clip((luminance-low)*235/(high-low)+10,0,255)
    balanced=np.clip(.65*stretched+.35*luminance,0,255).astype(np.uint8)
    # Apply CLAHE to lightness only so colors do not shift independently.
    local=cv2.createCLAHE(clipLimit=1.5,tileGridSize=(4,4)).apply(balanced)
    detail=.65*balanced.astype(np.float32)+.35*local.astype(np.float32)
    blur=cv2.GaussianBlur(detail,(0,0),.7)
    lab[:,:,0]=np.clip(detail+.3*(detail-blur),0,255).astype(np.uint8)
    return cv2.cvtColor(lab,cv2.COLOR_LAB2RGB)


def build(root):
    directory=root/'public/data'
    original=cv2.imread(str(directory/'satellite-rgb.png'))
    if original is None:
        raise RuntimeError('Build the aligned satellite-rgb.png before enhancing it.')
    rgb=cv2.cvtColor(original,cv2.COLOR_BGR2RGB)
    enhanced=enhance_rgb(rgb)
    # Interpolation makes enlarged display smoother; it adds no observed detail.
    display=cv2.resize(enhanced,None,fx=4,fy=4,interpolation=cv2.INTER_CUBIC)
    output=directory/'satellite-enhanced.png'
    if not cv2.imwrite(str(output),cv2.cvtColor(display,cv2.COLOR_RGB2BGR)):
        raise RuntimeError('Could not save enhanced imagery.')
    metadata_path=directory/'imagery.json'
    metadata=json.loads(metadata_path.read_text())
    metadata['enhancedImage']='/data/satellite-enhanced.png'
    metadata['enhancement']={
        'displayOnly':True,'nativeResolutionM':10,
        'techniques':['2–98 percentile lightness stretch (65% blend)',
                      'CLAHE on LAB lightness (clip limit 1.5, 4×4 regions, 35% blend)',
                      'Lightness unsharp mask (sigma 0.7, strength 0.3)',
                      '4× bicubic display interpolation; no added spatial resolution']}
    metadata_path.write_text(json.dumps(metadata,indent=2))
    print(f'Saved enhanced display {display.shape[1]}×{display.shape[0]}; native resolution unchanged.')


if __name__=='__main__':
    build(Path(__file__).resolve().parents[1])
