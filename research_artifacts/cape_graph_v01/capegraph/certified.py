"""Certified column generation for finite, globally coupled prior ambiguity.

Compile a shared observation DAG, price pure policies with exact weighted
Bellman recursion, use floating LP only to propose feasible rational mixtures.
Every returned lower/upper bound uses exact arithmetic and full pricing.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as F
from math import lcm, isfinite
from typing import Iterable
from .adaptive import _setup, response_id
from .planner import _grade
from .robust import Prior, RobustDecision, RobustPolicy, replay_robust

@dataclass(frozen=True)
class Node:
    worlds: tuple[int, ...]
    reward: int
    actions: tuple[tuple[str, int, tuple[tuple[str,int],...]],...]

@dataclass(frozen=True)
class Column:
    decision: RobustDecision
    rewards: tuple[int,...]
    costs: tuple[int,...]

@dataclass(frozen=True)
class CertifiedMix:
    support: tuple[tuple[F,Column],...]
    nature: tuple[F,...]
    lower: F
    upper: F
    scenario_rewards: tuple[F,...]
    scenario_costs: tuple[F,...]
    iterations: int
    generated_columns: int
    dag_nodes: int
    reason: str
    history: tuple[tuple[F,F],...]

    @property
    def gap(self): return self.upper-self.lower

class EvidenceDAG:
    """All reachable histories, including zero-mass worlds, compiled once."""
    def __init__(self, goals, probes, worlds, budget, initial=(), max_nodes=100000):
        self.gs,self.qs,self.ws,self.initial=_setup(goals,probes,worlds,budget,initial)
        self.budget=budget
        self.nodes=[]; memo={}
        def rec(available,possible,left,receipts):
            key=(available,possible,left,response_id(receipts))
            if key in memo:return memo[key]
            # Postorder IDs: every child precedes its parent.
            actions=[]
            for q in available:
                probe=self.qs[q]
                if probe.cost>left:continue
                groups={}
                for i in possible:
                    obs=self.ws[i].responses[probe.name]; h=response_id(obs)
                    if h not in groups:groups[h]=([],obs)
                    groups[h][0].append(i)
                next_q=tuple(k for k in available if k!=q)
                children=tuple((h,rec(next_q,tuple(ids),left-probe.cost,receipts+obs))
                               for h,(ids,obs) in sorted(groups.items()))
                actions.append((probe.name,probe.cost,children))
            if len(self.nodes)>=max_nodes: raise ValueError('observation DAG node cap exceeded')
            idx=len(self.nodes);self.nodes.append(Node(possible,_grade(self.gs,receipts)[0],tuple(actions)))
            memo[key]=idx
            return idx
        self.root=rec(tuple(range(len(self.qs))),tuple(range(len(self.ws))),budget,self.initial)
        self.nodes=tuple(self.nodes)

    def price(self, weights: tuple[F,...]):
        """Exact best response over ALL deterministic contingent policies.

        No division by posterior mass: zero-weight histories still get a safe
        stop/continuation. Integer-scaled unnormalized Bellman values avoid
        Fraction arithmetic at every edge. Tie break by expected cost.
        """
        if len(weights)!=len(self.ws) or any(not isinstance(x,F) or x<0 for x in weights) or sum(weights,F(0))!=1:
            raise ValueError('require normalized nonnegative rational world weights')
        d=lcm(*(x.denominator for x in weights)); w=tuple(int(x*d) for x in weights)
        values=[]; costs=[]; decisions=[]
        for node in self.nodes:
            mass=sum(w[i] for i in node.worlds)
            best_v=node.reward*mass;best_c=0;best=RobustDecision(None)
            for name,cost,children in node.actions:
                v=sum(values[k] for _,k in children)
                c=cost*mass+sum(costs[k] for _,k in children)
                if (v,-c)>(best_v,-best_c):
                    best_v,best_c=v,c
                    best=RobustDecision(name,tuple((h,decisions[k]) for h,k in children))
            values.append(best_v);costs.append(best_c);decisions.append(best)
        col=self.replay(decisions[self.root])
        val=sum((x*y for x,y in zip(weights,col.rewards)),F(0))
        assert val==F(values[self.root],d)
        return col,val

    def replay(self,decision):
        # Replay independently of the compiled DAG; every world is checked.
        dummy=RobustPolicy(decision,F(0),F(0),(),(),(),(),0,0)
        pairs=[replay_robust(dummy,w,self.qs,self.gs,self.initial) for w in self.ws]
        if any(c>self.budget for _,c in pairs):raise ValueError('pathwise query budget violated')
        return Column(decision,tuple(v for v,_ in pairs),tuple(c for _,c in pairs))

def _priors(dag,priors):
    ps=tuple(sorted(priors,key=lambda p:p.name))
    if not 1<=len(ps)<=64 or len({p.name for p in ps})!=len(ps) or any(not isinstance(p,Prior) or not p.name for p in ps):
        raise ValueError('require 1..64 distinct named priors')
    names={w.name for w in dag.ws};vec=[]
    for p in ps:
        if set(p.probabilities)!=names:raise ValueError('each prior must cover every world')
        v=tuple(p.probabilities[w.name] for w in dag.ws)
        if any(not isinstance(x,F) or x<0 for x in v) or sum(v,F(0))!=1:raise ValueError('invalid prior')
        vec.append(v)
    return tuple(vec)

def _dot(a,b):return sum((x*y for x,y in zip(a,b)),F(0))

def _simplex(xs,denominator=10**9):
    # Rationalize, clip tiny numeric negatives, normalize exactly. No reliance
    # on LP solver's claimed objective or feasibility for certificate validity.
    if any(not isfinite(float(x)) or x < -1e-6 for x in xs):raise ValueError('invalid LP vector')
    ys=tuple(F(float(max(0.,x))).limit_denominator(denominator) for x in xs)
    total=sum(ys,F(0))
    if not total:raise ValueError('empty LP simplex')
    return tuple(y/total for y in ys)

def _restricted(payoffs):
    import numpy as np
    from scipy.optimize import linprog
    a=np.asarray([[float(x) for x in row] for row in payoffs]); n,m=a.shape
    # Scale objective for solver conditioning; exact bounds use unscaled rewards.
    a=a/max(1.,float(np.max(np.abs(a))))
    p=linprog([0.]*n+[-1.], A_ub=np.column_stack((-a.T,np.ones(m))),b_ub=np.zeros(m),A_eq=[[1.]*n+[0.]],b_eq=[1.],bounds=[(0,None)]*n+[(None,None)],method='highs')
    q=linprog([0.]*m+[1.], A_ub=np.column_stack((a,-np.ones(n))),b_ub=np.zeros(n),A_eq=[[1.]*m+[0.]],b_eq=[1.],bounds=[(0,None)]*m+[(None,None)],method='highs')
    if not p.success or not q.success:raise RuntimeError('restricted LP failed')
    return _simplex(p.x[:-1]),_simplex(q.x[:-1])

def solve_certified(goals,probes,worlds,budget,priors,initial=(),*,epsilon=F(1,10**7),max_iterations=64,max_nodes=100000):
    """Anytime certificate, finite scenario polytope and pathwise budgets.

    Returned gap is valid even at an iteration cap or numeric stagnation.
    Nature selects one prior before hidden root randomization is observed.
    No expected-cost optimization guarantee beyond the pathwise budget.
    """
    if not isinstance(epsilon,F) or epsilon<0 or type(max_iterations)!=int or max_iterations<1:raise ValueError('invalid stopping parameters')
    dag=EvidenceDAG(goals,probes,worlds,budget,initial,max_nodes)
    ps=_priors(dag,priors);m=len(ps)
    columns=[];payoffs=[];keys=set();history=[]
    def add(c):
        # Only reward vectors affect reward minimax, keeping one representative.
        if c.rewards in keys:return False
        keys.add(c.rewards);columns.append(c);payoffs.append(tuple(_dot(p,c.rewards) for p in ps));return True
    nominal=tuple(sum((p[i] for p in ps),F(0))/m for i in range(len(dag.ws)))
    add(dag.price(nominal)[0]);best_l=None;best_u=None
    reason='iteration_cap'
    for it in range(1,max_iterations+1):
        x,y=_restricted(payoffs)
        scenario=tuple(sum((a*r[j] for a,r in zip(x,payoffs)),F(0)) for j in range(m))
        lower=min(scenario)
        support=tuple((a,c) for a,c in zip(x,columns) if a)
        spent=tuple(sum((a*_dot(p,c.costs) for a,c in support),F(0)) for p in ps)
        weights=tuple(sum((a*p[i] for a,p in zip(y,ps)),F(0)) for i in range(len(dag.ws)))
        new,upper=dag.price(weights)
        if best_l is None or lower>best_l[0]:best_l=(lower,support,scenario,spent)
        if best_u is None or upper<best_u[0]:best_u=(upper,y)
        lo,hi=best_l[0],best_u[0]
        assert hi>=lo
        history.append((lo,hi))
        if hi-lo<=epsilon:reason='certified';break
        if it==max_iterations:break
        if not add(new):reason='numerical_stall';break
    lo,support,scenario,spent=best_l;hi,y=best_u
    return CertifiedMix(support,y,lo,hi,scenario,spent,it,len(columns),len(dag.nodes),reason,tuple(history))

def verify_certificate(result,goals,probes,worlds,budget,priors,initial=()):
    """Recompile problem and independently replay every claimed support tree."""
    dag=EvidenceDAG(goals,probes,worlds,budget,initial);ps=_priors(dag,priors)
    if len(result.nature)!=len(ps) or any(not isinstance(x,F) or x<0 for x in result.nature) or sum(result.nature,F(0))!=1:raise ValueError('invalid dual')
    if not result.support or any(not isinstance(x,F) or x<=0 for x,_ in result.support) or sum((x for x,_ in result.support),F(0))!=1:raise ValueError('invalid primal')
    replayed=tuple((x,dag.replay(c.decision)) for x,c in result.support)
    if replayed!=result.support:raise ValueError('support replay differs')
    scenario=tuple(sum((x*_dot(p,c.rewards) for x,c in replayed),F(0)) for p in ps)
    costs=tuple(sum((x*_dot(p,c.costs) for x,c in replayed),F(0)) for p in ps)
    weights=tuple(sum((a*p[i] for a,p in zip(result.nature,ps)),F(0)) for i in range(len(dag.ws)))
    _,hi=dag.price(weights)
    if scenario!=result.scenario_rewards or costs!=result.scenario_costs or min(scenario)!=result.lower or hi!=result.upper or result.lower>hi:raise ValueError('invalid certificate bounds')
    return result.lower,result.upper

@dataclass(frozen=True)
class FlowCertificate:
    """Rational behavioral policy indexed by the canonical DAG state IDs."""
    probabilities: tuple[tuple[F,...],...]
    nature: tuple[F,...]
    lower: F
    upper: F
    scenario_rewards: tuple[F,...]
    scenario_costs: tuple[F,...]
    dag_nodes: int
    lp_variables: int
    @property
    def gap(self):return self.upper-self.lower


def _flow_evaluate(dag,ps,probabilities):
    """Exact per-world behavioral evaluation, not solver flow/objective values.

    Recurrence computes outcomes conditional on reaching each compatible state;
    independently uses the actual observation of the given world at every step.
    """
    if len(probabilities)!=len(dag.nodes):raise ValueError('wrong state count')
    for p,node in zip(probabilities,dag.nodes):
        if len(p)!=len(node.actions)+1 or any(not isinstance(x,F) or x<0 for x in p) or sum(p,F(0))!=1:raise ValueError('invalid behavioral simplex')
    rewards=[];costs=[]
    for i,w in enumerate(dag.ws):
        v={};c={}
        for k,node in enumerate(dag.nodes):
            if i not in node.worlds:continue
            probs=probabilities[k];vr=probs[0]*node.reward;cr=F(0)
            for prob,(name,cost,branches) in zip(probs[1:],node.actions):
                child=dict(branches)[response_id(w.responses[name])]
                vr+=prob*v[child];cr+=prob*(cost+c[child])
            v[k]=vr;c[k]=cr
        rewards.append(v[dag.root]);costs.append(c[dag.root])
    return tuple(_dot(p,rewards) for p in ps),tuple(_dot(p,costs) for p in ps)


def solve_flow(goals,probes,worlds,budget,priors,initial=(),*,max_nodes=100000):
    """One sparse realization-flow LP, followed by rational proof checking.

    At an information node, flow is the arrival probability conditional on
    ANY world consistent with that node. A queried action broadcasts its flow
    to each observation child (not a probabilistic split): any particular
    world selects exactly one child. Histories sharing the same remaining
    probes, observed receipts, budget and surviving worlds may be merged.
    """
    import numpy as np
    from scipy.sparse import coo_matrix
    from scipy.optimize import linprog
    dag=EvidenceDAG(goals,probes,worlds,budget,initial,max_nodes);ps=_priors(dag,priors)
    n=len(dag.nodes);m=len(ps);offset=[];nv=0
    for node in dag.nodes:
        offset.append(nv);nv+=len(node.actions)+1
    er=[];ec=[];ev=[];ur=[];uc=[];uv=[]
    scale=max(1,sum(g.value for g in dag.gs))
    for k,node in enumerate(dag.nodes):
        j=offset[k]
        for a in range(len(node.actions)+1):er.append(k);ec.append(j+a);ev.append(1.)
        for a,(_,_,children) in enumerate(node.actions,1):
            for _,child in children:er.append(child);ec.append(j+a);ev.append(-1.)
        if node.reward:
            for p,weights in enumerate(ps):
                r=F(node.reward,scale)*sum((weights[i] for i in node.worlds),F(0))
                if r:ur.append(p);uc.append(j);uv.append(-float(r))
    for p in range(m):ur.append(p);uc.append(nv);uv.append(1.)
    eq=coo_matrix((ev,(er,ec)),shape=(n,nv+1)).tocsr()
    ub=coo_matrix((uv,(ur,uc)),shape=(m,nv+1)).tocsr(); rhs=np.zeros(n);rhs[dag.root]=1.
    lp=linprog([0.]*nv+[-1.],A_ub=ub,b_ub=np.zeros(m),A_eq=eq,b_eq=rhs,bounds=[(0,None)]*nv+[(None,None)],method='highs')
    if not lp.success:raise RuntimeError('flow LP failed: '+lp.message)
    probs=[]
    for k,node in enumerate(dag.nodes):
        x=lp.x[offset[k]:offset[k]+len(node.actions)+1]
        # Even if LP flow rounds to zero, the behavioral policy is well-defined.
        if sum(max(0.,v) for v in x)<=1e-14:probs.append((F(1),)+(F(0),)*len(node.actions))
        else:probs.append(_simplex(x/sum(max(0.,v) for v in x)))
    probs=tuple(probs);nature=_simplex(-lp.ineqlin.marginals)
    scenario,costs=_flow_evaluate(dag,ps,probs)
    weights=tuple(sum((a*p[i] for a,p in zip(nature,ps)),F(0)) for i in range(len(dag.ws)))
    _,upper=dag.price(weights);lower=min(scenario)
    assert lower<=upper
    return FlowCertificate(probs,nature,lower,upper,scenario,costs,n,nv+1)


def verify_flow(result,goals,probes,worlds,budget,priors,initial=()):
    dag=EvidenceDAG(goals,probes,worlds,budget,initial);ps=_priors(dag,priors)
    y=result.nature
    if len(y)!=len(ps) or any(not isinstance(x,F) or x<0 for x in y) or sum(y,F(0))!=1:raise ValueError('invalid dual')
    scenario,costs=_flow_evaluate(dag,ps,result.probabilities)
    w=tuple(sum((a*p[i] for a,p in zip(y,ps)),F(0)) for i in range(len(dag.ws)))
    _,upper=dag.price(w)
    if scenario!=result.scenario_rewards or costs!=result.scenario_costs or min(scenario)!=result.lower or upper!=result.upper or result.lower>upper:raise ValueError('invalid flow certificate')
    return result.lower,result.upper

@dataclass(frozen=True)
class Execution:
    status: str
    reward: int | None
    spent: int
    queried: tuple[str,...]
    verified_goals: tuple[str,...]
    reason: str


def execute_flow(dag: EvidenceDAG, result: FlowCertificate, read_probe, *, randbelow=None):
    """Execute a policy using only read-only callback receipts, never world ID.

    A caller MUST authenticate the service adapter and witness contents first.
    This function checks source binding and observation membership, not actual
    service signatures or authorization. A novel observation or adapter error
    returns UNVERIFIED, with no positive reward attributed to the failed run.
    """
    from secrets import randbelow as private_randbelow
    from .planner import Witness
    rng=private_randbelow if randbelow is None else randbelow
    # Validate all action distributions before invoking any service.
    if len(result.probabilities)!=len(dag.nodes):raise ValueError('wrong policy state count')
    for p,node in zip(result.probabilities,dag.nodes):
        if len(p)!=len(node.actions)+1 or any(not isinstance(x,F) or x<0 for x in p) or sum(p,F(0))!=1:raise ValueError('invalid behavioral simplex')
    node_id=dag.root; receipts=dag.initial; spent=0; queried=[]
    lookup={p.name:p for p in dag.qs}
    while True:
        node=dag.nodes[node_id];p=result.probabilities[node_id]
        denom=lcm(*(x.denominator for x in p));coin=rng(denom)
        if type(coin) is not int or not 0<=coin<denom:raise ValueError('invalid private random sample')
        action=None
        for k,weight in enumerate(p):
            coin-=int(weight*denom)
            if coin<0:action=k;break
        assert action is not None
        if action==0:
            value,verified=_grade(dag.gs,receipts)
            if value!=node.reward:raise AssertionError('execution/graph receipt mismatch')
            return Execution('COMPLETED',value,spent,tuple(queried),verified,'')
        name,cost,branches=node.actions[action-1]
        if spent+cost>dag.budget or name in queried:raise AssertionError('unsafe query schedule')
        spent+=cost;queried.append(name);probe=lookup[name]
        try:
            observed=read_probe(probe)
            if not isinstance(observed,tuple) or any(not isinstance(w,Witness) or w.issuer!=probe.channel for w in observed):
                return Execution('UNVERIFIED',None,spent,tuple(queried),(),'invalid or source-mismatched receipts')
            if len({(w.token,w.at) for w in observed})!=len(observed):
                return Execution('UNVERIFIED',None,spent,tuple(queried),(),'duplicate token/time receipt')
            child=dict(branches).get(response_id(observed))
        except Exception:
            return Execution('UNVERIFIED',None,spent,tuple(queried),(),'adapter failure')
        if child is None:return Execution('UNVERIFIED',None,spent,tuple(queried),(),'out-of-model observation')
        receipts+=observed;node_id=child
