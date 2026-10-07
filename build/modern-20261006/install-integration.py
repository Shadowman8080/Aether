#!/usr/bin/env python3
"""Install first-party integration into an explicit offline Aether root."""
import json,os,shutil,subprocess,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve(); source=Path(sys.argv[2]).resolve(); build=Path(sys.argv[3]).resolve()
assert root!=Path('/') and 'ID=aether' in (root/'etc/os-release').read_text().splitlines()
def put(src,dest,mode=0o644):
 p=root/dest.lstrip('/');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((source/src).read_bytes().replace(b'\r\n',b'\n'));p.chmod(mode)
def write(dest,text,mode=0o644):
 p=root/dest.lstrip('/');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);p.chmod(mode)
def enable(unit,target):
 p=root/'etc/systemd/system'/target/(unit);p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists() and not p.is_symlink():p.symlink_to('../'+unit)
subprocess.run(['rsync','-aH',str(build/'stage')+'/',str(root)+'/'],check=True)
for name in ('client.py','repository.py','package_signing.py','release.py','runtime.py','slots.py','make_root.py'):
 put('updates/'+name,'/usr/lib/aether-updates/'+name)
subprocess.run(['rsync','-a',str(build/'python')+'/',str(root/'usr/lib/aether-updates/vendor')+'/'],check=True)
write('/usr/bin/aether-update',"#!/usr/bin/python3\nimport sys\nsys.path[:0]=['/usr/lib/aether-updates','/usr/lib/aether-updates/vendor']\nfrom runtime import main\ntry:main()\nexcept Exception as e:print('Update operation stopped:',str(e),file=sys.stderr);sys.exit(1)\n",0o755)
put('updates/aether-recovery','/usr/bin/aether-recovery',0o755)
put('updates/notify.py','/usr/libexec/aether-update-notify',0o755)
write('/usr/bin/aether-signing-setup',"#!/usr/bin/python3\nimport sys,runpy\nsys.path[:0]=['/usr/lib/aether-updates','/usr/lib/aether-updates/vendor']\nrunpy.run_path('/usr/lib/aether-updates/make_root.py',run_name='__main__')\n",0o755)
put('updates/LOCAL-KEY-SETUP.md','/usr/share/doc/aether-updates/LOCAL-KEY-SETUP.md')
put('controlcenter/preferences.py','/usr/bin/aether-preferences',0o755)
put('controlcenter/aether-system-admin','/usr/libexec/aether-system-admin',0o755)
put('nimbrel/library.py','/usr/bin/nimbrel-library',0o755)
put('nimbrel/client.py','/usr/bin/nimbrel-client',0o755)
put('nimbrel/local_server.py','/opt/nimbrel/local_server.py',0o755)
for unit in ('nimbrel-local.service','nimbrel-engine.service','nimbrel-local.socket'):
 put('nimbrel/'+unit,'/etc/systemd/system/'+unit)
for unit in ('nimbrel-local.service','nimbrel-engine.service'):
 (root/'etc/systemd/system/multi-user.target.wants'/unit).unlink(missing_ok=True)
enable('nimbrel-local.socket','sockets.target.wants')
for unit,target in [('aether-update-check.service',None),('aether-update-check.timer','timers.target.wants'),('aether-system-health.service','graphical.target.wants')]:
 put('updates/'+unit,'/etc/systemd/system/'+unit)
 if target:enable(unit,target)
put('security/aether-firewall','/usr/bin/aether-firewall',0o755)
put('security/encrypted-init','/usr/lib/aether-initramfs/encrypted-init',0o755)
put('security/aether-mkinitramfs','/usr/bin/aether-mkinitramfs',0o755)
write('/usr/share/applications/org.aether.Settings.desktop','[Desktop Entry]\nType=Application\nName=Aether Settings\nComment=Updates, recovery, privacy and your desktop\nExec=aether-settings\nIcon=preferences-system\nCategories=Settings;System;\n')
write('/etc/xdg/autostart/aether-welcome.desktop','[Desktop Entry]\nType=Application\nName=Welcome to Aether\nExec=aether-settings --first-run\nIcon=preferences-system\nX-KDE-autostart-phase=2\n')
write('/etc/xdg/autostart/aether-update-notify.desktop','[Desktop Entry]\nType=Application\nName=Aether update notifications\nExec=/usr/libexec/aether-update-notify\nNoDisplay=true\nX-KDE-autostart-phase=2\n')
write('/usr/share/doc/aether-updates/policy.json',json.dumps({'automatic_checks':True,'automatic_installation':False,'automatic_restart':False,'public_release_trust':'operator-provisioned; no keys bundled'},indent=2)+'\n')
subprocess.run(['chroot',str(root),'ldconfig'],check=True)
subprocess.run(['chroot',str(root),'glib-compile-schemas','/usr/share/glib-2.0/schemas'],check=True)
# KDE rebuilds its service cache on login; desktop-file-utils is optional here.
if (root/'usr/bin/update-desktop-database').exists():subprocess.run(['chroot',str(root),'update-desktop-database','/usr/share/applications'],check=True)
print('Integration installed into',root)
