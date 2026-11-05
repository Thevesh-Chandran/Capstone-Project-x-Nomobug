"""Eleven distinct native-Looker compositions for the CP2 design reference."""

def big_number(c,x,y,w,h,label,value,note,dark=False):
    c.rect((x,y,x+w,y+h),'ink' if dark else 'white',16,None if dark else 'line')
    c.text(x+28,y+26,label,17,'white' if dark else 'ink',True,width=w-56)
    c.text(x+28,y+72,value,58,'white' if dark else 'ink',True)
    c.text(x+28,y+h-50,note,13,'#BECCF1' if dark else 'muted',width=w-56)
    c.blocks.append({'title':label,'x':x,'y':y,'width':w,'height':h})

def small_stats(c,x,y,w,items):
    c.rect((x,y,x+w,y+112),'white',12,'line')
    cw=w/len(items)
    for i,(label,value) in enumerate(items):
        xx=x+i*cw
        if i:c.line([(xx,y+23),(xx,y+89)])
        c.text(xx+24,y+24,label,13,'muted',True,width=cw-48)
        c.text(xx+24,y+52,value,30,'ink',True)
    c.blocks.append({'title':' / '.join(a for a,b in items),'x':x,'y':y,'width':w,'height':112})

def render(c,index):
    if index==0:
        big_number(c,246,166,340,322,'Sales (RM)','RM —','Package prices recorded in SALES.',True)
        c.trend(c.panel(606,166,958,434,'Sales by month','A clear view of recorded business activity · RM'))
        small_stats(c,246,508,340,[('Packages sold','—')])
        small_stats(c,246,640,1318,[('Scheduled visits','—'),('Warranty visits','—'),('Last source update','—')])
        b=c.panel(246,772,750,254,'Scheduled visits by month','Package, warranty and other visits');c.legend(608,800,[('Package','green'),('Warranty','blue'),('Other','#ADBEB7')]);c.trend(b,bars=True,stacked=True)
        c.table(c.panel(1016,772,548,254,'Last data update','Use actual extraction times'),['Source','Updated','Age'],[['Sales','—','—'],['Calendar','—','—'],['Recurring','—','—']],[.40,.38,.22])
    elif index==1:
        c.panel(246,166,930,500,'Enquiries by month','Month of the first staff reply')
        c.text(274,248,'—',56,'ink',True);c.text(374,276,'enquiry records in the selected period',14,'muted')
        c.trend((274,346,874,270))
        for i,(label,note) in enumerate([('Open enquiries','Source conversation status'),('Closed enquiries','Source conversation status'),('Marked as won','Separate remark; may overlap')]):c.metric(1196,166+i*176,368,label,note,'—',i==0)
        c.table(c.panel(246,686,780,340,'Information to check','Whole-source checks keep unknown dates visible'),['Issue','Records'],[['Missing first reply date','—'],['Future reply date','—'],['Acquisition details','—']],[.75,.25])
        c.table(c.panel(1046,686,518,340,'Payment-link context','Separate records, not a conversion funnel'),['Month','Records','Marked won'],[['Month','—','—'],['Month','—','—'],['Unknown','—','—']],[.40,.30,.30])
    elif index==2:
        big_number(c,246,166,650,225,'Sales recorded','RM —','Package prices in SALES.',True)
        big_number(c,916,166,648,225,'Packages sold','—','Sold package records in the selected period.')
        c.trend(c.panel(246,411,1318,302,'Sales by month','Closed sales · RM'))
        b=c.panel(246,733,500,293,'Payments in sheet','Incomplete records · not verified cash received');c.trend(b)
        c.table(c.panel(766,733,390,293,'Sales to check','Review the original sheet'),['Issue','Records'],[['Missing total','—'],['Unknown date','—'],['Excluded sale','—']],[.75,.25])
        c.table(c.panel(1176,733,388,293,'Payments to check','Separate payment date grain'),['Issue','Records'],[['Missing amount','—'],['Unknown date','—'],['Reference review','—']],[.75,.25])
    elif index==3:
        c.heat(c.panel(246,166,868,490,'The service week','Visits by team and weekday · historical bookings'),['Team 01','Team 02','Team 03','Team 04'],['Su','Mo','Tu','We','Th','Fr','Sa'])
        c.pill(941,184,'Team: All','pale','muted',149)
        c.hbars(c.panel(1134,166,430,490,'Scheduled visits by team','Calendar labels'),['Team 01','Team 02','Team 03','Team 04'])
        small_stats(c,246,676,1318,[('Scheduled visits','—'),('Warranty visits','—'),('Visits linked to sales','—%')])
        c.trend(c.panel(246,808,760,218,'Daily appointments','Historical period selected above'),['01','05','09','13','17','21','25','30'])
        c.trend(c.panel(1026,808,538,218,'Next 14 days','Separate future range · not completed work'),['D1','D3','D5','D7','D9','D11','D14'],bars=True)
    elif index==4:
        c.hbars(c.panel(246,166,750,490,'When do return visits happen?','Days since the previous matched service-like visit'),['0–7 days','8–14 days','15–30 days','31–60 days','61+ days','Unknown / review'])
        big_number(c,1016,166,548,225,'Warranty visits','—','Calendar warranty entries.',True)
        small_stats(c,1016,411,548,[('Share of scheduled visits','—%')])
        c.pill(1016,546,'RETURN VISITS ARE NOT FORMAL CLAIM FORMS','sand','amber',500)
        c.trend(c.panel(246,676,750,350,'Warranty visits by month','Recorded workload, not proof of treatment failure'))
        c.panel(1016,676,548,350,'Refunds and warranty policy','Separate source records')
        c.text(1040,763,'Refunds recorded (RM)',14,'muted');c.text(1040,794,'RM —',37,'ink',True)
        c.text(1040,859,'3x: 30 days after the actual third service.',13,width=500)
        c.text(1040,897,'4x / 6x / 12x: service period + 30 days.',13,width=500)
        c.text(1040,935,'Commercial and residential 1x: no warranty.',13,width=500)
        c.text(1040,976,'Rescheduling does not remove 3x eligibility.',12,'muted',width=500)
    elif index==5:
        c.heat(c.panel(246,166,1318,430,'Pest × package demand','Pivot table · packages sold · 2026 snapshot'),['Pest group 01','Pest group 02','Mixed pests','Unknown'],['1x','3x','4x','6x','12x'])
        for x,txt,w in [(1030,'Pest: All',135),(1180,'Package: All',158),(1353,'Contract: All',187)]:c.pill(x,184,txt,'pale','muted',w)
        small_stats(c,246,616,1318,[('Packages sold','—'),('Sales (RM)','RM —'),('Warranty visits','—')])
        c.hbars(c.panel(246,748,570,278,'Package mix','Keep raw package labels'),['1x','3x','4x','6x','12x'])
        c.table(c.panel(836,748,728,278,'Package context','Mixed-pest sales are counted once'),['Pest','Package','Contract','Packages'],[['Source pest','Source package','Source contract','—'],['Mixed pests','Source package','Source contract','—'],['Unknown','Unknown','Unknown','—']],[.27,.26,.28,.19])
    elif index==6:
        c.map(c.panel(246,166,1318,565,'Where services are concentrated','Aggregate area centroids · schematic map, not actual property points'))
        # Native scorecards may sit over the map, with an opaque white background.
        c.metric(1172,290,344,'Visits with usable locations','Matching 2026 scope','—%')
        c.pill(1172,447,'AREA CODES · NO CUSTOMER ADDRESSES','white','muted',344)
        c.table(c.panel(246,751,650,275,'Area totals','Verified area codes'),['Area','Visits','Return visits'],[['Area code','—','—'],['Area code','—','—'],['Area code','—','—']],[.5,.25,.25])
        c.panel(916,751,648,275,'Groups of nearby properties','The radius changes clusters, not model accuracy')
        for i,txt in enumerate(['1 km','2 km','5 km']):c.pill(940+i*135,837,txt,'green' if i==1 else 'pale','white' if i==1 else 'muted',115)
        c.table((940,885,600,110),['Cluster','Properties','Return visits'],[['Cluster ID','—','—'],['Cluster ID','—','—']],[.5,.25,.25])
    elif index==7:
        c.metric(246,166,318,'Prior rainfall','14 days before the visit','— mm',True)
        c.metric(246,322,318,'Prior humidity','7 days before the visit','—%')
        c.panel(246,478,318,310,'Patterns, not causes','Observational comparisons')
        c.text(270,574,'Weather can guide investigation.',23,bold=True,width=265)
        c.text(270,670,'It does not establish why pests returned or prove flooding at a property.',14,'muted',width=265)
        for y,title,sub in [(166,'Rain before visits','Average prior 14-day rainfall · mm'),(486,'Humidity before visits','Average prior 7-day humidity · %')]:
            b=c.panel(584,y,980,300,title,sub);c.legend(1190,y+28,[('Warranty','green'),('Other','blue')]);c.trend(b,dual=True)
        c.table(c.panel(246,808,1318,218,'Weather coverage','Counts behind the comparison'),['Month','Visit group','Scheduled visits','Complete weather'],[['Month','Warranty','—','—'],['Month','Other visits','—','—']],[.23,.31,.23,.23])
    elif index==8:
        big_number(c,246,166,490,420,'Callbacks found in the top 20','4 of 5','Historical test; only five callback cases.',True)
        c.text(278,360,'EXPERIMENTAL',13,'#A7C4FF',True)
        small_stats(c,756,166,808,[('Services tested','100'),('Callback cases','5'),('Model accuracy','94%')])
        c.panel(756,298,808,288,'At the same review capacity','20 services reviewed · 5 callback cases available')
        for j,(label,val,color) in enumerate([('Current model',4,'green'),('Earlier model',3,'blue')]):
            yy=391+j*79;c.text(780,yy,label,14,'muted');c.rect((956,yy,1450,yy+24),'pale',3);c.rect((956,yy,956+494*val/5,yy+24),color,3);c.text(1475,yy,str(val),21,bold=True)
        c.text(956,535,'0',11,'muted');c.text(1389,535,'5 callbacks',11,'muted')
        c.panel(246,606,490,420,'Accuracy needs context','Always predicting no callback scores 95%')
        for j,(label,val,col) in enumerate([('Model',94,'green'),('Always no callback',95,'blue')]):
            yy=710+j*97;c.text(274,yy,label,14,'muted');c.text(614,yy,f'{val}%',22,bold=True);c.rect((274,yy+37,698,yy+60),'pale',3);c.rect((274,yy+37,274+424*val/100,yy+60),col,3)
        c.text(274,887,'0%',11,'muted');c.text(666,887,'100%',11,'muted')
        c.text(274,935,'A separate 13-service check missed its one callback. Keep it separate.',14,'muted',width=430)
        c.panel(756,606,808,420,'The next evidence','Future test · result pending')
        for j,(date,txt) in enumerate([('5–27 October','Log predictions before outcomes'),('Through 26 November','Collect the complete 30-day outcomes'),('27 November','Evaluate only if coverage checks pass')]):
            yy=709+j*92;c.dot(792,yy+10,6,'green');c.text(819,yy,date,19,bold=True);c.text(819,yy+30,txt,13,'muted')
            if j<2:c.line([(792,yy+23),(792,yy+80)])
    elif index==9:
        c.table(c.panel(246,166,970,360,'Source update register','The current published snapshot'),['Source','Extracted on','Hours old'],[['Sales','—','—'],['Calendar','—','—'],['Prospects','—','—'],['Recurring','—','—'],['Payments','—','—']],[.42,.36,.22])
        c.table(c.panel(246,546,970,480,'Records that need checking','Issues can overlap; do not sum them into one health score'),['Source','Issue','Records','Action'],[['Sales','Missing amount','—','Check source'],['Calendar','Unmatched sale','—','Review link'],['Prospects','Unknown reply date','—','Check source'],['Recurring','Unclear schedule','—','Review terms'],['Payments','Missing reference','—','Check source']],[.23,.34,.13,.30])
        for j,(a,b) in enumerate([('Visits linked to sales','Matched / scheduled visits'),('Visits with locations','Usable / scheduled visits'),('Visits with weather','Complete / scheduled visits')]):c.metric(1236,166+j*166,328,a,b,'—%',j==0)
        c.panel(1236,684,328,342,'Before sharing','Coverage: Jan–Sep 2026')
        for j,txt in enumerate(['Check the source dates.','Keep unknown values.','Resolve missing references.','Recheck filtered totals.']):c.text(1260,773+j*48,txt,14,'muted',width=280)
    else:
        c.rect((246,166,626,1026),'ink',16)
        c.blocks.append({'title':'Contract payment summary','x':246,'y':166,'width':380,'height':860})
        for yy,label,val in [(200,'Contract sales (RM)','RM —'),(382,'Paid (RM)','RM —'),(564,'Remaining balance (RM)','RM —')]:
            c.text(276,yy,label,16,'#BECCF1',True,width=320);c.text(276,yy+44,val,49,'white',True)
            c.line([(276,yy+137),(596,yy+137)],'#41516D')
        c.text(276,787,'SALES is the payment source.',18,'white',True,width=315)
        c.text(276,852,'Paid = deposit + cumulative balance paid. Reminder dates do not prove payment.',14,'#BECCF1',width=310)
        c.hbars(c.panel(646,166,918,335,'Payment progress by plan','Paid and remaining amounts · RM'),['Monthly','Quarterly','Custom terms','Other'],stack=True)
        c.legend(1120,193,[('Paid','green'),('Remaining','blue')]);c.pill(1360,229,'Plan: All','pale','muted',178)
        small_stats(c,646,521,918,[('Plans to remind in 7 days','—'),('Missing reminder dates','—')])
        c.trend(c.panel(646,653,548,373,'Upcoming reminder dates','Next 30 days · staff reminder schedule'),['06 Oct','13 Oct','20 Oct','27 Oct'],bars=True)
        c.table(c.panel(1214,653,350,373,'Plans to check','Green only means the date passed'),['Check','Plans'],[['Missing dates','—'],['Custom terms','—'],['Balance review','—'],['Schedule review','—']],[.75,.25])
    c.save()
