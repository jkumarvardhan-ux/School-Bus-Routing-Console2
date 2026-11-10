import React, { useEffect, useState } from 'react';

const api = async (path, options) => {
  const response = await fetch(`/api${path}`, options);
  const body = await response.json();
  if (!response.ok) throw new Error((body.errors || [body.error || 'Request failed']).join(', '));
  return body;
};
const post = (path, body) => api(path, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });

function Panel({title, children}) { return <section className="panel"><h2>{title}</h2>{children}</section>; }
function App() {
  const [stats, setStats] = useState({});
  const [events, setEvents] = useState([]);
  const [disruptions, setDisruptions] = useState([]);
  const [message, setMessage] = useState('Ready. New assignments are validated by the backend.');
  const [assignment, setAssignment] = useState({student_id:'', route_id:'', stop_id:''});
  const [attendance, setAttendance] = useState({student_id:'', event_date:new Date().toISOString().slice(0,10), status:'present'});
  const [disruption, setDisruption] = useState({route_id:'', disruption_type:'bus_breakdown', starts_at:''});
  const [capacity, setCapacity] = useState({bus_id:'', new_capacity:'', reason:'temporary capacity adjustment'});
  const refresh = async () => {
    const [s,e,d] = await Promise.all([api('/stats'), api('/operational_events?limit=25'), api('/disruptions?limit=25')]);
    setStats(s); setEvents(e); setDisruptions(d);
  };
  useEffect(() => { refresh().catch(err => setMessage(err.message)); }, []);
  const submit = async (fn, success) => { try { const result = await fn(); setMessage(JSON.stringify(result)); await refresh(); } catch (err) { setMessage(`${success} rejected: ${err.message}`); } };
  return <main>
    <header><div><span className="eyebrow">TRANSPORT OPERATIONS</span><h1>School Bus Routing Console</h1><p>Safe assignments · capacity · pickup windows · attendance · audit history</p></div><span className="seed">Synthetic seed · 20261022</span></header>
    <div className="metrics">{[['Students',stats.student],['Routes',stats.route],['Buses',stats.bus],['Assignments',stats.assignment],['Missed pickups',stats.missed_pickups],['Ground-truth issues',stats.ground_truth]].map(([label,value])=><div className="metric" key={label}><small>{label}</small><strong>{Number(value||0).toLocaleString()}</strong></div>)}</div>
    <div className="forms">
      <Panel title="Assign / reassign student"><form onSubmit={e=>{e.preventDefault();submit(()=>post('/assign',assignment),'Assignment');}}>
        {['student_id','route_id','stop_id'].map(k=><label key={k}>{k.replace('_',' ')}<input required value={assignment[k]} placeholder={k==='student_id'?'STU-000001':k==='route_id'?'ROUTE-2026-000001':'STOP-000001'} onChange={e=>setAssignment({...assignment,[k]:e.target.value.trim()})}/></label>)}<button>Validate & save</button>
      </form><p className="hint">Capacity, accessible vehicle, approved stop, active driver, zone match, route feasibility and pickup-window overlap are enforced.</p></Panel>
      <Panel title="Daily attendance"><form onSubmit={e=>{e.preventDefault();submit(()=>post('/attendance',attendance),'Attendance');}}>
        <label>Student ID<input required value={attendance.student_id} onChange={e=>setAttendance({...attendance,student_id:e.target.value.trim()})}/></label>
        <label>Date<input required type="date" value={attendance.event_date} onChange={e=>setAttendance({...attendance,event_date:e.target.value})}/></label>
        <label>Status<select value={attendance.status} onChange={e=>setAttendance({...attendance,status:e.target.value})}>{['present','absent','late','missed_pickup','boarded','dropped_off'].map(x=><option key={x}>{x}</option>)}</select></label><button>Record attendance</button>
      </form><p className="hint">Absent and missed-pickup events notify only a valid primary synthetic guardian contact.</p></Panel>
      <Panel title="Route disruption"><form onSubmit={e=>{e.preventDefault();submit(()=>post('/disruptions',disruption),'Disruption');}}>
        <label>Route ID<input required value={disruption.route_id} onChange={e=>setDisruption({...disruption,route_id:e.target.value.trim()})}/></label>
        <label>Type<select value={disruption.disruption_type} onChange={e=>setDisruption({...disruption,disruption_type:e.target.value})}>{['bus_breakdown','driver_unavailable','road_closure','weather'].map(x=><option key={x}>{x}</option>)}</select></label>
        <label>Starts at<input required type="datetime-local" value={disruption.starts_at} onChange={e=>setDisruption({...disruption,starts_at:e.target.value})}/></label><button>Report disruption</button>
      </form></Panel>
      <Panel title="Bus capacity change"><form onSubmit={e=>{e.preventDefault();submit(()=>post('/bus-capacity',capacity),'Capacity change');}}>
        <label>Bus ID<input required value={capacity.bus_id} onChange={e=>setCapacity({...capacity,bus_id:e.target.value.trim()})}/></label>
        <label>New capacity<input required type="number" min="1" value={capacity.new_capacity} onChange={e=>setCapacity({...capacity,new_capacity:e.target.value})}/></label>
        <label>Reason<input required value={capacity.reason} onChange={e=>setCapacity({...capacity,reason:e.target.value})}/></label><button>Validate & save capacity</button>
      </form><p className="hint">Capacity changes are rejected if they fall below any active route load, and every change is retained in history.</p></Panel>
      <Panel title="Latest decision"><pre className="result">{message}</pre></Panel>
    </div>
    <div className="tables"><Panel title="Operational audit trail"><div className="scroll"><table><thead><tr><th>Time</th><th>Entity</th><th>Entity ID</th><th>Event</th><th>Actor</th><th>Details</th></tr></thead><tbody>{events.map(e=><tr key={e.event_id}><td>{e.event_at}</td><td>{e.entity_type}</td><td>{e.entity_id}</td><td>{e.event_type}</td><td>{e.actor}</td><td>{e.details_json}</td></tr>)}</tbody></table></div></Panel>
    <Panel title="Route disruptions"><div className="scroll"><table><thead><tr><th>Route</th><th>Type</th><th>Start</th><th>Status</th><th>Notes</th></tr></thead><tbody>{disruptions.map(d=><tr key={d.disruption_id}><td>{d.route_id}</td><td>{d.disruption_type}</td><td>{d.starts_at}</td><td>{d.status}</td><td>{d.notes} {d.status==='open' && <button className="small" onClick={()=>submit(()=>post('/disruptions/resolve',{disruption_id:d.disruption_id}),'Resolve disruption')}>Resolve</button>}</td></tr>)}</tbody></table></div></Panel></div>
  </main>;
}
export default App;
