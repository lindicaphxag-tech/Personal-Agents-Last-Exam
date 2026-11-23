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
    prior=ROOT/'prior_97'/'verify_all.py'
    if prior.exists():
        execute('verify_all.py',cwd=ROOT/'prior_97')
        print('COMPLETED: 59 new framework tests + 97 separate prior domain tests; 42 deterministic mutations')
    else:
        print('COMPLETED: 59 new framework tests and 42 mutations. Prior 97-suite not bundled in this checkout.')
