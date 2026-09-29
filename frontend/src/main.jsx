import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function App(){
  const [token,setToken]=useState(localStorage.token||''); const [user,setUser]=useState(null);
  const [requests,setRequests]=useState([]); const [episodes,setEpisodes]=useState([]); const [error,setError]=useState('');
  const api=async(path,options={})=>{const r=await fetch(API+path,{...options,headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`,...options.headers}});if(!r.ok)throw new Error((await r.json()).detail||'Request failed');return r.json()};
  const load=async()=>{try{const me=await api('/me');setUser(me);setRequests(await api('/requests'));if(me.role!=='client')setEpisodes(await api('/episodes?available=true&limit=100'));}catch(e){logout()}};
  useEffect(()=>{if(token)load()},[token]);
  const login=async e=>{e.preventDefault();setError('');const f=new FormData(e.currentTarget);try{const data=await fetch(API+'/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(f))}).then(async r=>{if(!r.ok)throw new Error((await r.json()).detail);return r.json()});localStorage.token=data.access_token;setToken(data.access_token)}catch(e){setError(e.message)}};
  const logout=()=>{localStorage.removeItem('token');setToken('');setUser(null)};
  const create=async e=>{e.preventDefault();const f=Object.fromEntries(new FormData(e.currentTarget));f.episodes_requested=Number(f.episodes_requested);try{await api('/requests',{method:'POST',body:JSON.stringify(f)});e.currentTarget.reset();load()}catch(e){setError(e.message)}};
  const transition=async(id,status)=>{try{await api(`/requests/${id}/status`,{method:'POST',body:JSON.stringify({status})});load()}catch(e){setError(e.message)}};
  const assign=async(id,episodeId)=>{try{await api(`/requests/${id}/assignments`,{method:'POST',body:JSON.stringify({episode_ids:[episodeId]})});load()}catch(e){setError(e.message)}};
  if(!token)return <main className="login"><section><h1>Dataset Request Desk</h1><p>Sign in to manage robotics datasets.</p><form onSubmit={login}><label>Email<input name="email" type="email" required/></label><label>Password<input name="password" type="password" required/></label><button>Sign in</button></form>{error&&<div className="error">{error}</div>}<small>Try client-a@example.com / client123</small></section></main>;
  if(!user)return <main>Loading…</main>;
  return <><header><div><strong>Dataset Request Desk</strong><span>{user.name} · {user.role}</span></div><button className="ghost" onClick={logout}>Sign out</button></header><main>{error&&<div className="error">{error}<button onClick={()=>setError('')}>×</button></div>}
    {user.role==='client'&&<section><h2>New dataset request</h2><form className="grid" onSubmit={create}><label>Task name<input name="task_name" required/></label><label>Episodes<input name="episodes_requested" type="number" min="1" required/></label><label>Deadline<input name="deadline" type="date" required/></label><label className="wide">Notes<textarea name="notes"/></label><button>Create request</button></form></section>}
    <section><div className="section-title"><div><h2>{user.role==='client'?'My requests':'All requests'}</h2><p>{requests.length} total</p></div><button className="ghost" onClick={load}>Refresh</button></div><div className="cards">{requests.map(r=><article key={r.id}><div className="row"><h3>{r.task_name}</h3><span className={'badge '+r.status}>{r.status.replace('_',' ')}</span></div><p>{r.assigned_count} / {r.episodes_requested} episodes · due {r.deadline}</p>{r.notes&&<p className="muted">{r.notes}</p>}<div className="actions">{user.role==='client'&&r.status==='delivered'&&<><button onClick={()=>transition(r.id,'accepted')}>Accept</button><button className="danger" onClick={()=>transition(r.id,'rejected')}>Reject</button></>}{user.role!=='client'&&<OperatorActions request={r} episodes={episodes} transition={transition} assign={assign}/>}</div></article>)}</div></section>
  </main></>;
}
function OperatorActions({request:r,episodes,transition,assign}){const [episode,setEpisode]=useState('');return <>{r.status==='submitted'&&<button onClick={()=>transition(r.id,'in_progress')}>Start work</button>}{r.status==='rejected'&&<button onClick={()=>transition(r.id,'in_progress')}>Start rework</button>}{r.status==='in_progress'&&<><select value={episode} onChange={e=>setEpisode(e.target.value)}><option value="">Choose available episode</option>{episodes.map(e=><option key={e.id} value={e.id}>{e.episode_id} · {e.task_name} · {e.quality}</option>)}</select><button disabled={!episode} onClick={()=>{assign(r.id,Number(episode));setEpisode('')}}>Assign</button><button disabled={r.assigned_count<r.episodes_requested} onClick={()=>transition(r.id,'delivered')}>Deliver</button></>}</>}
createRoot(document.getElementById('root')).render(<App/>);

