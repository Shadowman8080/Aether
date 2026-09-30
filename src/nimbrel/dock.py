#!/usr/bin/env python3
"""Add Nimbrel once without resetting the user's panels."""
import os,re,runpy
from pathlib import Path
def main():
    helper=runpy.run_path('/usr/libexec/aether-vector-migrate.py')
    config=Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')
    panel=config/'plasma-org.kde.plasma.desktop-appletsrc'
    marker=config/'nimbrel-dock-v1'
    if marker.exists() or not panel.exists():return
    helper['checked'](panel)
    original=panel.read_text()
    groups=helper['sections'](original)
    for name,lines in list(groups.items()):
        if not re.fullmatch(r'\[Containments\]\[\d+\]',name):continue
        if helper['value'](lines,'plugin')!='org.kde.panel' or helper['value'](lines,'location')!='4':continue
        for app,values in list(groups.items()):
            if not re.fullmatch(re.escape(name)+r'\[Applets\]\[\d+\]',app):continue
            if helper['value'](values,'plugin') not in ('org.kde.plasma.icontasks','org.kde.plasma.taskmanager'):continue
            general=app+'[Configuration][General]'
            pins=[v for v in helper['value'](groups.get(general,[]),'launchers').split(',') if v]
            if 'applications:org.aether.Nimbrel.desktop' not in pins:
                index=next((i for i,v in enumerate(pins) if 'org.aether.Vector.desktop' in v),len(pins)-1)
                pins.insert(index+1,'applications:org.aether.Nimbrel.desktop')
                helper['put'](groups,general,'launchers',','.join(pins))
    result=''.join(''.join(v) for v in groups.values())
    if result!=original:
        backup=panel.with_name(panel.name+'.before-nimbrel')
        if not backup.exists():
            fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as f:f.write(original)
        helper['save'](panel,result)
    fd=os.open(marker,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    os.close(fd)
if __name__=='__main__':
    try:main()
    except (OSError,ValueError):print('Nimbrel dock migration deferred; desktop startup continues.')
