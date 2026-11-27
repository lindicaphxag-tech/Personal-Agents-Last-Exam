'use strict';
function eventPartition(nodes,edges,start,end,cap){
  const cuts=new Map(nodes.map(n=>[n,new Set()])), rev=new Map(nodes.map(n=>[n,[]]));
  for(const e of edges)rev.get(e.to).push(e);
  const todo=[];let count=0;
  function add(n,x){
    if(x<start||x>end+1||cuts.get(n).has(x))return true;
    if(count>=cap)return false;
    cuts.get(n).add(x);todo.push([n,x]);count++;return true;
  }
  for(const n of nodes)if(!add(n,start)||!add(n,end+1))return null;
  for(const e of edges)for(const [a,b] of e.windows||[])if(!add(e.from,a)||!add(e.from,b))return null;
  for(let i=0;i<todo.length;i++){const [v,x]=todo[i];for(const e of rev.get(v))if(!add(e.from,x-e.dt))return null;}
  return {count,cuts:new Map(nodes.map(n=>[n,[...cuts.get(n)].sort((a,b)=>a-b)]))};
}
function solve(graph,source,target,{depart=0,deadline,budget,limit=100000,partitionLimit=20000,mode="event"}={}){
  const {nodes,edges}=graph;
  if(!Array.isArray(nodes)||new Set(nodes).size!==nodes.length||!nodes.includes(source)||!nodes.includes(target)||!Array.isArray(edges)||![depart,deadline,budget,limit,partitionLimit].every(Number.isSafeInteger)||depart<0||deadline<depart||deadline===Number.MAX_SAFE_INTEGER||budget<0||limit<1||partitionLimit<1||!["event","time"].includes(mode))throw Error("invalid contract");
  const adj=new Map(nodes.map(n=>[n,[]])),rev=new Map(nodes.map(n=>[n,[]])),ids=new Set();
  for(const e of edges){
    if(typeof e.id!=="string"||!e.id||ids.has(e.id)||!adj.has(e.from)||!adj.has(e.to)||!Number.isSafeInteger(e.dt)||e.dt<0||!Number.isSafeInteger(e.dw)||e.dw<0||(e.windows!==undefined&&(!Array.isArray(e.windows)||e.windows.some(w=>!Array.isArray(w)||w.length!==2||!w.every(Number.isSafeInteger)||w[0]>=w[1]))))throw Error("invalid edge");
    ids.add(e.id);adj.get(e.from).push(e);rev.get(e.to).push(e);
  }
  const staticGraph=edges.every(e=>e.windows===undefined);
  const partition=!staticGraph&&mode==="event"?eventPartition(nodes,edges,depart,deadline,partitionLimit):null;
  const method=staticGraph?"static":partition?"event":"exact-time";
  function cell(n,t){
    if(staticGraph)return 0;
    if(!partition)return t;
    const a=partition.cuts.get(n);let lo=0,hi=a.length-1;
    while(hi-lo>1){const mid=(lo+hi)>>1;if(a[mid]<=t)lo=mid;else hi=mid;}
    return lo;
  }
  function reverse(key,cap){
    const d=new Map(nodes.map(n=>[n,Infinity]));d.set(target,0);const un=new Set(nodes);
    while(un.size){let u=null;for(const n of un)if(u===null||d.get(n)<d.get(u))u=n;
      un.delete(u);const v=d.get(u);if(!Number.isFinite(v))break;
      for(const e of rev.get(u))if(e[key]<=cap-v&&v+e[key]<d.get(e.from))d.set(e.from,v+e[key]);
    }return d;
  }
  const dur=reverse("dt",deadline-depart),dist=reverse("dw",budget);
  const labels=new Map(nodes.map(n=>[n,new Map()])),heap=[];
  let serial=0,expanded=0,generated=0,dominated=0,pruned=0,exhausted=false,peak=0;
  const less=(a,b)=>a.t<b.t||(a.t===b.t&&(a.w<b.w||(a.w===b.w&&a.serial<b.serial)));
  function push(x){let i=heap.length;heap.push(x);while(i){const p=(i-1)>>1;if(!less(x,heap[p]))break;heap[i]=heap[p];i=p;}heap[i]=x;peak=Math.max(peak,heap.length);}
  function pop(){const x=heap[0],v=heap.pop();if(heap.length){let i=0;while(i*2+1<heap.length){let j=i*2+1;if(j+1<heap.length&&less(heap[j+1],heap[j]))j++;if(!less(heap[j],v))break;heap[i]=heap[j];i=j;}heap[i]=v;}return x;}
  function insert(n,t,w,parent,edge){
    if(dur.get(n)>deadline-t||dist.get(n)>budget-w){pruned++;return;}
    const k=cell(n,t),m=labels.get(n),list=m.get(k)||[];
    if(list.some(x=>x.active&&x.t<=t&&x.w<=w)){dominated++;return;}
    if(generated>=limit){exhausted=true;return;}
    for(const x of list)if(x.active&&t<=x.t&&w<=x.w){x.active=false;dominated++;}
    const l={n,t,w,parent,edge,active:true,serial:serial++};list.push(l);m.set(k,list);push(l);generated++;
  }
  const stats=()=>({method,partitionCuts:partition?.count||0,expanded,generated,dominated,pruned,peak});
  insert(source,depart,0,null,null);
  while(heap.length&&!exhausted){
    const l=pop();if(!l.active)continue;expanded++;
    if(l.n===target){const path=[];for(let p=l;p.parent;p=p.parent)path.unshift(p.edge.id);return {status:"optimal",arrival:l.t,distance:l.w,path,...stats()};}
    for(const e of adj.get(l.n)){
      if(e.dt>deadline-l.t||e.dw>budget-l.w||(e.windows!==undefined&&!e.windows.some(([a,b])=>a<=l.t&&l.t<b)))continue;
      insert(e.to,l.t+e.dt,l.w+e.dw,l,e);if(exhausted)break;
    }
  }
  return {status:exhausted?"incomplete":"infeasible",...stats()};
}
module.exports={solve,eventPartition};
