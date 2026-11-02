"""Reproducible marketing A/B analysis. Run from the repository root."""
import sys, pathlib, json, sqlite3, hashlib, math
ROOT = pathlib.Path(__file__).resolve().parents[2]
# Install dependencies from requirements.txt.
import numpy as np
import pandas as pd
from scipy import stats, optimize, special

P = ROOT / 'marketing'
OUT = P / 'output'
OUT.mkdir(exist_ok=True)
DAYS = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
SOURCE = 'https://www.kaggle.com/datasets/faviovaz/marketing-ab-testing'
raw = pd.read_csv(P/'data/marketing_AB.csv')
df = raw.rename(columns={'user id':'user_id','test group':'test_group','total ads':'total_ads','most ads day':'peak_day','most ads hour':'peak_hour'}).drop(columns='Unnamed: 0')
df['converted'] = df.converted.astype(int)
assert not df.isna().any().any()
assert df.user_id.is_unique
assert set(df.test_group)=={'ad','psa'} and set(df.converted)=={0,1}
assert df.peak_hour.between(0,23).all() and df.total_ads.ge(0).all()
assert set(df.peak_day)==set(DAYS)
bins = [-1,0,5,10,20,50,100,200,np.inf]
labels = ['00 | 0','01 | 1-5','02 | 6-10','03 | 11-20','04 | 21-50','05 | 51-100','06 | 101-200','07 | 201+']
df['frequency_band'] = pd.cut(df.total_ads,bins,labels=labels).astype(str)
df['day_order'] = df.peak_day.map({d:i+1 for i,d in enumerate(DAYS)})
df['variant'] = df.test_group.map({'psa':'A | PSA control','ad':'B | Product ads'})
df.to_csv(P/'data/marketing_clean.csv',index=False)
con = sqlite3.connect(P/'data/marketing.sqlite')
raw.to_sql('raw_marketing',con,if_exists='replace',index=False)
df.to_sql('marketing',con,if_exists='replace',index=False)
con.execute('CREATE INDEX IF NOT EXISTS idx_group ON marketing(test_group)')

def wilson(c,n):
    z=stats.norm.ppf(.975);p=c/n;den=1+z*z/n
    mid=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return mid-half,mid+half

def effect(a,b):
    """a=PSA, b=ad; Newcombe hybrid score interval, uncorrected Wilson."""
    na,ca=int(a['users']),int(a['conversions']);nb,cb=int(b['users']),int(b['conversions'])
    pa,pb=ca/na,cb/nb;d=pb-pa;pool=(ca+cb)/(na+nb)
    se0=math.sqrt(pool*(1-pool)*(1/na+1/nb));se=math.sqrt(pa*(1-pa)/na+pb*(1-pb)/nb)
    la,ua=wilson(ca,na);lb,ub=wilson(cb,nb)
    lo=d-math.sqrt((pb-lb)**2+(ua-pa)**2);hi=d+math.sqrt((ub-pb)**2+(pa-la)**2)
    rr=pb/pa if pa else float('nan')
    rrse=math.sqrt(1/cb-1/nb+1/ca-1/na) if min(ca,cb)>0 else float('nan')
    z=d/se0
    return dict(n_psa=na,n_ad=nb,c_psa=ca,c_ad=cb,p_psa=pa,p_ad=pb,delta=d,ci_low=lo,ci_high=hi,
                relative_lift=rr-1,risk_ratio=rr,rr_low=math.exp(math.log(rr)-1.959964*rrse) if pa else None,
                rr_high=math.exp(math.log(rr)+1.959964*rrse) if pa else None,z=z,p_value=2*stats.norm.sf(abs(z)),
                wald_low=d-1.959964*se,wald_high=d+1.959964*se,psa_low=la,psa_high=ua,ad_low=lb,ad_high=ub)

