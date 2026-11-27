'use strict';
function solve(graph,source,target,{depart=0,deadline,budget,limit=100000,prune=true}={}){
  // integer ticks; entry-time availability, no waiting, positive duration.
  const {nodes,edges}=graph;
  if(!Array.isArray(nodes)||new Set(nodes).size!==nodes.length||!nodes.includes(source)||!nodes.includes(target)||![depart,deadline,budget,limit].every(Number.isSafeInteger)||depart<0||deadline<depart||budget<0||limit<1||!Array.isArray(edges))throw Error("invalid contract");
  const adj=new Map(nodes.map(n=>[n,[]])),rev=new Map(nodes.map(n=>[n,[]])),ids=new Set();
  for(const e of edges){
    if(typeof e.id!=="string"||!e.id||ids.has(e.id)||!adj.has(e.from)||!adj.has(e.to)||!Number.isSafeInteger(e.dt)||e.dt<=0||!Number.isSafeInteger(e.dw)||e.dw<0|| (e.windows!==undefined&&(!Array.isArray(e.windows)||e.windows.some(w=>!Array.isArray(w)||w.length!==2||!w.every(Number.isSafeInteger)||w[0]>=w[1]))))throw Error("invalid edge");
    ids.add(e.id);adj.get(e.from).push(e);rev.get(e.to).push(e);
  }
  const staticGraph=edges.every(e=>e.windows===undefined);
  // Admissible lower bounds: independent relaxed shortest duration and distance.
  function reverse(key){
    const d=new Map(nodes.map(n=>[n,Infinity]));d.set(target,0);const un=new Set(nodes);
    while(un.size){let u=null;for(const n of un)if(u===null||d.get(n)<d.get(u))u=n;
      un.delete(u);if(!Number.isFinite(d.get(u)))break;
      for(const e of rev.get(u)){const v=d.get(u)+e[key];if(v<d.get(e.from))d.set(e.from,v);}
    }return d;
  }
  const dt=reverse("dt"),dw=reverse("dw");
  const labels=new Map(nodes.map(n=>[n,[]])),queue=[];
  let expanded=0,generated=0,dominated=0,boundPruned=0,peak=0,serial=0,exhausted=false;
  function insert(node,t,w,parent,edge){
    if(!Number.isSafeInteger(t)||!Number.isSafeInteger(w)||t>deadline||w>budget)return;
    if(prune&&(t+dt.get(node)>deadline||w+dw.get(node)>budget)){boundPruned++;return;}
    const list=labels.get(node);
    const dominates=(x,y)=>x.w<=y.w&&(staticGraph?x.t<=y.t:x.t===y.t);
    const l={node,t,w,parent,edge,active:true,serial:serial++};
    if(list.some(x=>x.active&&dominates(x,l))){dominated++;return;}
    if(generated>=limit){exhausted=true;return;}
    for(const x of list)if(x.active&&dominates(l,x)){x.active=false;dominated++;}
    list.push(l);queue.push(l);generated++;peak=Math.max(peak,queue.length);
  }
  insert(source,depart,0,null,null);
  while(queue.length&&!exhausted){
    queue.sort((a,b)=>a.t-b.t||a.w-b.w||a.serial-b.serial);
    const l=queue.shift();if(!l.active)continue;expanded++;
    if(l.node===target){const path=[];for(let p=l;p.parent;p=p.parent)path.unshift(p.edge.id);
      return {status:"optimal",arrival:l.t,distance:l.w,path,expanded,generated,dominated,boundPruned,peak,staticGraph};}
    for(const e of adj.get(l.node)){
      if(e.windows!==undefined&&!e.windows.some(([a,b])=>a<=l.t&&l.t<b))continue;
      insert(e.to,l.t+e.dt,l.w+e.dw,l,e);if(exhausted)break;
    }
  }
  return {status:exhausted?"incomplete":"infeasible",expanded,generated,dominated,boundPruned,peak,staticGraph};
}
module.exports={solve};
