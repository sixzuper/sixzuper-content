import base64
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ig_ai_illustration as m  # type: ignore[reportMissingImports]
import prepare_ig_slot_login as producer  # type: ignore[reportMissingImports]

class ImagePipelineTests(unittest.TestCase):
    def setUp(self):
        self.draft=json.loads((Path(__file__).resolve().parents[1]/'content/ig-slot-proof-20261021-13.json').read_text())

    @staticmethod
    def api_image():
        im=Image.new('RGB',(1024,1280),(55,80,120));out=io.BytesIO();im.save(out,'PNG')
        return base64.b64encode(out.getvalue()).decode()

    def test_generates_topic_specific_art_to_private_file(self):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/'test.png'
            response=Mock(ok=True,status_code=200)
            response.json.return_value={'candidates':[{'content':{'parts':[{'inlineData':{'mimeType':'image/png','data':self.api_image()}}]}}]}
            with patch.object(m.requests,'post',return_value=response) as send:
                info=m.generate(self.draft,target,'fixture-secret')
            with Image.open(target) as image:
                self.assertEqual(image.size,(1024,1280))
            self.assertEqual(target.stat().st_mode & 0o777,0o600)
            self.assertIn('STB',send.call_args.kwargs['json']['contents'][0]['parts'][0]['text'])
            self.assertNotIn('fixture-secret',str(info))
            self.assertEqual(info['model'],m.MODEL)

    def test_quota_failure_never_writes_image_or_logs_secret(self):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/'test.png';response=Mock(ok=False,status_code=429)
            response.json.return_value={'error':{'code':429,'status':'RESOURCE_EXHAUSTED','message':'fixture-secret'}}
            with patch.object(m.requests,'post',return_value=response):
                with self.assertRaisesRegex(RuntimeError,'HTTP 429') as err:
                    m.generate(self.draft,target,'fixture-secret')
            self.assertNotIn('fixture-secret',str(err.exception))
            self.assertFalse(target.exists())

    def test_corrupt_or_tiny_image_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/'test.png';response=Mock(ok=True,status_code=200)
            response.json.return_value={'candidates':[{'content':{'parts':[{'inlineData':{'mimeType':'image/png','data':base64.b64encode(b'not an image').decode()}}]}}]}
            with patch.object(m.requests,'post',return_value=response):
                with self.assertRaisesRegex(RuntimeError,'invalid'):
                    m.generate(self.draft,target,'fixture-secret')
            self.assertFalse(target.exists())

    def test_overlay_uses_generated_background_and_keeps_jpeg(self):
        with tempfile.TemporaryDirectory() as td:
            background=Path(td)/'bg.png';out=Path(td)/'post.jpg'
            Image.new('RGB',(1024,1280),(55,80,120)).save(background)
            producer.render(self.draft,out,background=background)
            with Image.open(out) as image:
                self.assertEqual((image.format,image.size,image.mode),('JPEG',(1080,1350),'RGB'))
                self.assertNotEqual(image.getpixel((540,550)),image.getpixel((540,220)))

    def test_preview_composites_only_after_generation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);draft_file=root/'draft.json';draft_file.write_text(json.dumps(self.draft))
            env=root/'.env';env.write_text('GOOGLE_API_KEY=fixture-secret\n');env.chmod(0o600)
            def image(d, path, key):
                Image.new('RGB',(1024,1280),(55,80,120)).save(path,'PNG')
                return {'model':m.MODEL}
            with patch.object(m,'generate',side_effect=image):
                output=m.preview(draft_file,root/'out',env)
            with Image.open(output) as im:
                self.assertEqual((im.format,im.size),('JPEG',(1080,1350)))
            with self.assertRaisesRegex(RuntimeError,'already exists'):
                m.preview(draft_file,root/'out',env)

    def test_preview_quota_failure_does_not_create_jpeg(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);draft_file=root/'draft.json';draft_file.write_text(json.dumps(self.draft))
            env=root/'.env';env.write_text('GOOGLE_API_KEY=fixture-secret\n');env.chmod(0o600)
            with patch.object(m,'generate',side_effect=RuntimeError('Image API HTTP 429')):
                with self.assertRaisesRegex(RuntimeError,'HTTP 429'):
                    m.preview(draft_file,root/'out',env)
            self.assertFalse(list((root/'out').glob('*.jpg')))

if __name__=='__main__':unittest.main()
