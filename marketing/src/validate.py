from pathlib import Path
import sys,json,sqlite3,math
R=Path(__file__).resolve().parents[2]
import pandas as pd
from scipy import stats
P=R/'marketing';s=json.loads((P/'output/results.json').read_text())['primary'];c=sqlite3.connect(P/'data/marketing.sqlite')
r=pd.read_sql_query('SELECT test_group,COUNT(*) n,SUM(converted) c,SUM(total_ads) ads FROM marketing GROUP BY test_group',c).set_index('test_group')
assert int(r.loc['ad','n'])==s['n_ad'] and int(r.loc['psa','c'])==s['c_psa']
assert abs(s['chi2_p']-s['p_value'])<1e-25
assert abs(s['p_ad']-s['p_psa']-s['delta'])<1e-15
assert s['ci_low']<s['delta']<s['ci_high']
assert s['bootstrap_low']<s['delta']<s['bootstrap_high']
cube=pd.read_csv(P/'output/powerbi/marketing_cube.csv');assert cube.Users.sum()==588101 and cube.Conversions.sum()==14843
assert cube.Impressions.sum()==r.ads.sum()
for name in ['weekday_effects','hour_effects']:
 d=pd.read_csv(P/f'output/{name}.csv');assert d.n_psa.sum()==23524 and d.n_ad.sum()==564577;assert d.holm_p.ge(d.p_value-1e-14).all()
for row in pd.read_csv(P/'output/sample_size_planning.csv').itertuples():
 p0=s['p_psa'];p1=p0*(1+row.relative_target);ratio=row.n_ad/row.n_psa;pooled=(p0+ratio*p1)/(1+ratio)
 se0=math.sqrt(pooled*(1-pooled)*(1/row.n_psa+1/row.n_ad));se1=math.sqrt(p0*(1-p0)/row.n_psa+p1*(1-p1)/row.n_ad)
 power=stats.norm.sf((stats.norm.ppf(.975)*se0-(p1-p0))/se1)+stats.norm.cdf((-stats.norm.ppf(.975)*se0-(p1-p0))/se1)
 assert .7999<power<.801,(row,power)
print('Validated SQL/Python totals, dashboard cube, test equivalence, Holm monotonic bounds, and prospective 80% power.')
