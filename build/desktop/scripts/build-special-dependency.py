#!/usr/bin/env python3
from pathlib import Path
import subprocess,shutil,sys
key,source,jobs=sys.argv[1:];src=Path(source)
def run(*cmd,cwd=src): subprocess.run(cmd,cwd=cwd,check=True)
def install(source,target,mode=0o644):
 p=Path(target);p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,p);p.chmod(mode)
if key=='lua':
 run('make','-j'+jobs,'MYCFLAGS=-fPIC','linux')
 run('cc','-shared','-Wl,-soname,liblua.so.5.4','-o','liblua.so.5.4.8','-Wl,--whole-archive','src/liblua.a','-Wl,--no-whole-archive','-lm','-ldl')
 run('make','INSTALL_TOP=/usr','install')
 install(src/'liblua.so.5.4.8','/usr/lib/liblua.so.5.4.8',0o755)
 for name in ('liblua.so','liblua.so.5.4'):
  p=Path('/usr/lib')/name
  if p.is_symlink(): p.unlink()
  p.symlink_to('liblua.so.5.4.8')
 Path('/usr/lib/pkgconfig/lua.pc').write_text('prefix=/usr\nlibdir=${prefix}/lib\nincludedir=${prefix}/include\nName: Lua\nDescription: Lua language runtime\nVersion: 5.4.8\nLibs: -L${libdir} -llua\nLibs.private: -lm -ldl\nCflags: -I${includedir}\n')
elif key=='libvpx':
 run('./configure','--prefix=/usr','--enable-shared','--enable-pic','--disable-examples','--disable-tools','--disable-docs','--disable-unit-tests')
 run('make','-j'+jobs)
 run('make','install')
elif key=='ffmpeg':
 run('./configure','--prefix=/usr','--enable-shared','--disable-static','--enable-gpl','--enable-libvpx','--enable-libopus','--enable-libvorbis','--enable-pic','--disable-doc')
 run('make','-j'+jobs)
 run('make','install')
else:
 src=src/'wpa_supplicant'
 options=['CONFIG_DRIVER_NL80211=y','CONFIG_LIBNL32=y','CONFIG_CTRL_IFACE=y','CONFIG_CTRL_IFACE_DBUS_NEW=y','CONFIG_CTRL_IFACE_DBUS_INTRO=y','CONFIG_DEBUG_SYSLOG=y','CONFIG_IPV6=y','CONFIG_TLS=openssl','CONFIG_IEEE80211W=y','CONFIG_SAE=y','CONFIG_OWE=y','CONFIG_EAP_TLS=y','CONFIG_EAP_PEAP=y','CONFIG_EAP_TTLS=y','CONFIG_EAP_MSCHAPV2=y','CONFIG_WPS=y','CONFIG_PKCS12=y','CONFIG_SMARTCARD=y','CONFIG_INTERWORKING=y','CONFIG_IEEE80211R=y','CONFIG_P2P=y','CONFIG_AP=y']
 (src/'.config').write_text('\n'.join(options)+'\n')
 subprocess.run(['make','-j'+jobs,'BINDIR=/usr/sbin','LIBDIR=/usr/lib'],cwd=src,check=True)
 for name in ('wpa_cli','wpa_passphrase','wpa_supplicant'): install(src/name,'/usr/sbin/'+name,0o755)
 for p in (src/'systemd').glob('*.service'): install(p,'/usr/lib/systemd/system/'+p.name)
 install(src/'dbus/fi.w1.wpa_supplicant1.service','/usr/share/dbus-1/system-services/fi.w1.wpa_supplicant1.service')
 install(src/'dbus/dbus-wpa_supplicant.conf','/etc/dbus-1/system.d/wpa_supplicant.conf')
