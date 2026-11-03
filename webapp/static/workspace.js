'use strict';
// Operational decisions use published evidence. Review notes never alter Sales.
let deskData,deskPending,deskWeekChoice,deskFilter='all',deskQuery='',selectedDeskTask;
const deskHome=document.querySelector('[data-view="home"]');
Array.from(deskHome.children).forEach(n=>n.hidden=true);
const deskRoot=el('div',undefined,'operations-desk');deskHome.prepend(deskRoot);
const previousToolsLoader=window.loadWorkspaceTools;
async function deskLoad(force=false){
 if(force)deskData=null;
 if(deskData)return deskData;
 if(!deskPending)deskPending=api('/api/workspace'+(deskWeekChoice?'?week='+deskWeekChoice:'')).then(r=>deskData=r).finally(()=>deskPending=null);
 return deskPending;
}
const deskDay=v=>v?new Date(v+'T12:00:00+08:00').toLocaleDateString('en-MY',{day:'numeric',month:'short'}):'No date';
const deskDecimal=v=>v==null?'-':new Intl.NumberFormat('en-MY',{maximumFractionDigits:1}).format(v);
function deskButton(text,fn,cls='secondary'){const b=el('button',text,cls);b.type='button';b.addEventListener('click',fn);return b;}
function deskLink(text,href,cls='secondary'){const a=el('a',text,cls);a.href=href;return a;}
function deskStatus(s){return {open:'To review',reviewed:'Reviewed',waiting:'Waiting',contacted:'Contact logged'}[s]||'To review';}
function deskWeek(r){return deskDay(r.week_start)+' – '+deskDay(r.week_end);}
function deskPanel(title,sub){const p=el('article',undefined,'desk-panel');const h=el('div',undefined,'desk-panel-head');h.append(el('h2',title));if(sub)h.append(el('span',sub,'desk-muted'));p.append(h);return p;}
function deskHeader(title,subtitle,button){const h=el('div',undefined,'desk-page-head'),left=el('div');left.append(el('h1',title),el('p',subtitle));h.append(left);if(button)h.append(button);return h;}
function deskMetric(title,value,detail,cls){const m=el('div',undefined,'desk-metric '+(cls||''));m.append(el('span',title),el('strong',value),el('small',detail));return m;}
function deskError(target,error){target.replaceChildren(el('p',error.message||String(error),'desk-error'));}
function renderDesk(r){
 const refresh=deskButton('Refresh workspace ↻',async()=>{refresh.disabled=true;try{const v=await deskLoad(true);renderDesk(v);}catch(e){deskError(deskRoot,e);}finally{refresh.disabled=false;}});
 refresh.textContent='Refresh';
 const actions=el('div',undefined,'desk-header-actions');actions.append(refresh,deskLink('Book a visit','#plan','secondary'));
 deskRoot.replaceChildren(deskHeader('Customer follow-up','',actions));
 const source=el('div',undefined,'desk-source');source.append(el('span',r.source_stale?'Published records need refreshing':'Published source records','desk-dot '+(r.source_stale?'amber':'')),el('span',r.source_updated?new Date(r.source_updated).toLocaleString('en-MY',{timeZone:'Asia/Kuala_Lumpur',dateStyle:'medium',timeStyle:'short'})+' MYT':'Freshness unavailable'));deskRoot.append(source);
 if(!r.log_available)deskRoot.append(el('p','Shared progress is temporarily unavailable. You can still inspect source records.','desk-error'));
 const layout=el('div',undefined,'desk-crm-layout'),rail=el('nav',undefined,'desk-queue-nav');rail.setAttribute('aria-label','Follow-up views');
 const views=[['all','All records',r.counts.total,'Every follow-up record'],['upcoming','Due in 7 days',r.counts.upcoming,'Check the balance before contacting'],['details','Needs checking',r.counts.missing+r.counts.unknown+r.counts.status,'Missing dates, amounts or contract details'],['reviewed','Team progress',r.counts.reviewed,'Reviewed, waiting or contact logged']];
 views.forEach(([key,label,count,detail])=>{const b=deskButton('',()=>{deskFilter=key;renderDesk(r);},'desk-queue-option'+(deskFilter===key?' active':''));b.setAttribute('aria-pressed',String(deskFilter===key));const title=el('span',label);title.append(el('strong',number(count)));b.title=detail;b.append(title);rail.append(b);});
 const inbox=el('article',undefined,'desk-queue-panel');
 const controls=el('div',undefined,'desk-inbox-controls');
 const search=el('input');search.type='search';search.placeholder='Search customer or sale ID';search.setAttribute('aria-label','Find a follow-up');search.value=deskQuery;search.addEventListener('input',()=>{deskQuery=search.value;renderDeskTasks(r,list);});const links=el('div',undefined,'desk-list-links');links.append(deskLink('Payment overview','#payments','desk-text-link'),deskLink('Customer history','#customers','desk-text-link'));controls.append(search,links);inbox.append(controls);
 const list=el('div',undefined,'desk-task-list');inbox.append(list);renderDeskTasks(r,list);
 const note=el('p','Review status is a staff record. It does not change payment balances or send a message.','desk-footnote');
 inbox.append(note);
 layout.append(rail,inbox);deskRoot.append(layout);

}
function renderDeskTasks(r,list){
 const rows=r.tasks.filter(t=>{
  if(deskFilter==='upcoming'&&(t.review_kind!=='upcoming'||t.status!=='open'))return false;
  if(deskFilter==='details'&&(t.review_kind==='upcoming'||t.status!=='open'))return false;
  if(deskFilter==='reviewed'&&t.status==='open')return false;
  return (t.name+' '+t.sales_record_id).toLowerCase().includes(deskQuery.toLowerCase());
 });list.replaceChildren();
 if(!rows.length){const blank=el('div',undefined,'desk-empty');blank.append(el('strong','Nothing in this view'),el('p','Try “Needs checking” or “All records” to inspect the other records.'),deskButton('Show all records',()=>{deskFilter='all';deskQuery='';renderDesk(r);}));list.append(blank);return;}
 const table=el('table',undefined,'desk-records'),thead=el('thead'),heading=el('tr');
 table.setAttribute('aria-label','Customer payment follow-ups');
 ['Customer','Check','Reminder','Contract balance','Progress',''].forEach(title=>{const th=el('th',title);th.scope='col';heading.append(th);});thead.append(heading);table.append(thead);
 const body=el('tbody');
 rows.slice(0,40).forEach(t=>{
  const row=el('tr',undefined,'desk-task'),customer=el('td'),name=deskButton(t.name,()=>openDeskTask(t,r),'desk-record-name');
  const identity=el('div',undefined,'desk-customer-identity'),text=el('div');const initials=el('span',(t.name.replace(/\(.*?\)/g,' ').match(/[A-Za-z][A-Za-z]*/g)||['?']).slice(0,2).map(v=>v[0]).join('').toUpperCase(),'desk-avatar');initials.setAttribute('aria-hidden','true');text.append(name,el('span',t.sales_record_id||'Sale not linked','desk-sale-id'));identity.append(initials,text);customer.append(identity);
  const reason=el('td'),kind=t.source_changed?'Changed record':({upcoming:'Reminder',missing:'Missing date',unknown:'Check amount',status:'Check contract'}[t.review_kind]||'Review details');
  const badge=el('span',kind,'desk-reason '+t.review_kind);badge.title=t.source_changed?'Source facts changed; review again':t.review_reason;reason.append(badge);
  const date=el('td',t.next_scheduled_reminder_date?deskDay(t.next_scheduled_reminder_date):'Not recorded','desk-record-date');
  const balance=el('td',t.sales_remaining_balance_rm==null?'Not recorded':money(t.sales_remaining_balance_rm),'desk-record-money');balance.title='Recorded remaining contract balance, not an individual instalment due';
  const progress=el('td');progress.append(el('span',deskStatus(t.status),'desk-status '+t.status));
  const action=el('td');action.append(deskButton('Review',()=>openDeskTask(t,r),'desk-review-button'));
  row.append(customer,reason,date,balance,progress,action);body.append(row);
 });table.append(body);list.append(table);list.append(el('p','Showing '+Math.min(rows.length,40)+' of '+number(rows.length)+' records','desk-list-count'));if(rows.length>40)list.append(el('p',number(rows.length)+' matching records. Search by customer or sale to narrow the list.','desk-footnote'));
}
let deskDrawer;
function closeDeskDrawer(){if(deskDrawer){deskDrawer.remove();deskDrawer=null;document.body.classList.remove('desk-drawer-open');}}
function openDeskTask(t,r){
 closeDeskDrawer();selectedDeskTask=t;
 deskDrawer=el('div',undefined,'desk-drawer-shell');const shade=deskButton('Close review',closeDeskDrawer,'desk-drawer-shade');shade.setAttribute('aria-label','Close review');
 const panel=el('section',undefined,'desk-drawer');panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');panel.setAttribute('aria-label','Review '+t.name);
 const top=el('div',undefined,'desk-drawer-top');top.append(el('span','CUSTOMER FOLLOW-UP','desk-eyebrow'),deskButton('Close ×',closeDeskDrawer,'quiet'));panel.append(top,el('h2',t.name),el('p',t.sales_record_id+', '+t.review_reason,'desk-muted'));
 const facts=el('div',undefined,'desk-drawer-facts');facts.append(deskMetric('Recorded paid',money(t.sales_total_recorded_paid_rm),'Sales source'),deskMetric('Contract balance',money(t.sales_remaining_balance_rm),'Not an instalment due amount'),deskMetric('Reminder date',deskDay(t.next_scheduled_reminder_date),'Staff reminder schedule'));panel.append(facts);
 const steps=el('ol',undefined,'desk-review-steps');[['Verify the record','Check the current Sales balance and agreed payment schedule.'],['Prepare a message','Edit the draft below. Send it through your normal channel only after checking the record.'],['Record the next step','Save a review status and note for the team.']].forEach(([h,p])=>{const li=el('li');li.append(el('strong',h),el('p',p));steps.append(li);});panel.append(steps);
 const checklist=el('details',undefined,'desk-checklist');checklist.append(el('summary','Review checklist'),steps);panel.append(checklist);
 const history=deskButton('Open full customer history',()=>{closeDeskDrawer();openReviewCustomer(t);},'desk-text-link');panel.append(history);
 const label=el('label','Message draft','desk-field'),draft=el('textarea');draft.value=t.draft??'Confirm the cancellation or relocation note in the source before preparing a payment reminder.';draft.disabled=t.draft===null;draft.rows=4;draft.setAttribute('aria-label','Message draft');label.append(draft);panel.append(label);
 const copyStatus=el('span',undefined,'desk-muted'),copy=deskButton('Copy draft',async()=>{try{await navigator.clipboard.writeText(draft.value);copyStatus.textContent='Copied. Nothing was sent.';}catch{copyStatus.textContent='Select and copy the text manually.';}});copy.disabled=t.draft===null;const copyRow=el('div',undefined,'desk-inline');copyRow.append(copy,copyStatus);panel.append(copyRow);
 const form=el('form',undefined,'desk-review-form'),statusLabel=el('label','Progress','desk-field'),status=el('select');status.setAttribute('aria-label','Review progress');[['open','To review'],['reviewed','Record checked'],['waiting','Waiting for an update'],['contacted','Contact logged by staff']].forEach(([v,text])=>{const o=el('option',text);o.value=v;status.append(o);});status.value=t.status;statusLabel.append(status);
 const noteLabel=el('label','Team note','desk-field'),note=el('textarea');note.rows=2;note.maxLength=400;note.value=t.note||'';note.setAttribute('aria-label','Team note');noteLabel.append(note);const save=el('button','Save progress','primary');save.disabled=!r.log_available;const outcome=el('p',undefined,'desk-save-status');outcome.setAttribute('role','status');form.append(statusLabel,noteLabel,save,outcome);
 form.addEventListener('submit',async e=>{e.preventDefault();save.disabled=true;try{await jsonPost('/api/workspace/actions',{id:t.id,evidence_hash:t.evidence_hash,status:status.value,note:note.value,revision:r.action_revision});const fresh=await deskLoad(true);renderDesk(fresh);outcome.textContent='Saved for the team. Source records are unchanged.';save.textContent='Saved ✓';save.disabled=true;}catch(err){outcome.textContent=err.message;save.disabled=false;}});panel.append(form,el('p','Source: '+r.release+', '+(r.source_updated?new Date(r.source_updated).toLocaleString('en-MY',{timeZone:'Asia/Kuala_Lumpur'}):'Freshness unavailable'),'desk-footnote'));
 deskDrawer.append(shade,panel);document.body.append(deskDrawer);document.body.classList.add('desk-drawer-open');panel.querySelector('button').focus();
}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDeskDrawer();if(e.key==='Tab'&&deskDrawer){const nodes=Array.from(deskDrawer.querySelector('.desk-drawer').querySelectorAll('button,input,select,textarea,a[href]')).filter(n=>!n.disabled);const first=nodes[0],last=nodes[nodes.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
function renderPlanDecision(target,r,capacity=r.settings.capacity_hours,buffer=r.settings.buffer_hours){
 target.replaceChildren();target.className='plan-decision';
 const f=r.current_forecasts.find(v=>v.id==='booked_hours_h1');
 const cap=capacity==null||capacity===''?null:Number(capacity),extra=Number(buffer||0);
 let title=r.plan_summary.title,action=r.plan_summary.action,status=r.plan_summary.status;
 const valid=cap!==null&&Number.isFinite(cap)&&cap>=0&&cap<=2000&&Number.isFinite(extra)&&extra>=0&&extra<=500;
 if(f&&!r.source_stale&&valid){const gap=Number(f.prediction)+extra-cap;status=gap>0?'shortfall':'within_plan';title=gap>0?'Review '+deskDecimal(gap)+' more appointment hours':deskDecimal(-gap)+' hours remain in this scenario';action=gap>0?'Check whether the teams can offer more appointment slots or adjust new bookings. Confirm changes with the team.':'Keep the remaining hours available for changes. This comparison does not require additional staffing.';}
 else if(f&&!r.source_stale){status='enter_capacity';title='Compare demand with your available hours';action='Enter the full-week appointment hours the teams can offer. Booking counts alone cannot establish spare capacity.';}
 const content=el('div',undefined,'plan-decision-copy');content.append(el('span','Next decision','desk-eyebrow'),el('h2',title),el('p',action));
 if(capacity!==r.settings.capacity_hours||buffer!==r.settings.buffer_hours)content.append(el('small','Unsaved scenario, save below to share it with the team.','desk-footnote'));
 const facts=el('div',undefined,'plan-decision-facts');facts.append(deskMetric('Expected hours',f?deskDecimal(f.prediction):'Not issued','Full selected week'),deskMetric('Available hours',valid?deskDecimal(cap):'Enter below','Staff assumption'));
 target.dataset.status=status;target.append(content,facts);
 if(f&&valid&&!r.source_stale){const chart=el('div',undefined,'plan-hour-comparison'),max=Math.max(Number(f.prediction)+extra,cap,1);[['Expected + buffer',Number(f.prediction)+extra,'demand'],['Available hours',cap,'capacity']].forEach(([name,value,cls])=>{const row=el('div',undefined,'plan-hour-row');row.append(el('span',name));const track=el('div',undefined,'plan-hour-track'),fill=el('div',undefined,cls);fill.style.width=(value/max*100)+'%';track.append(fill);row.append(track,el('strong',deskDecimal(value)+' h'));chart.append(row);});chart.setAttribute('role','img');chart.setAttribute('aria-label','Expected appointment hours plus staff buffer '+deskDecimal(Number(f.prediction)+extra)+'; staff available hours '+deskDecimal(cap));target.append(chart);}
}
function renderWeekPlan(r){
 const root=$('week-planner');root.replaceChildren(deskHeader('Plan','Find a booking option or review weekly demand.',deskButton('Refresh',async()=>renderWeekPlan(await deskLoad(true)))));
 const ribbon=el('div',undefined,'desk-plan-ribbon');const weekPicker=el('select');weekPicker.setAttribute('aria-label','Planning week');r.week_options.forEach(w=>{const o=el('option',w.label+', '+deskDay(w.start));o.value=w.start;weekPicker.append(o);});weekPicker.value=r.week_start;weekPicker.addEventListener('change',async()=>{deskWeekChoice=weekPicker.value;renderWeekPlan(await deskLoad(true));});ribbon.append(weekPicker,el('strong',deskWeek(r)),el('span','Whole-week planning, Malaysia time'));root.append(ribbon);
 const decision=el('article');renderPlanDecision(decision,r);root.append(decision);
 const grid=el('div',undefined,'desk-planner-grid'),main=el('div'),side=el('div');
 const schedule=deskPanel('Upcoming bookings in this week',r.schedule.available?number(r.schedule.bookings)+' appointments':'Feed unavailable');
 if(!r.schedule.available)schedule.append(el('p','The advance-booking feed has not been delivered. No count has been substituted.','desk-error'));
 else{const heat=el('table',undefined,'desk-heatmap'),thead=el('thead'),hr=el('tr');hr.append(el('th','Team'));const days=Array.from({length:7},(_,i)=>{const d=new Date(r.week_start+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+i);return d.toISOString().slice(0,10);});days.forEach(d=>{const th=el('th');th.append(el('span',new Date(d+'T12:00:00Z').toLocaleDateString('en-MY',{weekday:'short'})),el('small',deskDay(d)));hr.append(th);});thead.append(hr);heat.append(thead);const body=el('tbody'),teams=[...new Set(r.schedule.rows.map(v=>v.calendar_name))].sort();
  if(!teams.length)schedule.append(el('p','No upcoming bookings remain in this week’s advance-calendar snapshot.','desk-muted'));
  const max=Math.max(1,...r.schedule.rows.map(v=>v.scheduled_event_rows));teams.forEach(team=>{const tr=el('tr');tr.append(el('th',team.replace(/TEAM\s*/i,'')));days.forEach(day=>{const count=r.schedule.rows.filter(v=>v.calendar_name===team&&v.service_date===day).reduce((a,v)=>a+v.scheduled_event_rows,0),td=el('td');const cell=el('span',String(count));cell.style.background=count?'rgba(29,78,216,'+(0.1+0.7*count/max)+')':'#f5f5f5';cell.style.color=count/max>.55?'white':'#262626';cell.title=team+', '+day+', '+count+' bookings';td.append(cell);tr.append(td);});body.append(tr);});heat.append(body);const wrap=el('div',undefined,'desk-heatmap-wrap');wrap.append(heat);schedule.append(wrap,el('p','Calendar covers '+deskDay(r.schedule.coverage_start)+' onward. Colour shows bookings, not free slots or completed treatments.','desk-footnote'));}
 const daySummary=el('div',undefined,'plan-day-summary');if(r.plan_summary.busiest_days.length){daySummary.append(el('strong','Most booked upcoming days'));r.plan_summary.busiest_days.forEach(d=>daySummary.append(el('span',deskDay(d.date)+', '+number(d.bookings)+' bookings')));daySummary.append(el('small','Review appointment details before changing the roster. Counts do not establish workload or free time.'));}schedule.append(daySummary);
 main.append(schedule);
 const forecast=deskPanel('Demand forecast','Experimental, saved before the week');const cards=el('div',undefined,'desk-demand-grid');
 for(const model of r.planning.evidence.models){const current=r.current_forecasts.find(v=>v.id===model.id),card=el('div',undefined,'desk-demand-card');card.append(el('span',String(model.title).replace(/\s*\u00b7\s*/g,', '),'desk-muted'));
  if(current)card.append(el('strong',deskDecimal(current.prediction)+' '+model.unit),el('p',deskDecimal(current.already_booked)+' already booked when issued'));
  else {const before=r.week_start<r.planning.evidence.first_origin,started=r.week_start<=r.today;card.append(el('strong',before?'Before this test':started?'No verified forecast':'Not issued yet','desk-pending'),el('p',before?'This weekly test starts '+deskDay(r.planning.evidence.first_origin)+'.':started?'No matched timely forecast is available for this week. Check the collection evidence.':'Published Sundays at 11:50 pm for the coming week.'));}
  const evidence=el('details');evidence.append(el('summary','Check historical evidence'));evidence.append(el('p',model.test_windows+' windows, average error '+model.mae.toFixed(1)+' '+model.unit+' vs '+model.baseline_mae.toFixed(1)+' for the simple baseline.','desk-footnote'));forecastTrend(evidence,model.history,model.title+' historical comparison');card.append(evidence);cards.append(card);
 }forecast.append(cards,el('p','The booking estimate covers two weeks; the hours estimate covers one. Team/day forecasts are not available.','desk-footnote'));main.append(forecast);
 const capacity=deskPanel('Set the working plan','Staff assumptions');const form=el('form',undefined,'desk-capacity-form');const input=el('input');input.type='number';input.min=0;input.max=2000;input.step='.5';input.required=true;input.value=r.settings.capacity_hours??'';input.placeholder='Enter available slot hours';input.setAttribute('aria-label','Available appointment hours');const label=el('label','Total appointment hours available for this week','desk-field');label.append(input,el('small','Use the full-week slot budget across teams, including earlier days. This is not employee working hours.'));
 const buffer=el('input');buffer.type='number';buffer.min=0;buffer.max=500;buffer.step='.5';buffer.value=r.settings.buffer_hours??0;buffer.setAttribute('aria-label','Planning buffer hours');const bl=el('label','Extra buffer, hours','desk-field');bl.append(buffer,el('small','Your allowance for changes. It is not a statistical confidence interval.'));const save=el('button','Save the weekly plan','primary');save.disabled=!r.log_available;const output=el('div',undefined,'desk-capacity-output');output.setAttribute('role','status');form.append(label,bl,save,output);
 function compare(){renderPlanDecision(decision,r,input.value===''?null:Number(input.value),Number(buffer.value));output.replaceChildren();if(input.value==='')return;if(!input.checkValidity()||!buffer.checkValidity()){output.append(el('p','Check the available-hours and buffer values.','desk-error'));return;}output.append(el('p','The comparison above uses your entries. Save to share this scenario with the team.','desk-muted'));}
 input.addEventListener('input',compare);buffer.addEventListener('input',compare);compare();form.addEventListener('submit',async e=>{e.preventDefault();save.disabled=true;try{await jsonPost('/api/workspace/actions',{kind:'capacity',week:r.week_start,capacity_hours:Number(input.value),buffer_hours:Number(buffer.value),revision:r.action_revision});const fresh=await deskLoad(true);renderWeekPlan(fresh);$('week-planner').querySelector('.desk-capacity-output').append(el('p','Plan saved for the team.','desk-success'));}catch(err){output.append(el('p',err.message,'desk-error'));save.disabled=false;}});capacity.append(form);side.append(capacity);
 grid.append(main,side);root.append(grid,deskLink('Inspect all model evidence','#status','desk-text-link'));
 if(window.attachBookingTools)attachBookingTools(root);
}
window.loadWorkspaceTools=async page=>{try{if(page==='home'){renderDesk(await deskLoad());return;}if(page==='plan'){renderWeekPlan(await deskLoad());return;}await previousToolsLoader(page);}catch(e){deskError(page==='plan'?$('week-planner'):deskRoot,e);}};
if(state&&location.hash==='#home')window.loadWorkspaceTools('home');

window.addEventListener('hashchange',()=>{closeDeskDrawer();window.scrollTo({top:0,behavior:'instant'});});
