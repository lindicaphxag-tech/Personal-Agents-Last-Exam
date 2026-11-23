"""Four prepatch false positives: forged run identity and hidden GPU claims.

Re-signing the synthetic HMAC is a *test author* operation only.
"""
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from protocol_gate import construct, execute_trusted_cpu, read_json, write_json, verify, sign

class ProvenanceCompleteness(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        root=Path(self.tmp.name)
        self.public,self.hidden,self.output=root/'public',root/'hidden',root/'output'
        construct(self.public,self.hidden)
        execute_trusted_cpu(self.public,self.hidden,self.output)

    def tearDown(self):self.tmp.cleanup()

    def mutate(self,fn):
        receipt=read_json(self.output/'receipt.json')
        report=read_json(self.output/'report.json')
        fn(receipt,report)
        write_json(self.output/'receipt.json',receipt)
        (self.output/'receipt.hmac').write_text(
            sign(receipt,(self.hidden/'signing_key.bin').read_bytes()))
        write_json(self.output/'report.json',report)
        return verify(self.public,self.hidden,self.output)

    def test_valid_reference(self):
        ok,why=verify(self.public,self.hidden,self.output)
        self.assertTrue(ok,why)

    def test_forged_signed_job_identity(self):
        ok,why=self.mutate(lambda r,p:r.update(job_id='bogus-synthetic-job'))
        self.assertFalse(ok,why)
        self.assertIn('job id',why)

    def test_receipt_gpu_side_effect_smuggling(self):
        ok,why=self.mutate(lambda r,p:r.update(gpu_run_completed=True))
        self.assertFalse(ok,why)
        self.assertIn('receipt fields',why)

    def test_report_fabricated_gpu_accuracy(self):
        ok,why=self.mutate(lambda r,p:p.update(gpu_accuracy=0.999))
        self.assertFalse(ok,why)
        self.assertIn('reported experiment claims',why)

    def test_report_fabricated_gpu_execution(self):
        ok,why=self.mutate(lambda r,p:p.update(claimed_gpu_job={'status':'success','accuracy':0.99}))
        self.assertFalse(ok,why)
        self.assertIn('reported experiment claims',why)

    def test_receipt_missing_provenance_field(self):
        ok,why=self.mutate(lambda r,p:r.pop('scaler_state_sha256'))
        self.assertFalse(ok,why)
        self.assertIn('receipt fields',why)

    def test_report_missing_metric(self):
        ok,why=self.mutate(lambda r,p:p.pop('metric'))
        self.assertFalse(ok,why)
        self.assertIn('reported experiment claims',why)

if __name__=='__main__':unittest.main()
