"""Deterministic reproducible two-prior mixed-policy game checks.

The 240 balanced problems are deliberately constructed to stress pure-policy
randomization. The 180 frozen v0.4 cases are retained as a non-enriched check.
No external task, model rollout, actual user transaction or empirical prior.
"""
from __future__ import annotations

import json
import random
import sys
from fractions import Fraction as F
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from capegraph.adaptive import Probe,World
from capegraph.core import digest
from capegraph.mixed import solve_mixed,independent_replay,exact_two_prior_game_reference
from capegraph.planner import Goal,Need,Witness
from capegraph.robust import Prior,solve_robust
from experiments.robust_benchmark import random_case,coupled_case

UNFILTERED = 180
BALANCED = 240
SEED = 2026112400


def balanced_problem(seed):
    """Explicitly selected conflict-of-interest cases, not iid agent logs."""
    rng=random.Random(seed)
    vA=rng.randint(4,20);vB=rng.randint(4,20)
    prior_gap=F(rng.randint(6,9),10) # 0.6 to 0.9 A-prior
    gs=(Goal('A',(Need('A','ok',('official',),0,100),),vA),
        Goal('B',(Need('B','ok',('official',),0,100),),vB))
    qs=(Probe('proofA',1,'official'),Probe('proofB',1,'official'))
    ws=(World('A',F(1,2),{'proofA':(Witness('A','ok','official',10),),'proofB':()}),
        World('B',F(1,2),{'proofA':(),'proofB':(Witness('B','ok','official',10),)}))
    ps=(Prior('A-skew',{'A':prior_gap,'B':1-prior_gap}),
        Prior('B-skew',{'A':1-prior_gap,'B':prior_gap}))
    return gs,qs,ws,1,ps


def _one(name,problem):
    gs,qs,ws,b,ps=problem
    exact=solve_mixed(gs,qs,ws,b,ps)
    pure=solve_robust(gs,qs,ws,b,ps)
    assert exact.guaranteed_reward>=pure.worst_case_reward
    assert exact.dual_upper_bound==exact.guaranteed_reward
    assert independent_replay(exact,ws,qs,gs,ps)==(exact.guaranteed_reward,exact.max_expected_cost)
    return {
        'case':name,'budget':b,'worlds':len(ws),'queries':len(qs),
        'mixed':str(exact.guaranteed_reward),'deterministic':str(pure.worst_case_reward),
        'gain':str(exact.guaranteed_reward-pure.worst_case_reward),
        'strictly_better':exact.guaranteed_reward>pure.worst_case_reward,
        'support':[{'probability':str(s.probability), 'root_query':s.decision.query} for s in exact.support],
        'nature_dual_weights':[str(x) for x in exact.dual_prior_weights],
        'primal_dual_gap':str(exact.dual_upper_bound-exact.guaranteed_reward),
        'frontier_size':exact.frontier_size
    }


def run():
    deterministic=[_one('unfiltered:'+str(k),random_case(SEED+k)) for k in range(UNFILTERED)]
    selected=[_one('balanced:'+str(k),balanced_problem(SEED+k)) for k in range(BALANCED)]
    coupled=_one('constructed:nonrectangular-two-stage',coupled_case())
    def stat(rows):
        gain=sum((F(x['gain']) for x in rows),F(0))
        return {'n':len(rows), 'strict_mixed_gain':sum(x['strictly_better'] for x in rows),
                'equal':sum(not x['strictly_better'] for x in rows),
                'cumulative_gain':str(gain),
                'mean_gain':str(gain/len(rows))}
    result={
        'scope':'finite-world, two-fixed-prior, synthetic, globally coupled, private-coin max-min',
        'seed_start':SEED,
        'unfiltered':stat(deterministic),
        'balanced_deliberately_conflicting':stat(selected),
        'coupled_two_stage':coupled,
        'exact_primal_dual_certificates_count':UNFILTERED+BALANCED+1,
        'no_actual_agent_or_service_traces':True,
        'rows':deterministic+selected}
    result['sha256_without_digest']=digest(result)
    return result

if __name__=='__main__':
    result=run()
    folder=Path(__file__).parent
    # Keep the complete JSON inside the distribution ZIP, and publish a
    # reviewable summary+JSONL on GitHub (one source record per line).
    summary={k:v for k,v in result.items() if k!='rows'}
    json_text=json.dumps(summary,ensure_ascii=False,indent=2)
    assert json_text.endswith('\n}')
    json_text=json_text[:-2]+',\n  "rows": [\n'+',\n'.join(
        '    '+json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=False)
        for row in result['rows'])+'\n  ]\n}\n'
    (folder/'mixed_results.json').write_text(json_text)
    (folder/'mixed_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    (folder/'mixed_results.jsonl').write_text(''.join(
        json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n'
        for row in result['rows']))
    print(summary)
