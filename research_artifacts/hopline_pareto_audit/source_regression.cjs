'use strict';
// Source-level reproduction: no App harness or substitute search.
const assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path'), crypto=require('node:crypto');
const pins={planner:'43ef9a8790aa737348311e8f7f4d10d74874e672',common:'711f38893ec06dcc805b9493e3fb05615a0a5ae8',network:'be3fc5fdce4a89da4e8541871ac7bef7306c2388',catalog:'a1fe463f36126d18f9944b0bb9402c57cdb821a8',time:'fc67b5990a86c505df73cf7ba7b5d3e110751c9a','domain-utils':'931f916aa09cdaeec1112a4adcd448bd14ef8556',diagnostics:'67d20e449404aecfac5adf0f100aafbf373c9a5d'};
function pinned(file,sha){const b=fs.readFileSync(file);assert.equal(crypto.createHash('sha1').update(Buffer.from('blob '+b.length+'\0')).update(b).digest('hex'),sha);return b;}
const [app,seed]=process.argv.slice(2);if(!app||!seed)throw Error('Usage: node source_regression.cjs <apps/hopline> <#110 seed.json>');
const base=path.resolve(app,'src');for(const [name,sha] of Object.entries(pins))pinned(path.join(base,name+'.cjs'),sha);
const data=JSON.parse(pinned(path.resolve(seed),'57651d4ff6860b22394b9c1e92fbeaa3510e820a'));
const planner=require(path.join(base,'planner.cjs'));
const depart=Date.parse('2026-11-21T14:30:00+08:00'),asOf=Date.parse('2026-11-21T08:00:00+08:00');
function run(d,cap){const r=planner.search(d,planner.endpoint(d,'pl-jules','bad_from'),planner.endpoint(d,'pl-recipient-b','bad_to'),{depart,asOf,stepFree:true,maxWalk:cap,maxRides:0,avoid:[],relaxed:false});const b=r.best[0];return b?{seconds:(b.time-depart)/1000,walk:b.walk}:null;}
const a=structuredClone(data),alt=new Set(['pw-hill-cc-ep','pw-hill-ep-rr','pw-rr-ramp','pw-canal-rr-ep','pw-canal-ep-cc']);
for(const p of a.pathways){if(p.pathway_id==='pw-cc-lift')p.length_m=100;else if(alt.has(p.pathway_id))p.length_m=10;}
const observed={original2500:run(data,2500),modified2500:run(a,2500),modified375:run(a,375),modified350:run(a,350),modified400:run(a,400)};
// This asserts the known behavior at the pinned old revision, not desired behavior.
assert.deepEqual(observed,{original2500:{seconds:330,walk:310},modified2500:{seconds:330,walk:400},modified375:null,modified350:null,modified400:{seconds:330,walk:400}});
console.log(JSON.stringify({observed,expectedFeasible:{seconds:870,walk:350},scope:'source-level walking-only regression'},null,2));
