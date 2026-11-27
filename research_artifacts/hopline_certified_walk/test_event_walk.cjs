'use strict';
const {solve}=require('./event_walk.cjs');
const {walkingGraph}=require('./walking_adapter.cjs');
function tests(solve){
  const E=(id,from,to,dt,dw,windows)=>({id,from,to,dt,dw,...(windows===undefined?{}:{windows})});
  // Independent full discrete state reachability; no dominance or reverse bounds.
  function oracle(g,s,t,c){
    const todo=[[s,c.depart||0,0]],seen=new Set(),ans=[];let i=0;
    while(i<todo.length){const [n,time,w]=todo[i++];const key=JSON.stringify([n,time,w]);if(seen.has(key))continue;seen.add(key);if(n===t){ans.push([time,w]);continue;}
      for(const e of g.edges)if(e.from===n&&time+e.dt<=c.deadline&&w+e.dw<=c.budget&&(e.windows===undefined||e.windows.some(([a,b])=>a<=time&&time<b)))todo.push([e.to,time+e.dt,w+e.dw]);
    }ans.sort((a,b)=>a[0]-b[0]||a[1]-b[1]);return ans[0]||null;
  }
  function checkResult(g,s,t,c,r,ref){
    if(!ref){if(r.status!=="infeasible")throw Error("false feasible/incomplete");return;}
    if(r.status!=="optimal"||r.arrival!==ref[0]||r.distance!==ref[1])throw Error("wrong optimum "+JSON.stringify({g,c,r,ref}));
    let n=s,time=c.depart||0,w=0;for(const id of r.path){const e=g.edges.find(e=>e.id===id);if(!e||e.from!==n||(e.windows!==undefined&&!e.windows.some(([a,b])=>a<=time&&time<b)))throw Error("bad witness");n=e.to;time+=e.dt;w+=e.dw;}
    if(n!==t||time!==r.arrival||w!==r.distance)throw Error("bad witness metrics");
  }
  const cases=[];function check(n,x){if(!x)throw Error(n);cases.push(n);}
  const g={nodes:["s","a","x","t"],edges:[E("fast","s","x",2,1),E("slow1","s","a",3,0),E("slow2","a","x",3,1),E("facility","x","t",1,1,[[6,8]]),E("zero","x","x",0,0)]};
  const c={deadline:10,budget:2};const r=solve(g,"s","t",c);
  check("late path required and zero self-cycle terminates",r.arrival===7&&r.distance===2);
  check("partition fallback",solve(g,"s","t",{...c,partitionLimit:1}).method==="exact-time");
  check("fallback exact",solve(g,"s","t",{...c,partitionLimit:1}).arrival===7);
  check("state cap is incomplete",solve(g,"s","t",{...c,limit:1}).status==="incomplete");
  const zero={nodes:["s","x","t"],edges:[E("a","s","x",0,0),E("b","x","s",0,0),E("c","x","t",0,0)]};
  check("zero-cost zero-time cycle",solve(zero,"s","t",{deadline:0,budget:0}).arrival===0);
  check("half-open facility endpoint",solve({nodes:["s","t"],edges:[E("a","s","t",0,0,[[0,1]])]},"s","t",{depart:1,deadline:2,budget:0}).status==="infeasible");
  // A downstream opening must split the upstream node even if it has no local windows.
  const downstream={nodes:["s","x","y","t"],edges:[E("fast","s","x",1,0),E("slow","s","x",3,0),E("advance","x","y",2,0),E("gate","y","t",0,0,[[5,6]])]};
  check("backward propagated event",solve(downstream,"s","t",{deadline:8,budget:0}).arrival===5);
  let seed=20261127;const rng=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
  let feasible=0,dynamic=0,oldLabels=0,newLabels=0,better=0,worse=0,fallback=0;
  for(let i=0;i<1600;i++){
    const nodes=Array.from({length:4+i%3},(_,j)=>String(j)),edges=[];
    for(const a of nodes)for(const b of nodes){if(rng()>.24)continue;
      const dt=Math.floor(rng()*4),dw=Math.floor(rng()*4),windows=i%2&&rng()<.55?[[Math.floor(rng()*5),5+Math.floor(rng()*5)]]:undefined;
      edges.push(E("e"+edges.length,a,b,dt,dw,windows));}
    const g={nodes,edges},c={depart:i%3,deadline:7+i%4,budget:i%7};
    const s=nodes[0],t=nodes.at(-1),ref=oracle(g,s,t,c),old=solve(g,s,t,{...c,mode:"time"}),nw=solve(g,s,t,c),fb=solve(g,s,t,{...c,partitionLimit:2});
    for(const x of [old,nw,fb])checkResult(g,s,t,c,x,ref);
    feasible+=!!ref;dynamic+=nw.method==="event";fallback+=fb.method==="exact-time";oldLabels+=old.expanded;newLabels+=nw.expanded;better+=nw.expanded<old.expanded;worse+=nw.expanded>old.expanded;
  }
  check("1600 exact state-space comparisons",true);
  const nodes=Array.from({length:13},(_,i)=>"n"+i).concat("target"),edges=[];
  for(let i=0;i<12;i++){edges.push(E("lo"+i,nodes[i],nodes[i+1],1,0),E("hi"+i,nodes[i],nodes[i+1],1+2**i,0));}
  edges.push(E("gate",nodes[12],"target",1,0,[[2048,4096]]));
  const stress={nodes,edges},sc={deadline:4200,budget:0};
  const old=solve(stress,nodes[0],"target",{...sc,mode:"time"}),nw=solve(stress,nodes[0],"target",sc);
  checkResult(stress,nodes[0],"target",sc,old,[2049,0]);checkResult(stress,nodes[0],"target",sc,nw,[2049,0]);
  check("stress reduces expansions",nw.expanded<old.expanded);
  return {checks:cases,random:{cases:1600,feasible,dynamic,fallback,oldLabels,newLabels,better,worse},stress:{old,nw}};
}
function fixtureTests(solve,seed){
 const d=Date.parse("2026-11-21T14:30:00+08:00"),end=d+3600000,asOf=Date.parse("2026-11-21T08:00:00+08:00");
 const run=(seed,from,to,budget,at=asOf,allowEstimates=false)=>solve(walkingGraph(seed,from,to,d,end,at,allowEstimates),from,to,{depart:d,deadline:end,budget});
 const original=run(seed,"pl-jules","pl-recipient-b",2500),zero=run(seed,"pl-depot","pl-jules",150);
 const closed=JSON.parse(JSON.stringify(seed));closed.facilities[0].history=[{seq:1,status:"out_of_service",since:"2026-11-21T09:00:00+08:00",recorded_at:"2026-11-21T09:00:00+08:00",expected_return:"2026-11-23T09:00:00+08:00"}];
 const later=run(closed,"pl-jules","pl-recipient-b",2500,Date.parse("2026-11-21T09:10:00+08:00"));
 const est=JSON.parse(JSON.stringify(closed));est.facilities[0].history[0].expected_return="2026-11-21T14:00:00+08:00";
 const noEstimate=run(est,"pl-jules","pl-recipient-b",2500,Date.parse("2026-11-21T09:10:00+08:00")),yesEstimate=run(est,"pl-jules","pl-recipient-b",2500,Date.parse("2026-11-21T09:10:00+08:00"),true);
 const seconds=r=>(r.arrival-d)/1000;
 if(seconds(original)!==330||seconds(zero)!==120||seconds(later)!==870||seconds(noEstimate)!==870||seconds(yesEstimate)!==330)throw Error("pinned fixture mismatch");
 return Object.fromEntries(Object.entries({original,zero,later,noEstimate,yesEstimate}).map(([k,v])=>[k,{...v,seconds:seconds(v)}]));
}
console.log(JSON.stringify({...tests(solve),fixture:fixtureTests(solve,require('./pinned_seed.json'))},null,2));
