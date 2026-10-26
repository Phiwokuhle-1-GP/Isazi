"""PDF tests use the same database-independent state as the live route."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from state import seed_state
from status_report import build_status_pdf

class StatusPDFTests(unittest.TestCase):
    def test_report_contains_real_steps_and_version(self):
        state = seed_state()
        data = build_status_pdf(state, 12, [])
        self.assertTrue(data.startswith(b'%PDF-'))
        self.assertGreater(len(data),3000)
        try:
            import fitz
        except ImportError:
            return
        d=fitz.open(stream=data,filetype='pdf')
        text='\n'.join(p.get_text() for p in d)
        self.assertIn('Domain registration',text)
        self.assertIn('version 12',text)
        self.assertIn('Awaiting client',text)
        self.assertIn('No concept is officially selected yet',text)
    def test_notes_and_updated_status(self):
        state=seed_state()
        step=state['client_steps'][0]
        step['status']='Completed'
        state['designs'][0]['status']='Selected'
        notes=[dict(subject_type='step',subject_id=step['id'],author='client1',feedback_type='Comment',comment='Our registrar confirmed the domain',created_at='2026-10-26T14:15:00+00:00')]
        data=build_status_pdf(state, 13, notes)
        self.assertTrue(data.startswith(b'%PDF-'))
        try:import fitz
        except ImportError:return
        text=' '.join(p.get_text() for p in fitz.open(stream=data,filetype='pdf'))
        self.assertIn('Botanical Classic',text)
        self.assertIn('Our registrar confirmed the domain',text)
        self.assertIn('1 / 9',text)

if __name__=='__main__':unittest.main()
