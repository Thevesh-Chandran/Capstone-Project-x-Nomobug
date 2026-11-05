"""Render the Looker Studio design reference, without querying private data.

Blank metrics and deliberately schematic chart shapes are layout examples.
Only the explicitly labelled historical model figures are observed results.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import html, json, math, re

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/dashboard_design/20261004_complete_guide'
W,H,S=1600,1100,2
C={'bg':'#F4F5FA','ink':'#172B4D','green':'#3659D9','mint':'#EAF0FF',
   'blue':'#20A6A0','amber':'#C48B36','muted':'#6D7D94','line':'#E1E6EF',
   'pale':'#EFF2F7','white':'#FFFFFF','sand':'#FBF3E6'}
TITLES=['Overview','Enquiries','Sales and payments','Services and teams',
        'Warranty and returns','Pests and packages','Service areas','Weather',
        'Prediction model','Data checks','Recurring payments']
SUBS=['Business activity at a glance','Enquiry activity and recorded outcomes',
      'Sales trends and the payment records in your sheets','Scheduled visits by date and team',
      'Return visits, timing and refund records','Package demand across recorded pest groups',
      'Service locations and groups of nearby properties','Weather before warranty and other visits',
      'What the model has shown so far','Source updates, missing information and coverage',
      'Paid amounts, remaining balances and staff reminder dates']
SCOPES=['1 Jan – 30 Sep 2026','1 Jan – 30 Sep 2026','1 Jan – 30 Sep 2026',
        '1–30 Sep 2026','1 Jan – 30 Sep 2026','2026 snapshot','2026 snapshot',
        '1 Jan – 30 Sep 2026','Historical test','Current source snapshot','Current payment plans']
GEOMETRY={}

def font(size,bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',int(size*S))

class Canvas:
    def __init__(self,index):
        self.index=index;self.im=Image.new('RGB',(W*S,H*S),C['bg']);self.d=ImageDraw.Draw(self.im);self.blocks=[]
    def rect(self,box,fill='white',radius=12,outline=None):
        self.d.rounded_rectangle(tuple(int(v*S) for v in box),radius*S,fill=C.get(fill,fill),outline=C.get(outline,outline) if outline else None,width=S)
    def line(self,points,fill='line',width=1):
        self.d.line([(int(x*S),int(y*S)) for x,y in points],fill=C.get(fill,fill),width=max(1,int(width*S)))
    def text(self,x,y,value,size=14,color='ink',bold=False,width=None):
        f=font(size,bold);words=str(value).split();lines=[];line=''
        for word in words:
            candidate=(line+' '+word).strip()
            if width and line and self.d.textlength(candidate,font=f)>width*S:lines.append(line);line=word
            else:line=candidate
        lines.append(line)
        for i,row in enumerate(lines):self.d.text((x*S,(y+i*(size+5))*S),row,font=f,fill=C.get(color,color))
        return len(lines)*(size+5)
    def dot(self,x,y,r,fill):
        self.d.ellipse(((x-r)*S,(y-r)*S,(x+r)*S,(y+r)*S),fill=C.get(fill,fill))
    def pill(self,x,y,text,fill='mint',color='green',w=None):
        w=w or self.d.textlength(text,font=font(12,True))/S+24
        self.rect((x,y,x+w,y+28),fill,7);self.text(x+12,y+7,text,12,color,True)
    def panel(self,x,y,w,h,title,sub=None):
        self.rect((x,y,x+w,y+h),'white',12,'line')
        self.text(x+24,y+22,title,18,bold=True,width=w-48)
        if sub:self.text(x+24,y+49,sub,12,'muted',width=w-48)
        self.blocks.append({'title':title,'x':x,'y':y,'width':w,'height':h})
        return (x+24,y+88,w-48,h-116)
    def metric(self,x,y,w,label,note,value='—',lead=False):
        self.rect((x,y,x+w,y+136),'ink' if lead else 'white',12,None if lead else 'line')
        color='white' if lead else 'ink';secondary='#BECCF1' if lead else C['muted']
        self.text(x+22,y+20,label,14,color,True,width=w-44)
        self.text(x+22,y+49,value,38,color,True)
        self.text(x+22,y+106,note,11,secondary,width=w-44)
        self.blocks.append({'title':label,'x':x,'y':y,'width':w,'height':136})
    def cards(self,items):
        n=len(items);width=(1318-(n-1)*20)/n
        for i,item in enumerate(items):self.metric(246+i*(width+20),166,width,*item,lead=i==0)
    def legend(self,x,y,labels):
        for name,color in labels:
            self.dot(x+4,y+7,4,color);self.text(x+15,y,name,12,'muted');x+=self.d.textlength(name,font=font(12))/S+40
    def trend(self,box,labels=None,dual=False,bars=False,stacked=False):
        x,y,w,h=box; labels=labels or ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep'];h-=20
        for r in range(4):
            yy=y+10+r*(h-20)/3;self.line([(x+28,yy),(x+w,yy)]);self.text(x,yy-5,'—',11,'muted')
        self.line([(x+28,y+h-10),(x+w,y+h-10)],'line')
        vals=[.29,.43,.36,.58,.51,.69,.63,.77,.70][:len(labels)]
        points=[]
        for i,(label,val) in enumerate(zip(labels,vals)):
            xx=x+42+i*(w-58)/(len(labels)-1);yy=y+h-10-val*(h-25)
            if bars:
                bw=min(30,(w-65)/len(labels)*.45);base=y+h-10
                if stacked:
                    height=base-yy
                    self.rect((xx-bw/2,base-height*.64,xx+bw/2,base),'green',2)
                    self.rect((xx-bw/2,base-height*.87,xx+bw/2,base-height*.64),'blue',0)
                    self.rect((xx-bw/2,yy,xx+bw/2,base-height*.87),'#ADBEB7',2)
                else:
                    self.rect((xx-bw/2,yy,xx+bw/2,base),'green',3)
                    if dual:self.rect((xx+bw/2+4,base-(base-yy)*.33,xx+bw+4,base),'blue',3)
            else:points.append((xx,yy))
            self.text(xx-11,y+h+5,label,11,'muted')
        if not bars:
            self.line(points,'green',3)
            for xx,yy in points:self.dot(xx,yy,3.4,'green')
            if dual:
                pts=[(xx,yy+26+(i%3)*7) for i,(xx,yy) in enumerate(points)]
                self.line(pts,'blue',2)
                for xx,yy in pts:self.dot(xx,yy,2.8,'blue')
    def hbars(self,box,labels,color='green',stack=False):
        x,y,w,h=box;row=h/len(labels);left=min(135,w*.32)
        for i,label in enumerate(labels):
            yy=y+i*row;self.text(x,yy+8,label,13,'muted',width=left-10)
            maxw=w-left-30;full=maxw*(.88-.105*i)
            if stack:
                self.rect((x+left,yy+7,x+left+full,yy+28),'blue',3)
                self.rect((x+left,yy+7,x+left+full*.59,yy+28),color,3)
            else:self.rect((x+left,yy+7,x+left+full,yy+28),color,3)
            self.text(x+w-13,yy+9,'—',12,'muted')
    def table(self,box,headers,rows,widths=None):
        x,y,w,h=box; widths=widths or [1/len(headers)]*len(headers);rowh=min(43,(h-34)/max(1,len(rows)))
        self.rect((x,y,x+w,y+32),'pale',5)
        xx=x
        for label,pct in zip(headers,widths):self.text(xx+10,y+10,label,11,'muted',True,width=w*pct-17);xx+=w*pct
        for i,row in enumerate(rows):
            yy=y+32+i*rowh;xx=x
            self.line([(x,yy+rowh),(x+w,yy+rowh)])
            for j,(val,pct) in enumerate(zip(row,widths)):
                self.text(xx+10,yy+12,str(val),12,'ink' if j==0 else 'muted',j==0,width=w*pct-18);xx+=w*pct
    def heat(self,box,rowlabels,colnames):
        x,y,w,h=box;left=112;cw=(w-left)/len(colnames);rh=(h-32)/len(rowlabels)
        for j,col in enumerate(colnames):self.text(x+left+j*cw+8,y,col,12,'muted')
        palette=['#EAF0FF','#CCDAFF','#92A9EB','#607EDC','#3659D9']
        for i,name in enumerate(rowlabels):
            self.text(x,y+36+i*rh,name,12,'muted',width=100)
            for j in range(len(colnames)):
                shade=(i*2+j)%5;xx=x+left+j*cw;yy=y+30+i*rh
                self.rect((xx+3,yy,xx+cw-4,yy+rh-8),palette[shade],4)
                self.text(xx+cw/2-5,yy+(rh-8)/2-7,'—',13,'white' if shade>2 else 'green',True)
    def map(self,box,clusters=False):
        x,y,w,h=box;self.rect((x,y,x+w,y+h),'#EFF3ED',8)
        # Deliberately abstract: no false locality names or property coordinates.
        for i in range(6):
            self.line([(x,min(y+h-3,y+20+i*h/5)),(x+w*.3,min(y+h-3,y+10+i*h/5)),(x+w*.65,min(y+h-3,y+40+i*h/5)),(x+w,min(y+h-3,y+10+i*h/5))],'#FFFFFF',5)
        self.line([(x+w*.67,y+9),(x+w*.51,y+h*.25),(x+w*.57,y+h*.6),(x+w*.44,y+h-9)],'#C9DDE5',15)
        for px,py,r in [(.14,.24,13),(.37,.31,24),(.26,.73,18),(.70,.66,29),(.83,.29,16),(.56,.85,12)]:
            xx=x+px*w;yy=y+py*h;self.dot(xx,yy,r+4,'white');self.dot(xx,yy,r,'blue' if clusters else 'green');self.dot(xx,yy,3,'white')
        self.pill(x+12,y+12,'Cluster centroids' if clusters else 'Area centroids','white','muted')
    def shell(self):
        self.rect((0,0,210,H),'white',0);self.line([(210,0),(210,H)])
        self.rect((25,32,62,69),'ink',9);self.text(36,40,'N',22,'white',True)
        self.text(73,36,'NOMObug',21,bold=True);self.text(74,61,'Management',11,'muted')
        self.text(26,119,'BUSINESS REPORT',10,'muted',True)
        for i,title in enumerate(TITLES):
            yy=155+i*57
            if i==self.index:self.rect((14,yy-7,197,yy+42),'mint',8)
            self.text(27,yy+7,f'{i+1:02}',11,'green' if i==self.index else 'muted',True)
            self.text(55,yy+5,title,13,'green' if i==self.index else 'muted',i==self.index,width=132)
        self.line([(25,823),(185,823)]);self.text(26,846,'CP2 / 2026',12,bold=True)
        self.text(26,868,'Management dashboard',11,'muted',width=150)
        self.rect((22,966,188,1044),'pale',8);self.text(35,980,'Design reference',12,bold=True)
        self.text(35,1002,'Build in Looker Studio',11,'muted',width=140)
        self.text(246,29,'REPORT  /  '+('VALIDATION' if self.index in [8,9] else 'BUSINESS'),11,'muted',True)
        self.text(246,57,TITLES[self.index],34,bold=True)
        self.text(246,106,SUBS[self.index],15,'muted')
        self.pill(1290,30,f'PAGE {self.index+1:02} / 11','white','muted',137)
        self.rect((1250,74,1564,118),'white',8,'line');self.text(1267,90,SCOPES[self.index],13,'ink',True)
        if self.index not in [5,6,8,9,10]:self.line([(1536,94),(1540,99),(1544,94)],'muted',1.5)
        self.line([(246,143),(1564,143)])
        self.line([(246,1048),(1564,1048)])
        self.text(246,1064,'DESIGN PREVIEW  ·  Charts are illustrative; business totals are blank.',11,'muted')
        self.text(1262,1064,'NOMObug  /  Management',11,'muted')
    def save(self):
        self.im.resize((W,H),Image.Resampling.LANCZOS).save(OUT/f'page_{self.index+1:02}.png')
        GEOMETRY[TITLES[self.index]]=self.blocks

def build(index):
    if __package__:
        from .dashboard_mockup_layouts import render
    else:
        from dashboard_mockup_layouts import render
    c=Canvas(index);c.shell();render(c,index)


def update_guide():
    path=OUT/'index.html';doc=path.read_text(encoding='utf-8')
    css='''*{box-sizing:border-box}body{margin:0;background:#F4F6F5;color:#153A38;font:15px/1.65 Arial,sans-serif}aside{position:fixed;width:230px;height:100vh;background:#fff;border-right:1px solid #DFE7E3;padding:25px 15px;overflow:auto}aside h1{font-size:21px;padding:0 12px}button{display:block;width:100%;border:0;background:transparent;color:#667C76;text-align:left;padding:12px;border-radius:8px;font:13px Arial;cursor:pointer;margin:2px 0}button.active,button:hover{background:#E7F3EE;color:#137C6E;font-weight:700}button:focus-visible,a:focus-visible{outline:3px solid #137C6E;outline-offset:3px}main{margin-left:230px;padding:32px;max-width:1920px}header{margin-bottom:25px}h1,h2,h3{color:#153A38;line-height:1.3}h1{font-size:30px}h2{font-size:23px}h3{font-size:18px}img{display:block;width:100%;height:auto;border-radius:12px;border:1px solid #DFE7E3}article{background:white;padding:28px;margin-top:20px;border:1px solid #DFE7E3;border-radius:12px}.page{display:none}.page.active{display:block}table{width:100%;border-collapse:collapse;display:block;overflow:auto;margin:20px 0}td{padding:12px;border-bottom:1px solid #DFE7E3;vertical-align:top}tr:first-child{background:#E7F3EE;font-weight:600}code{font:13px Consolas,monospace;overflow-wrap:anywhere;color:#137C6E}pre{background:#F4F6F5;padding:18px;overflow:auto}a{color:#137C6E}.badge{background:#E7F3EE;padding:13px 18px;border-radius:8px;color:#153A38}.bullet{margin:6px 0}.design-actions{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}.design-actions a{border:1px solid #DFE7E3;border-radius:8px;padding:9px 14px;background:white;text-decoration:none;font-weight:700;font-size:13px}.design-actions a:first-child{background:#153A38;color:white;border-color:#153A38}.design-help{padding:15px 18px;background:#E7F3EE;border-radius:8px;margin:15px 0}.download{margin:12px 0}@media(max-width:800px){aside{position:static;width:100%;height:auto}aside nav{display:flex;overflow:auto}button{min-width:180px}main{margin:0;padding:14px}article{padding:18px}h1{font-size:24px}}@media print{aside,header,.design-actions{display:none}main{margin:0;padding:0}.page{display:block;break-before:page}img{max-height:640px;object-fit:contain}}'''
    doc=re.sub(r'<style>.*?</style>','<style>'+css+'</style>',doc,count=1,flags=re.S)
    for old,new in {'#F4F6F5':'#F4F5FA','#153A38':'#172B4D','#137C6E':'#3659D9','#E7F3EE':'#EAF0FF','#667C76':'#6D7D94','#DFE7E3':'#E1E6EF'}.items():doc=doc.replace(old,new)
    doc=doc.replace('Dashboard guide and design mockups','Your Looker Studio design guide')
    doc=re.sub(r'<p class="badge">.*?</p>','<p class="badge">11 distinct page compositions · native Looker Studio components · updated 5 October. Chart patterns are illustrative; the model page contains verified historical figures.</p>',doc,count=1,flags=re.S)
    if 'class="design-actions"' not in doc:
        doc=doc.replace('</header>','<div class="design-actions"><a href="CP2_dashboard_mockups.pdf">Open all 11 pages as a PDF</a><a href="LOOKER_STUDIO_DESIGN_RECIPE.md">Colours, sizes and build recipe</a><a href="layout_coordinates.json">Exact panel positions</a></div></header>')
    for i,title in enumerate(TITLES):
        doc=re.sub(rf'(<section class="page" id="page{i+1}"><h2>).*?(</h2>)',lambda m:m[1]+f'{i+1:02d} · '+title+m[2],doc,count=1)
        doc=doc.replace(f'src="page_{i+1:02}.png"',f'src="page_{i+1:02}.png?v=design3"') if '?v=design3' not in doc else doc
    # Cache-busting all images, including when the guide is already open.
    doc=re.sub(r'src="(page_\d+\.png)(?:\?v=[^"]*)?"',r'src="\1?v=design3"',doc)
    for i in range(1,12):
        marker=f'<!-- fullsize-{i} -->'
        if marker not in doc:
            pattern=rf'(<img src="page_{i:02}\.png\?v=design3"[^>]*>)'
            doc=re.sub(pattern,lambda m:m[1]+marker+f'<p class="download"><a href="page_{i:02}.png" target="_blank">Open this mockup at full size</a></p>',doc,count=1)
    doc=re.sub(r'<p>3\. (?:Build|Use).*?</p>','<p>3. Use the new 1600 × 1100 design recipe: 210 px white sidebar, Arial, navy feature panels, cobalt primary charts and teal comparisons. Every page has its own composition and exact positions.</p>',doc,count=1)
    doc=doc.replace('Start with about 1,200 px width','Use the 1600 × 1100 design canvas')
    doc=doc.replace('These definitions are prepared locally; stable Gold publication and the hosted image update remain outstanding.','These aggregate sources are published to stable Gold. Verify source freshness before sharing the finished dashboard.')
    notice='<div class="design-help"><strong>Build the new design:</strong> use the theme and coordinates in <a href="LOOKER_STUDIO_DESIGN_RECIPE.md">the design recipe</a>. It replaces the older layout sizes below; the source and calculation instructions still apply.</div>'
    if notice not in doc:doc=doc.replace('<article>',notice+'<article>',1)
    path.write_text(doc,encoding='utf-8')
    guide=OUT/'CP2_dashboard_complete_build_guide.md';text=guide.read_text(encoding='utf-8')
    text=re.sub(r'3\. Build a 1440.*?\n4\.', '3. Follow [the updated Looker Studio design recipe](LOOKER_STUDIO_DESIGN_RECIPE.md): 1600 × 1100 canvas, 210 px light sidebar, deep-green text, white panels and native charts. The recipe and `layout_coordinates.json` replace the earlier layout specification.\n4.',text,count=1)
    text=text.replace('Start with about 1,200 px width','Use the 1600 × 1100 canvas')
    text=text.replace('deep-green text','navy text').replace('Prepared 4 October 2026.','Design updated 5 October 2026; source definitions checked 4 October.')
    text=text.replace('These definitions are prepared locally; stable Gold publication and the hosted image update remain outstanding.','These aggregate sources are published to stable Gold. Verify source freshness before sharing the finished dashboard.')
    guide.write_text(text,encoding='utf-8')

def embed_recipe():
    recipe=OUT/'LOOKER_STUDIO_DESIGN_RECIPE.md'
    if not recipe.exists():return
    # Reuse the existing guide's small Markdown renderer without running its warehouse reads.
    import ast
    source=ROOT/'outputs/project_audit/20261004/build_dashboard_guide.py'
    tree=ast.parse(source.read_text(encoding='utf-8'))
    funcs=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['inline','render']],type_ignores=[])
    scope={'html':html,'re':re};exec(compile(funcs,str(source),'exec'),scope)
    section='<section class="page" id="design"><article>'+scope['render'](recipe.read_text(encoding='utf-8'))+'</article></section>'
    path=OUT/'index.html';doc=path.read_text(encoding='utf-8')
    doc=re.sub(r'<section class="page" id="design">.*?</section>','',doc,flags=re.S)
    doc=doc.replace('</main>',section+'</main>')
    if 'data-page="design"' not in doc:doc=doc.replace('<button data-page="setup">','<button data-page="design">Theme and build recipe</button><button data-page="setup">')
    doc=doc.replace('href="LOOKER_STUDIO_DESIGN_RECIPE.md"','href="#design" onclick="select(\'design\');return false;"')
    path.write_text(doc,encoding='utf-8')

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    for index in range(11):build(index)
    (OUT/'layout_coordinates.json').write_text(json.dumps({'canvas':{'width':W,'height':H,'sidebar_width':210,'content_x':246,'content_width':1318,'gap':20},'pages':GEOMETRY},indent=2),encoding='utf-8')
    pages=[Image.open(OUT/f'page_{i:02}.png').convert('RGB') for i in range(1,12)]
    pages[0].save(OUT/'CP2_dashboard_mockups.pdf',save_all=True,append_images=pages[1:],resolution=120)
    for p in pages:p.close()
    update_guide()
    embed_recipe()
    print(json.dumps({'mockups':11,'canvas':[W,H],'output':str(OUT),'private_source_queries':0}))
