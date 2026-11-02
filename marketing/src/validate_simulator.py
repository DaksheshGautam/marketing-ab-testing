"""Independent numerical checks for the final dashboard planning measures."""
from math import sqrt,ceil
from statistics import NormalDist
from pathlib import Path
import json
N=NormalDist()
def sample(p=.018,lift=.2,power=.8,ad_share=.5):
    assert 0<p<1 and lift>0 and p*(1+lift)<1
    assert .5<power<1 and 0<ad_share<1
    p1=p*(1+lift);r=ad_share/(1-ad_share);pooled=(p+r*p1)/(1+r)
    n0=ceil(((N.inv_cdf(.975)*sqrt((1+1/r)*pooled*(1-pooled))+N.inv_cdf(power)*sqrt(p*(1-p)+p1*(1-p1)/r))/(p1-p))**2)
    n1=ceil(n0*r)
    return n0,n1,n0+n1
checks=[({},(23507,23507,47014)),({'power':.9},(31469,31469,62938)),({'lift':.4},(6399,6399,12798)),({'ad_share':.96},(12626,303024,315650)),({'p':.02},(21109,21109,42218))]
for inputs,expected in checks:
    actual=sample(**inputs)
    assert actual==expected,(inputs,actual,expected)
    print(inputs or 'defaults',actual)
root=Path(__file__).resolve().parents[2]
model=json.loads((root/'marketing/output/powerbi/Marketing Experiment v4.SemanticModel/model.bim').read_text())
names={t['name'] for t in model['model']['tables']}
assert {'Baseline','Target lift','Power','Ad allocation','Lift curve'}<=names
print('Validated all four simulator inputs and five reference scenarios.')
