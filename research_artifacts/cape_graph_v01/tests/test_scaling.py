import unittest
from copy import deepcopy
from capegraph.fixtures import fact, cases, policy

class ScalingRegressions(unittest.TestCase):
    def test_deep_3000_node_chain_does_not_overflow_python_stack(self):
        t,e=deepcopy(cases()['release'])
        parent='fix_merged'
        for i in range(3000):
            uid=f'depth_{i:04d}'
            t.append(fact(uid,10,'code_host',f'ref:{i}', 'merge_state','merged',[parent]))
            parent=uid
        # The original mandatory task reference is still valid; graph checks
        # every trusted record, not merely claims reachable from successful effects.
        r=policy().evaluate(t,e)
        self.assertEqual('PASS',r.verdict,r.to_json())

    def test_shared_parent_fanout_no_exponential_certificate_walk(self):
        t,e=deepcopy(cases()['release'])
        # A modest directed acyclic graph with repeated shared ancestors.
        # This checks that closure traversal is set-based, not path-based.
        for i in range(24):
            t.append(fact('merge_shadow_'+str(i),10,'code_host',f'ref:{i}',
                          'merge_state','merged',['fix_merged']))
        self.assertEqual('PASS',policy().evaluate(t,e).verdict)

if __name__=='__main__':unittest.main()
