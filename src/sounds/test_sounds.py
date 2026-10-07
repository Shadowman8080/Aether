# SPDX-License-Identifier: GPL-3.0-or-later
import array
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave
import generate
import manage


class SoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = generate.generate(Path(cls.temp.name))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_audio_format_levels_edges_and_distinct_events(self):
        manifest = manage.validate(self.root)
        hashes = set()
        for entry in manifest['sounds']:
            with self.subTest(event=entry['event']):
                with wave.open(str(self.root / entry['file'])) as f:
                    samples = array.array('h', f.readframes(f.getnframes()))
                if sys.byteorder != 'little':
                    samples.byteswap()
                self.assertGreater(len(samples), 4800)
                self.assertLess(len(samples), 48000 * 3)
                self.assertEqual(list(samples[-96:]), [0] * 96)
                self.assertEqual(samples[0], 0)
                peak = max(map(abs, samples))
                self.assertGreater(peak, 1000)
                self.assertLessEqual(peak, 8300)  # At least 11.9 dB of digital headroom.
                self.assertLess(abs(sum(samples) / len(samples)), 15)
                rms = math.sqrt(sum(v*v for v in samples) / len(samples))
                self.assertGreater(rms, 100)
                self.assertLess(max(abs(b-a) for a, b in zip(samples, samples[1:])), 4000)
                hashes.add(entry['sha256'])
        self.assertEqual(len(hashes), 42)

    def test_repeatable_recipe(self):
        self.assertEqual(generate.synth(generate.BANK[0]), generate.synth(generate.BANK[0]))

    def test_tampering_is_rejected(self):
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'theme'; shutil.copytree(self.root, root)
            p = root / 'stereo/desktop-login.wav'; p.write_bytes(p.read_bytes()[:-8])
            with self.assertRaisesRegex(ValueError, 'checksum'):
                manage.validate(root)

    def test_path_escape_is_rejected(self):
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'theme'; shutil.copytree(self.root, root)
            p = root / 'manifest.json'; data = json.loads(p.read_text())
            data['sounds'][0]['file'] = '../../outside.wav'; p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'path'):
                manage.validate(root)

    def test_install_upgrade_preserves_old_theme(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            with patch.dict(os.environ, {'XDG_DATA_HOME': str(base/'data'), 'XDG_STATE_HOME': str(base/'state')}):
                manage.install(self.root)
                (base/'data/sounds/AetherGlass/user-note').write_text('Keep my previous files')
                manage.install(self.root)
                backups = list((base/'data/sounds').glob('.AetherGlass.backup-*'))
                self.assertEqual(len(backups), 1)
                self.assertEqual((backups[0]/'user-note').read_text(), 'Keep my previous files')
                manage.validate(base/'data/sounds/AetherGlass')

    def test_activation_preserves_mute_and_remembers_previous_theme(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            with patch.dict(os.environ, {'XDG_DATA_HOME': str(base/'data'), 'XDG_STATE_HOME': str(base/'state')}):
                manage.install(self.root)
                with patch.object(manage, 'kde_read', return_value='my-existing-theme'), patch.object(manage, 'kde_write') as write:
                    manage.activate()
                    write.assert_called_once_with('Theme', 'AetherGlass')
                with patch.object(manage, 'kde_read', return_value='AetherGlass'), patch.object(manage, 'kde_write'):
                    manage.activate()
                saved = json.loads((base/'state/aether-sounds/previous-theme.json').read_text())
                self.assertEqual(saved['Theme'], 'my-existing-theme')

    def test_failed_replacement_restores_existing_theme(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            with patch.dict(os.environ, {'XDG_DATA_HOME': str(base/'data'), 'XDG_STATE_HOME': str(base/'state')}):
                manage.install(self.root)
                target = base/'data/sounds/AetherGlass'
                (target/'user-note').write_text('original')
                rename = Path.rename
                def fail_staged(path, destination):
                    if path.parent.name.startswith('.aether-sounds-'):
                        raise OSError('simulated replacement failure')
                    return rename(path, destination)
                with patch.object(Path, 'rename', fail_staged):
                    with self.assertRaisesRegex(OSError, 'simulated'):
                        manage.install(self.root)
                self.assertEqual((target/'user-note').read_text(), 'original')


if __name__ == '__main__':
    unittest.main(verbosity=2)
