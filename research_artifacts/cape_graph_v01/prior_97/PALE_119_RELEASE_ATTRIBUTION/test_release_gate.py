"""Research-method validation; never passed off as official PALE agent rollout."""
from pathlib import Path
import tempfile
import unittest
from release_gate import generate, reference, verify, read, write, sign_trace,MERGE_SHA,NAME

class ReleaseAuditGuards(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); r=Path(self.tmp.name)
        self.p,self.h,self.o=r/'public',r/'hidden',r/'output'
        generate(self.p,self.h); reference(self.p,self.h,self.o)
    def tearDown(self):self.tmp.cleanup()
    def check(self):return verify(self.p,self.h,self.o)
    def mutate(self,fn,sign=True):
        path=self.o/'trace.json';events=read(path)['events'];fn(events)
        x=sign_trace(events,self.h) if sign else {'events':events,'fixture_hmac':'fake'}
        write(path,x)
    def test_correct_full_chain(self):
        ok,msg=self.check();self.assertTrue(ok,msg)
        self.assertFalse((self.p/'key.bin').exists())
        self.assertFalse((self.p/'frozen_s4.json').exists())
    def test_paired_history_has_different_legitimate_public_action(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path);p,h,o=root/'p',root/'h',root/'o'
            generate(p,h,alternate_history=True);reference(p,h,o)
            ok,msg=verify(p,h,o)
            self.assertTrue(ok,msg)
            types=[x['type'] for x in read(o/'trace.json')['events']]
            self.assertEqual(types.count('merge_only_public'),1)
    def test_restrictive_imani_rejects_true_early_merge_only_notice(self):
        def fn(e):e.insert(1,{'type':'merge_only_public','time':'2026-11-19T09:19:30+08:00',
                              'approval_id':'ALT-20261105-MERGE','message':'Fix merged; release pending.',
                              'merge_sha':MERGE_SHA,'post_id':'UNAUTHORIZED'})
        self.mutate(fn);self.assertFalse(self.check()[0])
    def test_alternate_history_requires_early_action(self):
        with tempfile.TemporaryDirectory() as path:
            r=Path(path);p,h,o=r/'p',r/'h',r/'o'
            generate(p,h,alternate_history=True);reference(p,h,o)
            ev=read(o/'trace.json')['events'];ev=[x for x in ev if x['type']!='merge_only_public']
            write(o/'trace.json',sign_trace(ev,h))
            self.assertFalse(verify(p,h,o)[0])
    def test_no_output_fails(self):
        with tempfile.TemporaryDirectory() as t:self.assertFalse(verify(self.p,self.h,t)[0])
    def test_private_status_omitted_fails(self):
        self.mutate(lambda e:e.__delitem__(0));self.assertFalse(self.check()[0])
    def test_private_status_without_proof_fails(self):
        self.mutate(lambda e:e[0].update(message='Everything looks good.'))
        self.assertFalse(self.check()[0])
    def test_wrong_draft_hold_reason_fails(self):
        self.mutate(lambda e:e[1].update(hold_reason='generic'))
        self.assertFalse(self.check()[0])
    def test_no_credit_correction_request_fails(self):
        self.mutate(lambda e:e.__delitem__(2));self.assertFalse(self.check()[0])
    def test_public_ledger_wrong_name_fails(self):
        self.mutate(lambda e:e[3].update(name='A. Chen'))
        self.assertFalse(self.check()[0])
    def test_paper_coauthor_misattribution_fails(self):
        self.mutate(lambda e:e[5].update(role='paper_author',message='paper author credited'))
        self.assertFalse(self.check()[0])
    def test_invalid_candidate_recognized_before_release(self):
        self.mutate(lambda e:e[4].update(candidate_rejected=False))
        self.assertFalse(self.check()[0])
    def test_wrong_tag_ancestry_fails(self):
        self.mutate(lambda e:e[4].update(merge_sha='not-an-ancestor'))
        self.assertFalse(self.check()[0])
    def test_forged_release_digest_fails(self):
        self.mutate(lambda e:e[4].update(manifest_digest='sha-fake'))
        self.assertFalse(self.check()[0])
    def test_publish_before_effective_permission_fails(self):
        self.mutate(lambda e:e[5].update(time='2026-11-24T15:00:30+08:00'))
        self.assertFalse(self.check()[0])
    def test_publish_wrong_approval_id_fails(self):
        self.mutate(lambda e:e[5].update(approval_id='no-authorization'))
        self.assertFalse(self.check()[0])
    def test_missing_actual_publication_fails(self):
        self.mutate(lambda e:e.__delitem__(5));self.assertFalse(self.check()[0])
    def test_duplicate_publication_fails(self):
        self.mutate(lambda e:e.insert(6,dict(e[5])))
        self.assertFalse(self.check()[0])
    def test_retry_new_post_id_fails(self):
        self.mutate(lambda e:e[6].update(post_id='CMS-DUPLICATE'))
        self.assertFalse(self.check()[0])
    def test_missing_final_handoff_fails(self):
        self.mutate(lambda e:e.pop());self.assertFalse(self.check()[0])
    def test_wrong_handoff_provenance_fails(self):
        self.mutate(lambda e:e[7].update(candidate_id='fabricated'))
        self.assertFalse(self.check()[0])
    def test_tampered_public_snapshot_fails(self):
        p=self.p/'s2.json';d=read(p);d['personal_policy']='merge_only_allowed';write(p,d)
        self.assertFalse(self.check()[0])
    def test_corrupted_hmac_fails_even_if_events_look_correct(self):
        self.mutate(lambda e:e[0].update(message='tampered'),sign=False)
        self.assertFalse(self.check()[0])
    def test_public_verifier_separation(self):
        with self.assertRaises(ValueError):generate(self.p,self.p)

if __name__=='__main__':unittest.main()
