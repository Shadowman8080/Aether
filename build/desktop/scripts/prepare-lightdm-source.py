#!/usr/bin/env python3
"""Build the native login service and clients without API/help documentation.

The upstream 1.33.1 archive needs autotools bootstrapping. Optional gtk-doc and
Yelp documentation are excluded; PAM, daemon, clients and installed man pages
are unchanged. Bundled introspection/Vala macros support their disable flags.
"""
from pathlib import Path
import subprocess,sys
src=Path(sys.argv[1])
p=src/'configure.ac';s=p.read_text().replace('GTK_DOC_CHECK','# Aether: API documentation is not built').replace('YELP_HELP_INIT','# Aether: Yelp help is not built');p.write_text(s)
for name in ['doc/Makefile.am','help/Makefile.am']:
 (src/name).write_text('# Optional documentation is not part of the native desktop build.\n')
subprocess.run(['intltoolize','--force','--copy'],cwd=src,check=True)
