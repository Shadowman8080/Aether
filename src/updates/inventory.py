#!/usr/bin/env python3
"""Read-only inventory of package identities and critical runtime file ownership.

This reports evidence; it never manufactures ownership or enables updates.
Offline absolute symlinks are resolved inside the supplied filesystem root.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat

PREFIXES = ('/usr/bin', '/usr/sbin', '/usr/lib', '/usr/lib64', '/bin', '/sbin', '/lib', '/lib64', '/boot')

def inside(root, logical):
    pending = list(PurePosixPath(logical).parts)
    if pending and pending[0] == '/': pending.pop(0)
    resolved = []; links = 0
    while pending:
        part = pending.pop(0)
        if part in ('', '.'): continue
        if part == '..':
            if not resolved: raise ValueError('Path escapes inventory root')
            resolved.pop(); continue
        candidate = root.joinpath(*resolved, part)
        if candidate.is_symlink():
            links += 1
            if links > 40: raise ValueError('Symlink loop')
            target = PurePosixPath(os.readlink(candidate))
            if target.is_absolute(): resolved = []
            pending = [v for v in target.parts if v != '/'] + pending
        else: resolved.append(part)
    return root.joinpath(*resolved)

def packages(root):
    result = []
    for stanza in (root/'var/lib/dpkg/status').read_text().split('\n\n'):
        fields = {}
        for line in stanza.splitlines():
            if line and not line[0].isspace() and ': ' in line:
                key, value = line.split(': ', 1); fields[key] = value
        if fields.get('Status') != 'install ok installed': continue
        result.append({'name': fields['Package'], 'version': fields['Version'],
            'architecture': fields.get('Architecture', 'unknown'),
            'synthetic_record': fields.get('Section') == 'aether-synthetic' or 'synthetic' in fields.get('Maintainer', '').lower()})
    return sorted(result, key=lambda p: p['name'])

def audit(root):
    root = root.resolve(strict=True)
    records = packages(root); names = {p['name'] for p in records}
    owners = {}; errors = []
    for manifest in sorted((root/'var/lib/dpkg/info').glob('*.list')):
        owner = manifest.name[:-5].split(':', 1)[0]
        if owner not in names: continue
        for logical in manifest.read_text().splitlines():
            if not logical.startswith('/') or '..' in PurePosixPath(logical).parts:
                errors.append({'manifest': manifest.name, 'reason': 'invalid package path'}); continue
            try:
                entry = PurePosixPath(logical)
                real = inside(root, str(entry.parent)) / entry.name
            except ValueError as e:
                errors.append({'manifest': manifest.name, 'reason': str(e)}); continue
            owners.setdefault(str(real.relative_to(root)), set()).add(owner)
    files = {}; unowned = []; conflicts = []
    for prefix in PREFIXES:
        start = inside(root, prefix)
        if not start.is_dir(): continue
        for base, dirs, entries in os.walk(start, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not (Path(base)/d).is_symlink())
            for name in sorted(entries):
                p = Path(base)/name
                if p.is_symlink() or not p.is_file(): continue
                logical = '/' + p.relative_to(root).as_posix()
                if logical in files: continue
                info = p.stat()
                with p.open('rb') as stream:
                    magic = stream.read(4)
                    critical = magic.startswith(b'\x7fELF') or bool(info.st_mode & 0o111) or logical.startswith('/boot/')
                    if not critical: continue
                    stream.seek(0); digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                assigned = sorted(owners.get(logical.lstrip('/'), set()))
                files[logical] = {'sha256': digest, 'bytes': info.st_size, 'mode': stat.S_IMODE(info.st_mode), 'packages': assigned}
                if not assigned: unowned.append(logical)
                if len(assigned) > 1: conflicts.append({'path': logical, 'packages': assigned})
    return {'schema': 1, 'scope': 'Critical runtime executables, libraries and boot files; excludes home, credentials and file contents',
        'packages': records, 'files': files, 'unowned': sorted(unowned), 'ownership_conflicts': conflicts,
        'metadata_errors': errors, 'synthetic_packages': [p['name'] for p in records if p['synthetic_record']],
        'production_updates_authorized': False,
        'note': 'Ownership and hashes are inventory evidence, not upstream authenticity, vulnerability clearance or approval to upgrade synthetic base packages.'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root)
    with args.output.open('x', encoding='utf-8') as out: json.dump(result, out, indent=2); out.write('\n')
    print(json.dumps({'packages': len(result['packages']), 'critical_files': len(result['files']),
        'unowned': len(result['unowned']), 'conflicts': len(result['ownership_conflicts']), 'metadata_errors': len(result['metadata_errors'])}))

if __name__ == '__main__': main()
