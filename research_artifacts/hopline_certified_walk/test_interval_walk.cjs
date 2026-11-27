'use strict';
const {intervalSolve}=require('./interval_walk.cjs');
const {solve}=require('./event_walk.cjs');
const {walkingGraph}=require('./walking_adapter.cjs');
function verifyAll(solve,previous,adapter,seed){
 const E=(id,from,to,dt,dw,windows)=>({id,from,to,dt,dw,...(windows===undefined?{}:{windows})});
 function oracle(g,s,t,c){
  const todo=[[s,c.depart||0,0]],seen=new Set();let best=null;
  for(let i=0;i<todo.length;i++){const [n,time,w]=todo[i],k=JSON.stringify([n,time,w]);if(seen.has(k))continue;seen.add(k);
   if(n===t){if(!best||time<best[0]||(time===best[0]&&w<best[1]))best=[time,w];continue;}
   for(const e of g.edges)if(e.from===n&&e.dt<=c.deadline-time&&e.dw<=c.budget-w&&(e.windows===undefined||e.windows.some(([a,b])=>a<=time&&time<b)))todo.push([e.to,time+e.dt,w+e.dw]);
  }return best;
 }
 function check(g,s,t,c,r,ref){
  if(!ref){if(r.status!=="infeasible")throw Error("false feasible");return;}
  if(r.status!=="optimal"||r.arrival!==ref[0]||r.distance!==ref[1])throw Error("bad optimum "+JSON.stringify({g,c,r,ref}));
  let n=s,time=c.depart||0,w=0;
  for(const id of r.path){const e=g.edges.find(e=>e.id===id);if(!e||e.from!==n||(e.windows!==undefined&&!e.windows.some(([a,b])=>a<=time&&time<b)))throw Error("bad witness");n=e.to;time+=e.dt;w+=e.dw;}
  if(n!==t||time!==r.arrival||w!==r.distance)throw Error("bad witness metrics");
 }
 const tests=[];function ok(name,v){if(!v)throw Error(name);tests.push(name);}
 const z={nodes:["s","x","t"],edges:[E("a","s","x",0,0),E("b","x","s",0,0),E("c","x","t",0,0)]};
 ok("zero time cycles",solve(z,"s","t",{deadline:0,budget:0}).arrival===0);
 ok("work cap reports incomplete",solve(z,"s","t",{deadline:0,budget:0,workLimit:1}).status==="incomplete");
 ok("storage cap reports incomplete",solve(z,"s","t",{deadline:0,budget:0,limit:1}).status==="incomplete");
 ok("source equals target",solve(z,"s","s",{deadline:0,budget:0}).path.length===0);
 const late={nodes:["s","x","t"],edges:[E("a","s","x",1,0),E("b","s","x",3,0),E("gate","x","t",1,0,[[3,4]])]};
 ok("no implicit waiting",solve(late,"s","t",{deadline:4,budget:0}).arrival===4);
 ok("closing boundary",solve(late,"s","t",{depart:3,deadline:9,budget:0}).status==="infeasible");
 let rngState=20261128;const rng=()=>{rngState=(Math.imul(rngState,1664525)+1013904223)>>>0;return rngState/4294967296;};
 let feasible=0,dynamic=0,zero=0,newWork=0,oldExpanded=0,intervals=0;
 for(let i=0;i<2000;i++){
  const nodes=Array.from({length:4+i%4},(_,j)=>String(j)),edges=[];
  for(const a of nodes)for(const b of nodes){if(rng()>.23)continue;
   const dt=Math.floor(rng()*4),dw=Math.floor(rng()*5),w=i%2&&rng()<.6?[[Math.floor(rng()*6),6+Math.floor(rng()*6)]]:undefined;
   edges.push(E("e"+edges.length,a,b,dt,dw,w));}
  const g={nodes,edges},c={depart:i%3,deadline:7+i%5,budget:i%9},s=nodes[0],t=nodes.at(-1);
  const ref=oracle(g,s,t,c),a=solve(g,s,t,c),b=previous(g,s,t,{...c,mode:"time"});
  check(g,s,t,c,a,ref);check(g,s,t,c,b,ref);
  feasible+=!!ref;dynamic+=edges.some(e=>e.windows!==undefined);zero+=edges.some(e=>!e.dt&&!e.dw);newWork+=a.work;oldExpanded+=b.expanded;intervals+=a.peakIntervals;
 }
 ok("2000 random cases with independent oracle",true);
 const stress=[];
 for(const n of [8,12,14,18]){
  const nodes=Array.from({length:n+1},(_,i)=>"n"+i).concat("target"),edges=[];
  for(let i=0;i<n;i++){edges.push(E("lo"+i,nodes[i],nodes[i+1],1,0),E("hi"+i,nodes[i],nodes[i+1],1+2**i,0));}
  edges.push(E("gate",nodes[n],"target",1,0,[[2**(n-1),2**n]]));
  const g={nodes,edges},c={deadline:2**n+n+10,budget:0},s=nodes[0],t="target",expected=[2**(n-1)+1,0];
  // Fixed repeats; report timings including all preprocessing and witness recovery.
  const methods={interval:()=>solve(g,s,t,c),event:()=>previous(g,s,t,c),time:()=>previous(g,s,t,{...c,mode:"time"})};
  const rows={};
  for(const [k,f] of Object.entries(methods)){const ms=[];let r;
   for(let j=0;j<3;j++){const st=Date.now();r=f();ms.push(Date.now()-st);}
   if(r.status!=="incomplete")check(g,s,t,c,r,expected);
   ms.sort((a,b)=>a-b);rows[k]={...r,medianMs:ms[1],timesMs:ms};
  }
  if(rows.interval.status!=="optimal")throw Error("interval stress failed");
  stress.push({layers:n,...rows});
 }
 ok("layered stress exact",true);
 const d=Date.parse("2026-11-21T14:30:00+08:00"),end=d+3600000,asOf=Date.parse("2026-11-21T08:00:00+08:00");
 const fixture=[];
 for(const [s,t,b] of [["pl-jules","pl-recipient-b",2500],["pl-depot","pl-jules",150],["pl-jules","pl-recipient-b",300],["pl-rowan","pl-recipient-c",2500]]){
  const g=adapter(seed,s,t,d,end,asOf),c={depart:d,deadline:end,budget:b};
  const old=previous(g,s,t,c),r=solve(g,s,t,c);
  const expected=old.status==="optimal"?[old.arrival,old.distance]:null;check(g,s,t,c,r,expected);
  fixture.push({s,t,b,status:r.status,seconds:r.arrival===undefined?null:(r.arrival-d)/1000,distance:r.distance??null,work:r.work,oldExpanded:old.expanded});
 }
 ok("pinned walking fixture",true);
 return {checks:tests,random:{cases:2000,feasible,dynamic,zero,newWork,oldExpanded,intervals},stress,fixture};
}
console.log(JSON.stringify(verifyAll(intervalSolve,solve,walkingGraph,require('./pinned_seed.json')),null,2));
