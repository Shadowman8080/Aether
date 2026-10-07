"""Test first-boot enablement with real systemctl against an isolated file tree."""
import shutil,subprocess,tempfile,unittest
from pathlib import Path
@unittest.skipUnless(shutil.which('systemctl'),'Requires systemctl')
class PresetTests(unittest.TestCase):
 def test_first_boot_keeps_ai_on_demand_and_optional_services_off(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);units=root/'usr/lib/systemd/system';units.mkdir(parents=True)
   preset=root/'etc/systemd/system-preset';preset.mkdir(parents=True)
   shutil.copy2(Path(__file__).with_name('00-aether.preset'),preset/'00-aether.preset')
   service='[Service]\nExecStart=/usr/bin/true\n[Install]\nWantedBy=multi-user.target\n'
   for name in ('nimbrel-engine.service','nimbrel-local.service','lightdm.service','NetworkManager.service','unreviewed.service'):(units/name).write_text(service)
   (units/'nimbrel-local.socket').write_text('[Socket]\nListenStream=/run/nimbrel/api.sock\n[Install]\nWantedBy=sockets.target\n')
   for name in ('getty@.service','serial-getty@.service'):(units/name).write_text('[Service]\nExecStart=/usr/bin/true\n[Install]\nWantedBy=getty.target\n')
   subprocess.run(['systemctl','--root='+str(root),'preset-all'],check=True,capture_output=True,text=True)
   for name in ('nimbrel-engine.service','nimbrel-local.service','unreviewed.service'):
    self.assertFalse((root/'etc/systemd/system/multi-user.target.wants'/name).is_symlink(),name)
   for directory,name in [('multi-user.target.wants','lightdm.service'),('multi-user.target.wants','NetworkManager.service'),('sockets.target.wants','nimbrel-local.socket'),('getty.target.wants','getty@tty1.service'),('getty.target.wants','serial-getty@ttyS0.service')]:
    self.assertTrue((root/'etc/systemd/system'/directory/name).is_symlink(),name)
if __name__=='__main__':unittest.main()
