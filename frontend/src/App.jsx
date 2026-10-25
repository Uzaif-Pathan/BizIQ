import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Routes, Route, Navigate, Link, NavLink, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  Menu, X, LayoutDashboard, Building2, ChartNoAxesCombined, Users, Package, TrendingUp,
  MapPinned, FileSearch, ClipboardList, FileText, Settings, LogOut, ChevronDown, Plus,
  ArrowUpRight, ArrowRight, Search, Bell, CircleHelp, SlidersHorizontal, Upload, FileSpreadsheet,
  CheckCircle2, AlertCircle, CircleDashed, MoreHorizontal, Download, CalendarDays, Sparkles,
  PanelLeftClose, PanelLeftOpen, Eye, EyeOff, Save, RefreshCw, Check, LockKeyhole, Mail,
  Store, BriefcaseBusiness, Wallet, Target, Activity, Clock3, ExternalLink, Filter, Info, Trash2, UserRound
} from 'lucide-react';
import {
  ResponsiveContainer, AreaChart, Area, CartesianGrid, XAxis, YAxis, Tooltip,
  BarChart, Bar, Legend, PieChart, Pie, Cell
} from 'recharts';

import { api, ApiError, describeError, businessFromApi, businessToApi, businessCreateFromLocal, businessUpdateFromProfile } from './services/api';
import { migrateBusinessId } from './utils/businessState';
import { currency, pct } from './utils/format';
import { useLatestAnalysis } from './hooks/useLatestAnalysis';
const STORE_KEY = 'biziq-state-v2';
const navItems = [
  ['dashboard','Dashboard',LayoutDashboard],
  ['financial','Financial Analysis',Wallet],
  ['customers','Customer Analysis',Users],
  ['products','Product & Service Analysis',Package],
  ['trends','Trends & Benchmarks',TrendingUp],
  ['market','Location & Market Analysis',MapPinned],
  ['findings','Findings',FileSearch],
  ['recommendations','Recommendations',ClipboardList],
  ['report','Final Report',FileText],
  ['update-data','Update Business Data',RefreshCw],
];
const monthly = [
  {month:'Nov',revenue:70000,expenses:50000},{month:'Dec',revenue:76000,expenses:53000},
  {month:'Jan',revenue:72000,expenses:52000},{month:'Feb',revenue:74500,expenses:53500},
  {month:'Mar',revenue:79000,expenses:55500},{month:'Apr',revenue:78000,expenses:55000},
  {month:'May',revenue:82000,expenses:57000},{month:'Jun',revenue:91000,expenses:61500},
  {month:'Jul',revenue:87000,expenses:59000},{month:'Aug',revenue:103000,expenses:68000},
  {month:'Sep',revenue:98000,expenses:65000},{month:'Oct',revenue:112000,expenses:71000}
];
const DATA_YEAR = new Date().getFullYear();
const monthlyDated = monthly.map((m,i)=>({...m,idx:i-2}));
const emptyWorkspace = () => ({businesses:[], selected:null, profiles:{}, uploads:{}, recs:{}});
const initialRoot = () => {
  try { const saved = JSON.parse(localStorage.getItem(STORE_KEY)); if (saved && Array.isArray(saved.accounts)) return {accounts:saved.accounts, workspaces:saved.workspaces||{}, user:saved.user||null, settingsOpen:false}; } catch {}
  return {accounts:[], workspaces:{}, user:null, settingsOpen:false};
};
const today = () => new Date().toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'});
async function hashPassword(email,password) {
  try {
    const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(email+':'+password));
    return Array.from(new Uint8Array(buf)).map(b=>b.toString(16).padStart(2,'0')).join('');
  } catch { return 'plain:'+password; }
}
function useAppState() {
  const [root,setRoot] = useState(initialRoot);
  const rootRef = useRef(root); rootRef.current = root;
  useEffect(()=>{localStorage.setItem(STORE_KEY,JSON.stringify({accounts:root.accounts,workspaces:root.workspaces,user:root.user}));},[root]);
  const state = useMemo(()=>({...emptyWorkspace(),...((root.user&&root.workspaces[root.user.email])||{}),user:root.user,settingsOpen:root.settingsOpen}),[root]);
  const setState = useCallback(fn=>setRoot(r=>{
    const cur = {...emptyWorkspace(),...((r.user&&r.workspaces[r.user.email])||{}),user:r.user,settingsOpen:r.settingsOpen};
    const {user,settingsOpen,...ws} = typeof fn==='function'?fn(cur):fn;
    const accounts = user&&r.user&&user.name!==r.user.name?r.accounts.map(a=>a.email===user.email?{...a,name:user.name}:a):r.accounts;
    return {...r,accounts,user,settingsOpen:!!settingsOpen,workspaces:user?{...r.workspaces,[user.email]:ws}:r.workspaces};
  }),[]);
  const register = useCallback(async(name,email,password)=>{
    const em = email.trim().toLowerCase();
    if (rootRef.current.accounts.some(a=>a.email===em)) return 'An account with this email already exists. Sign in instead.';
    const hash = await hashPassword(em,password);
    const user = {name:name.trim(),email:em};
    setRoot(r=>({...r,accounts:[...r.accounts,{...user,hash}],user,workspaces:{...r.workspaces,[em]:emptyWorkspace()}}));
    return null;
  },[]);
  const login = useCallback(async(email,password)=>{
    const em = email.trim().toLowerCase();
    const acct = rootRef.current.accounts.find(a=>a.email===em);
    if (!acct) return 'No account found for this email. Create one first.';
    if (acct.hash!==await hashPassword(em,password)) return 'Incorrect password.';
    setRoot(r=>({...r,user:{name:acct.name,email:acct.email},workspaces:r.workspaces[em]?r.workspaces:{...r.workspaces,[em]:emptyWorkspace()}}));
    return null;
  },[]);
  return [state,setState,{register,login}];
}
function Button({children,variant='primary',...props}) { return <button className={`btn ${variant}`} {...props}>{children}</button>; }
function Tag({children,tone='neutral'}) { return <span className={`tag ${tone}`}>{children}</span>; }
function EmptyState({icon:Icon=FileSearch,title,body,action}) { return <div className="empty"><div className="empty-icon"><Icon size={21}/></div><h3>{title}</h3><p>{body}</p>{action}</div>; }

