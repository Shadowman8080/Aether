from pathlib import Path
from PIL import Image
for p in Path('/opt/aether/logs/next').glob('guest-*.ppm'):
 Image.open(p).save(p.with_suffix('.png'))
 print(p.with_suffix('.png'))
