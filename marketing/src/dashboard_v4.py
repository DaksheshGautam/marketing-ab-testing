"""Author a native, self-contained PBIP dashboard for Power BI Desktop."""
import pathlib,json,uuid,sys
ROOT=pathlib.Path(__file__).resolve().parents[2];P=ROOT/'marketing';O=P/'output';B=P/'src/templates/Template.Report'
# Standard-library dashboard builder; no external package directory required.
import csv
from types import SimpleNamespace
s=json.loads((O/'results.json').read_text())['primary']
cube=list(csv.reader((O/'powerbi/marketing_cube.csv').open()))[1:]
R=O/'powerbi/Marketing Experiment v4.Report';M=O/'powerbi/Marketing Experiment v4.SemanticModel'
def dump(p,x):p.parent.mkdir(exist_ok=True,parents=True);p.write_text(json.dumps(x,indent=2),encoding='utf-8')
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def uid():return str(uuid.uuid4())
def lit(x):return {'expr':{'Literal':{'Value':x}}}
def solid(c):return {'solid':{'color':lit("'"+c+"'")}}
dump(O/'powerbi/Marketing Experiment v4.pbip',{'version':'1.0','artifacts':[{'report':{'path':R.name}}],'settings':{'enableAutoRecovery':True}})
dump(R/'definition.pbir',{'version':'4.0','datasetReference':{'byPath':{'path':'../'+M.name}}})
dump(M/'definition.pbism',{'version':'4.2','settings':{'qnaEnabled':False}})
cols=[('Variant','string'),('Day order','int64'),('Peak day','string'),('Peak hour','int64'),('Frequency band','string'),('Users','int64'),('Conversions','int64'),('Impressions','int64')]
rows=[]
for row in cube:rows.append('{'+','.join(json.dumps(str(x)) if t=='string' else str(int(x)) for x,(n,t) in zip(row,cols))+'}')
defs=', '.join('#"'+n+'" = '+('text' if t=='string' else 'Int64.Type') for n,t in cols)
expr='let Source = #table(type table ['+defs+'], {'+','.join(rows)+'}) in Source'
measures=[
 ('Users','SUM(Experiment[Users count])','#,0'),
 ('Conversions','SUM(Experiment[Conversions count])','#,0'),
 ('Impressions','SUM(Experiment[Impressions count])','#,0'),
 ('Conversion rate','DIVIDE([Conversions],[Users])','0.00%'),
 ('Ads per user','DIVIDE([Impressions],[Users])','0.0'),
 ('PSA rate','CALCULATE([Conversion rate],REMOVEFILTERS(Experiment[Variant]),Experiment[Variant]="A | PSA control")','0.00%'),
 ('Ad rate','CALCULATE([Conversion rate],REMOVEFILTERS(Experiment[Variant]),Experiment[Variant]="B | Product ads")','0.00%'),
 ('PSA users','CALCULATE([Users],REMOVEFILTERS(Experiment[Variant]),Experiment[Variant]="A | PSA control")','#,0'),
 ('Ad users','CALCULATE([Users],REMOVEFILTERS(Experiment[Variant]),Experiment[Variant]="B | Product ads")','#,0'),
 ('Lift pp','IF([PSA users]>0 && [Ad users]>0,100*([Ad rate]-[PSA rate]))','+0.000" pp";-0.000" pp";0.000" pp"'),
 ('Relative lift','DIVIDE([Ad rate]-[PSA rate],[PSA rate])','+0.0%;-0.0%;0.0%'),
 ('Modeled incremental conversions','[Ad users]*([Ad rate]-[PSA rate])','#,0'),
 ('Total impressions, full cohort','CALCULATE([Impressions],REMOVEFILTERS(Experiment))','#,0'),
 ('Full cohort p-value',f"{s['p_value']:.16g}",'0.00E+00'),
 ('Full cohort risk ratio',f"{s['risk_ratio']:.16g}",'0.000'),
 ('Full cohort lower lift pp',f"{100*s['ci_low']:.16g}",'0.000" pp"'),
 ('Full cohort upper lift pp',f"{100*s['ci_high']:.16g}",'0.000" pp"'),
 ('Full cohort incremental low',f"{s['incremental_low']:.16g}",'#,0'),
 ('Full cohort incremental high',f"{s['incremental_high']:.16g}",'#,0'),
 ('Full cohort lift pp',str(s['delta']*100),'+0.000" pp"'),
 ('Full cohort relative lift',str(s['relative_lift']),'+0.0%'),
 ('Full cohort incremental conversions',str(s['incremental_ad']),'#,0'),
 ('Balanced plan users', '47406','#,0'),
 ('Holdout plan users', '318275','#,0'),
 ('Planning target pp',str(s['p_psa']*.2*100),'0.000" pp"'),
 ('Planning power','0.8','0%'),
 ('Planning alpha','0.05','0%'),
 ('Planning baseline',str(s['p_psa']),'0.000%'),
 ('Missing values','0','#,0'),
 ('Duplicate users','0','#,0'),
 ('Excluded users','0','#,0'),
 ('Holdout share','0.04','0%'),
 ('PSA variance share',str(s['variance_psa_share']),'0%'),
 ('Fisher exact p',str(s['fisher_p']),'0.00E+00'),
 ('Illustrative break-even CPM',str(s['cpm_break_even_per_unit_margin']*25),'0.00'),
]
columns=[]
for n,t in cols:
    c={'name':n+' count' if n in ['Users','Conversions','Impressions'] else n,'sourceColumn':n,'dataType':t,'summarizeBy':'none','lineageTag':uid()}
    if n=='Peak day':c['sortByColumn']='Day order'
    columns.append(c)
