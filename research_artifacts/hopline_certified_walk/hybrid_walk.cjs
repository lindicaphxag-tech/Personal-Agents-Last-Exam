'use strict';
function deltaIntervals(graph,source,target,{depart=0,deadline,budget,limit=100000,workLimit=1000000}={}){
 const {nodes,edges}=graph;
 if(!Array.isArray(nodes)||new Set(nodes).size!==nodes.length||!nodes.includes(source)||!nodes.includes(target)||!Array.isArray(edges)||![depart,deadline,budget,limit,workLimit].every(Number.isSafeInteger)||depart<0||deadline<depart||deadline===Number.MAX_SAFE_INTEGER||budget<0||limit<1||workLimit<1)throw Error("invalid contract");
 const adj=new Map(nodes.map(n=>[n,[]])),rev=new Map(nodes.map(n=>[n,[]])),ids=new Set();
 for(const e of edges){
  if(typeof e.id!=="string"||!e.id||ids.has(e.id)||!adj.has(e.from)||!adj.has(e.to)||!Number.isSafeInteger(e.dt)||e.dt<0||!Number.isSafeInteger(e.dw)||e.dw<0||(e.windows!==undefined&&(!Array.isArray(e.windows)||e.windows.some(w=>!Array.isArray(w)||w.length!==2||!w.every(Number.isSafeInteger)||w[0]>=w[1]))))throw Error("invalid edge");
  ids.add(e.id);adj.get(e.from).push(e);rev.get(e.to).push(e);
 }
 let work=0,exhausted=false;
 function tick(){if(work>=workLimit){exhausted=true;return false;}work++;return true;}
 function reverse(key,cap){
  const d=new Map(nodes.map(n=>[n,Infinity])),un=new Set(nodes);d.set(target,0);
  while(un.size&&!exhausted){let u=null;
   for(const n of un){if(!tick())break;if(u===null||d.get(n)<d.get(u))u=n;}
   if(exhausted)break;
   un.delete(u);const v=d.get(u);if(!Number.isFinite(v))break;
   for(const e of rev.get(u)){if(!tick())break;if(e[key]<=cap-v&&v+e[key]<d.get(e.from))d.set(e.from,v+e[key]);}
  }return d;
 }
 const dur=reverse("dt",deadline-depart),dist=reverse("dw",budget);
 const table=new Map(nodes.map(n=>[n,new Map()])),queue=[];
 let cursor=0,states=0,updates=0,stored=0,pendingStored=0,peak=0,transforms=0,pruned=0,witnessStates=0,best=null;
 function stats(){return {states,updates,work,transforms,pruned,peakIntervals:peak,witnessStates};}
 function merge(a,b){
  const out=[];let i=0,j=0;
  while(i<a.length||j<b.length){
   if(!tick())return null;
   const x=j>=b.length||(i<a.length&&a[i][0]<=b[j][0])?a[i++]:b[j++];
   const last=out.at(-1);if(last&&last[1]>=x[0])last[1]=Math.max(last[1],x[1]);else out.push([...x]);
  }return out;
 }
 function add(n,c,l,h){
  if(exhausted||l>=h)return;
  const dt=dur.get(n),dw=dist.get(n);
  if(dw>budget-c||dt>deadline-l){pruned++;return;}
  // Strictly improve the incumbent lexicographic target pair, if one exists.
  let upper=deadline-dt+1;
  if(best)upper=Math.min(upper,best.t-dt+(dw<best.c-c?1:0));
  h=Math.min(h,upper);if(l>=h){pruned++;return;}
  let st=table.get(n).get(c);
  if(!st){if(states>=limit){exhausted=true;return;}st={n,c,all:[],pending:[],queued:false};table.get(n).set(c,st);states++;}
  const delta=[];let pos=l;
  for(const [a,b] of st.all){
   if(!tick())return;
   if(b<=pos)continue;if(a>=h)break;
   if(a>pos)delta.push([pos,Math.min(a,h)]);
   pos=Math.max(pos,b);if(pos>=h)break;
  }
  if(pos<h)delta.push([pos,h]);if(!delta.length)return;
  const all=merge(st.all,delta);if(!all)return;
  const pending=n===target?[]:merge(st.pending,delta);if(!pending)return;
  const ns=stored-st.all.length+all.length,np=pendingStored-st.pending.length+pending.length;
  if(ns+np>limit){exhausted=true;return;}
  stored=ns;pendingStored=np;peak=Math.max(peak,ns+np);
  st.all=all;st.pending=pending;updates++;
  if(n===target){const t=all[0][0];if(!best||t<best.t||(t===best.t&&c<best.c))best={t,c};return;}
  if(!st.queued){st.queued=true;queue.push(st);}
 }
 add(source,0,depart,depart+1);
 while(cursor<queue.length&&!exhausted){
  const st=queue[cursor++];st.queued=false;
  const fresh=st.pending;pendingStored-=fresh.length;st.pending=[];
  for(const e of adj.get(st.n)){
   if(exhausted)break;
   if(e.dw>budget-st.c||e.dt>deadline-depart)continue;
   for(const [a,b] of fresh){
    if(exhausted)break;
    const end=Math.min(b,deadline-e.dt+1);
    for(const [x,y] of e.windows===undefined?[[depart,deadline+1]]:e.windows){
     if(!tick())break;transforms++;
     const l=Math.max(a,x),h=Math.min(end,y);
     if(l<h)add(e.to,st.c+e.dw,l+e.dt,h+e.dt);
     if(exhausted)break;
    }
   }
  }
 }
 if(exhausted)return {status:"incomplete",...stats()};
 if(!best)return {status:"infeasible",...stats()};
 const todo=[{n:target,t:best.t,c:best.c,next:null,edge:null}],seen=new Set();
 const key=x=>JSON.stringify([x.n,x.t,x.c]);seen.add(key(todo[0]));
 for(let i=0;i<todo.length;i++){
  const x=todo[i];witnessStates++;
  if(x.n===source&&x.t===depart&&x.c===0){const path=[];for(let y=x;y.next;y=y.next)path.push(y.edge.id);return {status:"optimal",arrival:best.t,distance:best.c,path,...stats()};}
  for(const e of rev.get(x.n)){
   if(!tick())return {status:"incomplete",...stats()};
   if(e.from===target||e.dt>x.t-depart||e.dw>x.c)continue;
   const t=x.t-e.dt,c=x.c-e.dw;
   if(e.windows!==undefined&&!e.windows.some(([a,b])=>a<=t&&t<b))continue;
   let reached=false;
   for(const [a,b] of table.get(e.from).get(c)?.all||[]){if(!tick())return {status:"incomplete",...stats()};if(a<=t&&t<b){reached=true;break;}}
   if(!reached)continue;
   const y={n:e.from,t,c,next:x,edge:e},k=key(y);
   if(!seen.has(k)){if(seen.size>=limit)return {status:"incomplete",...stats()};seen.add(k);todo.push(y);}
  }
 }
 throw Error("internal witness invariant");
}
function hybrid(graph,source,target,options,probe){
 const {probeLimit=128,limit=100000,...rest}=options;
 if(!Number.isSafeInteger(probeLimit)||probeLimit<0||!Number.isSafeInteger(limit)||limit<1)throw Error("invalid hybrid limits");
 if(probeLimit){
  const p=probe(graph,source,target,{...rest,limit:Math.min(probeLimit,limit),mode:"time"});
  if(p.status!=="incomplete")return {...p,engine:"label",probeGenerated:p.generated};
  const d=deltaIntervals(graph,source,target,{...rest,limit});
  return {...d,engine:"delta",probeGenerated:p.generated};
 }
 return {...deltaIntervals(graph,source,target,{...rest,limit}),engine:"delta",probeGenerated:0};
}
module.exports={deltaIntervals,hybrid};
