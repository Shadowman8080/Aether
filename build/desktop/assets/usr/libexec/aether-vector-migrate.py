#!/usr/bin/env python3
"""Migrate the signed-in user's existing panels before Plasma creates its views."""
from pathlib import Path
import os
import re
import stat
import tempfile

UPDATE = '/usr/share/plasma/shells/org.kde.plasma.desktop/contents/updates/aether-vector.js'
AURA = 'applications:org.aether.AuraSearch.desktop'
VECTOR = 'applications:org.aether.Vector.desktop'


def sections(text):
    result = {}
    group = ''
    for line in text.splitlines(keepends=True):
        if line.startswith('[') and line.rstrip().endswith(']'):
            group = line.strip()
        result.setdefault(group, []).append(line)
    return result


def value(lines, key, default=''):
    return next((line.split('=', 1)[1].strip() for line in lines if line.startswith(key + '=')), default)


def put(groups, group, key, val):
    lines = groups.setdefault(group, [group + '\n'])
    for i, line in enumerate(lines):
        if line.startswith(key + '='):
            lines[i] = key + '=' + val + '\n'
            return
    if lines and not lines[-1].endswith('\n'):
        lines[-1] += '\n'
    lines.append(key + '=' + val + '\n')


def transform(text):
    groups = sections(text)
    panels = [(group, value(lines, 'location')) for group, lines in groups.items()
              if re.fullmatch(r'\[Containments\]\[\d+\]', group) and value(lines, 'plugin') == 'org.kde.panel']
    for panel, location in panels:
        removed = set()
        for group, lines in list(groups.items()):
            match = re.fullmatch(re.escape(panel) + r'\[Applets\]\[(\d+)\]', group)
            if not match:
                continue
            plugin = value(lines, 'plugin')
            if location == '3' and plugin in ('org.kde.plasma.kickoff', 'org.kde.plasma.kicker', 'org.kde.plasma.kickerdash'):
                removed.add(match[1])
                for child in list(groups):
                    if child == group or child.startswith(group + '['):
                        del groups[child]
            if location == '4' and plugin in ('org.kde.plasma.icontasks', 'org.kde.plasma.taskmanager'):
                config = group + '[Configuration][General]'
                old = value(groups.get(config, []), 'launchers').split(',')
                pins = [pin for pin in old if pin and 'org.aether.Vector.desktop' not in pin and 'org.kde.dolphin.desktop' not in pin]
                index = next((i for i, pin in enumerate(pins) if 'org.aether.AuraSearch.desktop' in pin), -1)
                if index < 0:
                    pins = [AURA, VECTOR] + pins
                else:
                    pins.insert(index + 1, VECTOR)
                put(groups, config, 'launchers', ','.join(pins))
        if removed:
            config = panel + '[General]'
            order = value(groups.get(config, []), 'AppletOrder')
            if order:
                put(groups, config, 'AppletOrder', ';'.join(item for item in order.split(';') if item not in removed))
    return ''.join(''.join(lines) for lines in groups.values())


def checked(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError('Configuration must be a regular file owned by this user: ' + str(path))
    return info


def save(path, text):
    old = path.read_text() if path.exists() else None
    if old == text:
        return
    if path.exists():
        checked(path)
        backup = path.with_name(path.name + '.before-vector')
        if not backup.exists():
            with backup.open('x') as stream:
                os.chmod(backup, 0o600)
                stream.write(old)
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    config = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    panels = config / 'plasma-org.kde.plasma.desktop-appletsrc'
    if not panels.exists():
        return
    checked(panels)
    rc = config / 'plasmashellrc'
    if rc.exists():
        checked(rc)
    groups = sections(rc.read_text() if rc.exists() else '')
    done = value(groups.get('[Updates]', []), 'performed').split(',')
    if UPDATE in done:
        return
    save(panels, transform(panels.read_text()))
    if UPDATE not in done:
        put(groups, '[Updates]', 'performed', ','.join([item for item in done if item] + [UPDATE]))
        save(rc, ''.join(''.join(lines) for lines in groups.values()))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        # Keep login available; Plasma's fallback migration remains installed.
        print('Vector panel migration: ' + str(error), file=__import__('sys').stderr)