arm=df.groupby('test_group').agg(users=('user_id','size'),conversions=('converted','sum'),impressions=('total_ads','sum'))
s=effect(arm.loc['psa'],arm.loc['ad'])
s['fisher_p']=stats.fisher_exact([[s['c_ad'],s['n_ad']-s['c_ad']],[s['c_psa'],s['n_psa']-s['c_psa']]]).pvalue
s['chi2_p']=stats.chi2_contingency([[s['c_ad'],s['n_ad']-s['c_ad']],[s['c_psa'],s['n_psa']-s['c_psa']]],correction=False).pvalue
s['ad_share']=s['n_ad']/len(df)
s['srm_96_4_p']=stats.chisquare([s['n_psa'],s['n_ad']],f_exp=[len(df)*.04,len(df)*.96]).pvalue
s['srm_50_50_p']=stats.chisquare([s['n_psa'],s['n_ad']]).pvalue
rng=np.random.default_rng(20261101)
boot=rng.binomial(s['n_ad'],s['p_ad'],100000)/s['n_ad']-rng.binomial(s['n_psa'],s['p_psa'],100000)/s['n_psa']
s['bootstrap_low'],s['bootstrap_high']=np.quantile(boot,[.025,.975]).tolist()
s['incremental_ad']=s['delta']*s['n_ad'];s['incremental_low']=s['ci_low']*s['n_ad'];s['incremental_high']=s['ci_high']*s['n_ad']
s['attributable_fraction']=s['delta']/s['p_ad']
s['number_needed_expose']=1/s['delta']
s['variance_psa_share']=(s['p_psa']*(1-s['p_psa'])/s['n_psa'])/(s['p_psa']*(1-s['p_psa'])/s['n_psa']+s['p_ad']*(1-s['p_ad'])/s['n_ad'])
s['impressions_ad']=int(arm.loc['ad','impressions'])
s['cpm_break_even_per_unit_margin']=1000*s['incremental_ad']/s['impressions_ad']

def segment(field):
    rows=[]
    for val,g in df.groupby(field,observed=True):
        t=g.groupby('test_group').agg(users=('user_id','size'),conversions=('converted','sum'))
        if {'ad','psa'}<=set(t.index):
            e=effect(t.loc['psa'],t.loc['ad'])
            # Exact tests avoid unreliable score approximations in sparse overnight cells.
            e['z_p_value']=e['p_value']
            e['p_value']=stats.fisher_exact([[e['c_ad'],e['n_ad']-e['c_ad']],[e['c_psa'],e['n_psa']-e['c_psa']]]).pvalue
            rows.append({'segment':val,**e})
    return pd.DataFrame(rows)

days=segment('peak_day');days['order']=days.segment.map({d:i for i,d in enumerate(DAYS)});days=days.sort_values('order')
hours=segment('peak_hour').sort_values('segment');freq=segment('frequency_band').sort_values('segment')
tests=pd.concat([days.assign(family='weekday'),hours.assign(family='hour')],ignore_index=True).sort_values('p_value')
tests['holm_p']=np.minimum(1,np.maximum.accumulate(tests.p_value.to_numpy()*(len(tests)-np.arange(len(tests)))))
for t,fam in [(days,'weekday'),(hours,'hour')]:
    t['holm_p']=t.segment.map(tests[tests.family==fam].set_index('segment').holm_p)
    t['sparse']=((t.c_psa<10)|(t.c_ad<10)).astype(int)

def interaction(field):
    """Binomial logistic likelihood ratio: common log odds ratio vs category interactions."""
    a=df.groupby([field,'test_group']).converted.agg(['size','sum']).reset_index()
    cats=pd.get_dummies(a[field],drop_first=True,dtype=float).to_numpy();t=(a.test_group=='ad').astype(float).to_numpy()
    X=np.column_stack([np.ones(len(a)),t,cats]);n=a['size'].to_numpy();y=a['sum'].to_numpy()
    def fit(x):
        def objective(b):
            eta=x@b
            return float(np.sum(n*np.logaddexp(0,eta)-y*eta)), x.T@(n*special.expit(eta)-y)
        opt=optimize.minimize(objective,np.zeros(x.shape[1]),jac=True,method='L-BFGS-B',options={'ftol':1e-13,'gtol':1e-6,'maxiter':2000,'maxls':50})
        if not opt.success: raise RuntimeError(opt.message)
        return opt.fun
    null=fit(X)
    # Saturated grouped model has one parameter per category and group; direct log likelihood.
    p=y/n;ll=np.sum(special.xlogy(y,p)+special.xlogy(n-y,1-p))
    lr=max(0,2*(null+ll));k=len(a[field].unique())-1
    return {'field':field,'lr':lr,'df':k,'p':stats.chi2.sf(lr,k),'scale':'odds-ratio interaction; exploratory'}

