const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
class Element{
 constructor(tag,text='',cls=''){this.tag=tag;this.textContent=text;this.className=cls;this.children=[];this.dataset={};this.attrs={};this.handlers={};this.style={setProperty:(k,v)=>this.attrs[k]=v};this.classList={add:c=>this.className+=' '+c};}
 append(...rows){this.children.push(...rows)}
 replaceChildren(...rows){this.children=rows}
 setAttribute(k,v){this.attrs[k]=v}
 addEventListener(k,fn){this.handlers[k]=fn}
 querySelectorAll(tag){return this.children.flatMap(c=>[(c.tag===tag?c:null),...c.querySelectorAll(tag)]).filter(Boolean)}
}
const ctx={console,Date,Intl,Event:class{},navigator:{clipboard:{writeText:async()=>{}}},el:(tag,text,cls)=>new Element(tag,text,cls),deskButton:(text,click,cls)=>{const e=new Element('button',text,cls);e.addEventListener('click',click);return e;}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('webapp/static/booking.js','utf8'),ctx);
const teams=[{id:'ace',active:true,visit_type:'treatment',calendar_name:'TEAM ACE (fixture)'},{id:'sales',active:true,visit_type:'consultation',calendar_name:'SALES TEAM'}];
const data={status:'ready',window_start:'2099-11-01',window_end:'2099-11-30',teams,events:[{key:'a'.repeat(64),team_id:'ace',start:'2099-11-03T10:00:00+08:00',end:'2099-11-03T11:00:00+08:00',label:'Fixture customer',reschedulable:true}]};
const host=new Element('section');let moved=null,chosenDate=null;
const cal=ctx.createBookingCalendar(host,data,{date:'2099-11-03',onDate:d=>chosenDate=d,onMove:e=>moved=e.key});
const all=()=>[host,...host.querySelectorAll('button'),...host.querySelectorAll('div')];
let busy=host.querySelectorAll('button').find(e=>e.className==='booking-calendar-event');assert(busy);assert.equal(busy.style.height,'78px');busy.handlers.click();
let move=host.querySelectorAll('button').find(e=>e.textContent==='Find a replacement slot');assert(move);move.handlers.click();assert.equal(moved,'a'.repeat(64));
cal.update('2099-11-03',[{team_id:'ace',team:'TEAM ACE',start:'2099-11-03T12:00:00+08:00',end:'2099-11-03T13:00:00+08:00',coverage:'usual_area',travel_buffer_minutes:30,reason:'Usual team'}]);
const slot=host.querySelectorAll('button').find(e=>e.className.includes('booking-calendar-slot'));assert(slot);slot.handlers.click();assert(host.querySelectorAll('button').some(e=>e.textContent==='Copy option'));
host.querySelectorAll('button').find(e=>e.textContent==='Week, one team').handlers.click();assert.equal(host.querySelectorAll('button').filter(e=>e.className==='booking-calendar-column-head').length,7);
cal.update('',[]);assert.equal(host.querySelectorAll('button').filter(e=>e.className.includes('booking-calendar-slot')).length,0);
console.log('Calendar DOM interactions passed: day/week, appointment inspection, reschedule selection, suggested-slot detail, clearing suggestions.');
