import importlib.machinery,importlib.util,json,os,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
loader=importlib.machinery.SourceFileLoader('usbtrial',str(Path(__file__).with_name('aether-usbguard')))
spec=importlib.util.spec_from_loader(loader.name,loader);usb=importlib.util.module_from_spec(spec);loader.exec_module(usb)
class TrialTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);root=Path(self.temp.name)
  directory=root/'config';directory.mkdir();runtime=root/'run';runtime.mkdir();system=root/'devices';system.mkdir();state=root/'state';state.mkdir()
  self.keyboard=system/'1-1';self.keyboard.mkdir();(self.keyboard/'authorized').write_text('1\n')
  controller=system/'usb1';controller.mkdir();(controller/'authorized_default').write_text('1\n')
  for name,value in {'DIRECTORY':directory,'RUNTIME':runtime,'SYS':system,'STATEDIR':state,'CONFIG':directory/'usbguard-daemon.conf','RULES':directory/'rules.conf','STATE':state/'trial.json'}.items():
   p=patch.object(usb,name,value);p.start();self.addCleanup(p.stop)
  usb.CONFIG.write_text('# previous configuration\n')
  self.commands=[];self.timer_failure=False;self.block_on_start=False
  def command(*args,**kwargs):
   self.commands.append(args)
   if args[0]=='systemd-run' and self.timer_failure:raise subprocess.CalledProcessError(1,args)
   if args[:3]==('systemctl','start','usbguard.service') and self.block_on_start:(self.keyboard/'authorized').write_text('0\n')
   return subprocess.CompletedProcess(args,0,'allow id 1234:5678\n','')
  def run(args,**kwargs):return subprocess.CompletedProcess(args,3 if args[1]=='is-active' else 1 if args[1]=='is-enabled' else 0,'','')
  for p in (patch.object(usb,'command',side_effect=command),patch.object(usb.subprocess,'run',side_effect=run),patch.object(usb.sys.stdin,'isatty',return_value=True)):
   p.start();self.addCleanup(p.stop)
 def test_timer_is_armed_before_daemon_starts(self):
  with patch('builtins.input',side_effect=['TRIAL','KEEP']):usb.setup()
  names=[args[0:2] for args in self.commands]
  self.assertLess(names.index(('systemd-run','--quiet')),names.index(('systemctl','start')))
  timer=next(args for args in self.commands if args[0]=='systemd-run')
  self.assertIn('--on-active=60s',timer)
  self.assertIn('--timer-property=AccuracySec=1s',timer)
  self.assertIn(('systemctl','enable','usbguard.service'),self.commands)
  self.assertFalse(usb.STATE.exists())
 def test_cancel_restores_keyboard_and_original_config(self):
  self.block_on_start=True
  with patch('builtins.input',side_effect=['TRIAL','CANCEL']):usb.setup()
  self.assertEqual((self.keyboard/'authorized').read_text(),'1\n')
  self.assertEqual(usb.CONFIG.read_text(),'# previous configuration\n')
  self.assertFalse(usb.RULES.exists());self.assertFalse(usb.STATE.exists())
  self.assertIn(('systemctl','disable','--now','usbguard.service'),self.commands)
 def test_timer_failure_never_starts_daemon(self):
  self.timer_failure=True
  with patch('builtins.input',return_value='TRIAL'),self.assertRaises(RuntimeError):usb.setup()
  self.assertNotIn(('systemctl','start','usbguard.service'),self.commands)
  self.assertEqual(usb.CONFIG.read_text(),'# previous configuration\n');self.assertFalse(usb.STATE.exists())
 def test_expired_confirmation_cannot_enable_protection(self):
  with patch('builtins.input',side_effect=['TRIAL','KEEP']),patch.object(usb.time,'monotonic',side_effect=[1,100]),self.assertRaises(RuntimeError):usb.setup()
  self.assertNotIn(('systemctl','enable','usbguard.service'),self.commands)
  self.assertTrue(usb.STATE.exists())
  usb.rollback(json.loads(usb.STATE.read_text())['token'])
  self.assertEqual(usb.CONFIG.read_text(),'# previous configuration\n')
 def test_existing_active_daemon_is_not_reconfigured(self):
  with patch.object(usb.subprocess,'run',return_value=subprocess.CompletedProcess([],0)),patch('builtins.input',return_value='TRIAL'),self.assertRaises(RuntimeError):usb.setup()
  self.assertFalse(self.commands);self.assertEqual(usb.CONFIG.read_text(),'# previous configuration\n')
 def test_existing_policy_is_preserved(self):
  usb.RULES.write_text('block id 1111:2222\n')
  with patch('builtins.input',return_value='TRIAL'),self.assertRaises(RuntimeError):usb.setup()
  self.assertEqual(usb.RULES.read_text(),'block id 1111:2222\n');self.assertFalse(self.commands)
 def test_wrong_rollback_identity_does_not_touch_state(self):
  usb.STATE.write_text(json.dumps({'token':'a'*32}))
  with self.assertRaises(RuntimeError):usb.rollback('b'*32)
  self.assertTrue(usb.STATE.exists());self.assertFalse(self.commands)
 def test_recovery_path_escape_rejected(self):
  for name in ('../../outside','..','.'):
   with self.assertRaises(ValueError):usb.restore_authorization([{'device':name,'attribute':'authorized','value':'1'}])
 def test_reboot_recovery_does_not_write_old_device_paths(self):
  token='a'*32
  usb.STATE.write_text(json.dumps({'token':token,'boot_id':'old-boot','authorization':[{'device':'1-1','attribute':'authorized','value':'0'}],'config':{'text':'# before\n','mode':384},'rules':None}))
  usb.rollback(token)
  self.assertEqual((self.keyboard/'authorized').read_text(),'1\n')
  self.assertEqual(usb.CONFIG.read_text(),'# before\n');self.assertFalse(usb.STATE.exists())
 def test_symlink_configuration_rejected(self):
  usb.RULES.symlink_to(usb.CONFIG)
  with self.assertRaises(RuntimeError):usb.read_optional(usb.RULES)
 def test_noninteractive_setup_rejected(self):
  with patch.object(usb.sys.stdin,'isatty',return_value=False),self.assertRaises(RuntimeError):usb.setup()
  self.assertFalse(self.commands)
if __name__=='__main__':unittest.main()