heterogeneity=[interaction('peak_day'),interaction('peak_hour')]
hp=np.array([h['p'] for h in heterogeneity]);ix=np.argsort(hp);adj=np.minimum(1,np.maximum.accumulate(hp[ix]*np.arange(2,0,-1)))
for i,j in enumerate(ix):heterogeneity[j]['holm_p']=float(adj[i])
dist=df.groupby('test_group').total_ads.describe(percentiles=[.5,.9,.95,.99]).reset_index()
cut=float(df.total_ads.quantile(.99));trim=df[df.total_ads<=cut]
tt=trim.groupby('test_group').agg(users=('user_id','size'),conversions=('converted','sum'));sensitivity=effect(tt.loc['psa'],tt.loc['ad'])
s['p99_exposure']=cut;s['above_p99_users']=int((df.total_ads>cut).sum());s['above_p99_impression_share']=float(df.loc[df.total_ads>cut,'total_ads'].sum()/df.total_ads.sum())
s['smd_exposure']=float((df[df.test_group=='ad'].total_ads.mean()-df[df.test_group=='psa'].total_ads.mean())/math.sqrt((df[df.test_group=='ad'].total_ads.var()+df[df.test_group=='psa'].total_ads.var())/2))
q=[]
def query(title,question,sql,interpretation):
    r=pd.read_sql_query(sql,con);num=len(q)+1
    r.to_csv(OUT/f'queries/{num:02d}.csv',index=False)
    q.append(dict(number=num,title=title,question=question,sql=sql,interpretation=interpretation,columns=list(r.columns),rows=r.astype(object).where(pd.notna(r),None).values.tolist()))
