"""Globally coupled prior-robust deterministic evidence-query replay.

Synthetic prior scenarios; NOT observed deployment distributions, calibrated
model priors, or claims of state-of-the-art runtime verification.
"""
from __future__ import annotations

from fractions import Fraction as F
from pathlib import Path
import json
import random
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capegraph.adaptive import Probe, World
from capegraph.planner import Goal, Need, Witness
from capegraph.robust import (Prior, solve_robust, robust_fixed_reference,
                              replay_robust, exhaustive_independent_reference)
from capegraph.core import digest

START = 2026112400
CASES = 180


def w(token, value='ok'):
    return Witness(token, value, 'official', 10)


def designed(kind: str):
    """A deliberately engineered stress test for prior shift: do not mix into random metrics."""
    goals = (Goal('domain-specific', (Need(kind+':A','ok',('official',),0,100),), 10),
             Goal('cross-world', (Need(kind+':G','ok',('official',),0,100),), 6))
    queries = (Probe('specific',1,'official'), Probe('general',1,'official'))
    worlds = (World('A', F(1,2), {'specific': (w(kind+':A'),), 'general': (w(kind+':G'),)}),
              World('B', F(1,2), {'specific': (), 'general': (w(kind+':G'),)}))
    priors = (Prior('nominal', {'A': F(9,10), 'B': F(1,10)}),
              Prior('shifted', {'A': F(1,10), 'B': F(9,10)}))
    return goals, queries, worlds, 1, priors



def coupled_case():
    """A distinct two-stage case: one prior must hold over the entire tree."""
    goals=(Goal('A', (Need('Aproof','ok',('official',),0,100),),10),
           Goal('B', (Need('Bproof','ok',('official',),0,100),),10))
    queries=(Probe('which',1,'official'),Probe('checkA',2,'official'),Probe('checkB',2,'official'))
    def world(name,branch,good):
        return World(name,F(1,4),{
            'which':(Witness('branch',branch,'official',10),),
            'checkA':(w('Aproof'),) if branch=='A' and good else (),
            'checkB':(w('Bproof'),) if branch=='B' and good else ()})
    worlds=(world('AG','A',True), world('AB','A',False),
            world('BG','B',True), world('BB','B',False))
    priors=(Prior('p1',{'AG':F(2,5),'AB':F(1,10),'BG':F(1,20),'BB':F(9,20)}),
            Prior('p2',{'AG':F(1,20),'AB':F(9,20),'BG':F(2,5),'BB':F(1,10)}))
    return goals,queries,worlds,3,priors

def random_case(seed: int):
    rng = random.Random(seed)
    tokens = [f't{i}' for i in range(rng.randint(2, 5))]
    goals = tuple(Goal(f'g{i}', tuple(Need(t,'ok',('official',),0,100)
                                         for t in rng.sample(tokens, rng.randint(1,min(3,len(tokens))))),
                       rng.randint(4,13)) for i in range(rng.randint(2, 5)))
    queries = tuple(Probe(f'q{i}', rng.randint(1,2), 'official')
                    for i in range(rng.randint(2,4)))
    nworlds = rng.randint(2,3)
    worlds = []
    for i in range(nworlds):
        responses = {}
        for q in queries:
            selected = rng.sample(tokens,rng.randint(0,min(2,len(tokens))))
            responses[q.name] = tuple(w(t,rng.choice(('ok','ok','bad'))) for t in selected)
        worlds.append(World(f'w{i}', F(1,nworlds), responses))
    dominant_a, dominant_b = 0, 1
    # Deliberately sample two substantially different priors; neither used by the agent
    # for future information beyond the stated uncertainty set.
    pa = {f'w{i}': F(8 if i==dominant_a else 1,nworlds+7) for i in range(nworlds)}
    pb = {f'w{i}': F(8 if i==dominant_b else 1,nworlds+7) for i in range(nworlds)}
    priors = (Prior('nominal',pa), Prior('shifted',pb))
    return goals, queries, tuple(worlds), rng.randint(0,5), priors


