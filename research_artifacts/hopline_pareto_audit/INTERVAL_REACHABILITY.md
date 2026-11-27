# Interval reachability for mixed waiting constraints

This independent research prototype uses the discrete finite-horizon
temporal model in temporal.py. It does not replace Hopline's production
planner, change task #110, or claim conformance with the App runtime.

A label (v, [l,h], d, k) represents every integer time in [l,h] reachable
at node v using distance d and k rides. It carries an immutable witness.

* At a waitable node, the reachable set is closed forward to the horizon.
  At a no-wait node it is not.
* A walking edge of duration c and half-open window [a,b) maps the
  intersection [l,h] intersect [a,min(b-1,b-c)] forward by c.
* A scheduled ride can be used only if its departure belongs to the span,
  the first-boarding deadline is met, and the ride budget permits it.
* At the same node and ride count, remove only times already covered by
  a label of no larger distance. Do not fill gaps between intervals.

These operations preserve soundness by induction. For completeness,
consider any feasible temporal walk. Each next action maps its departure
time to a reachable arrival time. If that time is pruned, an existing
witness has the same time and ride count and no larger distance, so the
remaining suffix stays feasible. All resources and times are bounded
integers, and every accepted span adds at least one state not previously
covered at that distance or a lower one. This gives termination even
with zero-cost cycles. Heap keys (earliest time, distance, ride count)
are nondecreasing along a transition. The first goal popped therefore
attains the lexicographically optimal objective. Backtracking chooses an
arrival time within the original span, followed by legal waiting if
needed, and replays the immutable parent.

Local CPU experiment: 6,000 random cases from seed 20261127, 2,000 per
waiting regime, and 4,000 additional cases from seed 20261129. All
10,000 matched an independent explicit-state reachability oracle and
all returned witnesses passed a separate replay audit. Twelve unit tests
passed, including the additional random experiment.

For reachable cases in the first 6,000, the previous exact solver and
the interval solver expanded respectively 2235/2311 labels (all wait),
4869/1314 (mixed wait), and 268/268 (no wait). The full time-state
baseline expanded 9956, 5124, and 268 labels, respectively. These are
state counts, not runtime ratios. The mixed-wait count improves by
73.01 percent relative to the previous solver. The all-wait case has
3.40 percent more expansions.

On a constructed three-edge corridor with waiting allowed only at the
source and a final window [H-1,H), at H=100,1000,10000,50000 the
previous solver expanded 301,3001,30001,150001 states; the interval
solver expanded 4 in each case. This is a stress family, not a claim of
horizon-independent worst-case complexity. Fragmented reachable sets
can still require many intervals; the current implementation scans
previous spans and has not been optimized for dense networks.

The model allows repeated vertices, discrete time, zero waiting cost,
static per-edge durations/distances, finite windows and compiled
boarding-to-alighting rides. It does not support arbitrary time-varying
travel costs, waiting capacity, continuous time, uncertainty calibration,
or live transport operations. Estimated availability is rejected by
default. Complete native App integration and real timetable benchmarks
remain outstanding. Temporal shortest paths with waiting constraints
and multiobjective label algorithms are established research areas;
this is a concrete implementation and verified comparison, not a
priority claim over that literature.