(OUT/'queries').mkdir(exist_ok=True)
query('Source schema','Which fields were actually supplied?','PRAGMA table_info(raw_marketing);','Seven source columns include an exported index. The index is not a user characteristic or experimental variable.')
query('Source coverage','What is the analysis unit and how many outcomes exist?', '''SELECT COUNT(*) rows, COUNT(DISTINCT "user id") users,
SUM(converted) conversions FROM raw_marketing;''','588,101 rows correspond to 588,101 distinct users and 14,843 conversions. No repeated-user aggregation is needed.')
query('Missingness','Are exclusions needed for missing source values?', '''SELECT SUM("user id" IS NULL) user_null,
SUM("test group" IS NULL) group_null, SUM(converted IS NULL) converted_null,
SUM("total ads" IS NULL) ads_null, SUM("most ads day" IS NULL) day_null,
SUM("most ads hour" IS NULL) hour_null FROM raw_marketing;''','All six meaningful fields are complete. Zero rows are excluded for missingness.')
query('Duplicate user IDs','Could repeated users violate the independent-user analysis?', '''SELECT COUNT(*) duplicate_users, COALESCE(SUM(n-1),0) extra_rows
FROM (SELECT user_id,COUNT(*) n FROM marketing GROUP BY user_id HAVING COUNT(*)>1);''','No duplicate user identifiers were found. Independence still relies on user identity and assignment being correctly recorded; one row per ID cannot verify household or device interference.')
query('Outcome and assignment categories','Are group labels and binary outcomes valid?', '''SELECT test_group,converted,COUNT(*) users FROM marketing
GROUP BY test_group,converted ORDER BY test_group,converted;''','Only ad/psa labels and 0/1 outcomes occur. Keep both converters and non-converters in the denominator.')
query('Range checks','Do exposure and time values fit their definitions?', '''SELECT MIN(total_ads) min_ads,MAX(total_ads) max_ads,
MIN(peak_hour) min_hour,MAX(peak_hour) max_hour,
SUM(total_ads<0 OR peak_hour NOT BETWEEN 0 AND 23) invalid_rows
FROM marketing;''','Ads range from 1 to 2,065 and hours from 0 to 23. Large exposure counts are not automatically errors; they remain in the primary comparison.')
query('Index audit','Is the extra index a usable analytical variable?', '''SELECT COUNT(*) rows,COUNT(DISTINCT "Unnamed: 0") distinct_index,
MIN("Unnamed: 0") first_index,MAX("Unnamed: 0") last_index
FROM raw_marketing;''','The index runs from 0 through 588,100. It is dropped during cleaning; there is no evidence it represents time or ordering of assignment.')
query('Cleaning reconciliation','Did preparation change outcomes or cohort size?', '''SELECT COUNT(*) users,COUNT(DISTINCT user_id) distinct_users,
SUM(converted) conversions,SUM(total_ads) impressions FROM marketing;''','All original users and outcomes are retained. Preparation renames fields, converts the Boolean outcome to 0/1, removes the index and adds derived labels. No outliers are discarded.')
query('Allocation','How unequal are the observed arm sizes?', '''SELECT test_group,COUNT(*) users,
1.0*COUNT(*)/(SELECT COUNT(*) FROM marketing) user_share
FROM marketing GROUP BY test_group;''',f"Ad users represent {s['ad_share']:.4%} of observations. Unequal allocation is not itself evidence of failure. A target split must be specified independently; 96/4 is only a diagnostic scenario here.")
query('Primary outcomes','What are the conversion rates and correct denominators?', '''SELECT test_group,COUNT(*) users,SUM(converted) conversions,
AVG(converted) conversion_rate FROM marketing GROUP BY test_group;''',f"The ad-minus-PSA difference is {s['delta']*100:.4f} percentage points, or {s['relative_lift']:.2%} relative lift. The smaller PSA arm governs most of the precision.")
query('Exposure volume','How much exposure is associated with each arm?', '''SELECT test_group,SUM(total_ads) impressions,AVG(total_ads) ads_per_user,
AVG(CASE WHEN converted=1 THEN total_ads END) ads_per_converter,
AVG(CASE WHEN converted=0 THEN total_ads END) ads_per_nonconverter
FROM marketing GROUP BY test_group;''','These are descriptive exposure summaries. Exposure may be affected by treatment, behavior and conversion; it cannot safely serve as a pre-treatment adjustment variable.')
query('Frequency-band outcomes','How does conversion vary with observed exposure?', '''SELECT frequency_band,test_group,COUNT(*) users,SUM(converted) conversions,
AVG(converted) rate,SUM(total_ads) impressions FROM marketing
GROUP BY frequency_band,test_group ORDER BY frequency_band,test_group;''','These bands were selected for readability, not optimized for significance. Different exposure bands contain different kinds of users; apparent dose-response does not establish a causal frequency effect.')
query('Weekday outcomes','How do rates vary by peak-exposure weekday?', '''SELECT day_order,peak_day,test_group,COUNT(*) users,
SUM(converted) conversions,AVG(converted) rate FROM marketing
GROUP BY day_order,peak_day,test_group ORDER BY day_order,test_group;''','Weekday means the day with the most ad exposure for that user. It is not the day of conversion, a dated cohort or a randomized scheduling treatment.')
query('Hour outcomes','What is the observed peak-hour conversion profile?', '''SELECT peak_hour,test_group,COUNT(*) users,SUM(converted) conversions,
AVG(converted) rate FROM marketing GROUP BY peak_hour,test_group
ORDER BY peak_hour,test_group;''','Use counts with rates. Sparse overnight PSA cells have noisy estimates, and selecting the highest observed hour would overstate certainty.')
query('Day-hour cells','What data support the heatmap?', '''SELECT day_order,peak_day,peak_hour,test_group,COUNT(*) users,
SUM(converted) conversions,AVG(converted) rate FROM marketing
GROUP BY day_order,peak_day,peak_hour,test_group
ORDER BY day_order,peak_hour,test_group;''','All populated day-hour-arm cells are shown. The report heatmap uses ad-arm conversion rates; it is an exploratory exposure-context display, not a scheduling recommendation.')
query('Sparse day-hour cells','Where should heatmap comparisons be treated cautiously?', '''SELECT test_group,COUNT(*) cells,SUM(n<100) cells_under_100_users,
SUM(c<10) cells_under_10_conversions FROM
(SELECT test_group,peak_day,peak_hour,COUNT(*) n,SUM(converted) c
FROM marketing GROUP BY test_group,peak_day,peak_hour) GROUP BY test_group;''','Low conversion counts, especially in the PSA arm, make fine-grained contrasts unstable. No 168-cell significance search is used to recommend a winning slot.')
query('Extreme exposures','How concentrated is the long tail?',f'''SELECT test_group,COUNT(*) users,SUM(total_ads) impressions,
SUM(converted) conversions FROM marketing WHERE total_ads>{cut}
GROUP BY test_group;''',f"Above the common 99th-percentile threshold ({cut:g} exposures), {s['above_p99_users']:,} users account for {s['above_p99_impression_share']:.2%} of all recorded impressions. Retain them for the primary test.")
query('Exposure-trim sensitivity','Does the sign persist after a common tail exclusion?',f'''SELECT test_group,COUNT(*) users,SUM(converted) conversions,
AVG(converted) rate FROM marketing WHERE total_ads<={cut}
GROUP BY test_group;''',f"The trimmed difference is {sensitivity['delta']*100:.4f} pp. This changes the population using a post-assignment variable; it is an influence diagnostic and cannot replace the full-cohort estimate.")
query('Outcome by exposure band share','How does the exposure mix differ between arms?', '''SELECT frequency_band,test_group,COUNT(*) users,
1.0*COUNT(*)/SUM(COUNT(*)) OVER(PARTITION BY test_group) within_arm_share
FROM marketing GROUP BY frequency_band,test_group ORDER BY frequency_band,test_group;''','Mix differences can explain descriptive patterns but are not baseline randomization balance checks. No pre-treatment covariates are supplied.')
query('Counterfactual conversion calculation','What would the ad arm produce at the PSA rate?', '''WITH a AS (SELECT COUNT(*) n,SUM(converted) c FROM marketing WHERE test_group='ad'),
p AS (SELECT AVG(converted) rate FROM marketing WHERE test_group='psa')
SELECT a.n ad_users,a.c observed_ad_conversions,p.rate psa_rate,
a.n*p.rate expected_at_psa_rate,a.c-a.n*p.rate modeled_incremental FROM a,p;''','This is a modeled counterfactual, not individually observed attribution. Its causal interpretation requires valid randomization, consistent measurement and no interference.')