def row(name,problem,ood_seed=None):
    goals, queries, worlds, budget, priors = problem
    robust = solve_robust(goals, queries, worlds, budget, priors)
    nominal = solve_robust(goals, queries, worlds, budget, priors[:1])
    robust_fixed, chosen = robust_fixed_reference(goals, queries, worlds, budget, priors)
    worst_nominal = min(sum((p.probabilities[w.name]*replay_robust(nominal,w,queries,goals)[0]
                             for w in worlds), F(0)) for p in priors)
    per_world = dict(robust.per_world_rewards)
    recomputed = tuple((p.name,sum((p.probabilities[w.name]*per_world[w.name]
                                    for w in worlds), F(0))) for p in priors)
    assert recomputed == robust.scenario_rewards
    assert robust.worst_case_reward >= max(worst_nominal,robust_fixed)
    assert all(replay_robust(robust,w,queries,goals)[1] <= budget for w in worlds)
    # A deliberately *out-of-set* prior is used only for post-hoc stress replay,
    # never by the solver or its fixed-prior ambiguity optimizer.
    ood_stats = {}
    if ood_seed is not None:
        rng = random.Random(ood_seed + 0x5EED)
        masses = [rng.randint(1, 13) for _ in worlds]
        mass_total = sum(masses)
        outside = {w.name:F(a, mass_total) for w,a in zip(worlds,masses)}
        robust_out = sum((outside[w.name]*replay_robust(robust,w,queries,goals)[0]
                          for w in worlds),F(0))
        nominal_out = sum((outside[w.name]*replay_robust(nominal,w,queries,goals)[0]
                           for w in worlds),F(0))
        ood_stats = {'ood_robust_value':str(robust_out),
                     'ood_nominal_value':str(nominal_out),
                     'ood_robust_better':robust_out>nominal_out,
                     'ood_nominal_better':robust_out<nominal_out}
    # Independent no-pruning oracle, rebuilt from scratch, with identical score semantics.
    independent=exhaustive_independent_reference(goals,queries,worlds,budget,priors)
    assert independent == (robust.worst_case_reward, robust.worst_case_cost)
    return dict(case=name, world_count=len(worlds),query_count=len(queries),budget=budget,
                robust_worst=str(robust.worst_case_reward),nominal_worst_under_shift=str(worst_nominal),
                fixed_robust_worst=str(robust_fixed),fixed_query_set=list(chosen),
                robust_root_query=robust.decision.query, nominal_root_query=nominal.decision.query,
                robust_expected_cost_worst=str(robust.worst_case_cost),
                robust_beats_nominal=robust.worst_case_reward > worst_nominal,
                robust_beats_fixed=robust.worst_case_reward > robust_fixed,
                independent_oracle_agreement=True,frontier_size=robust.frontier_size,
                states_expanded=robust.states_expanded,**ood_stats)


def run():
    engineered = [row('constructed:'+name,designed(name)) for name in ('release','lab','delivery')]
    engineered.append(row('constructed:globally-coupled-priors',coupled_case()))
    random_rows = [row('seed:'+str(seed),random_case(seed),ood_seed=seed)
                   for seed in range(START, START+CASES)]
    total = lambda key: str(sum((F(x[key]) for x in random_rows), F(0)))
    result = dict(
        label='globally coupled finite-prior synthetic deterministic-policy research; NOT field deployments',
        random_seed_start=START, random_cases=CASES, engineered_cases=len(engineered),
        independent_oracle_agreement=len(engineered)+len(random_rows),
        robust_strictly_beats_nominal_under_shift=sum(x['robust_beats_nominal'] for x in random_rows),
        robust_strictly_beats_fixed_minimax=sum(x['robust_beats_fixed'] for x in random_rows),
        robust_ties_nominal_under_shift=sum(not x['robust_beats_nominal'] for x in random_rows),
        robust_total_worst=total('robust_worst'),
        nominal_total_worst_under_shift=total('nominal_worst_under_shift'),
        robust_fixed_total_worst=total('fixed_robust_worst'),
        out_of_set_shift_robust_better=sum(x['ood_robust_better'] for x in random_rows),
        out_of_set_shift_nominal_better=sum(x['ood_nominal_better'] for x in random_rows),
        out_of_set_shift_tied=sum(not x['ood_robust_better'] and not x['ood_nominal_better']
                                  for x in random_rows),
        out_of_set_total_robust=total('ood_robust_value'),
        out_of_set_total_nominal=total('ood_nominal_value'),
        constructed_worst_robust='6', constructed_worst_nominal_under_shift='1',
        coupled_case_robust_worst='9/2', coupled_case_fixed_worst='1/2',
        rows=engineered+random_rows)
    result['sha256_without_digest']=digest(result)
    return result


if __name__ == '__main__':
    r = run()
    # Keep each per-case result on one line, for convenient git review.
    summary = {k: v for k, v in r.items() if k != 'rows'}
    prefix = json.dumps(summary, indent=2, ensure_ascii=False).rstrip()[:-1]
    rows = ',\n'.join('    '+json.dumps(row, separators=(',', ':'), ensure_ascii=False)
                      for row in r['rows'])
    rendered = prefix + ',\n  "rows": [\n' + rows + '\n  ]\n}\n'
    (Path(__file__).resolve().parent/'robust_results.json').write_text(rendered)
    assert json.loads(rendered) == r
    print(json.dumps({k:v for k,v in r.items() if k!='rows'},indent=2))
