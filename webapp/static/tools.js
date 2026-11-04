'use strict';
let planningData,planningPending,paymentData;
let queueView='all';
const customerForm=$('customer-search');
if(customerForm){const article=customerForm.closest('article');$('customer-history-slot').append(article);}
// Keep experimental targeting away from the everyday customer lookup.
const repeatPanel=$('repeat-list').closest('article');
const repeatDetails=el('details',undefined,'panel research-details');repeatDetails.append(el('summary','Experimental repeat-purchase list'));
repeatPanel.classList.remove('panel');repeatDetails.append(repeatPanel);document.querySelector('[data-view="status"]').append(repeatDetails);
const businessFirst=$('business-filter')?.closest('.panel');if(businessFirst)businessFirst.hidden=true;
const systemDetails=el('details',undefined,'panel research-details');systemDetails.append(el('summary','System status'),$('system-cards'));document.querySelector('[data-view="status"]').append(systemDetails);
// Keep the custom-area date controls visible without duplicating Looker charts.
const areaForm=$('business-radius');if(areaForm)areaForm.before($('business-filter'));
function paymentAction(value){return value==='USE_SOURCE_REMINDER_DATES_AND_SALES_CUMULATIVE_PAID; DELIVERY_STATUS_UNKNOWN'?'Check Sales updates before sending a reminder':'Review the source record';}
function knownTotal(rows,key){const values=rows.map(r=>r[key]).filter(v=>v!==null&&v!==undefined);return values.length?values.reduce((a,v)=>a+Number(v),0):null;}
function tooltipText(target,label,text){target.replaceChildren(el('span',label),help('About '+label,text));}
async function planning(){
 if(planningData)return planningData;
 if(!planningPending)planningPending=api('/api/planning').then(r=>{planningData=r;return r;}).finally(()=>planningPending=null);
 return planningPending;
}
function showPlanning(r){
 renderModelVisuals(r);
 const p=r.repeat_purchase;
 tooltipText($('repeat-evidence'),'Historical test: 13 of 19 repeat buyers found in 112 reviews', '557 customers tested; 99 flagged customers did not buy again within 90 days. Only 19 positive cases; no reliable purchase probability or guaranteed outcome.');
 table('repeat-list',p.customers,[['Priority','rank',number,true],['Customer','name'],['First recorded purchase','first_recorded_purchase',date],['Days since purchase','days_since_purchase',number,true],['Initial sales','initial_sales_rm',money,true]]);
 tooltipText($('repeat-notice'),number(p.eligible_customers)+' eligible customers, top 50 shown',p.notice+' Current source release: '+r.receipt.published_release+'.');
 const m=state.model.new_retrospective_test||{};
 table('model-evidence',[
 {measure:'Held-out services',value:number(m.services)},
 {measure:'Actual pest-related returns',value:number(m.callback_positive_service_windows)},
 {measure:'Fixed-threshold accuracy',value:percent(m.threshold_accuracy)},
 {measure:'Always-no-return baseline',value:percent(m.always_no_callback_accuracy)},
 {measure:'Recovery test, outcome review',value:state.model.recovery_earliest_final_evaluation?date(state.model.recovery_earliest_final_evaluation):'Date not available'}],
 [['Historical evidence','measure'],['Result','value']]);
}
async function paymentFollowup(){
 if(!paymentData)paymentData=await api('/api/payment-followup');
 const todayMY=new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Kuala_Lumpur'}),end=new Date(todayMY+'T12:00:00Z');end.setUTCDate(end.getUTCDate()+6);const endDay=end.toISOString().slice(0,10);
 let rows=paymentData.contracts;const view=$('payment-queue').value;
 if(view==='upcoming')rows=rows.filter(r=>r.next_scheduled_reminder_date&&r.next_scheduled_reminder_date>=todayMY&&r.next_scheduled_reminder_date<=endDay&&Number(r.sales_remaining_balance_rm)>0);
 if(view==='missing')rows=rows.filter(r=>!r.next_scheduled_reminder_date&&Number(r.sales_remaining_balance_rm)>0);
 if(view==='balance')rows=rows.filter(r=>Number(r.sales_remaining_balance_rm)>0);
 if(view==='unknown')rows=rows.filter(r=>r.sales_remaining_balance_rm==null||!Number.isFinite(Number(r.sales_remaining_balance_rm)));
 const unknownPaid=rows.filter(r=>r.sales_total_recorded_paid_rm===null||r.sales_total_recorded_paid_rm===undefined).length;
 const unknownBalance=rows.filter(r=>r.sales_remaining_balance_rm===null||r.sales_remaining_balance_rm===undefined).length;
 kpis('payment-totals',[['Matching contracts',number(rows.length)],['Recorded paid',money(knownTotal(rows,'sales_total_recorded_paid_rm')),unknownPaid?number(unknownPaid)+' amounts unknown':undefined],['Remaining balance',money(knownTotal(rows.map(r=>({...r,sales_remaining_balance_rm:r.sales_remaining_balance_rm==null?null:Math.max(0,Number(r.sales_remaining_balance_rm))})),'sales_remaining_balance_rm')),unknownBalance?number(unknownBalance)+' balances unknown':undefined]]);
 table('payment-contracts',rows,[['Customer','name'],['Sale','sales_record_id'],['Next reminder','next_scheduled_reminder_date',v=>v?date(v):'No source date'],['Recorded paid','sales_total_recorded_paid_rm',money,true],['Remaining','sales_remaining_balance_rm',money,true],['Follow-up','next_action',paymentAction]]);
 addCustomerActions('payment-contracts',rows);
 tooltipText($('payment-notice'),'Staff reminder schedule, '+paymentData.receipt.published_release.replace('cp2r_',''),paymentData.notice+' Actual instalment payment dates and sent-message status are not available.');
}
window.loadWorkspaceTools=async page=>{try{
 if(page==='home')await renderWorkQueue();
 if(page==='customers'){const mappedSale=sessionStorage.getItem('cp2_map_sale');if(mappedSale){$('customer-search').elements.q.value=mappedSale;sessionStorage.removeItem('cp2_map_sale');}loadCustomers();}
 if(page==='status')showPlanning(await planning());
 if(page==='payments')await paymentFollowup();
}catch(e){const target=page==='home'?'work-queue':page==='payments'?'payment-notice':page==='customers'?'customer-summary':'forecast-notice';$(target).textContent=e.message;}};
$('payment-queue').addEventListener('change',()=>paymentFollowup().catch(e=>$('payment-notice').textContent=e.message));
function openReviewCustomer(row){sessionStorage.setItem('cp2_map_sale',row.sales_record_id||row.name);location.hash='customers';}
function addCustomerActions(id,rows){
 const t=$(id).querySelector('table');if(!t)return;
 t.querySelector('thead tr').append(el('th','Action'));
 t.querySelectorAll('tbody tr').forEach((tr,i)=>{const cell=el('td'),button=el('button','Open customer','secondary');button.type='button';button.addEventListener('click',()=>openReviewCustomer(rows[i]));cell.append(button);tr.append(cell);});
}
async function renderWorkQueue(){
 if(!paymentData)paymentData=await api('/api/payment-followup');
 const q=paymentData.review_queue;if(!q)throw new Error('Review queue unavailable. Open Payment follow-up to inspect source records.');
 kpis('work-queue-counts',[['Reminders, next 7 days',number(q.counts.upcoming)],['Missing reminder dates',number(q.counts.missing)],['Unknown balances',number(q.counts.unknown)]]);
 const matching=q.tasks.filter(r=>queueView==='all'||r.review_kind===queueView),rows=matching.slice(0,15);
 document.querySelectorAll('[data-review]').forEach(b=>{b.classList.toggle('active',b.dataset.review===queueView);b.setAttribute('aria-pressed',String(b.dataset.review===queueView));});
 if(rows.length){table('work-queue',rows,[['Customer','name'],['Why review','review_reason'],['Reminder','next_scheduled_reminder_date',v=>v?date(v):'Confirm date'],['Recorded balance','sales_remaining_balance_rm',money,true],['Next step','review_action']]);addCustomerActions('work-queue',rows);}
 else empty($('work-queue'),'No matching review items in the published records.');
 $('work-queue-notice').replaceChildren(el('span',number(matching.length)+' matching items, first 15 shown, as of '+date(q.as_of)),help('About this review queue',q.notice+' Source release: '+paymentData.receipt.published_release));
}
document.querySelectorAll('[data-review]').forEach(button=>button.addEventListener('click',()=>{queueView=button.dataset.review;renderWorkQueue().catch(e=>$('work-queue').textContent=e.message);}));

