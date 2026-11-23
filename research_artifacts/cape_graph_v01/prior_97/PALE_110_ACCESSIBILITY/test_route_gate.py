import tempfile
from pathlib import Path
import unittest
from datetime import datetime
from route_gate import construct, reference, verify, read, dump, sign_events,route_duration,GRAPH

class DispatchedResearchTask(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        self.p,self.h,self.o=root/'public',root/'hidden',root/'out'
        construct(self.p,self.h);reference(self.p,self.h,self.o)
    def tearDown(self):self.tmp.cleanup()
    def check(self):return verify(self.p,self.h,self.o)
    def mutate(self,change):
        f=self.o/'trace.json';e=read(f)['events'];change(e);dump(f,sign_events(e,self.h))

    def test_reference_valid(self):self.assertTrue(self.check()[0],self.check()[1])
    def test_no_op_rejected(self):
        with tempfile.TemporaryDirectory() as out:self.assertFalse(verify(self.p,self.h,out)[0])
    def test_stairs_assigned_to_stepfree_volunteer(self):
        self.mutate(lambda e:e[0].update(route=['depot-east-stairs','east-kitb-stairs']))
        self.assertFalse(self.check()[0])
    def test_closed_lift_rejected(self):
        self.mutate(lambda e:e[0].update(route=['depot-center-lift','center-kitb']))
        self.assertFalse(self.check()[0])
    def test_stairs_ok_only_for_different_user_history(self):
        when=datetime.fromisoformat('2026-11-21T09:20:00+08:00')
        route=['depot-east-stairs','east-kitb-stairs']
        self.assertEqual(route_duration(GRAPH,route,'depot','kitb',when,False),15)
        with self.assertRaises(ValueError):route_duration(GRAPH,route,'depot','kitb',when,True)
    def test_wrong_item_consent_rejected(self):
        self.mutate(lambda e:e[1].update(item='KIT-B'))
        self.assertFalse(self.check()[0])
    def test_transfer_before_acceptance_rejected(self):
        self.mutate(lambda e:e[4].update(time='2026-11-21T14:00:00+08:00'))
        self.assertFalse(self.check()[0])
    def test_custody_transfer_without_any_acceptance_rejected(self):
        self.mutate(lambda e:e.__delitem__(3))
        ok, why=self.check()
        self.assertFalse(ok)
        self.assertIn('consent', why)
    def test_wrong_custody_destination_rejected(self):
        self.mutate(lambda e:e[4].update(to='Jules'))
        self.assertFalse(self.check()[0])
    def test_wrong_receipt_destination_rejected(self):
        self.mutate(lambda e:e[6].update(destination='kitb'))
        self.assertFalse(self.check()[0])
    def test_receipt_without_route_rejected(self):
        self.mutate(lambda e:e.__delitem__(5))
        self.assertFalse(self.check()[0])
    def test_duplicate_receipt_rejected(self):
        self.mutate(lambda e:e.insert(7,dict(e[6])))
        self.assertFalse(self.check()[0])
    def test_delivered_after_cutoff_rejected(self):
        self.mutate(lambda e:e[6].update(time='2026-11-21T17:30:00+08:00'))
        self.assertFalse(self.check()[0])
    def test_disconnected_edge_list_rejected(self):
        self.mutate(lambda e:e[0].update(route=['depot-garden','library-kitb']))
        self.assertFalse(self.check()[0])
    def test_forged_unsigned_receipt_rejected(self):
        f=self.o/'trace.json';t=read(f);t['events'][6]['receipt_id']='FAKE';dump(f,t)
        self.assertFalse(self.check()[0])
    def test_kita_duplicate_not_allowed(self):
        self.mutate(lambda e:e.append(dict(type='receipt',time='2026-11-21T15:00:00+08:00',item='KIT-A',destination='kit_a',volunteer='Jules',receipt_id='FAKE-A')))
        self.assertFalse(self.check()[0])
    def test_tampered_source_manifest_rejected(self):
        f=self.p/'dispatch.json';m=read(f);m['jules_step_free_only']=False;dump(f,m)
        self.assertFalse(self.check()[0])
    def test_public_and_verifier_roots_separate(self):
        with self.assertRaises(ValueError):construct(self.p,self.p)

if __name__=='__main__':unittest.main()
