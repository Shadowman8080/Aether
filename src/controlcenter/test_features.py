# SPDX-License-Identifier: GPL-3.0-or-later
import importlib.util,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
BASE=Path(__file__).resolve().parents[1]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
library=load('library',BASE/'nimbrel/library.py')
preferences=load('preferences',BASE/'controlcenter/preferences.py')
sys.path.insert(0,str(BASE/'updates'));import slots,runtime
class LibraryTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.home=Path(self.temp.name);self.env=patch.dict(os.environ,{'HOME':str(self.home),'XDG_DATA_HOME':str(self.home/'data')});self.env.start();self.docs=self.home/'Documents';self.docs.mkdir()
 def tearDown(self):self.env.stop();self.temp.cleanup()
 def test_opt_in(self):
  (self.docs/'a.txt').write_text('galaxy');self.assertEqual(library.rebuild()['indexed_files'],0);self.assertEqual(library.search('galaxy'),[])
 def test_search_and_private_permissions(self):
  (self.docs/'a.txt').write_text('Aether galaxy');library.set_folders([str(self.docs)]);self.assertEqual(library.rebuild()['indexed_files'],1);self.assertIn('galaxy',library.search('galaxy')[0]['excerpt']);self.assertEqual((library.state_dir()/'library.sqlite').stat().st_mode&0o777,0o600)
 def test_revocation_erases_index(self):
  (self.docs/'a.txt').write_text('galaxy');library.set_folders([str(self.docs)]);library.rebuild();library.set_folders([]);self.assertEqual(library.search('galaxy'),[]);self.assertFalse((library.state_dir()/'library.sqlite').exists())
 def test_reject_home_root(self):
  with self.assertRaises(ValueError):library.set_folders([str(self.home)])
 def test_reject_hidden_folder(self):
  p=self.home/'.ssh';p.mkdir()
  with self.assertRaises(ValueError):library.set_folders([str(p)])
 def test_reject_external_folder(self):
  with self.assertRaises(ValueError):library.set_folders(['/etc'])
 def test_skip_hidden_symlink_and_binary(self):
  (self.docs/'.secret.txt').write_text('galaxy');(self.docs/'link.txt').symlink_to('/etc/passwd');(self.docs/'binary.txt').write_bytes(b'galaxy\0');library.set_folders([str(self.docs)]);self.assertEqual(library.rebuild()['indexed_files'],0)
 def test_skip_oversized_file(self):
  (self.docs/'large.txt').write_bytes(b'a'*(library.MAX_FILE+1));library.set_folders([str(self.docs)]);self.assertEqual(library.rebuild()['indexed_files'],0)
 def test_deleted_file_not_returned(self):
  p=self.docs/'a.txt';p.write_text('galaxy');library.set_folders([str(self.docs)]);library.rebuild();p.unlink();self.assertEqual(library.search('galaxy'),[])
 def test_folder_replaced_by_link(self):
  library.set_folders([str(self.docs)]);self.docs.rmdir();self.docs.symlink_to('/etc',target_is_directory=True);self.assertEqual(library.rebuild()['indexed_files'],0)
class CatalogTests(unittest.TestCase):
 def item(self):return {'name':'aether-test','version':'1.0-1','target':'packages/aether-test_1.0-1_amd64.deb','sha256':'a'*64,'architecture':'amd64'}
 def catalog(self,p):return {'architecture':'x86_64','packages':p}
 def test_native_arch_mapping(self):self.assertEqual(len(runtime.validate_catalog(self.catalog([self.item()]),'x86_64')),1)
 def test_wrong_arch(self):
  p=self.item();p['architecture']='arm64'
  with self.assertRaises(ValueError):runtime.validate_catalog(self.catalog([p]),'x86_64')
 def test_duplicate_names(self):
  with self.assertRaises(ValueError):runtime.validate_catalog(self.catalog([self.item(),self.item()]),'x86_64')
 def test_path_escape(self):
  p=self.item();p['target']='packages/../etc/shadow'
  with self.assertRaises(ValueError):runtime.validate_catalog(self.catalog([p]),'x86_64')
 def test_missing_digest(self):
  p=self.item();p.pop('sha256')
  with self.assertRaises(ValueError):runtime.validate_catalog(self.catalog([p]),'x86_64')
 def test_unsafe_name(self):
  p=self.item();p['name']='--root=/'
  with self.assertRaises(ValueError):runtime.validate_catalog(self.catalog([p]),'x86_64')
class SlotTests(unittest.TestCase):
 def test_valid_slot(self):self.assertEqual(slots.current_id('quiet aether.slot=20261006T123456-0123abcd'),'20261006T123456-0123abcd')
 def test_escape(self):
  with self.assertRaises(ValueError):slots.current_id('aether.slot=../../root')
 def test_duplicate(self):
  with self.assertRaises(ValueError):slots.current_id('aether.slot=20261006T123456-0123abcd aether.slot=20261006T123456-0123abcd')
 def test_base(self):self.assertIsNone(slots.current_id('quiet root=UUID=abcd'))
class PreferenceTests(unittest.TestCase):
 def test_missing_optional_reload_tools_preserves_saved_profile(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_CONFIG_HOME':d}),patch.object(preferences,'run',return_value='__AETHER_UNSET__'),patch.object(preferences.subprocess,'run',side_effect=FileNotFoundError):
   self.assertEqual(preferences.profile('lightweight')['profile'],'lightweight')
   self.assertTrue((Path(d)/'aether/profile-before.json').is_file())
   self.assertEqual(preferences.profile('restore')['profile'],'restore')
   self.assertFalse((Path(d)/'aether/profile-before.json').exists())
 def test_repeated_lightweight_preserves_original_values(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'XDG_CONFIG_HOME':d}),patch.object(preferences,'run',return_value='original'),patch.object(preferences.subprocess,'run'):
   preferences.profile('lightweight');p=Path(d)/'aether/profile-before.json';before=p.read_bytes()
   preferences.profile('lightweight');self.assertEqual(p.read_bytes(),before)
class TrustConfigTests(unittest.TestCase):
 def test_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'link';p.symlink_to('/etc/passwd')
   with self.assertRaises(PermissionError):runtime.protected_file(p)
 def test_group_writable_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'trust';p.write_text('{}');p.chmod(0o664)
   with self.assertRaises(PermissionError):runtime.protected_file(p)
 def test_missing_configuration_does_not_report_up_to_date(self):
  with tempfile.TemporaryDirectory() as d,patch.object(runtime,'CONFIG',Path(d)/'missing'):
   with self.assertRaisesRegex(RuntimeError,'not configured'):runtime.configured()
if __name__=='__main__':unittest.main()
