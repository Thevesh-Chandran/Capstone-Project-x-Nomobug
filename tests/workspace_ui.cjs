const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
class Element{
 constructor(tag,text='',cls=''){this.tag=tag;this.textContent=text;this.className=cls;this.children=[];this.attrs={};this.handlers={};this.classList={add:c=>this.className+=' '+c};}
 prepend(...items){this.children.unshift(...items)} append(...items){this.children.push(...items)} replaceChildren(...items){this.children=items} setAttribute(k,v){this.attrs[k]=v} addEventListener(k,f){this.handlers[k]=f}
}
const home=new Element('section'),ctx={Date,Intl,console,document:{querySelector:()=>home},window:{},el:(...args)=>new Element(...args),number:String,money:v=>'RM'+v,api:async()=>{},openDeskTask:t=>ctx.opened=t.id};
vm.createContext(ctx);const script=fs.readFileSync('webapp/static/workspace.js','utf8');vm.runInContext(script.slice(0,script.indexOf('let deskDrawer;')),ctx);
const tasks=[{id:'1',name:'Reminder customer',sales_record_id:'SALE1',review_kind:'upcoming',status:'open',sales_remaining_balance_rm:100,next_scheduled_reminder_date:'2026-11-03'},{id:'2',name:'Missing date customer',sales_record_id:'SALE2',review_kind:'missing',status:'open'},{id:'3',name:'Reviewed customer',sales_record_id:'SALE3',review_kind:'upcoming',status:'reviewed'}];
const data={counts:{total:3,upcoming:1,missing:1,unknown:0,status:0,reviewed:1},tasks,log_available:true,schedule:{available:true,bookings:4},week_start:'2026-11-02',week_end:'2026-11-08'};
ctx.renderDesk(data);const walk=(e)=>[e,...e.children.flatMap(walk)],all=()=>walk(home),queue=()=>all().filter(e=>e.className==='desk-task');
assert.equal(queue().length,3);assert(all().some(e=>e.textContent==='Customer follow-up'));
all().find(e=>e.className.includes('desk-queue-option')&&e.children[0].textContent==='Due in 7 days').handlers.click();assert.equal(queue().length,1);
all().find(e=>e.textContent==='Review').handlers.click();assert.equal(ctx.opened,'1');
all().find(e=>e.className.includes('desk-queue-option')&&e.children[0].textContent==='All records').handlers.click();const search=all().find(e=>e.tag==='input');search.value='SALE2';search.handlers.input();assert.equal(queue().length,1);assert(all().some(e=>e.textContent==='Missing date customer'));
assert(all().some(e=>e.href==='#plan'));assert(all().some(e=>e.href==='#payments'));
console.log('Work queue passed: retained follow-ups, view filters, search, review action, booking and payment navigation.');
