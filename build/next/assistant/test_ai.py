import hashlib, importlib.util, json, os, pathlib, tempfile, unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('aether_ai', pathlib.Path(__file__).with_name('aether-ai.py'))
ai=importlib.util.module_from_spec(spec);spec.loader.exec_module(ai)

class ModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=pathlib.Path(self.tmp.name)
        self.env=patch.dict(os.environ, {'XDG_DATA_HOME':str(self.root/'data')})
        self.env.start()
        self.source=self.root/'source';self.source.write_bytes(b'test model data')
        self.info={'filename':'model.gguf','url':self.source.as_uri(),
            'sha256':hashlib.sha256(self.source.read_bytes()).hexdigest(), 'bytes':self.source.stat().st_size}
    def tearDown(self):
        self.env.stop();self.tmp.cleanup()
    def test_valid_download(self):
        with patch.object(ai,'emit'):ai.download(self.info)
        self.assertEqual(ai.model_path(self.info).read_bytes(), self.source.read_bytes())
    def test_bad_hash_preserves_existing_model(self):
        dest=ai.model_path(self.info);dest.write_bytes(b'old model')
        self.info['sha256']='0'*64
        with patch.object(ai,'emit'),self.assertRaises(ValueError):ai.download(self.info)
        self.assertEqual(dest.read_bytes(),b'old model')
        self.assertFalse(list(dest.parent.glob('*.part')))
    def test_oversized_download_rejected(self):
        self.info['bytes']=2
        with patch.object(ai,'emit'),self.assertRaises(ValueError):ai.download(self.info)
        self.assertFalse(ai.model_path(self.info).exists())
    def test_filename_traversal_rejected(self):
        self.info['filename']='../escape.gguf'
        with self.assertRaises(ValueError):ai.model_path(self.info)
    def test_no_model_does_not_start_inference(self):
        session=ai.Session(self.info)
        with patch.object(ai.subprocess,'Popen') as spawn,self.assertRaises(ValueError):session.start()
        spawn.assert_not_called()
    def test_corrupt_model_does_not_start_inference(self):
        ai.model_path(self.info).write_bytes(b'corrupted weights')
        session=ai.Session(self.info)
        with patch.object(ai,'emit'),patch.object(ai.subprocess,'Popen') as spawn,self.assertRaises(ValueError):
            session.start()
        spawn.assert_not_called()
    def test_oversized_prompt_rejected_before_inference(self):
        session=ai.Session(self.info)
        with patch.object(session,'start') as start,self.assertRaises(ValueError):session.answer('x'*6001)
        start.assert_not_called()

if __name__=='__main__':unittest.main()
