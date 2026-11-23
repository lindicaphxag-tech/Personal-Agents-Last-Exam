import sys,time,json,platform
from pathlib import Path
from statistics import median
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from experiments.certified_benchmark import branch_case
from capegraph.certified import solve_certified,solve_flow
p=branch_case(12,8);solve_flow(*p);solve_certified(*p)
raw={'column':[],'flow':[]}
for i in range(7):
    order=[('column',solve_certified),('flow',solve_flow)]
    if i%2:order.reverse()
    for name,solver in order:
        t=time.perf_counter();r=solver(*p);raw[name].append(time.perf_counter()-t);assert r.lower==r.upper==5
med={k:median(v) for k,v in raw.items()};d={'scope':'one constructed 24-world case; warm-up excluded, seven alternating end-to-end solves, includes DAG and exact certificate calculation, not external verification rerun','platform':platform.platform(),'python':sys.version,'raw_seconds':raw,'median_seconds':med,'speed_ratio':med['column']/med['flow']}
Path(__file__).with_name('certified_timing.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d))
