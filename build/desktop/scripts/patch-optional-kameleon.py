#!/usr/bin/env python3
"""Keep search runners available without the optional Rust RGB keyboard service."""
from pathlib import Path
import sys

root = Path(sys.argv[1])
changes = {
    'CMakeLists.txt': (
        'find_package(Corrosion REQUIRED)',
        'option(BUILD_KAMELEON "Build the RGB keyboard service" ON)\n'
        'if(BUILD_KAMELEON)\n    find_package(Corrosion REQUIRED)\nendif()',
    ),
    'kdeds/CMakeLists.txt': (
        'add_subdirectory(kameleon)',
        'if(BUILD_KAMELEON)\n    add_subdirectory(kameleon)\nendif()',
    ),
}
for name, (old, new) in changes.items():
    path = root / name
    text = path.read_text()
    if new in text:
        continue
    if text.count(old) != 1:
        raise SystemExit(f'Unexpected upstream source: {name}')
    path.write_text(text.replace(old, new))
