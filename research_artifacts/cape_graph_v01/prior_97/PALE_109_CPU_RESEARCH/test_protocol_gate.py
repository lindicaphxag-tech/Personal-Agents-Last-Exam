"""Independent negative-controls for synthetic PALE #109 scientific provenance."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np

from protocol_gate import (TRAIN_IDS, TEST_IDS, construct, execute_trusted_cpu,
                           read_json, write_json, verify, sign)


class FrozenProtocolGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.public, self.hidden, self.out = root / 'public', root / 'hidden', root / 'out'
        construct(self.public, self.hidden)
        execute_trusted_cpu(self.public, self.hidden, self.out)

    def tearDown(self):
        self.tmp.cleanup()

    def good(self):
        return verify(self.public, self.hidden, self.out)

    def mutate_receipt(self, fn, resign=True):
        path = self.out / 'receipt.json'
        d = read_json(path)
        fn(d)
        write_json(path, d)
        if resign:
            (self.out / 'receipt.hmac').write_text(sign(d, (self.hidden / 'signing_key.bin').read_bytes()))

    def test_reference_and_sealed_holdout(self):
        ok, reason = self.good()
        self.assertTrue(ok, reason)
        self.assertEqual(len(TEST_IDS), 9)
        self.assertFalse(set(TRAIN_IDS) & set(TEST_IDS))
        self.assertFalse((self.public / 'signing_key.bin').exists())
        self.assertFalse((self.public / 'test_labels.npz').exists())
        self.assertFalse((self.public / 'frozen_protocol.json').exists())

    def test_independent_seeds_have_valid_runs(self):
        for seed in (20261122, 20261203, 17):
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as t:
                t = Path(t)
                construct(t / 'public', t / 'hidden', seed)
                execute_trusted_cpu(t / 'public', t / 'hidden', t / 'out')
                ok, reason = verify(t / 'public', t / 'hidden', t / 'out')
                self.assertTrue(ok, reason)

    def test_empty_result_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertFalse(verify(self.public, self.hidden, t)[0])

    def test_fabricated_signature_rejected(self):
        self.mutate_receipt(lambda d: d.update(job_id='fake1234'), resign=False)
        ok, reason = self.good()
        self.assertFalse(ok)
        self.assertIn('signature', reason)

    def test_gpu_claim_rejected_even_with_forged_trusted_receipt(self):
        self.mutate_receipt(lambda d: d.update(job_type='GPU'))
        self.assertFalse(self.good()[0])

    def test_failed_execution_rejected_even_when_signed(self):
        self.mutate_receipt(lambda d: d.update(status='failed', exit_code=137))
        self.assertFalse(self.good()[0])

    def test_test_subject_in_training_fit_rejected(self):
        self.mutate_receipt(lambda d: d['fit_subject_ids'].append(TEST_IDS[0]))
        ok, why = self.good()
        self.assertFalse(ok)
        self.assertIn('leaked', why)

    def test_trial_level_substitution_rejected(self):
        self.mutate_receipt(lambda d: d.update(primary_estimand='within_subject_trial_generalization'))
        self.assertFalse(self.good()[0])

    def test_swapped_holdout_rejected_even_when_no_overlap(self):
        self.mutate_receipt(lambda d: d['test_subject_ids'].__setitem__(0, 'S99'))
        self.assertFalse(self.good()[0])

    def test_prediction_content_change_rejected(self):
        file = self.out / 'predictions.npz'
        with np.load(file, allow_pickle=False) as z:
            p = z['y_pred'].copy()
        p[0] = 1 - p[0]
        np.savez_compressed(file, y_pred=p)
        self.assertFalse(self.good()[0])

    def test_wrong_metric_rejected(self):
        file = self.out / 'report.json'
        data = read_json(file)
        data['score'] = 0.999
        write_json(file, data)
        ok, reason = self.good()
        self.assertFalse(ok)
        self.assertIn('score', reason)

    def test_wrong_uncertainty_rejected(self):
        file = self.out / 'report.json'
        data = read_json(file)
        data['subject_bootstrap_95ci'] = [0, 1]
        write_json(file, data)
        self.assertFalse(self.good()[0])

    def test_fabricated_gpu_report_rejected(self):
        file = self.out / 'report.json'
        d = read_json(file)
        d['gpu_run_status'] = 'completed'
        write_json(file, d)
        self.assertFalse(self.good()[0])

    def test_modified_protocol_rejected(self):
        file = self.public / 'protocol.json'
        d = read_json(file)
        d['test_subject_ids'][0] = 'S99'
        write_json(file, d)
        self.assertFalse(self.good()[0])

    def test_modified_training_data_rejected(self):
        file = self.public / 'train.npz'
        with file.open('ab') as stream:
            stream.write(b'junk')
        self.assertFalse(self.good()[0])

    def test_secret_and_public_cannot_overlap(self):
        with self.assertRaises(ValueError):
            construct(self.public, self.public)


if __name__ == '__main__':
    unittest.main()
