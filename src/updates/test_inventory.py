import tempfile
import unittest
from pathlib import Path
from inventory import audit, inside

class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        (self.root/'var/lib/dpkg/info').mkdir(parents=True)
        (self.root/'usr/lib').mkdir(parents=True)
        (self.root/'usr/lib/example.so').write_bytes(b'\x7fELFexample')
        (self.root/'lib').symlink_to('/usr/lib', target_is_directory=True)
        (self.root/'var/lib/dpkg/status').write_text('Package: example\nStatus: install ok installed\nVersion: 1\nArchitecture: amd64\nSection: aether-synthetic\n\n')
    def tearDown(self): self.temp.cleanup()
    def test_absolute_symlink_stays_in_offline_root(self):
        self.assertEqual(inside(self.root, '/lib/example.so'), self.root/'usr/lib/example.so')
    def test_ownership_alias_is_resolved(self):
        (self.root/'var/lib/dpkg/info/example.list').write_text('/lib/example.so\n')
        result = audit(self.root)
        self.assertEqual(result['unowned'], [])
        self.assertEqual(result['files']['/usr/lib/example.so']['packages'], ['example'])
        self.assertEqual(result['synthetic_packages'], ['example'])
        self.assertFalse(result['production_updates_authorized'])
    def test_owning_symlink_does_not_claim_target(self):
        (self.root/'usr/lib/alias.so').symlink_to('example.so')
        (self.root/'var/lib/dpkg/info/example.list').write_text('/usr/lib/alias.so\n')
        self.assertIn('/usr/lib/example.so', audit(self.root)['unowned'])
    def test_missing_ownership_is_reported(self):
        self.assertEqual(audit(self.root)['unowned'], ['/usr/lib/example.so'])
    def test_symlink_loop_rejected(self):
        (self.root/'loop').symlink_to('/loop')
        with self.assertRaises(ValueError): inside(self.root, '/loop/file')
    def test_escape_rejected(self):
        (self.root/'escape').symlink_to('../secret')
        with self.assertRaises(ValueError): inside(self.root, '/escape')
    def test_home_not_collected(self):
        (self.root/'home').mkdir(); (self.root/'home/private').write_bytes(b'\x7fELFsecret')
        self.assertNotIn('/home/private', audit(self.root)['files'])
if __name__ == '__main__': unittest.main()
