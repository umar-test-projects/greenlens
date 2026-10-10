# Optional visual-only GAN imagery

RealESRGAN_x4plus is a pretrained general-image restoration baseline, not a satellite measurement model. Its 4x output contains synthesized detail and is not evidence of smaller trees, buildings, or improved ground sampling. Native Sentinel pixels remain 10 m; the scientific grid, NDVI/vegetation, temperature and separate Landsat acquisition stay unchanged. The full aligned crop is processed before cell UV mapping so image extent and orientation stay identical.

The default build remains:

```powershell
.venv/Scripts/python.exe pipeline/build_imagery.py
```

This writes the original crop and existing contrast/bicubic display. GAN generation is opt-in. Use a separate Python 3.10 or 3.11 environment because the pinned BasicSR baseline needs older torchvision and NumPy than the geospatial environment. The pins avoid BasicSR's removed torchvision functional_tensor import. CPU inference works without a GPU but may be slow. No automatic model download occurs.

```powershell
py -3.11 -m venv .sr-venv
.sr-venv/Scripts/python.exe -m pip install -r pipeline/requirements-sr.txt
New-Item -ItemType Directory -Force weights
Invoke-WebRequest 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth' -OutFile weights/RealESRGAN_x4plus.pth
Get-FileHash weights/RealESRGAN_x4plus.pth -Algorithm SHA256
.sr-venv/Scripts/python.exe pipeline/super_resolution.py --super-resolution --weights weights/RealESRGAN_x4plus.pth --device cpu --tile 128
```

Download weights only from the official release; model checkpoints are trusted code inputs. Retain the printed SHA256 with the experiment and reuse the exact file. For a CUDA installation, install the matching torch 2.1.2 / torchvision 0.16.2 CUDA wheels from the official PyTorch index in that isolated environment and use `--device auto`. Auto selects CPU when CUDA is unavailable. Explicit `--device cuda` falls back to source imagery if CUDA is unavailable. Missing packages, missing/invalid weights, GPU memory errors and invalid model output also fall back, recording the reason. There is no automatic retry of failed CUDA inference; rerun with CPU if desired.

`build_imagery.py` also accepts `--super-resolution --weights PATH --device auto --tile 128` when optional dependencies are installed alongside rasterio/pyproj. The separate enhancement command above avoids that dependency conflict and can regenerate GAN output from the retained crop without fetching the satellite asset.

Output is `public/data/satellite-sr.png`, separate from `satellite-rgb.png` and `satellite-enhanced.png`. `imagery.json` retains the original `image`, `resolutionM`, cell mapping and scene provenance. Its additive `superResolution` record includes status/reason, model, source and weights SHA256, official weights URL, timestamp, native resolution, generated-detail label, tile settings, seed, precision, actual device, package versions and source/output dimensions and output hash on success. No 2.5 m scientific resolution is assigned. Seed 0 and deterministic cuDNN settings improve reproducibility; byte-identical results across devices/drivers are not guaranteed.

A failed rerun removes the generated output and its selectable URL, preventing stale output from being advertised. A default crop rebuild resets metadata so older GAN output cannot be selected. Original is the default frontend appearance. AI 4x is explicitly labeled as generated detail, visual only, with native resolution unchanged. A failed texture request retries the original texture; if that also fails, measured data colors remain available.

Verification (no weights, network or GPU required):

```powershell
.venv/Scripts/python.exe -m unittest discover -s pipeline -p 'test_*.py'
.venv/Scripts/python.exe -m unittest discover -s backend/tests -p 'test_*.py'
npm.cmd test
npm.cmd run build
```

Tests exercise preservation of original PNG bytes and scientific grid values, success dimensions/provenance with a stubbed model, missing weights, inference errors, invalid output, stale metadata removal, and frontend source selection. These are contract tests, not evidence of pretrained model quality. To smoke-test actual inference, run the CPU command with the official weights, check `superResolution.status` is `ready`, verify 4x dimensions, then compare Original/AI 4x in the app. Do not use generated imagery to measure or infer environmental values.

References: [official Real-ESRGAN implementation and weights](https://github.com/xinntao/Real-ESRGAN), [official inference baseline](https://github.com/xinntao/Real-ESRGAN/blob/master/inference_realesrgan.py).