table={'name':'Experiment','lineageTag':uid(),'columns':columns,'measures':[{'name':n,'expression':e,'formatString':f,'lineageTag':uid()} for n,e,f in measures],
       'partitions':[{'name':'Experiment','mode':'import','source':{'type':'m','expression':expr}}]}
plans=[SimpleNamespace(**{k:(v if k=='allocation' else float(v)) for k,v in r.items()}) for r in csv.DictReader((O/'sample_size_planning.csv').open())]
plan_rows=['{'+','.join([json.dumps(f'{r.relative_target:.0%} relative'),json.dumps(r.allocation),str(int(r.n_psa)),str(int(r.n_ad)),str(int(r.total))])+'}' for r in plans]
planning={'name':'Planning','lineageTag':uid(),
 'columns':[{'name':n,'sourceColumn':n,'dataType':t,'summarizeBy':'none','lineageTag':uid()} for n,t in [('Target','string'),('Allocation','string'),('PSA users','int64'),('Ad users','int64'),('Total users','int64')]],
 'measures':[{'name':'Required total users','expression':'SUM(Planning[Total users])','formatString':'#,0','lineageTag':uid()}],
 'partitions':[{'name':'Planning','mode':'import','source':{'type':'m','expression':'let Source = #table(type table [Target=text, Allocation=text, #"PSA users"=Int64.Type, #"Ad users"=Int64.Type, #"Total users"=Int64.Type], {'+','.join(plan_rows)+'}) in Source'}}]}
evidence_rows=','.join('{'+str(v*100)+'}' for v in [s['ci_low'],s['delta'],s['ci_high']])
evidence={'name':'Evidence','lineageTag':uid(),'columns':[{'name':'Lift pp','sourceColumn':'Lift pp','dataType':'double','summarizeBy':'none','lineageTag':uid()}],
 'measures':[{'name':'95% interval','expression':'1','formatString':'0.000','lineageTag':uid()},
 {'name':'Estimate','expression':f"IF(ABS(SELECTEDVALUE(Evidence[Lift pp])-{s['delta']*100:.16g})<0.0000001,1,BLANK())",'lineageTag':uid()}],
 'partitions':[{'name':'Evidence','mode':'import','source':{'type':'m','expression':'let Source = #table(type table [#"Lift pp"=number], {'+evidence_rows+'}) in Source'}}]}
