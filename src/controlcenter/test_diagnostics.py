import json,os,stat,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import diagnostics
class DiagnosticTests(unittest.TestCase):
 def test_export_never_overwrites(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'report.json';p.write_text('original')
   with self.assertRaises(FileExistsError):diagnostics.save(p,{'schema':1})
   self.assertEqual(p.read_text(),'original')
 @unittest.skipUnless(os.name=='posix','POSIX permissions and links')
 def test_export_is_private_and_rejects_symlinks(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'report.json';diagnostics.save(p,{'schema':1})
   self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o600)
   link=Path(directory)/'link.json';link.symlink_to(p)
   with self.assertRaises(FileExistsError):diagnostics.save(link,{'secret':'replacement'})
   self.assertEqual(json.loads(p.read_text()),{'schema':1})
 def test_os_release_allowlist(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'os-release';p.write_text('ID=aether\nBUILD_ID="20261007"\nSECRET=credential\nHOME_URL=https://private.example\n')
   self.assertEqual(diagnostics.os_version(p),{'ID':'aether','BUILD_ID':'20261007'})
 def test_service_output_does_not_leak_extra_fields(self):
  result=subprocess.CompletedProcess([],0,'ActiveState=active\nResult=success\nNRestarts=2\nEnvironment=PASSWORD=secret\n')
  with patch.object(diagnostics.subprocess,'run',return_value=result):
   self.assertEqual(diagnostics.service('lightdm.service'),{'available':True,'state':'active','result':'success','restarts':2})
 def test_unknown_state_does_not_copy_arbitrary_output(self):
  result=subprocess.CompletedProcess([],0,'ActiveState=private-user\nResult=secret\nNRestarts=password\n')
  with patch.object(diagnostics.subprocess,'run',return_value=result):self.assertNotIn('secret',json.dumps(diagnostics.service('lightdm.service')))
 def test_timeout_is_reported_without_stderr(self):
  with patch.object(diagnostics.subprocess,'run',side_effect=subprocess.TimeoutExpired('systemctl',3,stderr='private')):
   self.assertEqual(diagnostics.service('lightdm.service'),{'available':False})
if __name__=='__main__':unittest.main()
