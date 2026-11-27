'use strict';
const {solve}=require('./certified_walk.cjs');
function benchmark(solve){
  function brute(g,s,t,c){
    let best=null,visits=0;
    function go(u,time,w,path){
      visits++;if(time>c.deadline||w>c.budget)return;
      if(u===t){if(!best||time<best.arrival||(time===best.arrival&&w<best.distance))best={arrival:time,distance:w,path};return;}
      for(const e of g.edges)if(e.from===u&&(e.windows===undefined||e.windows.some(([a,b])=>a<=time&&time<b)))go(e.to,time+e.dt,w+e.dw,[...path,e.id]);
    }go(s,c.depart||0,0,[]);return {best,visits};
  }
  function verify(g,s,t,c,r){
    if(r.status!=="optimal")return;
    let u=s,time=c.depart||0,w=0;
    for(const id of r.path){const e=g.edges.find(e=>e.id===id);if(!e||e.from!==u||(e.windows!==undefined&&!e.windows.some(([a,b])=>a<=time&&time<b)))throw Error("bad witness");u=e.to;time+=e.dt;w+=e.dw;}
    if(u!==t||time!==r.arrival||w!==r.distance||time>c.deadline||w>c.budget)throw Error("bad witness metrics");
  }
  const E=(id,from,to,dt,dw,windows)=>({id,from,to,dt,dw,...(windows===undefined?{}:{windows})});
  const tests=[];function check(name,ok){if(!ok)throw Error(name);tests.push(name);}
  const g={nodes:["s","x","a","t"],edges:[E("fast","s","x",2,8),E("slow1","s","a",3,2),E("slow2","a","x",3,2),E("finish","x","t",1,3)]};
  check("static distance tradeoff",solve(g,"s","t",{deadline:12,budget:7}).arrival===7);
  const h={nodes:["s","a","x","t"],edges:[E("fast","s","x",2,1),E("slow1","s","a",3,0),E("slow2","a","x",3,1),E("facility","x","t",1,1,[[6,8]])]};
  const r=solve(h,"s","t",{deadline:10,budget:2});check("later arrival enables facility",r.arrival===7&&r.distance===2);verify(h,"s","t",{deadline:10,budget:2},r);
  check("infeasible bound",solve(h,"s","t",{deadline:6,budget:2}).status==="infeasible");
  check("resource exhaustion distinct",solve(g,"s","t",{deadline:12,budget:20,limit:1}).status==="incomplete");
  check("zero-hop",solve(g,"s","s",{deadline:0,budget:0}).arrival===0);
  let threw=false;try{solve({nodes:["s","t"],edges:[E("bad","s","t",0,0)]},"s","t",{deadline:4,budget:0})}catch(e){threw=true;}check("reject nonpositive duration",threw);
  let seed=20261127;const rand=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
  let cases=0,feasible=0,staticCases=0,dynamicCases=0,baseExpanded=0,newExpanded=0,bruteVisits=0,pruned=0,improved=0,worse=0;
  for(let i=0;i<1200;i++){
    const nodes=Array.from({length:5+i%3},(_,j)=>String(j));const edges=[];const dynamic=i%2===1;const cyclic=i%4>=2;
    for(let a=0;a<nodes.length;a++)for(let b=0;b<nodes.length;b++){
      if(a===b||(!cyclic&&a>b)||rand()>.29)continue;
      const dt=1+Math.floor(rand()*4),dw=Math.floor(rand()*5);const win=dynamic&&rand()<.4?[[Math.floor(rand()*7),8+Math.floor(rand()*5)]]:undefined;
      edges.push(E("e"+edges.length,nodes[a],nodes[b],dt,dw,win));
    }
    const g={nodes,edges};const c={depart:0,deadline:8+i%5,budget:3+i%9};
    const s=nodes[0],t=nodes.at(-1),ref=brute(g,s,t,c),a=solve(g,s,t,{...c,prune:false}),b=solve(g,s,t,c);
    for(const x of [a,b]){if(x.status!==(ref.best?"optimal":"infeasible")||(ref.best&&(x.arrival!==ref.best.arrival||x.distance!==ref.best.distance)))throw Error("differential mismatch "+i);verify(g,s,t,c,x);}
    cases++;feasible+=!!ref.best;staticCases+=b.staticGraph;dynamicCases+=!b.staticGraph;baseExpanded+=a.expanded;newExpanded+=b.expanded;bruteVisits+=ref.visits;pruned+=b.boundPruned;improved+=b.expanded<a.expanded;worse+=b.expanded>a.expanded;
  }
  check("all differential cases exact",cases===1200);check("pruning never increased expanded labels in benchmark",worse===0);
  return {tests,cases,feasible,staticCases,dynamicCases,baseExpanded,newExpanded,bruteVisits,pruned,improved,worse};
}
function pinnedCase(solve,seed){
 const alt=new Set(['pw-hill-cc-ep','pw-hill-ep-rr','pw-rr-ramp','pw-canal-rr-ep','pw-canal-ep-cc']);
 const nodes=[...seed.nodes.map(n=>n.node_id),'pl-jules','pl-recipient-b'];const edges=[];
 for(const p of seed.pathways){if(!['walkway','ramp','elevator'].includes(p.mode))continue;
  const w=p.pathway_id==='pw-cc-lift'?100:alt.has(p.pathway_id)?10:p.length_m;
  edges.push({id:p.pathway_id+':f',from:p.from,to:p.to,dt:p.seconds,dw:w});
  if(p.bidirectional)edges.push({id:p.pathway_id+':r',from:p.to,to:p.from,dt:p.seconds,dw:w});
 }
 for(const p of seed.places.filter(x=>['pl-jules','pl-recipient-b'].includes(x.place_id)))for(const a of p.access){if(a.step_free!==true)continue;
  edges.push({id:'access:'+p.place_id+':'+a.node_id,from:p.place_id==='pl-jules'?p.place_id:a.node_id,to:p.place_id==='pl-jules'?a.node_id:p.place_id,dt:a.seconds,dw:a.length_m});}
 const g={nodes,edges};const caps=[349,350,375,400,2500];
 return caps.map(budget=>({budget,...solve(g,'pl-jules','pl-recipient-b',{deadline:10000,budget})}));
}
const seed=require('./pinned_seed.json');
const result={...benchmark(solve),pinned:pinnedCase(solve,seed)};
if(result.pinned[0].status!=='infeasible'||result.pinned[1].arrival!==870||result.pinned[1].distance!==350||result.pinned[2].arrival!==870||result.pinned[3].arrival!==330||result.pinned[3].distance!==400)throw Error('pinned regression mismatch');
console.log(JSON.stringify(result,null,2));
