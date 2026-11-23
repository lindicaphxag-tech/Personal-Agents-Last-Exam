"""Run new framework verification, synthetic ablation and optional prior 97 suite.

python run_all.py
"""
from pathlib import Path
import subprocess
import sys
import json

ROOT=Path(__file__).resolve().parent

def execute(*args,cwd=ROOT):
    print('RUN',*args,flush=True)
    return subprocess.run([sys.executable,*args],cwd=cwd,check=True)

if __name__=='__main__':
    execute('-m','unittest','discover','-v','-s','tests')
    execute('experiments/ablation.py')
    execute('experiments/cecs_pcr.py')
    execute('experiments/frontier_evaluation.py')
    execute('experiments/toy_policy_learning.py')
    prior=ROOT/'prior_97'/'verify_all.py'
    if prior.exists():
        execute('verify_all.py',cwd=ROOT/'prior_97')
        print('COMPLETED: 100 new framework tests + 97 separate prior domain tests; 42 original mutations + novel causal-family and 60-policy toy experiment')
    else:
        print('COMPLETED: 100 new framework tests, original 42 mutations, novel causal-family and 60-policy toy experiment. Prior 97-suite not bundled in this checkout.')
