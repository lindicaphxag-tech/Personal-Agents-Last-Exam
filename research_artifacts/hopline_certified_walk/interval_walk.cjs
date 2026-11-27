'use strict';
function intervalSolve(graph,source,target,{depart=0,deadline,budget,limit=100000,workLimit=1000000}={}){
 const {nodes,edges}=graph;
 if(!Array.isArray(nodes)||new Set(nodes).size!==nodes.length||!nodes.includes(source)||!nodes.includes(target)||!Array.isArray(edges)||![depart,deadline,budget,limit,workLimit].every(Number.isSafeInteger)||depart<0||deadline<depart||deadline===Number.MAX_SAFE_INTEGER||budget<0||limit<1||workLimit<1)throw Error("invalid contract");
 const adj=new Map(nodes.map(n=>[n,[]])),rev=new Map(nodes.map(n=>[n,[]])),ids=new Set();
 for(const e of edges){
  if(typeof e.id!=="string"||!e.id||ids.has(e.id)||!adj.has(e.from)||!adj.has(e.to)||!Number.isSafeInteger(e.dt)||e.dt<0||!Number.isSafeInteger(e.dw)||e.dw<0||(e.windows!==undefined&&(!Array.isArray(e.windows)||e.windows.some(w=>!Array.isArray(w)||w.length!==2||!w.every(Number.isSafeInteger)||w[0]>=w[1]))))throw Error("invalid edge");
  ids.add(e.id);adj.get(e.from).push(e);rev.get(e.to).push(e);
 }
 const table=new Map(nodes.map(n=>[n,new Map()])),queue=[];
 let cursor=0,states=0,updates=0,transforms=0,work=0,peakIntervals=0,stored=0,exhausted=false,best=null,witnessStates=0;
 const tick=()=>{if(work>=workLimit){exhausted=true;return false;}work++;return true;};
 function add(n,c,l,h){
  if(exhausted||l>=h)return;
  const map=table.get(n);let st=map.get(c);
  if(!st){if(states>=limit){exhausted=true;return;}st={n,c,intervals:[],pending:false};map.set(c,st);states++;}
  const a=st.intervals;
  if(a.some(([x,y])=>x<=l&&h<=y))return;
  let out=[],added=false;
  for(const [x,y] of a){
   if(y<l)out.push([x,y]);else if(h<x){if(!added){out.push([l,h]);added=true;}out.push([x,y]);}
   else{l=Math.min(l,x);h=Math.max(h,y);}
  }
  if(!added)out.push([l,h]);
  // Cap interval storage too, not merely the number of (node,cost) records.
  if(stored-a.length+out.length>limit){exhausted=true;return;}
  stored+=out.length-a.length;peakIntervals=Math.max(peakIntervals,stored);st.intervals=out;updates++;
  if(n===target){const t=out[0][0];if(!best||t<best.t||(t===best.t&&c<best.c))best={t,c};return;}
  if(!st.pending){st.pending=true;queue.push(st);}
 }
 add(source,0,depart,depart+1);
 while(cursor<queue.length&&!exhausted){
  const st=queue[cursor++];st.pending=false;
  // Snapshot of the union at dequeue time. A self-loop may enqueue a new update.
  const intervals=st.intervals;
  for(const e of adj.get(st.n)){
   if(e.dw>budget-st.c||e.dt>deadline-depart)continue;
   const maxEntry=deadline-e.dt;
   for(const [a,b] of intervals){
    if(a>maxEntry)continue;
    const end=Math.min(b,maxEntry+1);
    for(const [x,y] of e.windows===undefined?[[depart,deadline+1]]:e.windows){
     if(!tick())break;transforms++;
     const l=Math.max(a,x),h=Math.min(end,y);
     if(l<h)add(e.to,st.c+e.dw,l+e.dt,h+e.dt);
     if(exhausted)break;
    }
    if(exhausted)break;
   }
   if(exhausted)break;
  }
 }
 const stats=()=>({states,updates,transforms,work,peakIntervals,witnessStates});
 if(exhausted)return {status:"incomplete",...stats()};
 if(!best)return {status:"infeasible",...stats()};
 // Reverse walk in the exact reachable states. Every reached state has a
 // finite derivation from the source; visited triples remove zero-cost cycles.
 const todo=[{n:target,t:best.t,c:best.c,next:null,edge:null}],seen=new Set();
 const key=x=>JSON.stringify([x.n,x.t,x.c]);seen.add(key(todo[0]));
 for(let i=0;i<todo.length;i++){
  const x=todo[i];witnessStates++;
  if(x.n===source&&x.t===depart&&x.c===0){
   const path=[];for(let y=x;y.next;y=y.next)path.push(y.edge.id);
   return {status:"optimal",arrival:best.t,distance:best.c,path,...stats()};
  }
  for(const e of rev.get(x.n)){
   if(!tick())return {status:"incomplete",...stats()};
   if(e.dt>x.t-depart||e.dw>x.c||e.from===target)continue;
   const t=x.t-e.dt,c=x.c-e.dw;
   if(e.windows!==undefined&&!e.windows.some(([a,b])=>a<=t&&t<b))continue;
   if(!table.get(e.from).get(c)?.intervals.some(([a,b])=>a<=t&&t<b))continue;
   const y={n:e.from,t,c,next:x,edge:e},k=key(y);
   if(!seen.has(k)){if(seen.size>=limit)return {status:"incomplete",...stats()};seen.add(k);todo.push(y);}
  }
 }
 throw Error("internal reachability witness invariant");
}
module.exports={intervalSolve};
