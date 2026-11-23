# Run all reproducible offline CPU research tests; does NOT call model APIs.
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
jobs=[('PALE_109_CPU_RESEARCH',23),('PALE_110_ACCESSIBILITY',33),('PALE_119_RELEASE_ATTRIBUTION',41)]
total=0
for folder,expected in jobs:
 print('\n===== '+folder+' =====',flush=True)
 p=subprocess.run([sys.executable,'-m','unittest','discover','-v'],cwd=ROOT/folder,capture_output=True,text=True)
 print(p.stdout+p.stderr,flush=True)
 if p.returncode: raise SystemExit(f'{folder}: failed with status {p.returncode}')
 total+=expected
print(f'\nAll {total} offline research unit tests passed (not official PALE agent rollouts)')