const spatialLink=document.createElement('a');spatialLink.href='/maps';spatialLink.className='btn btn-ghost btn-sm';spatialLink.textContent='Open heatmaps';$('business-radius').closest('article')?.querySelector('.panel-head')?.append(spatialLink);


// Source-backed aggregate visuals; no customer-level scores or synthetic forecasts.
function modelChartPanel(id,title,before){
 let target=$(id);if(target)return target;
 const article=el('article',null,'panel');
 article.append(el('h2',title));target=el('div');target.id=id;article.append(target);
 before.before(article);return target;
}
function modelBars(target,rows,description){
 target.replaceChildren(el('p',description));
 const svg=svgNode('svg',{viewBox:'0 0 860 '+(rows.length*40+20),role:'img','aria-label':description,class:'model-bars'});
 const max=Math.max(1,...rows.map(r=>r.value));
 rows.forEach((r,i)=>{
  const y=6+i*40;
  svg.append(svgNode('text',{x:0,y:y+17,fill:'#262626','font-size':16},r.label));
  svg.append(svgNode('rect',{x:275,y:y+4,width:500*r.value/max,height:16,rx:4,fill:r.color}));
  svg.append(svgNode('text',{x:285+500*r.value/max,y:y+16,fill:'#0a0a0a','font-size':16,'font-weight':600},number(r.value)));
 });
 target.append(svg);
}
function renderModelVisuals(r){
 const anchor=$('model-evidence').closest('article');
 anchor.hidden=true;
 const oldForecast=$('forecast-history').closest('article');oldForecast.hidden=true;
 let nav=$('model-navigation');if(!nav){nav=el('nav',undefined,'model-navigation');nav.id='model-navigation';nav.setAttribute('aria-label','Prediction models');
 [['booking-chart','Planning forecasts'],['return-chart','Pest-return experiment']].forEach(([id,label])=>{const a=el('a',label);a.href='#'+id;a.addEventListener('click',e=>{e.preventDefault();$(id).closest('article').scrollIntoView({behavior:'instant',block:'start'});});nav.append(a);});oldForecast.before(nav);}
 const bookings=modelChartPanel('booking-chart','Plan the coming weeks',anchor);
 renderPlanningForecasts(bookings,r.planning);
 const returns=modelChartPanel('return-chart','Pest-return model, experimental',anchor);
 const e=r.return_evidence;
 if(e){
 modelBars(returns,[{label:'Actual returns, found',value:e.threshold_TP,color:'#1d4ed8'},
 {label:'Actual returns, missed',value:e.threshold_FN,color:'#0a0a0a'},
 {label:'Predicted returns, false alerts',value:e.threshold_FP,color:'#a3a3a3'}],
 'Will a paid service have a recorded pest-related return within 30 days? Earlier test: '+e.rows+' services, '+e.positive_rows+' actual returns.');
 returns.append(el('p',e.notice+' Only five return cases; 94% accuracy versus 95% for always predicting no return.'));
 modelFacts(returns,'Frozen 30-day model, Extra Trees',[
 ['Tested',number(e.rows)+' services'],['Actual returns',number(e.positive_rows)],['Accuracy','94.0%'],['No-return baseline','95.0%'],['Returns detected','40.0%'],['Alerts correct','40.0%']]);
 }else returns.replaceChildren(el('p','Historical outcome evidence is unavailable.'));
 const research=modelChartPanel('research-chart','Earlier 60-day return study',anchor),b=r.research_best?.candidate;
 if(b){modelBars(research,[{label:'Returns detected',value:b.TP,color:'#1d4ed8'},{label:'Returns missed',value:b.FN,color:'#0a0a0a'},{label:'False alerts',value:b.FP,color:'#a3a3a3'}],
 'Will a residential programme have a recorded pest return within 60 days after its final paid service?');
 modelFacts(research,'Research candidate, logistic regression',[
 ['Tested',number(b.services)+' programmes'],['Actual returns',number(b.positive_windows)],['Accuracy',percent(b.pooled_accuracy)],['No-return baseline',percent(b.always_no_return_accuracy)],['Returns detected',percent(b.pooled_recall)],['Alerts correct',percent(b.pooled_precision)],['F1 score',b.pooled_f1.toFixed(3)],['Time folds',number(b.folds)]]);
 research.append(el('p','Highest F1 in the inspected historical search; selected after comparing results. Different target and population from the 30-day test. Research only: not running live predictions and not a replacement for the frozen future test.','notice'));
 }else research.replaceChildren(el('p','Research evidence unavailable.'));
 const repeat=modelChartPanel('repeat-chart','Repeat purchases: ranking results',anchor);
 const p=r.repeat_purchase.evaluation;
 if(p){modelBars(repeat,[{label:'Actual repeat buyers, found',value:p.cases_in_review_list,color:'#1d4ed8'},
 {label:'Actual repeat buyers, missed',value:p.positive_customers-p.cases_in_review_list,color:'#0a0a0a'},
 {label:'Listed customers, did not repeat',value:p.false_alerts_in_review_list,color:'#a3a3a3'}],
 'Who might buy again within 90 days? Historical test: '+p.customers+' customers; '+p.review_budget+' on the ranked review list.');
 repeat.append(el('p','This is a ranking, not a reliable purchase probability. Finding 13 of 19 repeat buyers is not 68% classification accuracy.'));
 modelFacts(repeat,'Experimental ranking, 90-day repeat purchase',[
 ['Tested',number(p.customers)+' customers'],['Actual repeat buyers',number(p.positive_customers)],['Buyers found',percent(p.capture_fraction)],['Listed customers',number(p.review_budget)],['List precision',percent(p.cases_in_review_list/p.review_budget)],['Accuracy','Not a yes/no test']]);
 }else repeat.replaceChildren(el('p','Repeat-purchase evaluation is unavailable.'));
 let archive=$('earlier-model-studies');if(!archive){archive=el('details',undefined,'panel research-details');archive.id='earlier-model-studies';archive.append(el('summary','Earlier experiments, not used for decisions'));anchor.before(archive);}
 archive.append(research.closest('article'),repeat.closest('article'),repeatDetails);
}
function modelFacts(target,label,values){
 const head=el('div',label,'model-label'),grid=el('div',undefined,'model-facts');
 values.forEach(([name,value])=>{const box=el('div');box.append(el('span',name),el('strong',value));grid.append(box);});
 target.prepend(head,grid);target.closest('article').classList.add('model-section');
}

