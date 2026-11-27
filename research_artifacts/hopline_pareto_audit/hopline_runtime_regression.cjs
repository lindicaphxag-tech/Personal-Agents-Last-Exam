'use strict';
// Run against the pinned actual Hopline App and #110 task fixture. No substitute planner.
const assert = require('node:assert/strict');
const path = require('node:path');
const [appArg, seedArg] = process.argv.slice(2);
if (!appArg || !seedArg) throw Error('usage: node hopline_runtime_regression.cjs <apps/hopline> <#110 workspace/hopline>');
const app = path.resolve(appArg), task = path.resolve(seedArg);
const {fixture} = require(path.join(app,'tests/harness.cjs'));
const original = require(path.join(task,'seed.json'));
const binding = require(path.join(task,'binding.json'));
const T = x => '2026-11-21T'+x+':00+08:00';
const seed = structuredClone(original);
const alt = new Set(['pw-hill-cc-ep','pw-hill-ep-rr','pw-rr-ramp','pw-canal-rr-ep','pw-canal-ep-cc']);
let changed = 0;
for (const p of seed.pathways) {
  if (p.pathway_id==='pw-cc-lift') { p.length_m=100; changed++; }
  else if (alt.has(p.pathway_id)) { p.length_m=10; changed++; }
}
assert.equal(changed,6,'expected pinned fixture pathways');
const f = fixture({seed,binding,now:T('08:00')});
const plan = max_walk_m => f.call('hopline.trips.plan',{
  from:'pl-jules',to:'pl-recipient-b',depart_at:T('14:30'),step_free:true,max_walk_m,max_transfers:0
});
const loose = plan(2500).itineraries[0];
assert.ok(loose,'unconstrained control must be reachable');
assert.equal(loose.walk_m,400);
assert.equal((Date.parse(loose.arrive)-Date.parse(loose.depart))/1000,330);
const bounded = plan(375).itineraries[0];
assert.ok(bounded,'a 350m step-free route exists even under the 375m cap');
assert.equal(bounded.walk_m,350);
assert.equal((Date.parse(bounded.arrive)-Date.parse(bounded.depart))/1000,870);
assert.ok(bounded.edges.some(e=>e.pathway_id==='pw-rr-ramp'));
assert.ok(bounded.edges.every(e=>e.pathway_id!=='pw-cc-lift'));
assert.equal(bounded.edges[0].from,'pl-jules');
assert.equal(bounded.edges.at(-1).to,'pl-recipient-b');
for(let i=1;i<bounded.edges.length;i++) assert.equal(bounded.edges[i-1].to,bounded.edges[i].from);
console.log(JSON.stringify({loose:{walk_m:loose.walk_m,arrive:loose.arrive},bounded:{walk_m:bounded.walk_m,arrive:bounded.arrive}},null,2));