dump(M/'model.bim',{'compatibilityLevel':1606,'model':{'culture':'en-US','sourceQueryCulture':'en-US','defaultPowerBIDataSourceVersion':'powerBI_V3','tables':[table,planning,evidence],'annotations':[{'name':'PBI_ProTooling','value':'["DevMode"]'}]}})
(P/'src/dashboard_measures.dax').write_text('\n\n'.join(n+' = '+e for n,e,f in measures),encoding='utf-8')
dump(R/'definition/version.json',read(B/'definition/version.json'))
report=read(B/'definition/report.json');report['themeCollection']['customTheme']['name']='ExperimentTheme';report['resourcePackages'][0]['items'][0].update(name='ExperimentTheme',path='ExperimentTheme.json');dump(R/'definition/report.json',report)
theme={'name':'Experiment','dataColors':['#168C92','#E59B45','#65758B','#B96D77'],'background':'#F3F6F8','foreground':'#17324D','tableAccent':'#168C92'}
dump(R/'StaticResources/RegisteredResources/ExperimentTheme.json',theme);dump(O/'powerbi/Experiment Theme.json',theme)
pages=[('overview','01 | Decision & impact'),('planning','02 | Design & sample size'),('inference','03 | Evidence'),('exposure','04 | Exposure explorer'),('timing','05 | Timing explorer')]
dump(R/'definition/pages/pages.json',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json','pageOrder':[x[0] for x in pages],'activePageName':'overview'})
VP=B/'definition/pages/overview/visuals'
def proj(n,measure=True):return {'field':{'Measure' if measure else 'Column':{'Expression':{'SourceRef':{'Entity':'Experiment'}},'Property':n}},'queryRef':'Experiment.'+n,'nativeQueryRef':n,**({} if measure else {'active':True})}
def visual(page,name,template,x,y,w,h,title=None,text=None,measure=None,category=None,metric=None,kind='lineChart',series=True,size=None):
    v=read(VP/template/'visual.json');v['name']=name.replace(' ','_');v['position']={'x':x,'y':y,'width':w,'height':h,'z':1,'tabOrder':1}
    vv=v['visual']
    if title:vv['visualContainerObjects']['title'][0]['properties']['text']=lit("'"+title+"'")
    if text:
        run=vv['objects']['general'][0]['properties']['paragraphs'][0]['textRuns'][0];run['value']=text
        if size:run['textStyle']['fontSize']=str(size)+'pt'
    if measure:
        vv['query']={'queryState':{'Values':{'projections':[proj(measure)]}}}
        if name in ['ad','rel','incremental']:vv['objects']['labels'][0]['properties']['color']=solid('#C37E28')
    if category:
        vv['visualType']=kind
        vv['query']={'queryState':{'Category':{'projections':[proj(category,False)]},'Y':{'projections':[proj(metric)]}},
                     'sortDefinition':{'sort':[{'field':proj(category,False)['field'],'direction':'Ascending'}],'isDefaultSort':True}}
        if series:vv['query']['queryState']['Series']={'projections':[proj('Variant',False)]}
        vv['query']['queryState']['Tooltips']={'projections':[proj(n) for n in ['Users','Conversions','Ads per user'] if n!=metric]}
        vv['objects'].pop('dataPoint',None)
        vv['objects']['legend']=[{'properties':{'show':lit('true'),'position':lit("'Top'"),'fontSize':lit('10D')}}]
        if metric=='Conversion rate':vv['objects']['valueAxis'][0]['properties']['start']=lit('0D')
    dump(R/f'definition/pages/{page}/visuals/{name}/visual.json',v)
def text(page,name,x,y,w,h,t,size=14,band=False):visual(page,name,'header' if band else 'subtitle',x,y,w,h,text=t,size=size)
def card(page,name,x,y,w,h,m,title):visual(page,name,'revenue',x,y,w,h,measure=m,title=title)
def chart(page,name,x,y,w,h,cat,metric,title,kind='lineChart'):visual(page,name,'revenue_trend',x,y,w,h,category=cat,metric=metric,title=title,kind=kind)

def labeltile(page,name,x,y,w,h,label,value,color='#17324D'):
    visual(page,name,'subtitle',x,y,w,h,text=value,size=23)
    path=R/f'definition/pages/{page}/visuals/{name}/visual.json';v=read(path)
    v['visual']['visualContainerObjects']['background'][0]['properties']['color']=solid('#FFFFFF')
    v['visual']['objects']['general'][0]['properties']['paragraphs']=[
      {'textRuns':[{'value':label,'textStyle':{'fontFamily':'Segoe UI','fontSize':'12pt','color':'#65758B'}}]},
      {'textRuns':[{'value':value,'textStyle':{'fontFamily':'Segoe UI','fontSize':'23pt','fontWeight':'bold','color':color}}]}]
    dump(path,v)

def field(n,entity,measure=False):
    return {'field':{'Measure' if measure else 'Column':{'Expression':{'SourceRef':{'Entity':entity}},'Property':n}},'queryRef':entity+'.'+n,'nativeQueryRef':n,**({} if measure else {'active':True})}

def interval(page,name,x,y,w,h):
    visual(page,name,'revenue_trend',x,y,w,h,title='95% CONFIDENCE INTERVAL | ABSOLUTE LIFT (pp)')
    path=R/f'definition/pages/{page}/visuals/{name}/visual.json';v=read(path);vv=v['visual']
    vv['query']={'queryState':{'Category':{'projections':[field('Lift pp','Evidence')]},'Y':{'projections':[field('95% interval','Evidence',True),field('Estimate','Evidence',True)]}},'sortDefinition':{'sort':[{'field':field('Lift pp','Evidence')['field'],'direction':'Ascending'}],'isDefaultSort':True}}
    vv['objects'].pop('dataPoint',None)
    vv['objects']['categoryAxis'][0]['properties'].update(axisType=lit("'Scalar'"),start=lit('0D'),end=lit('1.1D'))
    vv['objects']['valueAxis'][0]['properties'].update(show=lit('false'),start=lit('0D'),end=lit('2D'),showAxisTitle=lit('false'))
    vv['objects']['shapes']=[{'properties':{'showMarker':lit('true'),'markerSize':lit('10D'),'strokeWidth':lit('4D')}}]
    vv['objects']['legend']=[{'properties':{'show':lit('true'),'position':lit("'Top'"),'fontSize':lit('11D')}}]
    dump(path,v)

def slicer(page):
    visual(page,'day_filter','revenue_trend',1098,92,318,76,title='PEAK WEEKDAY')
    path=R/f'definition/pages/{page}/visuals/day_filter/visual.json';v=read(path);vv=v['visual'];vv['visualType']='slicer'
    vv['query']={'queryState':{'Values':{'projections':[proj('Peak day',False)]}}}
    vv['objects']={'data':[{'properties':{'mode':lit("'Dropdown'")}}],'selection':[{'properties':{'singleSelect':lit('false'),'selectAllCheckboxEnabled':lit('true')}}]}
    dump(path,v)

def samplechart(page):
    visual(page,'sample_chart','revenue_trend',24,300,902,360,title='TOTAL USERS NEEDED | TARGET RELATIVE LIFT')
    path=R/f'definition/pages/{page}/visuals/sample_chart/visual.json';v=read(path);vv=v['visual'];vv['visualType']='clusteredColumnChart'
    vv['objects'].pop('dataPoint',None)
    vv['query']={'queryState':{'Category':{'projections':[field('Target','Planning')]},'Series':{'projections':[field('Allocation','Planning')]},'Y':{'projections':[field('Required total users','Planning',True)]}},'sortDefinition':{'sort':[{'field':field('Target','Planning')['field'],'direction':'Ascending'}],'isDefaultSort':True}}
    vv['objects']['legend']=[{'properties':{'show':lit('true'),'position':lit("'Top'"),'fontSize':lit('12D')}}]
    dump(path,v)

for page,title in pages:
    pg=read(B/'definition/pages/overview/page.json');pg.update(name=page,displayName=title.split(' | ')[1],width=1440,height=900);dump(R/f'definition/pages/{page}/page.json',pg)
    text(page,'header',24,18,1392,64,''+title.split(' | ')[1].upper(),28,True)
    text(page,'subtitle',24,94,1038,42,'Ads vs PSA | 588,101 users | Teal: PSA / amber: ads',14)
    text(page,'footer',24,850,1392,34,'Kaggle: faviovaz/marketing-ab-testing | Full methods and assumptions in the PDFs',11)

# One takeaway, four primary metrics and two substantial visuals.
text('overview','decision',24,152,1392,60,'LIFT SUPPORTED  /  Verify economics before scaling',25,True)
for i,(name,m,label) in enumerate([('psa','PSA rate','PSA CONVERSION'),('ad','Ad rate','AD CONVERSION'),('lift','Full cohort lift pp','ABSOLUTE LIFT'),('incremental','Full cohort incremental conversions','EXTRA CONVERSIONS*')]):
    card('overview',name,24+i*352,234,336,114,m,label)
chart('overview','rates',24,374,600,314,'Variant','Conversion rate','CONVERSION BY ARM','clusteredColumnChart')
interval('overview','confidence',648,374,768,314)
labeltile('overview','efficacy',24,714,448,96,'CONVERSION EVIDENCE','Positive lift','#168C92')
labeltile('overview','economics',496,714,448,96,'PROFITABILITY','Not measured','#C37E28')
labeltile('overview','action',968,714,448,96,'NEXT ACTION','Keep a holdout')
text('overview','scope',24,812,1392,32,'*Modeled incrementality; assumes valid assignment. Full-cohort interval: +0.587 to +0.936 pp.',12)

# Assumptions as cards; sample size as a comparison, protocol as four short steps.
text('planning','subtitle',24,94,1392,42,'Prospective scenarios | Two-sided test | Illustrative targets',14)
for i,(name,m,label) in enumerate([('baseline','Planning baseline','PSA BASELINE'),('power','Planning power','POWER'),('alpha','Planning alpha','SIGNIFICANCE'),('target','Planning target pp','20% RELATIVE TARGET')]):
    card('planning',name,24+i*352,160,336,114,m,label)
samplechart('planning')
card('planning','balanced',950,300,466,156,'Balanced plan users','20% TARGET | 50/50 TOTAL USERS')
card('planning','holdout',950,478,466,156,'Holdout plan users','20% TARGET | 96/4 TOTAL USERS')
for i,(n,a,b) in enumerate([('randomize','01','Randomize users'),('window','02','Fix follow-up'),('stopping','03','Predefine stopping'),('guardrails','04','Track costs')]):
    labeltile('planning',n,24+i*352,698,336,102,a,b)
text('planning','scope',24,812,1392,32,'96/4 = 96% ads, 4% PSA. Duration requires eligible traffic and conversion-window inputs.',12)

# Evidence page uses audit metrics and allocation rather than explanatory paragraphs.
text('inference','subtitle',24,94,1392,42,'Full cohort | Design validity still requires assignment and measurement logs',14)
for i,(name,m,label) in enumerate([('pvalue','Full cohort p-value','PRIMARY P-VALUE'),('rr','Full cohort risk ratio','RISK RATIO'),('missing','Missing values','MISSING VALUES'),('duplicates','Duplicate users','DUPLICATE USERS')]):
    card('inference',name,24+i*352,160,336,114,m,label)
chart('inference','allocation',24,300,664,340,'Variant','Users','OBSERVED ALLOCATION | USERS','clusteredColumnChart')
interval('inference','confidence',712,300,704,340)
for i,(n,m,label) in enumerate([('fisher','Fisher exact p','FISHER EXACT P'),('variance','PSA variance share','VARIANCE FROM PSA ARM'),('excluded','Excluded users','EXCLUDED USERS')]):
    card('inference',n,24+i*472,680,448,120,m,label)
text('inference','scope',24,812,1392,32,'Unequal allocation is not a failure without the planned split. Details and sensitivity checks: analysis report.',12)

text('exposure','subtitle',24,94,1038,42,'Observed frequency | Select a weekday or chart category to explore',14)
slicer('exposure')
for i,(n,m,label) in enumerate([('users','Users','USERS IN VIEW'),('impressions','Impressions','IMPRESSIONS'),('average','Ads per user','ADS PER USER'),('rel','Relative lift','RELATIVE LIFT IN VIEW')]):
    card('exposure',n,24+i*352,186,336,110,m,label)
chart('exposure','frequency_rate',24,322,880,382,'Frequency band','Conversion rate','CONVERSION BY OBSERVED FREQUENCY')
chart('exposure','frequency_impressions',926,322,490,382,'Frequency band','Impressions','IMPRESSION CONCENTRATION','clusteredColumnChart')
text('exposure','tail',24,730,1392,60,'TOP ~1% OF USERS  /  13% of recorded impressions',24,True)
text('exposure','scope',24,812,1392,32,'Association, not a causal dose curve. Randomize frequency caps before changing delivery.',12)

text('timing','subtitle',24,94,1038,42,'Peak-exposure context | Select a weekday to compare hourly profiles',14)
slicer('timing')
chart('timing','day_rates',24,186,664,296,'Peak day','Conversion rate','CONVERSION BY PEAK WEEKDAY','clusteredColumnChart')
chart('timing','hour_rates',710,186,706,296,'Peak hour','Conversion rate','CONVERSION BY PEAK HOUR')
chart('timing','hour_users',24,506,664,288,'Peak hour','Users','HOURLY DENOMINATORS','clusteredColumnChart')
chart('timing','day_users',710,506,706,288,'Peak day','Users','WEEKDAY DENOMINATORS','clusteredColumnChart')
text('timing','scope',24,812,1392,32,'Peak exposure time, not conversion time. Descriptive patterns; no causal scheduling recommendation.',12)
print('Created visual-first five-page dashboard v4: chart-led layouts, weekday filters and full-cohort interval plots.')
# Revision 4: native parameter tables and dynamic prospective planning.
import shutil
for folder in ['planning']:
    shutil.rmtree(R/f'definition/pages/{folder}/visuals')
model=read(M/'model.bim')
def input_table(name,values,fmt):
    return {'name':name,'lineageTag':uid(),'columns':[{'name':'Value','sourceColumn':'Value','dataType':'double','formatString':fmt,'summarizeBy':'none','lineageTag':uid()}],'partitions':[{'name':name,'mode':'import','source':{'type':'m','expression':'let Source = #table(type table [Value=number], {'+','.join('{'+str(v)+'}' for v in values)+'}) in Source'}}]}
for name,values,fmt in [('Baseline',[.005,.01,.015,.018,.02,.025,.03,.04,.05,.075,.1],'0.0%'),('Target lift',[x/100 for x in range(5,101,5)],'0%'),('Power',[.8,.85,.9,.95],'0%'),('Ad allocation',[.5,.6,.7,.75,.8,.85,.9,.95,.96],'0%'),('Lift curve',[x/100 for x in range(5,51,5)],'0%')]:
    model['model']['tables'].append(input_table(name,values,fmt))
formula='''VAR p0=SELECTEDVALUE(Baseline[Value],0.018)
VAR lift=SELECTEDVALUE('Target lift'[Value],0.20)
VAR pw=SELECTEDVALUE(Power[Value],0.80)
VAR a=SELECTEDVALUE('Ad allocation'[Value],0.50)
VAR p1=p0*(1+lift)
VAR r=DIVIDE(a,1-a)
VAR pb=DIVIDE(p0+r*p1,1+r)
VAR za=NORM.S.INV(0.975)
VAR zb=NORM.S.INV(pw)
VAR n0=ROUNDUP(DIVIDE(POWER(za*SQRT((1+1/r)*pb*(1-pb))+zb*SQRT(p0*(1-p0)+p1*(1-p1)/r),2),POWER(p1-p0,2)),0)
RETURN IF(p1<1,n0)'''
new=[('Required PSA users',formula,'#,0'),('Required ad users',"ROUNDUP([Required PSA users]*DIVIDE(SELECTEDVALUE('Ad allocation'[Value],0.5),1-SELECTEDVALUE('Ad allocation'[Value],0.5)),0)",'#,0'),('Required experiment users','[Required PSA users]+[Required ad users]','#,0'),('Curve total users',formula.replace("SELECTEDVALUE('Target lift'[Value],0.20)","SELECTEDVALUE('Lift curve'[Value],0.20)").replace('RETURN IF(p1<1,n0)','RETURN IF(p1<1,n0+ROUNDUP(n0*r,0))'),'#,0')]
model['model']['tables'][0]['measures'] += [{'name':n,'expression':e,'formatString':f,'lineageTag':uid()} for n,e,f in new]
dump(M/'model.bim',model)
def parameter(name,x,title,default):
    slug=name.replace(' ','_')
    visual('planning',slug+'_input','revenue_trend',x,150,336,120,title=title)
    path=R/f'definition/pages/planning/visuals/{slug}_input/visual.json';v=read(path);vv=v['visual'];vv['visualType']='slicer'
    vv['query']={'queryState':{'Values':{'projections':[field('Value',name)]}}}
    filt={'Version':2,'From':[{'Name':'p','Entity':name,'Type':0}],'Where':[{'Condition':{'In':{'Expressions':[{'Column':{'Expression':{'SourceRef':{'Source':'p'}},'Property':'Value'}}],'Values':[[{'Literal':{'Value':str(default)+'D'}}]]}}}]}
    vv['objects']={'data':[{'properties':{'mode':lit("'Dropdown'")}}],'selection':[{'properties':{'singleSelect':lit('true'),'selectAllCheckboxEnabled':lit('false')}}],'general':[{'properties':{'filter':{'filter':filt}}}]}
    dump(path,v)
for i,(name,title,default) in enumerate([('Baseline','BASELINE CONVERSION',.018),('Target lift','TARGET RELATIVE LIFT',.2),('Power','STATISTICAL POWER',.8),('Ad allocation','ALLOCATION TO ADS',.5)]):parameter(name,24+352*i,title,default)
text('planning','header',24,18,1392,64,'EXPERIMENT DESIGN SIMULATOR',28,True)
text('planning','subtitle',24,94,1392,42,'Change any input | Sample sizes update immediately | Two-sided alpha = 5%',14)
for i,(n,m,title) in enumerate([('total','Required experiment users','TOTAL USERS REQUIRED'),('control','Required PSA users','PSA USERS'),('treatment','Required ad users','AD USERS')]):card('planning',n,24+i*472,302,448,128,m,title)
visual('planning','curve','revenue_trend',24,464,1392,300,title='SENSITIVITY | REQUIRED USERS BY RELATIVE LIFT')
path=R/'definition/pages/planning/visuals/curve/visual.json';v=read(path);vv=v['visual'];vv['query']={'queryState':{'Category':{'projections':[field('Value','Lift curve')]},'Y':{'projections':[proj('Curve total users')]}},'sortDefinition':{'sort':[{'field':field('Value','Lift curve')['field'],'direction':'Ascending'}],'isDefaultSort':True}};vv['objects'].pop('dataPoint',None);dump(path,v)
text('planning','scope',24,788,1392,52,'Normal approximation; independent users, fixed horizon, no attrition. Curve varies lift; other inputs follow your selections.',14)
text('planning','footer',24,850,1392,34,'Choose an input from each dropdown. Defaults: 1.8% baseline / 20% relative lift / 80% power / 50% ads.',11)
# Keep only evidence that is useful at a glance; data quality remains in the report.
for n in ['missing','duplicates','excluded','fisher']:
    shutil.rmtree(R/f'definition/pages/inference/visuals/{n}')
for n,x,w in [('pvalue',24,448),('rr',496,448),('variance',968,448)]:
    path=R/f'definition/pages/inference/visuals/{n}/visual.json';v=read(path);v['position'].update(x=x,y=160,width=w,height=114);dump(path,v)
for n in ['allocation','confidence']:
    path=R/f'definition/pages/inference/visuals/{n}/visual.json';v=read(path);v['position'].update(y=310,height=460);dump(path,v)
# Exposure is descriptive: remove subgroup lift and average frequency cards.
for n in ['average','rel']:shutil.rmtree(R/f'definition/pages/exposure/visuals/{n}')
for n,x in [('users',24),('impressions',496)]:
    path=R/f'definition/pages/exposure/visuals/{n}/visual.json';v=read(path);v['position'].update(x=x,y=252,width=448,height=102);dump(path,v)
text('exposure','warning',24,154,1038,76,'OBSERVATIONAL ASSOCIATION / More exposure does not prove more conversions',20,True)
text('exposure','subtitle',24,94,1038,42,'Exposure was not randomized | Explore patterns, not a causal dose response',14)
for n in ['frequency_rate','frequency_impressions']:
    path=R/f'definition/pages/exposure/visuals/{n}/visual.json';v=read(path);v['position'].update(y=384,height=320);dump(path,v)
text('exposure','scope',24,802,1392,46,'Engagement and targeting can affect both exposure and conversion. Test randomized frequency caps before changing delivery.',14)
print('v4 simulator and leaner observational dashboard created')
