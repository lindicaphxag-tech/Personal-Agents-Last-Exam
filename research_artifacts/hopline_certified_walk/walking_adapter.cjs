'use strict';
function facilityAt(f,t,asOf){
  const known=f.history.filter(h=>Date.parse(h.recorded_at)<=asOf);
  const entry=t<=asOf?known.filter(h=>Date.parse(h.since)<=t).pop():known[known.length-1];
  if(!entry||entry.status==="in_service"||entry.status==="restored")return {usable:true,status:"in_service",seq:entry?.seq??0};
  const er=entry.expected_return?Date.parse(entry.expected_return):null;
  const state={status:"out_of_service",seq:entry.seq,since:entry.since,expected_return:entry.expected_return,estimate_passed:er!==null&&er<=asOf};
  if(t>asOf&&er!==null&&er>asOf&&er<=t)return {...state,usable:true,uses_estimate:true};
  return {...state,usable:false};
}
function walkingGraph(seed,from,to,depart,deadline,asOf,allowEstimates=false){
  const nodes=seed.nodes.map(n=>n.node_id).concat(from,to),edges=[];
  if(from===to||new Set(nodes).size!==nodes.length)throw Error("invalid endpoint identity");
  const facilities=new Map(seed.facilities.map(f=>[f.facility_id,f]));
  function windows(f){
    if(!f)throw Error("missing facility");
    const known=f.history.filter(h=>Date.parse(h.recorded_at)<=asOf);
    const cuts=new Set([depart,deadline+1]);
    for(const x of [asOf+1,...known.flatMap(h=>[Date.parse(h.since),h.expected_return?Date.parse(h.expected_return):NaN])])if(Number.isSafeInteger(x)&&x>depart&&x<=deadline)cuts.add(x);
    const a=[...cuts].sort((x,y)=>x-y),out=[];
    for(let i=0;i<a.length-1;i++){const st=facilityAt(f,a[i],asOf);if(st.usable&&(allowEstimates||!st.uses_estimate))out.push([a[i],a[i+1]]);}
    return out;
  }
  for(const p of seed.pathways){if(!["walkway","elevator","ramp"].includes(p.mode))continue;
    const e={id:p.pathway_id+":f",from:p.from,to:p.to,dt:p.seconds*1000,dw:p.length_m,...(p.facility_id?{windows:windows(facilities.get(p.facility_id))}:{})};edges.push(e);
    if(p.bidirectional)edges.push({...e,id:p.pathway_id+":r",from:p.to,to:p.from});
  }
  for(const id of [from,to]){const place=seed.places.find(p=>p.place_id===id);if(!place)throw Error("unknown place");
    for(const a of place.access)if(a.step_free===true)edges.push({id:"access:"+id+":"+a.node_id,from:id===from?id:a.node_id,to:id===from?a.node_id:id,dt:a.seconds*1000,dw:a.length_m});
  }
  return {nodes,edges};
}
module.exports={walkingGraph,facilityAt};