function AuthShell({children}) {
  return <main className="login-page"><div className="login-left"><Link to="/" className="brand"><span className="brand-mark">b.</span><span>BizIQ</span></Link><div className="login-copy"><Tag tone="blue">BUSINESS INTELLIGENCE, MADE PRACTICAL</Tag><h1>Clarity for the next<br/>business decision.</h1><div className="login-points"><span><CheckCircle2 size={17}/> Evidence-backed analysis</span><span><CheckCircle2 size={17}/> Recommendations you can act on</span><span><CheckCircle2 size={17}/> One clear report to share</span></div></div><div className="login-footer">© 2026 BizIQ <span>Built for better business decisions.</span></div></div><div className="login-right">{children}</div></main>;
}
function PasswordField({value,onChange,show,onToggle,placeholder,autoComplete,invalid,minLength}) {
  return <div className="field-icon"><LockKeyhole size={17}/><input value={value} onChange={onChange} type={show?'text':'password'} required minLength={minLength} autoComplete={autoComplete} aria-invalid={invalid} placeholder={placeholder}/><button type="button" className="icon-btn" onClick={onToggle} aria-label="Toggle password visibility">{show?<EyeOff size={16}/>:<Eye size={16}/>}</button></div>;
}
function AuthError({title,message}) {
  return <div className="login-error-panel" role="alert"><AlertCircle size={16}/><div><strong>{title}</strong><p>{message}</p></div></div>;
}
function Register({onRegister}) {
  const [name,setName]=useState(''),[email,setEmail]=useState(''),[password,setPassword]=useState(''),[confirm,setConfirm]=useState(''),[show,setShow]=useState(false),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  async function submit(e){
    e.preventDefault();setError('');
    if(name.trim().length<2){setError('Enter your full name.');return;}
    if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())){setError('Enter a valid email address.');return;}
    if(password.length<8){setError('Password must be at least 8 characters.');return;}
    if(password!==confirm){setError('Passwords do not match.');return;}
    setBusy(true);const err=await onRegister(name,email,password);setBusy(false);if(err)setError(err);
  }
  return <AuthShell><form className="login-form" onSubmit={submit} noValidate><div className="eyebrow">GET STARTED</div><h2>Create your account</h2><label>Full name</label><div className="field-icon"><UserRound size={17}/><input value={name} onChange={e=>{setName(e.target.value);setError('');}} type="text" required autoComplete="name" placeholder="Your name"/></div><label>Email address</label><div className="field-icon"><Mail size={17}/><input value={email} onChange={e=>{setEmail(e.target.value);setError('');}} type="email" required autoComplete="email" placeholder="you@company.com"/></div><label>Password</label><PasswordField value={password} onChange={e=>{setPassword(e.target.value);setError('');}} show={show} onToggle={()=>setShow(!show)} placeholder="At least 8 characters" autoComplete="new-password" invalid={!!error} minLength={8}/><label>Confirm password</label><PasswordField value={confirm} onChange={e=>{setConfirm(e.target.value);setError('');}} show={show} onToggle={()=>setShow(!show)} placeholder="Re-enter your password" autoComplete="new-password" invalid={!!error} minLength={8}/>{error&&<AuthError title="Couldn’t create account" message={error}/>}<Button type="submit" disabled={busy} style={{width:'100%',justifyContent:'center'}}>{busy?'Creating account…':'Create account'} <ArrowRight size={16}/></Button><div className="auth-switch">Already have an account? <Link to="/login">Sign in</Link></div></form></AuthShell>;
}
function Login({onLogin}) {
  const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[show,setShow]=useState(false),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  async function submit(e){
    e.preventDefault();setError('');
    if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())){setError('Enter a valid email address.');return;}
    setBusy(true);const err=await onLogin(email,password);setBusy(false);if(err)setError(err);
  }
  return <AuthShell><form className="login-form" onSubmit={submit} noValidate><div className="eyebrow">WELCOME BACK</div><h2>Sign in to BizIQ</h2><label>Email address</label><div className="field-icon"><Mail size={17}/><input value={email} onChange={e=>{setEmail(e.target.value);setError('');}} type="email" required autoComplete="email" placeholder="you@company.com"/></div><label>Password</label><PasswordField value={password} onChange={e=>{setPassword(e.target.value);setError('');}} show={show} onToggle={()=>setShow(!show)} placeholder="Enter your password" autoComplete="current-password" invalid={!!error}/>{error&&<AuthError title="Sign-in failed" message={error}/>}<Button type="submit" disabled={busy} style={{width:'100%',justifyContent:'center'}}>{busy?'Signing in…':'Sign in'} <ArrowRight size={16}/></Button><div className="auth-switch">New to BizIQ? <Link to="/register">Create an account</Link></div></form></AuthShell>;
}

