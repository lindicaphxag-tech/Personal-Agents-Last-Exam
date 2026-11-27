'use strict';
const {deltaIntervals,hybrid}=require('./hybrid_walk.cjs');
const {solve}=require('./event_walk.cjs');
const {intervalSolve}=require('./interval_walk.cjs');
const {walkingGraph}=require('./walking_adapter.cjs');
function validate(delta,hybrid,old,interval,adapter,seed){
 const E=(id,from,to,dt,dw,windows)=>({id,from,to,dt,dw,...(windows===undefined?{}:{windows})});
 function oracle(g,s,t,c){
  let best=null;const todo=[[s,c.depart||0,0]],seen=new Set();
  for(let i=0;i<todo.length;i++){const [n,time,w]=todo[i],k=JSON.stringify([n,time,w]);if(seen.has(k))continue;seen.add(k);
   if(n===t){if(!best||time<best[0]||(time===best[0]&&w<best[1]))best=[time,w];continue;}
   for(const e of g.edges)if(e.from===n&&e.dt<=c.deadline-time&&e.dw<=c.budget-w&&(e.windows===undefined||e.windows.some(([a,b])=>a<=time&&time<b)))todo.push([e.to,time+e.dt,w+e.dw]);
  }return best;
 }
 function check(g,s,t,c,r,ref){
  if(!ref){if(r.status!=="infeasible")throw Error("false feasible "+JSON.stringify(r));return;}
  if(r.status!=="optimal"||r.arrival!==ref[0]||r.distance!==ref[1])throw Error("wrong optimum "+JSON.stringify({g,c,r,ref}));
  let n=s,time=c.depart||0,w=0;
  for(const id of r.path){const e=g.edges.find(e=>e.id===id);if(!e||e.from!==n||(e.windows!==undefined&&!e.windows.some(([a,b])=>a<=time&&time<b)))throw Error("bad witness");n=e.to;time+=e.dt;w+=e.dw;}
  if(n!==t||time!==r.arrival||w!==r.distance||time>c.deadline||w>c.budget)throw Error("wrong witness");
 }
 const checks=[];function ok(name,b){if(!b)throw Error(name);checks.push(name);}
 const z={nodes:["s","x","t"],edges:[E("a","s","x",0,0),E("b","x","s",0,0),E("c","x","t",0,0)]};
 ok("zero cycle",delta(z,"s","t",{deadline:0,budget:0}).arrival===0);
 ok("work limit",delta(z,"s","t",{deadline:0,budget:0,workLimit:1}).status==="incomplete");
 ok("storage limit",delta(z,"s","t",{deadline:0,budget:0,limit:1}).status==="incomplete");
 ok("fallback executes",hybrid(z,"s","t",{deadline:0,budget:0,probeLimit:1},old).engine==="delta");
 const tie={nodes:["s","x","t"],edges:[E("expensive","s","t",5,8),E("a","s","x",2,1),E("b","x","t",3,1)]};
 ok("incumbent tie improves distance",delta(tie,"s","t",{deadline:9,budget:8}).distance===2);
 const early={nodes:["s","x","t"],edges:[E("late","s","t",8,0),E("a","s","x",2,1),E("b","x","t",3,1)]};
 ok("incumbent improves time despite higher cost",delta(early,"s","t",{deadline:9,budget:8}).arrival===5);
 const gate={nodes:["s","x","t"],edges:[E("fast","s","x",1,0),E("slow","s","x",3,0),E("gate","x","t",1,0,[[3,4]])]};
 ok("late arrival required",delta(gate,"s","t",{deadline:5,budget:0}).arrival===4);
 let rs=20261129;const rand=()=>{rs=(Math.imul(rs,1664525)+1013904223)>>>0;return rs/4294967296;};
 let feasible=0,dynamic=0,zero=0,chosen=0,forced=0,newTransforms=0,oldTransforms=0,oldWork=0,newWork=0;
 for(let i=0;i<2400;i++){
  const nodes=Array.from({length:4+i%4},(_,j)=>String(j)),edges=[];
  for(const a of nodes)for(const b of nodes){if(rand()>.27)continue;const dt=Math.floor(rand()*4),dw=Math.floor(rand()*4),win=i%2&&rand()<.6?[[Math.floor(rand()*5),5+Math.floor(rand()*6)]]:undefined;edges.push(E("e"+edges.length,a,b,dt,dw,win));}
  const g={nodes,edges},c={depart:i%3,deadline:8+i%5,budget:i%9},s=nodes[0],t=nodes.at(-1);
  const ref=oracle(g,s,t,c),a=delta(g,s,t,c),b=hybrid(g,s,t,c,old),f=hybrid(g,s,t,{...c,probeLimit:1},old),iv=interval(g,s,t,c);
  for(const r of [a,b,f,iv])check(g,s,t,c,r,ref);
  feasible+=!!ref;dynamic+=edges.some(e=>e.windows!==undefined);zero+=edges.some(e=>!e.dt&&!e.dw);chosen+=b.engine==="delta";forced+=f.engine==="delta";newTransforms+=a.transforms;oldTransforms+=iv.transforms;oldWork+=iv.work;newWork+=a.work;
 }
 ok("2400 independent graphs, four modes",true);
 const stress=[];
 for(const n of [8,12,14,18,22]){
  const nodes=Array.from({length:n+1},(_,i)=>"n"+i).concat("target"),edges=[];
  for(let i=0;i<n;i++)edges.push(E("lo"+i,nodes[i],nodes[i+1],1,0),E("hi"+i,nodes[i],nodes[i+1],1+2**i,0));
  edges.push(E("gate",nodes[n],"target",1,0,[[2**(n-1),2**n]]));
  const g={nodes,edges},c={deadline:2**n+n+10,budget:0},s=nodes[0],t="target",ref=[2**(n-1)+1,0];
  const a=delta(g,s,t,c),b=hybrid(g,s,t,c,old),iv=interval(g,s,t,c);
  for(const r of [a,b,iv])check(g,s,t,c,r,ref);
  stress.push({layers:n,delta:a,hybrid:b,interval:iv});
 }
 ok("22 layer stress",stress.at(-1).hybrid.status==="optimal");
 const d=Date.parse("2026-11-21T14:30:00+08:00"),end=d+3600000,asOf=Date.parse("2026-11-21T08:00:00+08:00"),fixtures=[];
 for(const [s,t,budget] of [["pl-jules","pl-recipient-b",2500],["pl-depot","pl-jules",150],["pl-jules","pl-recipient-b",300],["pl-rowan","pl-recipient-c",2500]]){
  const g=adapter(seed,s,t,d,end,asOf),c={depart:d,deadline:end,budget};
  const a=old(g,s,t,{...c,mode:"time"}),b=delta(g,s,t,c),h=hybrid(g,s,t,c,old),iv=interval(g,s,t,c);
  const ref=a.status==="optimal"?[a.arrival,a.distance]:null;
  for(const r of [b,h,iv])check(g,s,t,c,r,ref);
  fixtures.push({s,t,budget,old:a,delta:b,hybrid:h,interval:iv});
 }
 ok("pinned seed fixtures",true);
 return {checks,random:{cases:2400,feasible,dynamic,zero,defaultFallback:chosen,forcedFallback:forced,newTransforms,oldTransforms,newWork,oldWork},stress,fixtures};
}
console.log(JSON.stringify(validate(deltaIntervals,hybrid,solve,intervalSolve,walkingGraph,require('./pinned_seed.json')),null,2));
