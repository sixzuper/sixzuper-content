import sys
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ig_generate_daily_login as m  # type: ignore[reportMissingImports]

WIB=timezone(timedelta(hours=7))
NOW=datetime(2026,10,22,5,15,tzinfo=WIB)

def raw():
    body=' '.join(['STB dapat menjadi tempat belajar Linux dan home lab secara bertahap.']*10)
    return {'posts':[{'title':'Tahap belajar','card_title':'BELAJAR DI STB',
            'card_lines':['Mulai dari SSH','Pantau satu layanan','Catat langkah berikutnya'],
            'caption':body} for _ in range(3)]}

class GenerationTests(unittest.TestCase):
    def test_three_structured_slots(self):
        p=m.structure(raw(),NOW)
        self.assertEqual([x['id'] for x in p],['20261022-08','20261022-13','20261022-19'])
        self.assertEqual(len(set(x['caption'].split('#SZP')[1][:10] for x in p)),3)

    def test_missing_records_rejected(self):
        p=raw();p['posts']=p['posts'][:2]
        with self.assertRaisesRegex(RuntimeError,'Exactly three'):m.structure(p,NOW)

    def test_long_card_rejected(self):
        p=raw();p['posts'][0]['card_lines'][0]='K'*50
        with self.assertRaisesRegex(RuntimeError,'malformed'):m.structure(p,NOW)

    def test_full_daily_production_invokes_three_slots_without_meta(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            with patch.object(m,'ROOT',Path(td)), patch.object(m,'generate',return_value=raw()), patch.object(m,'run_batch') as run:
                self.assertEqual(m.main(dry_run=False,now=NOW),3)
                run.assert_called_once()
                self.assertEqual(len(run.call_args.args[0]),3)
                self.assertEqual(len(list((Path(td)/'data/ig-generated').glob('*.json'))),3)

    def test_existing_drafts_resume_without_regenerating(self):
        import json,tempfile
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base=root/'data/ig-generated';base.mkdir(parents=True)
            for d in m.structure(raw(),NOW):
                (base/(d['id']+'.json')).write_text(json.dumps(d))
            (root/'queue.json').write_text(json.dumps({'posts':[]}))
            with patch.object(m,'ROOT',root),patch.object(m,'generate') as generate,patch.object(m,'run_batch') as batch:
                self.assertEqual(m.main(now=NOW),3)
                generate.assert_not_called()
                batch.assert_called_once()

    def test_existing_queued_slots_are_noop(self):
        import json,tempfile
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base=root/'data/ig-generated';base.mkdir(parents=True)
            rows=m.structure(raw(),NOW)
            for d in rows:(base/(d['id']+'.json')).write_text(json.dumps(d))
            (root/'queue.json').write_text(json.dumps({'posts':[{**d,'status':'scheduled'} for d in rows]}))
            with patch.object(m,'ROOT',root),patch.object(m,'generate') as generate,patch.object(m,'run_batch') as batch:
                self.assertEqual(m.main(now=NOW),3)
                generate.assert_not_called()
                batch.assert_not_called()

    def test_friday_missing_source_rejected(self):
        friday=NOW+timedelta(days=1)
        with self.assertRaisesRegex(RuntimeError,'approved article'):m.structure(raw(),friday)
        with patch.object(m,'generate') as generate:
            with self.assertRaisesRegex(RuntimeError,'source-claim review'):
                m.main(dry_run=True,now=friday)
            generate.assert_not_called()

if __name__=='__main__':unittest.main()