function Shell({state,setState,children}) {
  const [collapsed,setCollapsed]=useState(false),[mobileOpen,setMobileOpen]=useState(false),[search,setSearch]=useState(''),[noticeOpen,setNoticeOpen]=useState(false);
  const loc=useLocation(),navigate=useNavigate();
  const active=state.businesses.find(b=>b.id===state.selected)||state.businesses[0];
  const page=navItems.find(n=>loc.pathname.includes('/'+n[0]))?.[1]||(loc.pathname.includes('/profile')?'Business profile':'My businesses');
  function logout(){setState(s=>({...s,user:null}));navigate('/login');}
  return <div className={`app-shell ${collapsed?'collapsed':''}`}>
    <aside className={`sidebar ${mobileOpen?'mobile-open':''}`}><div className="sidebar-top"><Link to="/" className="brand"><span className="brand-mark">b.</span>{!collapsed&&<span>BizIQ</span>}</Link><button className="icon-btn sidebar-close" onClick={()=>setMobileOpen(false)}><X size={18}/></button></div>
      {!collapsed&&<div className="workspace"><div className="workspace-avatar">B</div><div className="workspace-text"><strong>My workspace</strong><span>Business account</span></div><ChevronDown size={15}/></div>}
      <div className="side-label">{!collapsed?'WORKSPACE':''}</div>
      <nav className="side-nav"><NavLink to="/businesses" end title={collapsed?'My businesses':undefined} className={({isActive})=>`side-link ${isActive?'active':''}`} onClick={()=>setMobileOpen(false)}><Building2 size={18}/>{!collapsed&&<span>My businesses</span>}</NavLink>{active&&navItems.map(([id,label,Icon])=><NavLink key={id} to={`/business/${active.id}/${id}`} title={collapsed?label:undefined} className={({isActive})=>`side-link ${isActive?'active':''}`} onClick={()=>setMobileOpen(false)}><Icon size={18}/>{!collapsed&&<span>{label}</span>}{!collapsed&&id==='dashboard'&&<span className="side-dot"/>}</NavLink>)}</nav>
      <div className="sidebar-bottom"><button className="side-link" onClick={()=>setState(s=>({...s,settingsOpen:true}))}><Settings size={18}/>{!collapsed&&<span>Settings</span>}</button><button className="side-link" onClick={logout}><LogOut size={18}/>{!collapsed&&<span>Sign out</span>}</button><button className="collapse-btn" onClick={()=>setCollapsed(!collapsed)}>{collapsed?<PanelLeftOpen size={17}/>:<PanelLeftClose size={17}/>} {!collapsed&&'Collapse sidebar'}</button></div>
    </aside>
    {mobileOpen&&<div className="scrim" onClick={()=>setMobileOpen(false)}/>}
    <div className="main-column"><header className="topbar"><button className="icon-btn mobile-menu" onClick={()=>setMobileOpen(true)}><Menu size={19}/></button><div className="breadcrumbs"><span>Workspace</span><span className="crumb-slash">/</span><strong>{page}</strong></div><div className="top-actions"><div className="top-search"><Search size={16}/><input placeholder="Search anything…" value={search} onChange={e=>setSearch(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'){const q=search.trim();navigate(q?`/businesses?q=${encodeURIComponent(q)}`:'/businesses');}}}/></div><a className="icon-btn help-btn" title="Email support" aria-label="Email support" href="mailto:support@biziq.example?subject=BizIQ%20support"><CircleHelp size={18}/></a><button className="icon-btn notification-btn" title="Notifications" aria-label="Notifications" onClick={()=>setNoticeOpen(true)}><Bell size={18}/><i/></button><button type="button" className="user-menu" onClick={()=>setState(s=>({...s,settingsOpen:true}))} aria-label="Open account settings"><div className="user-avatar">{state.user?.name?.[0]||'A'}</div><div className="user-meta"><strong>{state.user?.name||'Account'}</strong><span>Business owner</span></div><ChevronDown size={15}/></button></div></header><div className="page-wrap">{children}</div><footer className="app-footer"><span>© 2026 BizIQ</span><span>Clear data. Better decisions.</span><a href="mailto:support@biziq.example">Support <ArrowUpRight size={12}/></a></footer></div>
    {state.settingsOpen&&<Modal title="Workspace settings" onClose={()=>setState(s=>({...s,settingsOpen:false}))}><SettingsPanel state={state} setState={setState}/></Modal>}{noticeOpen&&<Modal title="Notifications" onClose={()=>setNoticeOpen(false)}><div className="settings-form"><p className="muted">You’re all caught up.</p><Button onClick={()=>setNoticeOpen(false)}>Got it</Button></div></Modal>}
  </div>
}
function Modal({title,onClose,children}){return <div className="modal-backdrop" onMouseDown={e=>e.target===e.currentTarget&&onClose()}><div className="modal"><div className="modal-head"><h3>{title}</h3><button className="icon-btn" onClick={onClose}><X size={18}/></button></div>{children}</div></div>}
function SettingsPanel({state,setState}){const [name,setName]=useState(state.user?.name||'');return <form className="settings-form" onSubmit={e=>{e.preventDefault();setState(s=>({...s,user:{...s.user,name:name.trim()},settingsOpen:false}));}}><label>Display name</label><input className="input" value={name} onChange={e=>setName(e.target.value)} required/><label>Email address</label><input className="input" type="email" value={state.user?.email||''} readOnly disabled/><Button type="submit"><Save size={15}/> Save settings</Button></form>}
function PageHeader({eyebrow,title,subtitle,actions}){return <div className="page-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{subtitle&&<p>{subtitle}</p>}</div>{actions&&<div className="header-actions">{actions}</div>}</div>}
function StatCard({label,value,detail,icon:Icon,change}){return <div className="stat-card"><div className="stat-top"><span>{label}</span><span className="stat-icon"><Icon size={17}/></span></div><div className="stat-value">{value}</div><div className="stat-bottom">{change&&<span className="stat-change">{change}</span>}<span>{detail}</span></div></div>}

function BusinessPicker({state,setState}){const [open,setOpen]=useState(false);const active=state.businesses.find(b=>b.id===state.selected)||state.businesses[0];return <div className="business-picker-wrap"><button className="business-picker" onClick={()=>setOpen(!open)}><div className="business-icon"><Store size={18}/></div><div className="business-picker-text"><span>ACTIVE BUSINESS</span><strong>{active?.name||'Select a business'}</strong></div><ChevronDown size={16}/></button>{open&&<><div className="picker-dismiss" onClick={()=>setOpen(false)}/><div className="picker-menu">{state.businesses.map(b=><button key={b.id} className={active?.id===b.id?'selected':''} onClick={()=>{setState(s=>({...s,selected:b.id}));setOpen(false);}}><span className="business-icon small"><Store size={15}/></span><span><strong>{b.name}</strong><small>{b.industry}</small></span>{active?.id===b.id&&<Check size={15}/>}</button>)}<Link to="/businesses" onClick={()=>setOpen(false)}><Plus size={15}/> Manage businesses</Link></div></>}</div>}
function Businesses({state,setState}) {
  const [params]=useSearchParams();
  const [query,setQuery]=useState(params.get('q')||''),[filter,setFilter]=useState('All businesses'),[showAdd,setShowAdd]=useState(false),[toDelete,setToDelete]=useState(null);
  useEffect(()=>{setQuery(params.get('q')||'');},[params]);
  const [loading,setLoading]=useState(true),[loadError,setLoadError]=useState('');
  const [syncing,setSyncing]=useState(null),[syncError,setSyncError]=useState(null);
  useEffect(()=>{
    let cancelled=false;
    (async()=>{
      try{
        const remote=await api.listBusinesses(200,0);
        if(cancelled)return;
        setState(s=>{
          const remoteIds=new Set(remote.map(b=>b.id));
          const localById=Object.fromEntries(s.businesses.map(b=>[b.id,b]));
          const fromServer=remote.map(b=>businessFromApi(b,localById[b.id]));
          const notOnServer=s.businesses.filter(b=>!remoteIds.has(b.id)).map(b=>({...b,synced:false}));
          const businesses=[...fromServer,...notOnServer];
          const selected=businesses.some(b=>b.id===s.selected)?s.selected:(businesses[0]?.id||null);
          return {...s,businesses,selected};
        });
        setLoadError('');
      }catch(e){ if(!cancelled) setLoadError(describeError(e)); }
      finally{ if(!cancelled) setLoading(false); }
    })();
    return ()=>{cancelled=true;};
  },[]);
  const filtered=state.businesses.filter(b=>(b.name+' '+b.industry+' '+b.location).toLowerCase().includes(query.trim().toLowerCase())&&(filter==='All businesses'||(filter==='With data'?b.hasData:!b.hasData)));
  async function syncBusiness(b){
    setSyncing(b.id);setSyncError(null);
    try{
      const created=await api.createBusiness(businessCreateFromLocal(b,state.profiles[b.id]));
      setState(s=>migrateBusinessId(s,b.id,businessFromApi(created,b)));
    }catch(e){setSyncError({id:b.id,message:describeError(e)});}
    finally{setSyncing(null);}
  }
  async function addBusiness(b){
    const created=await api.createBusiness(businessToApi(b));
    const nb=businessFromApi(created);
    setState(s=>({...s,selected:s.selected&&s.businesses.some(x=>x.id===s.selected)?s.selected:nb.id,businesses:[...s.businesses,nb]}));
    setShowAdd(false);
  }
  function deleteBusiness(id){setState(s=>{const businesses=s.businesses.filter(b=>b.id!==id);const {[id]:_p,...profiles}=s.profiles;const {[id]:_u,...uploads}=s.uploads;const {[id]:_r,...recs}=s.recs||{};return {...s,businesses,profiles,uploads,recs,selected:s.selected===id?(businesses[0]?.id||null):s.selected};});setToDelete(null);}
  return <><PageHeader eyebrow="WORKSPACE" title="My businesses" actions={<Button onClick={()=>setShowAdd(true)}><Plus size={16}/> Add business</Button>}/>{loading&&<div className="notice-banner slim"><div className="notice-icon"><Info size={18}/></div><div><strong>Loading businesses…</strong></div></div>}{loadError&&<div className="notice-banner slim"><div className="notice-icon"><AlertCircle size={18}/></div><div><strong>Could not load from the server</strong><p>{loadError} Showing businesses saved on this device.</p></div></div>}<div className="metric-strip"><div><span className="metric-number">{state.businesses.length.toString().padStart(2,'0')}</span><span>Businesses added</span></div><div><span className="metric-number">{state.businesses.filter(b=>b.hasData).length.toString().padStart(2,'0')}</span><span>With business data</span></div><div><span className="metric-number">{state.businesses.filter(b=>!b.hasData).length.toString().padStart(2,'0')}</span><span>Awaiting data</span></div></div><div className="panel"><div className="panel-toolbar"><div className="search-field"><Search size={16}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search businesses"/></div><select className="select-control" value={filter} onChange={e=>setFilter(e.target.value)}><option>All businesses</option><option>With data</option><option>Awaiting data</option></select><button className="btn secondary" onClick={()=>{setQuery('');setFilter('All businesses')}}><SlidersHorizontal size={15}/> Reset</button></div><div className="business-grid">{filtered.map(b=><article className="business-card" key={b.id}><div className="business-card-top"><div className="business-icon large"><Store size={21}/></div><div className="business-card-actions"><Link className="icon-btn" aria-label={`Edit ${b.name}`} title="Edit business" to={`/business/${b.id}/profile`} onClick={()=>setState(s=>({...s,selected:b.id}))}><MoreHorizontal size={19}/></Link><button type="button" className="icon-btn danger" aria-label={`Delete ${b.name}`} title={b.synced===true?'Deleting is not supported by the server yet':'Delete business'} disabled={b.synced===true} onClick={()=>setToDelete(b)}><Trash2 size={17}/></button></div></div><h3>{b.name}</h3><p className="business-industry">{b.industry}</p><div className="business-location"><MapPinned size={14}/>{b.location}</div><div className="business-card-divider"/>{b.synced===false&&<div className="business-card-meta"><span>SERVER</span><Tag tone="amber">Not saved on server</Tag></div>}{b.synced===false&&<button type="button" className="text-link" disabled={syncing===b.id} onClick={()=>syncBusiness(b)}>{syncing===b.id?'Saving to server…':'Save to server'}</button>}{syncError?.id===b.id&&<div className="inline-message warn"><AlertCircle size={16}/> {syncError.message}</div>}<div className="business-card-meta"><span>DATA STATUS</span><Tag tone={b.hasData?'green':'neutral'}>{b.hasData?'Data available':'Not uploaded'}</Tag></div><div className="business-card-meta"><span>LAST UPDATED</span><span className="muted small-text">{b.updated}</span></div><Link className="business-card-action" to={`/business/${b.id}/dashboard`} onClick={()=>setState(s=>({...s,selected:b.id}))}>{b.hasData?'Open dashboard':'Set up business'}<ArrowUpRight size={16}/></Link></article>)}</div>{!filtered.length&&(state.businesses.length?<EmptyState title="No businesses found" body="Try a different search or filter." action={<Button variant="secondary" onClick={()=>{setQuery('');setFilter('All businesses')}}>Clear filters</Button>}/>:<EmptyState icon={Store} title="No businesses yet" body="Add your first business to get started." action={<Button onClick={()=>setShowAdd(true)}><Plus size={15}/> Add business</Button>}/>)}</div>{showAdd&&<Modal title="Add a business" onClose={()=>setShowAdd(false)}><AddBusinessForm onAdd={addBusiness}/></Modal>}{toDelete&&<Modal title="Delete business" onClose={()=>setToDelete(null)}><div className="settings-form"><p>Delete <strong>{toDelete.name}</strong>? Its profile and uploaded file records will be removed permanently.</p><div className="confirm-actions"><Button variant="secondary" onClick={()=>setToDelete(null)}>Cancel</Button><Button variant="danger" onClick={()=>deleteBusiness(toDelete.id)}><Trash2 size={15}/> Delete</Button></div></div></Modal>}</>;
}
function AddBusinessForm({onAdd}){
  const [name,setName]=useState(''),[industry,setIndustry]=useState('Retail'),[type,setType]=useState('Retail'),[location,setLocation]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  async function submit(e){
    e.preventDefault();
    setBusy(true);setError('');
    try{await onAdd({name:name.trim(),industry,type,location:location.trim()});}
    catch(err){setError(describeError(err));setBusy(false);}
  }
  return <form className="stack-form" onSubmit={submit}><label>Business name</label><input className="input" value={name} onChange={e=>setName(e.target.value)} placeholder="e.g. Cornerstone Studio" minLength={2} maxLength={200} required/><label>Industry</label><select className="input" value={industry} onChange={e=>setIndustry(e.target.value)}><option>Retail</option><option>Food service</option><option>Professional services</option><option>Healthcare</option><option>Education</option><option>Manufacturing</option><option>Other</option></select><label>Business model</label><div className="choice-row"><button type="button" className={`choice ${type==='Retail'?'chosen':''}`} onClick={()=>setType('Retail')}><Package size={17}/> Product / Retail</button><button type="button" className={`choice ${type==='Service'?'chosen':''}`} onClick={()=>setType('Service')}><BriefcaseBusiness size={17}/> Service business</button></div><label>City, State</label><input className="input" value={location} onChange={e=>setLocation(e.target.value)} placeholder="e.g. Nashik, Maharashtra" required/>{error&&<div className="inline-message warn"><AlertCircle size={16}/> {error}</div>}<Button type="submit" disabled={busy}><Plus size={15}/> {busy?'Creating…':'Create business'}</Button></form>}

function AnalysisPanel({business,res}){
  const {analysis,loading,running,error,run,onServer}=res;
  const isMock=!!analysis?.method_version&&analysis.method_version.startsWith('mock');
  const m=analysis?.metrics||{};
  const failed=analysis?.status==='failed';
  return <section className="panel" style={{marginBottom:24}}>
    <div className="panel-heading"><div><h3>Analysis</h3><p>Run the analysis engine on the server for this business</p></div>{onServer&&<Button onClick={run} disabled={running||loading}><RefreshCw size={15}/> {running?'Running…':analysis?'Run again':'Run analysis'}</Button>}</div>
    {!onServer&&<div className="notice-banner slim"><div className="notice-icon"><Info size={18}/></div><div><strong>Not saved on the server</strong><p>Analyses run on the server, so this business has to be saved there first. Create it again with “Add business” while the backend is running.</p></div></div>}
    {onServer&&loading&&<p className="muted">Loading the latest analysis…</p>}
    {onServer&&error&&<div className="inline-message warn"><AlertCircle size={16}/> {error}</div>}
    {onServer&&!loading&&!analysis&&!error&&<EmptyState icon={Activity} title="No analysis yet" body="Run an analysis to see metrics, findings and recommendations from the server."/>}
    {analysis&&<>
      <div style={{display:'flex',gap:8,flexWrap:'wrap',margin:'4px 0 16px'}}><Tag tone={analysis.status==='completed'?'green':'amber'}>{analysis.status}</Tag><Tag>Evidence: {analysis.evidence_level}</Tag><Tag>Benchmarks: {analysis.benchmark_status}</Tag>{analysis.method_version&&<Tag>Method {analysis.method_version}</Tag>}</div>
      {isMock&&<div className="notice-banner slim"><div className="notice-icon"><AlertCircle size={18}/></div><div><strong>Sample output — not calculated from your data</strong><p>The server is still using its development engine, so these numbers are placeholders.</p></div></div>}
      {failed&&<div className="inline-message warn"><AlertCircle size={16}/> This analysis failed: {analysis.error_message}</div>}
      {!failed&&<div className="stats-grid"><StatCard label="Revenue" value={currency(m.revenue)} detail="Recorded period" icon={Wallet}/><StatCard label="Expenses" value={currency(m.expenses)} detail="Recorded period" icon={Activity}/><StatCard label="Profit" value={currency(m.profit)} detail="Revenue minus expenses" icon={TrendingUp}/><StatCard label="Profit margin" value={pct(m.profit_margin)} detail="Share of revenue" icon={Target}/></div>}
      {!failed&&<p className="small-text muted">{analysis.findings.length} findings · {analysis.recommendations.length} recommendations</p>}
      {analysis.limitations?.length>0&&<ul className="small-text muted">{analysis.limitations.map((x,i)=><li key={i}>{x}</li>)}</ul>}
    </>}
  </section>;
}
const isMockAnalysis = a => !!a?.method_version && a.method_version.startsWith('mock');
function SampleBanner(){return <div className="notice-banner slim"><div className="notice-icon"><AlertCircle size={18}/></div><div><strong>Sample output — not calculated from your data</strong><p>The server is still using its development engine, so these results are placeholders.</p></div></div>;}
// Returns a message to show instead of the page content, or null when a usable analysis is loaded.
function analysisGate(business,res,what){
  const {analysis,loading,error,onServer}=res;
  if(!onServer)return <div className="notice-banner slim"><div className="notice-icon"><Info size={18}/></div><div><strong>Not saved on the server</strong><p>Analysis results come from the server, so this business has to be saved there first. Create it again with “Add business” while the backend is running.</p></div></div>;
  if(loading)return <p className="muted">Loading the latest analysis…</p>;
  if(error)return <div className="inline-message warn"><AlertCircle size={16}/> {error}</div>;
  if(!analysis)return <EmptyState icon={FileSearch} title={`No ${what} yet`} body="Run an analysis from the dashboard to generate them." action={<Link className="btn primary" to={`/business/${business.id}/dashboard`}>Go to dashboard</Link>}/>;
  if(analysis.status==='failed')return <div className="inline-message warn"><AlertCircle size={16}/> The latest analysis failed: {analysis.error_message||'no details were provided.'} Run it again from the dashboard.</div>;
  return null;
}
function Dashboard({state,setState,business}) {
  const navigate=useNavigate();const profile=state.profiles[business.id]||{};const isRetail=business.type==='Retail';const upload=state.uploads[business.id];const [from,setFrom]=useState(`${DATA_YEAR}-05-01`);const [to,setTo]=useState(`${DATA_YEAR}-10-31`);const inRange=m=>{const first=new Date(DATA_YEAR,m.idx,1),last=new Date(DATA_YEAR,m.idx+1,0);return (!from||last>=new Date(from+'T00:00:00'))&&(!to||first<=new Date(to+'T00:00:00'));};const cur=monthlyDated.filter(inRange);const n=cur.length;const firstIdx=n?monthlyDated.indexOf(cur[0]):0;const prev=n&&firstIdx>=n?monthlyDated.slice(firstIdx-n,firstIdx):[];const sum=(arr,k)=>arr.reduce((t,m)=>t+m[k],0);const revenue=sum(cur,'revenue'),expenses=sum(cur,'expenses');const growth=prev.length===n&&sum(prev,'revenue')?(revenue/sum(prev,'revenue')-1)*100:null;
  const res=useLatestAnalysis(business,setState);
  const analysisDone=res.analysis?.status==='completed';
  const recList=res.analysis?.recommendations||[];
  const recDoneIds=state.recs?.[business.id]||[];
  const recDone=recList.filter(r=>recDoneIds.includes(r.recommendation_id)).length;
  const recsAllDone=analysisDone&&recList.length>0&&recDone===recList.length;
  const steps=[
    {title:'Saved on the server',note:business.synced===true?'Business exists on the server':'Save this business to the server first',done:business.synced===true},
    {title:'Business data',note:business.hasData?'File registered on this device (not sent to the server yet)':'Upload your records',done:!!business.hasData},
    {title:'Analysis',note:analysisDone?'Latest analysis completed':res.loading?'Checking…':'Run an analysis',done:analysisDone},
    {title:'Review recommendations',note:!analysisDone?'Available after an analysis':recList.length===0?'No recommendations in this analysis':`${recDone} of ${recList.length} completed`,done:recsAllDone}
  ];
  const doneN=steps.filter(s=>s.done).length,pctDone=Math.round(doneN/steps.length*100);
  const nextAction=business.synced!==true?null:!analysisDone?{label:'Run analysis',run:()=>{if(!res.running)res.run();}}:!recsAllDone?{label:'Review recommendations',run:()=>navigate(`/business/${business.id}/recommendations`)}:null;
  return <><PageHeader eyebrow="BUSINESS OVERVIEW" title={`Good ${new Date().getHours()<12?'morning':new Date().getHours()<17?'afternoon':'evening'}.`} subtitle={`Here’s where ${business.name} stands today.`} actions={<Button onClick={()=>navigate(`/business/${business.id}/findings`)}>View findings <ArrowRight size={15}/></Button>}/><div className="dashboard-context"><div className="business-context-icon"><Store size={20}/></div><div><strong>{business.name}</strong><span>{business.industry} <i/> {business.location}</span></div><Tag tone={business.hasData?'green':'neutral'}>{business.hasData?'Data available':'Limited data'}</Tag><div className="context-spacer"/><BusinessPicker state={state} setState={setState}/></div>
    
    <AnalysisPanel business={business} res={res}/><div className="section-heading"><div><h2>Business at a glance</h2></div><div className="period-picker"><label>Start date<input type="date" className="date-control" value={from} max={to||undefined} onChange={e=>setFrom(e.target.value)}/></label><label>End date<input type="date" className="date-control" value={to} min={from||undefined} onChange={e=>setTo(e.target.value)}/></label></div></div>{business.hasData&&n===0&&<p className="period-note">No reported months fall inside this date range.</p>}
    <div className="stats-grid"><StatCard label="Total revenue" value={business.hasData&&n?currency(revenue):'—'} detail={business.hasData?`Across ${cur.length} reported months · illustrative`:'Requires financial data'} icon={Wallet} change={business.hasData&&growth!=null?`${growth>=0?'+':''}${growth.toFixed(1)}% vs previous period`:null}/><StatCard label="Operating expenses" value={business.hasData&&n?currency(expenses):'—'} detail={business.hasData?'Illustrative operating costs':'Requires financial data'} icon={Activity}/><StatCard label="Customer count" value="—" detail="Not available yet" icon={Users}/><StatCard label={isRetail?'Product categories':'Service categories'} value="—" detail="Not available yet" icon={isRetail?Package:BriefcaseBusiness}/></div>
    <div className="dashboard-grid"><section className="panel chart-panel"><div className="panel-heading"><div><h3>Revenue & expenses</h3><p>Monthly view · INR · illustrative data</p></div><button className="icon-btn" title="Print chart" aria-label="Print chart" onClick={()=>window.print()}><MoreHorizontal size={18}/></button></div>{business.hasData?<div className="chart-area"><ResponsiveContainer width="100%" height="100%"><AreaChart data={cur} margin={{top:10,right:5,left:0,bottom:0}}><defs><linearGradient id="revFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#4568d4" stopOpacity={0.17}/><stop offset="100%" stopColor="#4568d4" stopOpacity={0}/></linearGradient></defs><CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#e9e9e7"/><XAxis dataKey="month" tickLine={false} axisLine={false} tick={{fill:'#858681',fontSize:14}} dy={8}/><YAxis tickLine={false} axisLine={false} tick={{fill:'#858681',fontSize:13}} tickFormatter={v=>`${v/1000}k`} width={42}/><Tooltip formatter={v=>currency(v)} contentStyle={{border:'1px solid #e8e8e5',borderRadius:10,fontSize:14}}/><Area type="monotone" dataKey="revenue" name="Revenue" stroke="#4568d4" strokeWidth={2.3} fill="url(#revFill)"/><Area type="monotone" dataKey="expenses" name="Expenses" stroke="#b5a18d" strokeWidth={2} fill="transparent"/></AreaChart></ResponsiveContainer></div>:<div className="chart-empty"><div className="chart-placeholder"><span/><span/><span/><span/><span/><span/></div><p>Upload your financial records to see your business trend.</p><Button variant="secondary" onClick={()=>navigate(`/business/${business.id}/update-data`)}>Upload financial data</Button></div>}<div className="chart-legend"><span><i className="legend-blue"/> Revenue</span><span><i className="legend-sand"/> Expenses</span></div></section>
    <section className="panel activity-panel"><div className="panel-heading"><div><h3>Analysis status</h3></div><Tag tone={doneN===steps.length?'green':doneN>1?'blue':'neutral'}>{doneN===steps.length?'Complete':doneN>1?'In progress':'Setup needed'}</Tag></div><div className="progress-line"><span style={{width:`${pctDone}%`}}/></div><div className="progress-meta"><span>{doneN} of {steps.length} steps complete</span><span>{pctDone}%</span></div><div className="activity-list">{steps.map(s=><div className="activity-item" key={s.title}><span className={`activity-check ${s.done?'done':''}`}>{s.done?<Check size={13}/>:<CircleDashed size={14}/>}</span><div><strong>{s.title}</strong><span>{s.note}</span></div><Tag tone={s.done?'green':'neutral'}>{s.done?'Done':'Pending'}</Tag></div>)}</div>{nextAction&&<button className="text-link" onClick={nextAction.run}>{nextAction.label} <ArrowRight size={15}/></button>}</section></div>
    <div className="section-heading lower-heading"><div><h2>Make your next move</h2></div></div><div className="quick-actions"><button onClick={()=>navigate(`/business/${business.id}/profile`)}><div className="quick-icon"><Building2 size={19}/></div><div><strong>Business profile</strong><span>Review your business details</span></div><ArrowUpRight size={17}/></button><button onClick={()=>navigate(`/business/${business.id}/update-data`)}><div className="quick-icon"><FileSpreadsheet size={19}/></div><div><strong>Manage business data</strong><span>Upload or replace your records</span></div><ArrowUpRight size={17}/></button><button onClick={()=>navigate(`/business/${business.id}/recommendations`)}><div className="quick-icon"><Target size={19}/></div><div><strong>Recommendations</strong><span>Explore practical next steps</span></div><ArrowUpRight size={17}/></button></div>
  </>;
}

function BusinessProfile({state,setState,business}) {
  const navigate=useNavigate(),[saved,setSaved]=useState(false),[saving,setSaving]=useState(false),[saveNote,setSaveNote]=useState('');const existing=state.profiles[business.id]||{};const [form,setForm]=useState({name:business.name,industry:business.industry,type:business.type,location:business.location,website:existing.website||'',description:existing.description||'',employees:existing.employees||'1–10',stage:existing.stage||'Operating',currency:existing.currency||'INR'});
  const update=(k,v)=>{setSaved(false);setForm(s=>({...s,[k]:v}));};
  async function save(e){
    e.preventDefault();
    setSaving(true);setSaveNote('');
    let serverBusiness=null,note='',markLocalOnly=false;
    if(business.synced===true){
      try{serverBusiness=await api.updateBusiness(business.id,businessUpdateFromProfile(form));}
      catch(err){
        if(err instanceof ApiError&&err.status===404){note='The server no longer has this business (it may have restarted), so these changes were saved on this device only.';markLocalOnly=true;}
        else{setSaveNote(describeError(err));setSaving(false);return;}
      }
    }else{note='This business is not saved on the server yet, so these changes were saved on this device only.';}
    setState(s=>({...s,businesses:s.businesses.map(b=>b.id!==business.id?b:(serverBusiness?businessFromApi(serverBusiness,b):{...b,name:form.name,industry:form.industry,type:form.type,location:form.location,synced:markLocalOnly?false:b.synced})),profiles:{...s.profiles,[business.id]:form}}));
    setSaving(false);setSaved(!note);setSaveNote(note);
  }
  return <><PageHeader eyebrow="BUSINESS SETUP" title="Business profile" actions={<Button form="profile-form" type="submit" disabled={saving}><Save size={15}/> {saving?'Saving…':'Save changes'}</Button>}/><form id="profile-form" className="profile-layout" onSubmit={save}><div className="panel form-panel"><div className="panel-heading"><div><h3>Business details</h3></div><Building2 size={19} className="muted"/></div><div className="form-grid"><div className="form-field full"><label>Business name</label><input className="input" value={form.name} onChange={e=>update('name',e.target.value)} minLength={2} maxLength={200} required/></div><div className="form-field"><label>Industry</label><select className="input" value={form.industry} onChange={e=>update('industry',e.target.value)}>{['Retail','Retail · Clothing','Food service','Professional services','Healthcare','Education','Manufacturing','Other'].map(x=><option key={x}>{x}</option>)}</select></div><div className="form-field"><label>Business model</label><select className="input" value={form.type} onChange={e=>update('type',e.target.value)}><option>Retail</option><option>Service</option></select></div><div className="form-field"><label>City, State</label><input className="input" value={form.location} onChange={e=>update('location',e.target.value)} required/></div><div className="form-field"><label>Website (optional)</label><input className="input" value={form.website} onChange={e=>update('website',e.target.value)} placeholder="https://yourbusiness.com"/></div><div className="form-field"><label>Team size</label><select className="input" value={form.employees} onChange={e=>update('employees',e.target.value)}>{['Just me','1–10','11–50','51–200','201+'].map(x=><option key={x}>{x}</option>)}</select></div><div className="form-field"><label>Business stage</label><select className="input" value={form.stage} onChange={e=>update('stage',e.target.value)}>{['Idea','Launching','Operating','Expanding','Established'].map(x=><option key={x}>{x}</option>)}</select></div><div className="form-field full"><label>What does your business do?</label><textarea className="input textarea" rows="4" value={form.description} onChange={e=>update('description',e.target.value)} placeholder="Describe your products, services and the customers you serve."/></div></div>{saveNote&&<div className="inline-message warn"><AlertCircle size={16}/> {saveNote}</div>}<div className="form-actions">{saved?<span className="small-text save-ok"><CheckCircle2 size={14}/> Changes saved</span>:<span/>}<Button type="submit" disabled={saving}><Save size={15}/> {saving?'Saving…':'Save profile'}</Button></div></div><aside className="panel side-info"><div className="info-illustration"><Building2 size={28}/></div><div className="info-rule"/><div className="info-stat"><span>Profile status</span><Tag tone="green">Created</Tag></div><div className="info-stat"><span>Data status</span><Tag tone={business.hasData?'green':'neutral'}>{business.hasData?'Available':'Not uploaded'}</Tag></div><button type="button" className="text-link" onClick={()=>navigate(`/business/${business.id}/update-data`)}>Go to data upload <ArrowRight size={15}/></button></aside></form></>;
}

function UpdateData({state,setState,business}) {
  const [category,setCategory]=useState('Financial records'),[file,setFile]=useState(null),[period,setPeriod]=useState('Last 6 months'),[notes,setNotes]=useState(''),[message,setMessage]=useState('');
  const inputId='file-upload';
  function submit(e){e.preventDefault();if(!file){setMessage('Choose a CSV or Excel file first.');return;}if(!/\.(csv|xlsx|xls)$/i.test(file.name)){setMessage('Unsupported file type. Choose a CSV, XLSX, or XLS file.');return;}if(file.size>10*1024*1024){setMessage('File is larger than 10 MB. Choose a smaller file.');return;}setState(s=>({...s,uploads:{...s.uploads,[business.id]:[...(s.uploads[business.id]||[]),{name:file.name,size:file.size,category,period,added:new Date().toLocaleDateString('en-IN'),notes,status:'Uploaded — validation needed'}]},businesses:s.businesses.map(b=>b.id===business.id?{...b,hasData:true,updated:today(),level:'Standard Data'}:b)}));setMessage(`“${file.name}” was added. Please validate the data before relying on any analysis.`);setFile(null);}
  const uploads=state.uploads[business.id]||[];
  function downloadTemplate(){const csv='date,revenue,expenses,notes\n2026-08-01,10000,6500,Example only\n';const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));a.download='biziq-data-template.csv';a.click();URL.revokeObjectURL(a.href);}
  return <><PageHeader eyebrow="DATA MANAGEMENT" title="Update business data" actions={<Tag tone={business.hasData?'green':'neutral'}>{business.hasData?'Data available':'Awaiting data'}</Tag>}/><div className="upload-layout"><section className="panel upload-panel"><div className="panel-heading"><div><h3>Upload business records</h3></div><Upload size={20} className="muted"/></div><form onSubmit={submit}><label>What kind of data are you adding?</label><div className="data-type-grid">{['Financial records','Customer data','Product / service data','Sales transactions','Market research','Other'].map((x,i)=><button key={x} type="button" className={`data-type ${category===x?'chosen':''}`} onClick={()=>setCategory(x)}><span className="data-type-icon">{[<Wallet/>,<Users/>,<Package/>,<ChartNoAxesCombined/>,<MapPinned/>,<FileSpreadsheet/>][i]}</span><span>{x}</span>{category===x&&<CheckCircle2 size={16} className="chosen-check"/>}</button>)}</div><label>Reporting period</label><select className="input" value={period} onChange={e=>setPeriod(e.target.value)}><option>Last 30 days</option><option>Last 3 months</option><option>Last 6 months</option><option>Last 12 months</option><option>Custom period</option></select><label>Choose a file</label><label htmlFor={inputId} className={`dropzone ${file?'has-file':''}`}><input id={inputId} type="file" accept=".csv,.xlsx,.xls" onChange={e=>{setFile(e.target.files?.[0]||null);setMessage('');}}/><div className="upload-symbol"><Upload size={21}/></div><strong>{file?file.name:'Drop your file here, or browse'}</strong><span>{file?`${(file.size/1024).toFixed(1)} KB · Ready to add`:'CSV, XLSX or XLS · Max 10 MB'}</span><span className="browse-label">{file?'Choose a different file':'Browse files'}</span></label><label>Notes (optional)</label><textarea className="input textarea" rows="3" value={notes} onChange={e=>setNotes(e.target.value)} placeholder="Add context about the data, missing months, or column meanings."/><div className="form-actions"><span/><Button type="submit"><Upload size={15}/> Add data file</Button></div>{message&&<div className={`inline-message ${/^(Choose|Unsupported|File is larger)/.test(message)?'warn':'success'}`}>{/(Choose|Unsupported|larger)/.test(message)?<AlertCircle size={16}/>:<CheckCircle2 size={16}/>} {message}</div>}</form></section><aside className="panel upload-help"><div className="template-box"><FileSpreadsheet size={21}/><div><strong>CSV template</strong></div><button type="button" className="text-link" onClick={downloadTemplate}>Download CSV <Download size={14}/></button></div></aside></div><section className="panel recent-uploads"><div className="panel-heading"><div><h3>Uploaded files</h3></div><Tag>{uploads.length} {uploads.length===1?'file':'files'}</Tag></div>{uploads.length?<div className="table-scroll"><table><thead><tr><th>FILE</th><th>DATA TYPE</th><th>PERIOD</th><th>ADDED</th><th>STATUS</th></tr></thead><tbody>{uploads.map((u,i)=><tr key={i}><td><span className="file-cell"><FileSpreadsheet size={17}/><span><strong>{u.name}</strong><small>{(u.size/1024).toFixed(1)} KB</small></span></span></td><td>{u.category}</td><td>{u.period}</td><td>{u.added}</td><td><Tag tone="amber">{u.status}</Tag></td></tr>)}</tbody></table></div>:<EmptyState icon={FileSpreadsheet} title="No files added yet" body="Your uploaded records will appear here once added."/>}</section></>;
}

function AnalysisPage({kind,state,business}) {
 const data=business.hasData;const isRetail=business.type==='Retail';
 const meta={
 financial:['FINANCIAL ANALYSIS','Know where the money goes','Revenue, expenses and operating performance — based on your records.',Wallet],
 customers:['CUSTOMER ANALYSIS','Understand your customers','Explore retention, segments and purchase behaviour when customer data is available.',Users],
 products:['PRODUCT & SERVICE ANALYSIS',isRetail?'See what sells and what doesn’t':'Understand your service mix','Compare product performance for retail businesses, or service categories and delivery for service businesses.',isRetail?Package:BriefcaseBusiness],
 trends:['TRENDS & BENCHMARKS','Put changes in context','Separate meaningful movement from normal variation, with source-backed comparisons only.',TrendingUp],
 market:['LOCATION & MARKET ANALYSIS','Understand your market','Bring local context and verified market evidence into business planning.',MapPinned]
 }[kind];const Icon=meta[3];
 return <><PageHeader eyebrow={meta[0]} title={meta[1]} actions={<Tag tone={data?'green':'neutral'}>{data?'Data available':'Limited data'}</Tag>}/>{!data?<EmptyState icon={Icon} title="Upload data to begin" body="There are no validated records for this business yet. BizIQ won’t invent figures or fill data gaps with assumptions." action={<Link className="btn primary" to={`/business/${business.id}/update-data`}><Upload size={15}/> Upload business data</Link>}/>:<><div className="notice-banner slim"><div className="notice-icon"><Info size={18}/></div><div><strong>Not calculated from your uploaded files.</strong><p>Analysis is not connected yet, so no results are shown for this page.</p></div></div><div className="stats-grid"><StatCard label="Records available" value={(state.uploads[business.id]||[]).length.toString()} detail="Files registered" icon={FileSpreadsheet}/><StatCard label="Validation status" value="Pending" detail="Schema checks not connected" icon={AlertCircle}/><StatCard label="Analysis status" value="Not run" detail="Awaiting validated data" icon={CircleDashed}/><StatCard label="Last updated" value={business.updated} detail="Latest data update" icon={Clock3}/></div></>}</>;
}

function Findings({state,business,setState}){
  const [expanded,setExpanded]=useState(0);
  const res=useLatestAnalysis(business,setState);
  const gate=analysisGate(business,res,'findings');
  const findings=res.analysis?.findings||[];
  const CAT={financial:'Financial',customer:'Customer',product:'Product',trend:'Trend',benchmark:'Benchmark',data_quality:'Data quality'};
  const SEV={info:'blue',warning:'amber',critical:'amber'};
  return <><PageHeader eyebrow="ANALYSIS OUTPUT" title="Findings" actions={<Button variant="secondary" onClick={()=>window.print()}><Download size={15}/> Export page</Button>}/>
  {gate||<>{isMockAnalysis(res.analysis)&&<SampleBanner/>}
  {findings.length===0?<EmptyState icon={FileSearch} title="No findings in this analysis" body="The analysis completed but did not report any findings for this business."/>:
  <div className="findings-list">{findings.map((f,i)=><article className="finding-card" key={f.finding_id}><button className="finding-head" onClick={()=>setExpanded(expanded===i?-1:i)}><div className="finding-number">{String(i+1).padStart(2,'0')}</div><div className="finding-title"><div><Tag>{CAT[f.category]||f.category}</Tag><Tag tone={SEV[f.severity]||'neutral'}>{f.severity}</Tag></div><h3>{f.title}</h3><p>{f.description}</p></div><ChevronDown className={expanded===i?'rotate':''} size={18}/></button>{expanded===i&&<div className="finding-detail"><div><span className="eyebrow">EVIDENCE</span>{f.evidence?.length?f.evidence.map((e,k)=><p key={k}>{e}</p>):<p>No evidence listed.</p>}</div>{f.metric_name&&<div><span className="eyebrow">METRIC</span><p>{f.metric_name}: {f.metric_value===null||f.metric_value===undefined?'Not available':f.metric_value}</p></div>}</div>}</article>)}</div>}</>}</>}

function Recommendations({state,setState,business}){
  const done=state.recs?.[business.id]||[];
  const setDone=fn=>setState(s=>({...s,recs:{...s.recs,[business.id]:fn(s.recs?.[business.id]||[])}}));
  const res=useLatestAnalysis(business,setState);
  const gate=analysisGate(business,res,'recommendations');
  const items=res.analysis?.recommendations||[];
  const PRI={high:'amber',medium:'blue',low:'neutral'};
  const doneCount=items.filter(x=>done.includes(x.recommendation_id)).length;
  return <><PageHeader eyebrow="ACTION PLAN" title="Recommendations" actions={<Button variant="secondary" onClick={()=>window.print()}><Download size={15}/> Export plan</Button>}/>
  {gate||<>{isMockAnalysis(res.analysis)&&<SampleBanner/>}
  {items.length===0?<EmptyState icon={Target} title="No recommendations in this analysis" body="The analysis completed but did not produce any recommendations for this business."/>:<>
  <div className="recommendation-summary"><div><span className="eyebrow">YOUR ACTION PLAN</span><h2>{doneCount} of {items.length} steps completed</h2><div className="progress-line"><span style={{width:`${doneCount/items.length*100}%`}}/></div></div><Tag tone={doneCount===items.length?'green':'neutral'}>{doneCount===items.length?'Complete':'In progress'}</Tag></div>
  <div className="recommendation-list">{items.map((x,i)=>{const isDone=done.includes(x.recommendation_id);return <article className={`recommendation-card ${isDone?'completed':''}`} key={x.recommendation_id}><button className="task-check" onClick={()=>setDone(s=>s.includes(x.recommendation_id)?s.filter(n=>n!==x.recommendation_id):[...s,x.recommendation_id])} aria-label="Mark recommendation complete">{isDone?<CheckCircle2 size={22}/>:<CircleDashed size={22}/>}</button><div className="recommendation-body"><div className="recommendation-meta"><span>STEP {String(i+1).padStart(2,'0')}</span><Tag tone={PRI[x.priority]||'neutral'}>{x.priority} priority</Tag>{x.kpi&&<span><Target size={13}/>{x.kpi}</span>}</div><h3>{x.title}</h3><p>{x.issue}</p><p><strong>Recommended action:</strong> {x.action}</p><div className="recommendation-why"><Sparkles size={15}/><span><strong>Why it matters</strong>{x.reason}</span></div>{x.evidence?.length>0&&<p className="small-text muted">Evidence: {x.evidence.join(' · ')}</p>}</div><Tag tone={isDone?'green':'neutral'}>{isDone?'Completed':'To do'}</Tag></article>;})}</div></>}</>}</>}

function Report({state,business,setState}){
  const [include,setInclude]=useState({overview:true,financial:true,customers:true,recommendations:true,limitations:true});
  const res=useLatestAnalysis(business,setState);
  const analysis=res.analysis;
  const ready=!!analysis&&analysis.status==='completed';
  const mock=isMockAnalysis(analysis);
  const m=analysis?.metrics||{};
  const na=v=>v===null||v===undefined?'Not available':v;
  const customerFindings=ready?analysis.findings.filter(f=>f.category==='customer'):[];
  const TITLE={overview:'Business overview',financial:'Financial analysis',customers:'Customer analysis',recommendations:'Recommendations',limitations:'Data limitations'};
  const NUM={overview:'01',financial:'02',customers:'03',recommendations:'04',limitations:'05'};
  const NOT_READY='Requires a completed analysis.';
  const previewText={
    overview:'Business profile and reporting context.',
    financial:ready?`Revenue ${currency(m.revenue)} · Expenses ${currency(m.expenses)} · Profit ${currency(m.profit)}`:NOT_READY,
    customers:ready?(customerFindings.length?`${customerFindings.length} customer finding(s).`:'No customer findings in this analysis.'):NOT_READY,
    recommendations:ready?`${analysis.recommendations.length} recommendation(s).`:NOT_READY,
    limitations:ready?(analysis.limitations.length?`${analysis.limitations.length} limitation(s) documented.`:'None listed.'):NOT_READY
  };
  const banner=!res.onServer?'This business is not saved on the server, so the report has no analysis results.':res.loading?'Loading the latest analysis…':res.error?res.error:!analysis?'No analysis has been run yet. Run one from the dashboard.':analysis.status==='failed'?'The latest analysis failed, so the report has no analysis results.':mock?'Sample output from the development engine — not calculated from your data.':null;
  function sectionRows(k){
    if(k==='overview')return [['Business overview','Business profile and reporting context']];
    if(!ready)return [[TITLE[k],'Not available — no completed analysis']];
    if(k==='financial')return [['Revenue',na(m.revenue)],['Expenses',na(m.expenses)],['Profit',na(m.profit)],['Profit margin (%)',na(m.profit_margin)]];
    if(k==='customers')return customerFindings.length?customerFindings.map(f=>['Customer finding',`${f.title}: ${f.description}`]):[['Customer analysis','No customer findings in this analysis']];
    if(k==='recommendations')return analysis.recommendations.length?analysis.recommendations.map(r=>[`Recommendation (${r.priority})`,`${r.title} — ${r.action}`]):[['Recommendations','None in this analysis']];
    return analysis.limitations.length?analysis.limitations.map(l=>['Limitation',l]):[['Limitations','None listed']];
  }
  function exportReport(){
    const rows=[['BizIQ Business Report',business.name],['Generated',new Date().toLocaleString()],['Industry',business.industry],['Location',business.location],['Data status',business.hasData?'Data available':'No data uploaded'],['Analysis method',analysis?.method_version||'Not available'],['Evidence level',analysis?.evidence_level||'Not available'],['Important note',banner||'Analysis results come from the BizIQ server.'],...Object.entries(include).filter(([k,v])=>v).flatMap(([k])=>sectionRows(k))];
    const csv=rows.map(r=>r.map(v=>`"${String(v).replace(/"/g,'""')}"`).join(',')).join('\n');
    const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));a.download=`${business.name.replace(/\s+/g,'-').toLowerCase()}-biziq-report.csv`;a.click();URL.revokeObjectURL(a.href);
  }
  return <><PageHeader eyebrow="REPORT BUILDER" title="Final report" actions={<Button onClick={exportReport}><Download size={15}/> Export report</Button>}/>{banner&&<div className="inline-message warn"><AlertCircle size={16}/> {banner}</div>}<div className="report-layout"><section className="panel report-options"><div className="panel-heading"><div><h3>Report sections</h3></div><FileText size={19} className="muted"/></div>{[['overview','Business overview','Profile, industry and reporting context'],['financial','Financial analysis','Revenue, costs and financial metrics'],['customers','Customer analysis','Segments, retention and behaviour'],['recommendations','Recommendations','Prioritised actions and rationale'],['limitations','Data limitations','Coverage, assumptions and caveats']].map(([k,t,d])=><label className="report-option" key={k}><input type="checkbox" checked={include[k]} onChange={e=>setInclude(s=>({...s,[k]:e.target.checked}))}/><span><strong>{t}</strong><small>{d}</small></span></label>)}<div className="report-bottom"><span/><Button onClick={exportReport}><Download size={15}/> Export CSV</Button></div></section><aside className="report-preview"><div className="preview-paper"><div className="preview-brand"><span className="brand-mark">b.</span><span>BizIQ</span><span className="preview-label">BUSINESS REPORT</span></div><div className="preview-rule"/><div className="eyebrow">BUSINESS INTELLIGENCE</div><h2>{business.name}</h2><p className="muted">{business.industry} · {business.location}</p><div className="preview-rule"/>{banner&&<div className="preview-warning"><AlertCircle size={16}/><span>{banner}</span></div>}{Object.entries(include).filter(([k,v])=>v).map(([k])=><div className="preview-section" key={k}><span>{NUM[k]}</span><div><strong>{TITLE[k]}</strong><p>{previewText[k]}</p></div></div>)}<div className="preview-rule"/><span className="preview-footer">Prepared with BizIQ · {new Date().toLocaleDateString('en-IN')}</span></div></aside></div></>;
}

