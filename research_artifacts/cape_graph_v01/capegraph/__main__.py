"""Offline demonstrator: python -m capegraph --case release --json."""
import argparse
import json
from .fixtures import policy, cases, personalized_notice
from .scoring import Outcome, grade


def main():
    p=argparse.ArgumentParser(description='CAPE-Graph offline synthetic research demonstration')
    p.add_argument('--case', choices=['release','lab','delivery','notice_restrictive','notice_permissive'],
                   default='release')
    p.add_argument('--json', action='store_true', help='emit machine-readable audit')
    args=p.parse_args()
    if args.case.startswith('notice_'):
        trusted,effects=personalized_notice(args.case=='notice_permissive')
    else:
        trusted,effects=cases()[args.case]
    r=policy().evaluate(trusted,effects)
    if args.case.startswith('notice_'):
        scoring={'total':0,'earned':0,'approved':False,'reason':'no task rubric attached to this counterfactual'}
    else:
        e=effects[0]
        rubric=[Outcome('completed',e['action'],e['scope'],100,
                        frozenset(c['predicate'] for c in e['claims']))]
        scoring=grade(rubric,r,effects,100).to_json()
    output={'case':args.case,'audit':r.to_json(),'illustrative_outcome':scoring}
    if args.json:
        print(json.dumps(output,ensure_ascii=False,indent=2))
    else:
        print(f"{args.case}: {r.verdict} / illustrative outcome: {scoring.get('earned',0)}")
        print(f"findings: {[f.code for f in r.findings]}")

if __name__=='__main__':main()
