#!/usr/bin/env python3
"""Exercise the generated boot hook without modifying the host or a VM."""
import ast
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


class GuestSessionTest(unittest.TestCase):
    def test_hypervisor_session_selection(self):
        tree = ast.parse(Path(__file__).with_name('configure-vmware-desktop.py').read_text())
        expression = next(node.value.args[1] for node in tree.body
                          if isinstance(node, ast.Expr)
                          and isinstance(node.value, ast.Call)
                          and isinstance(node.value.func, ast.Name)
                          and node.value.func.id == 'write'
                          and ast.literal_eval(node.value.args[0]) == '/usr/libexec/aether-guest-display-setup')
        script = eval(compile(ast.Expression(expression), '<boot-hook>', 'eval'),
                      {'shlex': shlex, 'x11': 'plasmax11'})
        bash = (r'C:\Program Files\Git\bin\bash.exe' if os.name == 'nt'
                else shutil.which('bash'))
        if not bash or not Path(bash).is_file():
            self.fail('bash is required to exercise the generated shell hook')
        for hypervisor in ('vmware', 'oracle', 'kvm', 'none'):
            with self.subTest(hypervisor=hypervisor), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / 'home/user').mkdir(parents=True)
                dmrc = root / 'home/user/.dmrc'
                dmrc.write_text('[Desktop]\nSession=plasma\nLanguage=en_US.UTF-8\n')
                config = root / 'guest.conf'
                config.write_text('stale guest override\n')
                isolated = script.replace('/etc/lightdm/lightdm.conf.d/60-aether-vmware-session.conf', './guest.conf')
                isolated = isolated.replace('/home/*/.dmrc', './home/*/.dmrc')
                isolated = isolated.replace('set -eu', 'set -eu\nexport PATH=/usr/bin:/bin:$PATH\nsystemd-detect-virt() { echo ' + hypervisor + '; }')
                hook = root / 'hook.sh'
                hook.write_text(isolated, newline='\n')
                for _ in range(2):
                    result = subprocess.run([bash, './hook.sh'], cwd=root,
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                if hypervisor in ('vmware', 'oracle'):
                    self.assertEqual(config.read_text(), '[Seat:*]\nuser-session=plasmax11\n')
                    self.assertEqual(dmrc.read_text().count('Session=plasmax11'), 1)
                    self.assertIn('Language=en_US.UTF-8', dmrc.read_text())
                else:
                    self.assertFalse(config.exists())
                    self.assertIn('Session=plasma\n', dmrc.read_text())


if __name__ == '__main__':
    unittest.main()