function RoutePage({state,setState}){const {businessId,section}=useParams();const business=state.businesses.find(b=>b.id===businessId);useEffect(()=>{if(business&&state.selected!==business.id)setState(s=>({...s,selected:business.id}));},[business?.id]);if(!business)return <Navigate to="/businesses" replace/>;if(section==='dashboard')return <Dashboard key={business.id} state={state} setState={setState} business={business}/>;if(section==='profile')return <BusinessProfile key={business.id} state={state} setState={setState} business={business}/>;if(section==='update-data')return <UpdateData key={business.id} state={state} setState={setState} business={business}/>;if(section==='findings')return <Findings key={business.id} state={state} setState={setState} business={business}/>;if(section==='recommendations')return <Recommendations key={business.id} state={state} setState={setState} business={business}/>;if(section==='report')return <Report key={business.id} state={state} setState={setState} business={business}/>;const kind=section==='financial'?'financial':section==='customers'?'customers':section==='products'?'products':section==='trends'?'trends':section==='market'?'market':null;if(kind)return <AnalysisPage key={business.id} kind={kind} state={state} business={business}/>;return <Navigate to={`/business/${business.id}/dashboard`} replace/>;}

function App(){
  const [state,setState,auth]=useAppState();const navigate=useNavigate();const location=useLocation();
  useEffect(()=>{const authPage=location.pathname==='/login'||location.pathname==='/register';if(!state.user&&!authPage)navigate('/register',{replace:true});else if(state.user&&authPage)navigate('/businesses',{replace:true});},[state.user,location.pathname]);
  const guard=el=>state.user?el:<Navigate to="/register" replace/>;
  return <Routes><Route path="/register" element={<Register onRegister={auth.register}/>}/><Route path="/login" element={<Login onLogin={auth.login}/>}/><Route path="/businesses" element={guard(<Shell state={state} setState={setState}><Businesses state={state} setState={setState}/></Shell>)}/><Route path="/business/:businessId/:section" element={guard(<Shell state={state} setState={setState}><RoutePage state={state} setState={setState}/></Shell>)}/><Route path="/" element={<Navigate to={state.user?'/businesses':'/register'} replace/>}/><Route path="*" element={<Navigate to="/" replace/>}/></Routes>}
export default App;
