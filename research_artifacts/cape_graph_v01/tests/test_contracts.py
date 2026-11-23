"""Finite CEGIS correctness, independently enumerated minimum contracts and safety."""
import random
import unittest
from itertools import product

from capegraph.contracts import (Atom, Trace, Contract, greedy_contract,
                                 synthesize_contract, independent_oracle,
                                 audit_frozen_split)
from capegraph.planner import Need, Witness


def a(name, cost=1):
    return Atom(name, Need(name, 'ok', ('service',), 10, 100), cost)


def w(name, value='ok', issuer='service', at=40):
    return Witness(name, value, issuer, at)


def sample(name, present, valid):
    return Trace(name, tuple(w(x) for x in present), valid)


class ContractSynthesisTests(unittest.TestCase):
    def test_exact_minimal_hitting_set_beats_greedy(self):
        atoms = (a('A'), a('B'), a('C'))
        pos = (sample('p', ('A', 'B', 'C'), True),)
        missing = [('A','B'),('A','B'),('A','C'),('A','C'),('B',),('C',)]
        neg = tuple(sample('n'+str(i), tuple(q for q in ('A','B','C') if q not in gaps), False)
                    for i, gaps in enumerate(missing))
        exact = synthesize_contract(atoms, pos, neg)
        self.assertEqual(exact.status, 'SEPARATED')
        self.assertEqual(tuple(x.name for x in exact.contract.atoms), ('B','C'))
        self.assertEqual(exact.contract.total_cost, 2)
        self.assertEqual(greedy_contract(atoms,pos,neg).total_cost, 3)
        self.assertEqual(exact.contract, independent_oracle(atoms,pos,neg))
        self.assertEqual(len(exact.rejected_negatives), 6)
        self.assertTrue(all(m for _,m in exact.rejected_negatives))

    def test_unknown_never_becomes_proven_violation(self):
        c=Contract((a('a'),),1)
        self.assertEqual(c.evaluate(()),'UNVERIFIED')
        self.assertEqual(c.with_effect_audit((w('a'),),'UNVERIFIED'),'UNVERIFIED')
        self.assertEqual(c.with_effect_audit((w('a'),),'FAIL'),'FAIL')
        self.assertEqual(c.with_effect_audit((w('a'),),'PASS'),'PASS')
        self.assertEqual(c.with_effect_audit((),'PASS'),'UNVERIFIED')
        with self.assertRaises(ValueError): c.with_effect_audit((w('a'),),'ok')

    def test_nonseparable_evidence_indistinguishability(self):
        p=sample('p',('a','b'),True)
        n=sample('n',('a','b'),False)
        c=synthesize_contract([a('a'),a('b')],[p],[n])
        self.assertEqual(c.status,'UNIDENTIFIABLE')
        self.assertEqual(c.indistinguishable,'n')
        self.assertEqual(c.contract.evaluate(p.receipts),'UNVERIFIED')

    def test_only_shared_positive_compatible_atoms_can_be_learned(self):
        pos=(sample('p1',('a','b'),True),sample('p2',('a',),True))
        neg=(sample('n1',('b',),False),)
        c=synthesize_contract([a('a'),a('b')],pos,neg)
        self.assertEqual(tuple(x.name for x in c.contract.atoms),('a',))
        self.assertTrue(all(c.contract.evaluate(x.receipts)=='PASS' for x in pos))

    def test_exact_obligation_checks_issuer_time_latest_conflict(self):
        atom=a('a')
        c=Contract((atom,),1)
        good=w('a')
        self.assertEqual(c.evaluate((good,)), 'PASS')
        self.assertEqual(c.evaluate((w('a','ok','attacker'),)), 'UNVERIFIED')
        self.assertEqual(c.evaluate((w('a','ok','service',9),)), 'UNVERIFIED')
        self.assertEqual(c.evaluate((w('a','ok','service',101),)), 'UNVERIFIED')
        self.assertEqual(c.evaluate((good,w('a','revoked','service',40))), 'UNVERIFIED')
        self.assertEqual(c.evaluate((good,w('a','revoked','service',50))), 'UNVERIFIED')
        self.assertEqual(c.evaluate((w('a','revoked','service',39),good)), 'PASS')

    def test_costed_minimum_not_just_fewest_rules(self):
        atoms=[a('x',1),a('y',1),a('z',10)]
        pos=[sample('p',('x','y','z'),True)]
        neg=[sample('n1',('y',),False),sample('n2',('x',),False)]
        # z is absent in both negatives but costs 10; x+y costs 2.
        c=synthesize_contract(atoms,pos,neg)
        self.assertEqual(c.contract.total_cost,2)
        self.assertEqual(tuple(z.name for z in c.contract.atoms),('x','y'))

    def test_determinism_on_input_order(self):
        atoms=[a(k) for k in 'abcd']
        pos=[sample('p',list('abcd'),True)]
        neg=[sample('n1',['a','b'],False),sample('n2',['c','d'],False),
             sample('n3',['a','d'],False)]
        first=synthesize_contract(atoms,pos,neg)
        second=synthesize_contract(reversed(atoms),pos,neg)
        self.assertEqual(first.contract,second.contract)
        self.assertEqual(first.as_dict()['contract'],second.as_dict()['contract'])

    def test_frozen_test_is_read_only(self):
        c=Contract((a('a'),),1)
        stats=audit_frozen_split(c,[sample('p1',['a'],True),sample('p2',[],True)],
                              [sample('n1',[],False),sample('n2',['a'],False)])
        self.assertEqual(stats,{'valid_count':2,'invalid_count':2,'valid_accepted':1,
                                'valid_withheld':1,'invalid_falsely_accepted':1,'invalid_withheld':1})
        self.assertEqual(c.total_cost,1)

    def test_malformed_intent_contracts_rejected(self):
        with self.assertRaises(ValueError): a('a',0)
        with self.assertRaises(ValueError): Contract((a('a'),a('a')),2)
        with self.assertRaises(ValueError): synthesize_contract([a('a')],
                                      [sample('p',('a',),True)],[])
        with self.assertRaises(ValueError): synthesize_contract([a('a'),a('a')],
                                      [sample('p',('a',),True)],[sample('n',(),False)])
        with self.assertRaises(ValueError): synthesize_contract([a('a')],
                                      [sample('p',(),False)],[sample('n',(),False)])

    def test_source_hashes_are_reproducible(self):
        x=Contract((a('a'),a('b')),2).as_dict()
        self.assertEqual(len(x['sha256_without_digest']),64)
        self.assertEqual(x,Contract((a('a'),a('b')),2).as_dict())

    def test_binary_random_cases_agree_with_fully_independent_exhaustive_oracle(self):
        for seed in range(210):
            rng=random.Random(20261124+seed)
            n=rng.randint(2,9)
            atoms=[a('q'+str(i),rng.randint(1,6)) for i in range(n)]
            tokens=[a.name for a in atoms]
            positives=[sample('p',tokens,True)]
            negs=[]
            for j in range(rng.randint(1,9)):
                tokens_present=[z for z in tokens if rng.random()>0.4]
                negs.append(sample('n'+str(j),tokens_present,False))
            result=synthesize_contract(atoms,positives,negs)
            independent=independent_oracle(atoms,positives,negs)
            self.assertEqual(result.status=='SEPARATED',independent is not None,seed)
            if independent is not None:
                self.assertEqual(result.contract, independent, seed)
                self.assertTrue(all(result.contract.evaluate(q.receipts)=='PASS' for q in positives))
                self.assertTrue(all(result.contract.evaluate(q.receipts)!='PASS' for q in negs))

    def test_maximum_candidate_bound(self):
        pos=[sample('p',tuple('a'),True)]
        neg=[sample('n',(),False)]
        atoms=[a(str(k)) for k in range(25)]
        with self.assertRaises(ValueError):synthesize_contract(atoms,pos,neg)


if __name__=='__main__':
    unittest.main()