# Derived statistical result tables remain queryable and are included in the workbook.
for t,name in [(days,'weekday_effects'),(hours,'hour_effects'),(freq,'frequency_effects')]:
    t.to_csv(OUT/f'{name}.csv',index=False);t.to_sql(name,con,if_exists='replace',index=False)
query('Weekday contrasts with multiplicity','Which weekday contrasts remain after a common correction?', '''SELECT segment weekday,n_psa,n_ad,delta*100 lift_pp,
ci_low*100 ci_low_pp,ci_high*100 ci_high_pp,p_value,holm_p
FROM weekday_effects ORDER BY "order";''','Intervals are pointwise 95% Newcombe intervals. Segment p-values use two-sided Fisher exact tests, including sparse hourly cells. Holm adjustment controls one exploratory family of 31 weekday/hour contrasts. Conditioning on peak day still limits causal interpretation.')
query('Hour contrasts with multiplicity','How much does multiple testing change hour-level evidence?', '''SELECT segment hour,n_psa,c_psa,n_ad,delta*100 lift_pp,
ci_low*100 ci_low_pp,ci_high*100 ci_high_pp,p_value,holm_p
FROM hour_effects ORDER BY segment;''','Two-sided Fisher exact p-values address within-segment ad-versus-PSA differences, not whether one hour has a larger effect than another. They avoid the small-cell z approximation. Formal interaction diagnostics are separate.')