function forecastTrend(target,rows,label){
 const width=520,height=240,left=44,right=14,top=14,bottom=34;
 const max=Math.max(1,...rows.flatMap(r=>[r.actual,r.selected,r.baseline]))*1.12;
 const x=i=>left+i*(width-left-right)/Math.max(1,rows.length-1),y=v=>height-bottom-v/max*(height-top-bottom);
 const svg=svgNode('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':label,class:'trend-svg'});
 for(let i=0;i<=4;i++){const v=max*i/4,yy=y(v);svg.append(svgNode('line',{x1:left,y1:yy,x2:width-right,y2:yy,stroke:'#ececec'}),svgNode('text',{x:left-8,y:yy+4,'text-anchor':'end',fill:'#525252','font-size':12},number(v)));}
 for(const [key,color,dash] of [['actual','#0a0a0a',false],['selected','#1d4ed8',false],['baseline','#a3a3a3',true]]){
  const attrs={points:rows.map((r,i)=>`${x(i)},${y(r[key])}`).join(' '),fill:'none',stroke:color,'stroke-width':2.3};if(dash)attrs['stroke-dasharray']='6 4';svg.append(svgNode('polyline',attrs));
 }
 [0,Math.floor((rows.length-1)/2),rows.length-1].forEach((i,k)=>svg.append(svgNode('text',{x:x(i),y:height-10,'text-anchor':k===0?'start':k===2?'end':'middle',fill:'#525252','font-size':12},date(rows[i].origin))));
 target.append(svg);
 const legend=el('div',undefined,'forecast-legend');[['Recorded','#0a0a0a'],['Forecast','#1d4ed8'],['Simple baseline','#a3a3a3']].forEach(([name,color])=>{const item=el('span',name);item.style.borderColor=color;legend.append(item);});target.append(legend);
}
function renderPlanningForecasts(target,p){
 target.replaceChildren();if(!p){empty(target,'Planning evidence is unavailable.');return;}
 const live=p.live||{},evidence=p.evidence,header=el('div',undefined,'planning-heading');
 const intro=el('div');intro.append(el('p','Plan appointment slots, rosters and supplies.','sub'));
 const refresh=el('button','Refresh','secondary');refresh.type='button';refresh.addEventListener('click',async()=>{refresh.disabled=true;try{planningData=null;showPlanning(await planning());}catch(e){target.append(el('p',e.message,'notice'));}finally{refresh.disabled=false;}});
 header.append(intro,refresh);target.append(header);
 const grid=el('div',undefined,'planning-grid');
 evidence.models.forEach(model=>{
  const card=el('section',undefined,'planning-card'),head=el('div',undefined,'panel-head');head.append(el('h3',String(model.title).replace(/\s*\u00b7\s*/g,', ')),help('About this forecast',evidence.notice+' Inputs: '+model.inputs+'. Booked hours are appointment durations, not technician productivity. The new live forecast is issued shortly before Monday; historical results used Monday origins.'));
  card.append(head);
  const current=(live.forecasts||[]).find(r=>r.id===model.id);
  if(current){
   card.append(el('span',live.stale?'Last saved forecast, refresh overdue':'Saved before the week started','model-label'),el('strong',number(current.prediction)+' '+model.unit,'forecast-value'));
   card.append(el('p',date(live.latest.origin.slice(0,10))+' – '+date(current.window_end.slice(0,10))+', end exclusive','sub'),el('p',number(current.already_booked)+' already booked when scored, simple baseline '+number(current.baseline),'sub'));
  }else{
   card.append(el('span',live.collection_overdue?'Forecast not received':'New weekly test','model-label'),el('strong','First week, '+date(evidence.first_origin),'forecast-pending'));
   card.append(el('p',live.status==='not_connected'?live.message:live.collection_overdue?'No verified forecast was received for the expected week. The missing window remains visible.':'Forecasts saved on Sundays at 11:50 pm, Malaysia time.','sub'));
  }
  const stats=el('div',undefined,'forecast-error-row');[['Historical average error',model.mae],['Simple baseline error',model.baseline_mae]].forEach(([label,value])=>{const stat=el('div');stat.append(el('span',label),el('strong',value.toFixed(1)+' '+model.unit));stats.append(stat);});card.append(stats);
  forecastTrend(card,model.history,model.title+', recorded, forecast and simple baseline in historical test');
  card.append(el('p',model.test_windows+' historical windows, '+(model.wape*100).toFixed(1)+'% WAPE (error, not accuracy)','sub'));
  grid.append(card);
 });target.append(grid);
 const details=el('details',undefined,'research-details');details.append(el('summary','New weekly test, collection and measured error'));
 const coverage=live.coverage||{};details.append(el('p',number(coverage.timely_windows||0)+' timely weeks logged, '+number((coverage.missing_weeks||[]).length)+' missed weeks. Late predictions are never backfilled.'));
 if(live.updated_at)details.append(el('p','Source and job last checked '+new Date(live.updated_at).toLocaleString('en-MY',{timeZone:'Asia/Kuala_Lumpur'})+' MYT','sub'));
 if((coverage.missing_weeks||[]).length)details.append(el('p','Missing: '+coverage.missing_weeks.join(', '),'notice'));
 for(const metric of live.evaluation||[]){const model=evidence.models.find(m=>m.id===metric.id);details.append(el('p',(model?.title||metric.id)+': '+metric.windows+' evaluated windows'+(metric.mae==null?', waiting for outcomes.':', average error '+metric.mae.toFixed(1)+' vs baseline '+metric.baseline_mae.toFixed(1)+'.')));}
 details.append(el('p','Outcomes are checked after each window ends plus a revision buffer. These results are separate from the frozen pest-return experiment.','sub'));target.append(details);
}
