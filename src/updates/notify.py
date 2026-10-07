#!/usr/bin/env python3
"""Session notifications for local checker results; never install or fetch."""
import hashlib,json,os,subprocess,time
from pathlib import Path
status=Path('/var/lib/aether-updates-status.json')
cache=Path(os.environ.get('XDG_CACHE_HOME',str(Path.home()/'.cache')))/'aether-update-notification'
while True:
 try:
  value=json.loads(status.read_text())
  state=value.get('state')
  messages={'updates-available':('Aether updates are available','Open Aether Settings → Updates to review and install.'),'restart-available':('Aether update prepared','Restart when convenient to try the prepared system. No automatic restart is scheduled.'),'error':('Aether could not check for updates','Open Aether Settings → Updates to review the error. Your installed system was not changed.')}
  if state in messages:
   identity={k:value.get(k) for k in ('state','packages','slot','message')}
   digest=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
   if not cache.exists() or cache.read_text()!=digest:
    title,body=messages[state]
    subprocess.run(['gdbus','call','--session','--dest','org.freedesktop.Notifications','--object-path','/org/freedesktop/Notifications','--method','org.freedesktop.Notifications.Notify','Aether','0','system-software-update',title,body,'[]','{}','10000'],check=True,capture_output=True,timeout=15)
    cache.parent.mkdir(parents=True,exist_ok=True);cache.write_text(digest)
 except (OSError,ValueError,subprocess.SubprocessError):pass
 time.sleep(60)