# Prospective planning: normal approximation with distinct null and alternative variances.
def planned_n(p0,p1,ratio):
    pooled=(p0+ratio*p1)/(1+ratio)
    A=math.sqrt(pooled*(1-pooled)*(1+1/ratio))
    B=math.sqrt(p0*(1-p0)+p1*(1-p1)/ratio)
    nc=math.ceil(((stats.norm.ppf(.975)*A+stats.norm.ppf(.8)*B)/(p1-p0))**2)
    return nc,math.ceil(nc*ratio)
planning=[]
for rel in [.1,.2,.3]:
    for ratio,label in [(1,'50/50'),(24,'96/4')]:
        nc,nt=planned_n(s['p_psa'],s['p_psa']*(1+rel),ratio)
        planning.append(dict(relative_target=rel,absolute_target_pp=s['p_psa']*rel*100,allocation=label,n_psa=nc,n_ad=nt,total=nc+nt))
planning=pd.DataFrame(planning);planning.to_csv(OUT/'sample_size_planning.csv',index=False)
economics=[]
for margin in [10,25,50]:
    for cpm in [2,5,10]:
        cost=s['impressions_ad']/1000*cpm
        economics.append(dict(margin=margin,cpm=cpm,ad_cost=cost,incremental_margin=s['incremental_ad']*margin,
                              net=s['incremental_ad']*margin-cost,net_low=s['incremental_low']*margin-cost,net_high=s['incremental_high']*margin-cost))
economics=pd.DataFrame(economics);economics.to_csv(OUT/'illustrative_economics.csv',index=False)
cells=df.groupby(['variant','day_order','peak_day','peak_hour','frequency_band'],observed=True).agg(Users=('user_id','size'),Conversions=('converted','sum'),Impressions=('total_ads','sum')).reset_index()
cells=cells.rename(columns={'variant':'Variant','day_order':'Day order','peak_day':'Peak day','peak_hour':'Peak hour','frequency_band':'Frequency band'})
cells.to_csv(OUT/'powerbi/marketing_cube.csv',index=False)
assert cells.Users.sum()==len(df) and cells.Conversions.sum()==int(df.converted.sum())
assert cells.Impressions.sum()==int(df.total_ads.sum())
summary=dict(source=SOURCE,download_date='2026-11-01',sha256=hashlib.sha256((P/'data/marketing_AB.csv').read_bytes()).hexdigest(),
             rows=len(df),excluded=0,primary=s,exposure_sensitivity=sensitivity,heterogeneity=heterogeneity,
             weekday_significant_holm=int((days.holm_p<.05).sum()),hour_significant_holm=int((hours.holm_p<.05).sum()),
             methods=dict(primary='two-sided pooled two-proportion z-test, alpha .05',ci='Newcombe hybrid Wilson, uncorrected',seed=20261101,bootstrap_draws=100000),
             versions=dict(pandas=pd.__version__,numpy=np.__version__))
(OUT/'results.json').write_text(json.dumps(summary,indent=2,default=lambda x:x.item()),encoding='utf-8')
(OUT/'investigations.json').write_text(json.dumps(q,indent=2,default=lambda x:x.item()),encoding='utf-8')
(P/'src/investigation.sql').write_text('\n\n'.join(f"-- {x['number']:02d}. {x['title']}\n-- {x['question']}\n{x['sql']}" for x in q),encoding='utf-8')
print(json.dumps(summary,indent=2,default=lambda x:x.item()))
