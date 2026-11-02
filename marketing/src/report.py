"""Create the in-depth report and the complete investigation PDF."""
import sys,pathlib,json,math,textwrap
ROOT=pathlib.Path(__file__).resolve().parents[2];P=ROOT/'marketing';O=P/'output';T=P/'tmp';T.mkdir(parents=True,exist_ok=True)
# Use the active Python environment; see requirements.txt.
import pandas as pd
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak,Preformatted,KeepTogether
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from xml.sax.saxutils import escape

j=json.loads((O/'results.json').read_text());s=j['primary'];sen=j['exposure_sensitivity']
SOURCE=j['source']
d=pd.read_csv(P/'data/marketing_clean.csv');day=pd.read_csv(O/'weekday_effects.csv');hour=pd.read_csv(O/'hour_effects.csv');freq=pd.read_csv(O/'frequency_effects.csv')
plan=pd.read_csv(O/'sample_size_planning.csv');econ=pd.read_csv(O/'illustrative_economics.csv');inv=json.loads((O/'investigations.json').read_text())
NAVY='#17324D';TEAL='#168C92';AMBER='#E59B45';GRAY='#65758B';LIGHT='#F2F6F8'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.labelcolor':NAVY,'text.color':NAVY,'axes.titleweight':'bold','grid.alpha':.2})
def chart(name):
    plt.tight_layout();plt.savefig(T/(name+'.png'),dpi=180,bbox_inches='tight');plt.close()
fig,ax=plt.subplots(figsize=(9,3.1));rates=np.array([s['p_psa'],s['p_ad']])*100
ax.bar(['PSA control','Product ads'],rates,color=[TEAL,AMBER],width=.5)
ax.errorbar([0,1],rates,yerr=[rates-np.array([s['psa_low'],s['ad_low']])*100,np.array([s['psa_high'],s['ad_high']])*100-rates],fmt='none',color=NAVY,capsize=5)
ax.set_ylim(0,3);ax.set_ylabel('Converted users (%)');ax.bar_label(ax.containers[0],fmt='%.3f%%',padding=17);chart('rates')
fig,ax=plt.subplots(figsize=(9,3.0))
for g,c in [('psa',TEAL),('ad',AMBER)]:
    vals=d.loc[d.test_group==g,'total_ads'].to_numpy();ax.hist(vals,bins=np.geomspace(1,2100,45),weights=np.ones(len(vals))/len(vals),histtype='step',linewidth=1.7,label=g.upper(),color=c)
ax.set_xscale('log');ax.yaxis.set_major_formatter(PercentFormatter(1));ax.set_xlabel('Total ads per user (logarithmic scale)');ax.set_ylabel('Share within arm');ax.legend(frameon=False);chart('exposure')
fig,ax=plt.subplots(figsize=(9,3.4));x=np.arange(len(freq))
for name,c,offset in [('psa',TEAL,-.09),('ad',AMBER,.09)]:
    p=freq['p_'+name].to_numpy()*100;lo=freq[name+'_low'].to_numpy()*100;hi=freq[name+'_high'].to_numpy()*100
    ax.errorbar(x+offset,p,yerr=[p-lo,hi-p],fmt='o-',capsize=3,color=c,label=name.upper())
ax.set_xticks(x,[v.split(' | ')[1] for v in freq.segment]);ax.set_xlabel('Observed total-ads band');ax.set_ylabel('Conversion (%)');ax.legend(frameon=False);chart('frequency')
fig,ax=plt.subplots(figsize=(9,3.2));y=np.arange(len(day));v=day.delta.to_numpy()*100
ax.errorbar(v,y,xerr=[v-day.ci_low.to_numpy()*100,day.ci_high.to_numpy()*100-v],fmt='o',color=TEAL,capsize=4)
ax.set_yticks(y,day.segment);ax.invert_yaxis();ax.axvline(0,color=GRAY,linewidth=1);ax.set_xlabel('Ad minus PSA conversion (percentage points) | pointwise 95% CI');chart('weekday')
fig,ax=plt.subplots(figsize=(9,3.1))
for g,c in [('psa',TEAL),('ad',AMBER)]:
    ax.plot(hour.segment,hour['p_'+g]*100,marker='o',markersize=3,color=c,label=g.upper())
ax.set_xticks(range(0,24,2));ax.set_ylabel('Conversion (%)');ax.set_xlabel('User peak-exposure hour (not conversion hour)');ax.legend(frameon=False);chart('hour')
DAYS=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
hm=d[d.test_group=='ad'].pivot_table(index='peak_day',columns='peak_hour',values='converted',aggfunc='mean').reindex(DAYS)*100
fig,ax=plt.subplots(figsize=(10,3.5));im=ax.imshow(hm.to_numpy(),aspect='auto',cmap='YlGnBu',vmin=0,vmax=np.nanquantile(hm,.98));ax.set_yticks(range(7),DAYS);ax.set_xticks(range(0,24,2));ax.set_xlabel('Peak-exposure hour');fig.colorbar(im,ax=ax,label='Ad-arm conversion (%)');chart('heatmap')
fig,ax=plt.subplots(figsize=(9,3.0));r=plan.pivot(index='relative_target',columns='allocation',values='total');r.index=[f'{x:.0%}' for x in r.index];r.plot.bar(ax=ax,color=[TEAL,AMBER],rot=0);ax.set_ylabel('Required total users');ax.set_xlabel('Target relative improvement over PSA baseline');ax.legend(title='Ad / PSA allocation',frameon=False);chart('planning')

styles=getSampleStyleSheet()
styles['BodyText'].fontSize=10;styles['BodyText'].leading=14.5;styles['BodyText'].spaceAfter=8
for k in ['Title','Heading1','Heading2','Heading3']:styles[k].textColor=colors.HexColor(NAVY)
styles['Title'].fontSize=30;styles['Title'].leading=34;styles['Title'].alignment=0
styles['Heading1'].fontSize=20;styles['Heading1'].leading=25;styles['Heading1'].spaceAfter=14
styles['Heading2'].fontSize=12;styles['Heading2'].leading=17;styles['Heading2'].spaceBefore=10
styles.add(ParagraphStyle(name='Deck',fontSize=12,leading=18,textColor=colors.HexColor(GRAY),spaceAfter=16))
styles.add(ParagraphStyle(name='Small',fontSize=8.2,leading=11,textColor=colors.HexColor(GRAY),spaceAfter=6))
styles.add(ParagraphStyle(name='Cell',fontSize=8.2,leading=11))
styles.add(ParagraphStyle(name='TH',fontSize=8.2,leading=11,fontName='Helvetica-Bold',textColor=colors.white))
def p(t,style='BodyText'):return Paragraph(t,styles[style])
def table(rows,widths=None):
    rows=[[Paragraph(escape(str(v)),styles['TH' if i==0 else 'Cell']) for v in row] for i,row in enumerate(rows)]
    t=Table(rows,colWidths=widths or [511/len(rows[0])]*len(rows[0]),repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(NAVY)),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor(LIGHT),colors.white]),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]));return t
def fig(n,h=185):return Image(str(T/(n+'.png')),width=511,height=h)
def pp(x):return f'{x*100:+.3f} pp'
def pv(x):return f'{x:.3g}'
def fmt(x):
    if x is None:return 'NULL'
    if isinstance(x,float):
        if x==int(x):return f'{int(x):,}'
        return f'{x:.6g}'
    return str(x)
def footer(c,doc):
    c.setStrokeColor(colors.HexColor(TEAL));c.line(42,40,553,40);c.setFont('Helvetica',8);c.setFillColor(colors.HexColor(GRAY));c.drawString(42,27,'Marketing A/B testing  |  Final export aligned  |  02 Nov 2026');c.drawRightString(553,27,str(doc.page))
def build(name,story):SimpleDocTemplate(str(O/'pdf'/name),pagesize=(595,842),leftMargin=42,rightMargin=42,topMargin=42,bottomMargin=54).build(story,onFirstPage=footer,onLaterPages=footer)
story=[]
def page(title,items):
    if story:story.append(PageBreak())
    story.extend([p(title,'Heading1')]+items)

page('Marketing A/B testing',[
 p('An in-depth evaluation of product advertising versus a public-service-announcement holdout','Deck'),
 p('Decision: evidence supports conversion lift; profitability remains unproven','Heading2'),
 p(f"Across {j['rows']:,} users, product ads converted at {s['p_ad']:.3%}, compared with {s['p_psa']:.3%} for PSA. The difference is <b>{pp(s['delta'])}</b>, equivalent to <b>{s['relative_lift']:.2%} relative lift</b>. The 95% Newcombe interval is [{s['ci_low']*100:.3f}, {s['ci_high']*100:.3f}] percentage points."),
 table([['Metric','PSA control','Product ads'],['Users',f"{s['n_psa']:,}",f"{s['n_ad']:,}"],['Converted',f"{s['c_psa']:,}",f"{s['c_ad']:,}"],['Conversion',f"{s['p_psa']:.3%}",f"{s['p_ad']:.3%}"]],[215,148,148]),
 Spacer(1,10),fig('rates',175),
 p(f"The two-sided pooled z-test gives p = {pv(s['p_value'])}. This is strong statistical evidence of different recorded conversion rates, under independent-user assumptions. Causal attribution remains conditional on the original experiment's assignment and measurement being valid."),
 p('Operational recommendation','Heading2'),p('Preserve a randomized holdout while validating assignment, the conversion window and campaign costs. Do not optimize ad frequency or scheduling from these observational exposure fields alone. Obtain contribution margin and impression cost before deciding whether to scale spend.'),
 p('Scope: all source users retained; no synthetic revenue, demographics, timestamps or funnel stages added.','Small')])
page('01 / Design, estimand and available evidence',[
 p('Business question','Heading2'),p('Does product advertising improve the probability that a user converts compared with showing a PSA? The primary estimand is the difference in user-level conversion probabilities, ad minus PSA, over the file\'s unspecified observation window.'),
 table([['Source field','Role and interpretation'],['user id','Unit identifier. One distinct ID per row.'],['test group','Observed arm: ad or psa. Assignment logs are unavailable.'],['converted','User-level binary outcome; the dataset describes purchase conversion.'],['total ads','Observed exposure count. Potentially post-assignment and post-conversion.'],['most ads day','Weekday with most exposure, not a dated event or purchase day.'],['most ads hour','Hour with most exposure, not conversion time.'],['Unnamed: 0','Exported row index; dropped from analytical fields.']],[130,381]),
 p('What the file can and cannot establish','Heading2'),p('One row per ID supports a user-level analysis. However, the file does not expose assignment timestamps, eligibility, failed deliveries, identity resolution, overlap across devices, conversion lag, the planned allocation, trial duration or the stopping rule. It therefore supports a comparison by recorded arm, not an independently verified intention-to-treat reconstruction.'),
 p('Why the distinction matters','Heading2'),p('If assignment was randomized and retained through follow-up, the arm comparison can estimate incremental advertising impact. If the arm label reflects who actually received an ad after selection or delivery, selection bias may remain. Statistical significance does not resolve that design uncertainty.'),
 p('Analysis hierarchy','Heading2'),p('Primary: full-cohort ad-versus-PSA rate comparison. Secondary: alternative inferential calculations. Exploratory: weekday, hour and frequency patterns. Scenario analysis: economic break-even and prospective sample size. These roles were chosen for this retrospective project, not claimed as a preregistered protocol.')])
page('02 / Data audit and allocation validity',[
 table([['Audit','Observed result','Action'],['Source coverage','588,101 rows; 588,101 IDs','Retain every user'],['Missing meaningful values','0','No missing-value exclusions'],['Duplicate user IDs','0','No deduplication'],['Outcome categories','0 and 1','Convert Boolean to integer'],['Group categories','ad and psa','No relabeling exclusions'],['Exposure count','1 to 2,065','Keep tail in primary estimate'],['Peak hour / weekday','0-23 / seven weekdays','No invalid categories'],['Preparation exclusions','0','Only index removed']],[155,188,168]),
 p('The observed allocation is highly unequal','Heading2'),p(f"{s['n_ad']:,} ad users and {s['n_psa']:,} PSA users imply {s['ad_share']:.4%} in the ad arm. A 50/50 goodness-of-fit test rejects overwhelmingly, but that does not diagnose an error unless 50/50 was the intended design."),
 p(f"As an explicitly hypothetical design check, a 96/4 target yields p = {s['srm_96_4_p']:.4f}. Compatibility with that split is not evidence that 96/4 was actually planned. Testing against the observed split would be circular, so no such validation is claimed."),
 p('Precision is limited by the holdout','Heading2'),p(f"Although PSA is only {1-s['ad_share']:.2%} of users, it contributes about {s['variance_psa_share']:.1%} of the estimated variance of the rate difference. More treatment traffic cannot fully compensate for a small control group. A future trial should choose allocation using power, cost and opportunity-cost considerations."),
 p('No baseline balance claim','Heading2'),p('The dataset contains no confirmed pre-treatment covariates. Similar exposure-count averages cannot validate randomization because exposure may itself be affected by treatment or user behavior. Day/hour exposure mixes are likewise not baseline balance tests.')])
page('03 / Primary inference and effect size',[
 p('Hypotheses and assumptions','Heading2'),p('H0: p(ad) = p(PSA). H1: the probabilities differ. Use a two-sided pooled two-proportion z-test with alpha = 0.05. The user is the independent unit; the outcome is binary. Both arms have ample successes and failures for a large-sample comparison, despite unequal sizes.'),
 table([['Quantity','Estimate','Interpretation'],['Absolute difference',pp(s['delta']),'Additional conversions per eligible user'],['95% Newcombe interval',f"[{s['ci_low']*100:.3f}, {s['ci_high']*100:.3f}] pp",'Wilson-based difference interval'],['Relative lift',f"{s['relative_lift']:.2%}",'Difference divided by PSA rate'],['Risk ratio',f"{s['risk_ratio']:.3f}",f"95% log interval [{s['rr_low']:.3f}, {s['rr_high']:.3f}]"],['Pooled z statistic',f"{s['z']:.4f}",'Null uses a common pooled rate'],['Two-sided p-value',pv(s['p_value']),'Not the probability H0 is true']],[148,154,209]),
 p('Practical interpretation','Heading2'),p(f"For 10,000 comparable users, the point estimate is {s['delta']*10000:.1f} extra conversions; the 95% interval is approximately {s['ci_low']*10000:.1f} to {s['ci_high']*10000:.1f}. Relative lift sounds larger because the PSA baseline is only {s['p_psa']:.2%}; report absolute and relative measures together."),
 p('Interval choice and p-value','Heading2'),p('The primary interval uses the Newcombe hybrid score construction from separate Wilson intervals. This avoids relying solely on a Wald interval for proportions. The score-style pooled z-test and Newcombe interval are related large-sample tools but not exact algebraic inverses, so their numerical behavior need not match perfectly near a decision threshold.'),
 p('What this conclusion excludes','Heading2'),p('The result establishes neither profitability nor the optimal advertising dose. It does not identify which specific users converted because of advertising, and it cannot correct design or measurement bias that is absent from the file.')])
page('04 / Incrementality and economic decisions',[
 p('Counterfactual calculation','Heading2'),p(f"At the PSA rate, the {s['n_ad']:,} ad users would be expected to produce approximately {s['n_ad']*s['p_psa']:,.0f} conversions. The recorded ad count is {s['c_ad']:,}. Their difference is <b>{s['incremental_ad']:,.0f} modeled incremental conversions</b>, with a rate-interval scaling of [{s['incremental_low']:,.0f}, {s['incremental_high']:,.0f}]. This is conditional counterfactual attribution, not direct observation of individual causes."),
 p(f"Under the same causal assumptions, approximately {s['attributable_fraction']:.1%} of recorded ad-arm conversions are incremental relative to the PSA benchmark; the remainder would be expected under that benchmark. The reciprocal risk difference is roughly one additional conversion per {s['number_needed_expose']:.0f} assigned users; it is not the number of impressions required."),
 p('Illustrative contribution economics','Heading2'),p('The file contains no cost or order value. The following grid assumes a fixed contribution margin per incremental conversion and a CPM charged on all recorded ad-arm impressions. It excludes PSA cost, fixed creative costs, customer lifetime effects and differences in purchase value. All money units below are hypothetical.'),
 table([['Margin / incremental sale','CPM = 2','CPM = 5','CPM = 10']]+[[f'{m:,.0f}']+[f"{econ[(econ.margin==m)&(econ.cpm==c)].iloc[0].net:,.0f}" for c in [2,5,10]] for m in [10,25,50]],[175,112,112,112]),
 p('Cells show estimated incremental contribution less modeled ad cost. They are scenarios, not measured profit.','Small'),
 p('Break-even rule','Heading2'),p(f"Break-even CPM = incremental conversions x margin / ad impressions x 1,000. Here, that is about <b>{s['cpm_break_even_per_unit_margin']:.3f} x contribution margin</b>. A margin of 25 implies a point-estimate break-even CPM of {s['cpm_break_even_per_unit_margin']*25:.2f}; using the lower lift limit gives {1000*s['incremental_low']/s['impressions_ad']*25:.2f}. Confirm real costs and measurement before using either boundary."),
 p('Decision implication','Heading2'),p('Conversion efficacy is promising; a spend decision requires incremental contribution to exceed incremental campaign cost under a defensible causal design. The PSA comparison measures ads versus PSA exposure, not necessarily ads versus no marketing.')])
page('05 / Exposure distribution and the long tail',[
 fig('exposure',205),
 table([['Arm','Mean ads','Median','90th pct','99th pct','Maximum']]+[[g.upper(),f'{v.mean():.2f}',f'{v.median():.0f}',f'{v.quantile(.9):.0f}',f'{v.quantile(.99):.0f}',f'{v.max():,}'] for g in ['psa','ad'] for v in [d[d.test_group==g].total_ads]],[65,89,89,89,89,90]),
 p('Concentration matters for spend interpretation','Heading2'),p(f"The common 99th percentile is {s['p99_exposure']:.0f} ads. Only {s['above_p99_users']:,} users lie strictly above it, but they account for {s['above_p99_impression_share']:.2%} of all recorded exposures. Averages alone hide this long tail; impression costs can be concentrated in a small user subset."),
 p('Why these are not automatic exclusions','Heading2'),p('High exposure can be genuine repeated delivery. Removing users because they received many impressions selects on observed behavior or delivery after assignment. The primary comparison therefore retains the complete cohort. Any frequency cap recommendation needs a randomized policy test, not an arbitrary percentile cutoff.'),
 p('Why not adjust the main test for exposure?','Heading2'),p('A regression controlling for total ads, peak day or peak hour could block part of the treatment pathway or induce selection bias. Without timing and delivery context, those controls do not identify a better causal estimate. This project uses exposure variables for exploration rather than primary covariate adjustment.')])
page('06 / Frequency: an association, not a dose rule',[
 fig('frequency',205),
 table([['Ads band','PSA users','Ad users','PSA CVR','Ad CVR','Difference']]+[[r.segment.split(' | ')[1],f'{r.n_psa:,}',f'{r.n_ad:,}',f'{r.p_psa:.2%}',f'{r.p_ad:.2%}',pp(r.delta)] for r in freq.itertuples()],[73,83,83,85,85,102]),
 p('What the pattern shows','Heading2'),p('Ad-arm conversion rises from 0.25% in the 1-5 band to 17.68% in the 101-200 band, then is 15.58% at 201+. PSA conversion also rises sharply, reaching 15.50% at 201+. The apparent dose-response is therefore not exclusive to product advertising. It can reflect engagement, retargeting, repeated visits or longer time at risk. Exposure counted after purchase can reverse the apparent temporal ordering.'),
 p('What would answer the operational question','Heading2'),p('Randomize eligible users to frequency-cap policies, such as different maximum deliveries, while keeping outcome follow-up fixed. Analyze assigned policies, record delivered exposure separately, and compare incremental contribution and negative-experience guardrails. The chart alone does not identify an optimal cap or prove ad fatigue.')])
page('07 / Weekday patterns and uncertainty',[
 fig('weekday',190),
 table([['Peak weekday','PSA CVR','Ad CVR','Lift (pp)','PSA users','Holm p']]+[[r.segment,f'{r.p_psa:.2%}',f'{r.p_ad:.2%}',f'{r.delta*100:+.3f}',f'{r.n_psa:,}',pv(r.holm_p)] for r in day.itertuples()],[108,77,77,77,87,85]),
 p('Read the intervals before ranking weekdays','Heading2'),p(f"{j['weekday_significant_holm']} of seven within-weekday ad-versus-PSA contrasts remain significant after the shared 31-test Holm correction. Tuesday has the largest observed difference (+1.599 pp); Thursday has the smallest (+0.141 pp). The intervals above are pointwise 95% intervals, not simultaneous intervals. A larger point estimate is not itself proof of a larger causal effect."),
 p('Selection and timing limits','Heading2'),p('Peak weekday is selected from the user\'s realized exposure history. It is neither a randomly assigned delivery day nor the purchase day. Different groups within a weekday can contain different exposure histories. Use these patterns to formulate scheduling experiments, not to shift budget causally.'),
 p('Missing calendar information','Heading2'),p('There is no actual date, assignment time or conversion timestamp. We cannot estimate a weekly time trend, cumulative stopping path, seasonality, conversion lag or day-specific spend from this file.')])
page('08 / Hour patterns and day-hour exploration',[
 fig('hour',165),fig('heatmap',180),
 p('Interpretation','Heading2'),p(f"Hourly rates vary, and {j['hour_significant_holm']} of 24 within-hour contrasts survive the 31-test Holm correction. Overnight control cells contain relatively few conversions; fine-grained comparisons can be noisy. The ad-arm heatmap emphasizes observed conversion context, not incremental effect or profit by slot."),
 p('No winning-hour claim','Heading2'),p('Peak-exposure hour is not the hour of conversion. Selecting the maximum among 24 hours or 168 day-hour cells creates a winner\'s curse. No day-hour cell testing is used to designate an optimal schedule. The companion workbook includes cell denominators and sparse-cell diagnostics so the visual can be audited.'),
 p('Actionable follow-up','Heading2'),p('Test a small number of scheduling policies prospectively, randomize before delivery, and record eligibility, cost and fixed follow-up. Do not treat the heatmap as a measured return-on-ad-spend surface.')])
page('09 / Multiple testing and heterogeneity',[
 p('A separate primary claim and an exploratory family','Heading2'),p('The overall arm comparison is the primary test. The seven weekday and 24 hour comparisons form one exploratory family of 31 two-sided Fisher exact tests. Exact tests avoid relying on a z approximation in sparse hourly cells. Holm\'s step-down adjustment is applied across the entire family and controls family-wise error under valid individual p-values, including dependence among contrasts.'),
 p('Within-segment significance does not establish effect differences','Heading2'),p('A significant ad-versus-PSA contrast on Monday and a non-significant contrast on Tuesday do not prove a Monday-versus-Tuesday difference. The correct diagnostic asks whether treatment effects vary across categories. We compare a common-treatment binomial logistic model with a model allowing category-by-treatment interaction.'),
 table([['Exploratory interaction','LR statistic','df','Raw p','Holm p (2 tests)']]+[[h['field'],f"{h['lr']:.3f}",h['df'],pv(h['p']),pv(h['holm_p'])] for h in j['heterogeneity']],[154,100,40,100,117]),
 p('Interaction scale and interpretation','Heading2'),p('The weekday interaction remains detectable after correcting two interaction tests (adjusted p = 0.025), whereas the hourly interaction does not (p = 0.177). These tests assess heterogeneity on the log-odds scale, not directly on the absolute-lift scale. The unrestricted grouped model is saturated. Rare cells make asymptotic results less dependable, particularly for hours.'),
 p('Design limits still dominate','Heading2'),p('Even an interaction signal cannot turn realized exposure categories into randomized subgroups. It is exploratory evidence of different observed patterns and may reflect selection, delivery or user behavior. Follow-up experiments are needed to identify causal scheduling effects.'),
 p('No significance fishing','Heading2'),p('No frequency band was selected to maximize lift. No 168-cell heatmap search is used for confirmatory claims. No predictive classifier is substituted for treatment-effect estimation, and no post-treatment adjustment is presented as a causal correction.')])
page('10 / Robustness and influence diagnostics',[
 table([['Method / cohort','Estimate or p-value','What it checks'],['Pooled two-proportion z',pv(s['p_value']),'Primary large-sample null test'],['Pearson chi-square, no correction',pv(s['chi2_p']),'Equivalent 2x2 null formulation'],['Fisher exact, two-sided',pv(s['fisher_p']),'Conditional exact-test cross-check'],['Newcombe 95% CI',f"[{s['ci_low']*100:.3f}, {s['ci_high']*100:.3f}] pp",'Primary uncertainty method'],['Wald 95% CI',f"[{s['wald_low']*100:.3f}, {s['wald_high']*100:.3f}] pp",'Simple interval sensitivity'],['Binomial bootstrap 95% CI',f"[{s['bootstrap_low']*100:.3f}, {s['bootstrap_high']*100:.3f}] pp",'100,000 independent arm draws'],['Exposure-trimmed lift',pp(sen['delta']),'Users with total ads <= p99']],[169,155,187]),
 p('What agrees','Heading2'),p('The primary tests and alternative interval calculations support the same positive direction. The binomial resampling uses observed arm probabilities and fixed arm sizes, with seed 20261101. For independent Bernoulli observations, this reproduces the distribution obtained by resampling outcomes within each arm; it does not model assignment failures, clustering or outcome mismeasurement.'),
 p('What trimming can and cannot tell us','Heading2'),p(f"Excluding users above {s['p99_exposure']:.0f} exposures leaves {sen['n_psa']+sen['n_ad']:,} users and a difference of {pp(sen['delta'])}, with a 95% interval [{sen['ci_low']*100:.3f}, {sen['ci_high']*100:.3f}] pp. Directional persistence suggests the overall association is not solely carried by the extreme tail."),
 p('However, this is a changed population defined after exposure. Its effect size need not equal the original estimand. It cannot establish what would happen if a frequency cap were imposed. The complete cohort remains primary.'),
 p('Unmeasured threats','Heading2'),p('Neither a second p-value nor a bootstrap can repair unverified randomization, spillovers between users, different attribution windows, missing eligible non-exposed users or outcome tracking differences. Those require experimental logs or a new controlled study.')])
page('11 / Prospective power and a better next trial',[
 p('Planning assumptions','Heading2'),p(f"Use the observed PSA rate ({s['p_psa']:.3%}) as a planning baseline, 80% power and two-sided alpha 0.05. Target improvements of 10%, 20% and 30% relative to that baseline. These targets are illustrative business choices, not a retrospective claim about what this experiment was powered to detect."),
 table([['Relative target','Absolute target','Allocation','PSA needed','Ad needed','Total']]+[[f'{r.relative_target:.0%}',f'{r.absolute_target_pp:.3f} pp',r.allocation,f'{r.n_psa:,}',f'{r.n_ad:,}',f'{r.total:,}'] for r in plan.itertuples()],[81,87,68,91,91,93]),
 fig('planning',170),
 p('Trade-off','Heading2'),p('An approximately balanced design generally needs fewer total users for comparable precision when outcome variability and user cost are similar. A small holdout can reduce exposure opportunity cost, but requires more total traffic. Allocation should be a planned trade-off rather than inferred from the final file.'),
 p('Trial specification','Heading2'),p('Define eligibility and a meaningful incremental-conversion or contribution threshold. Randomize stable users before delivery; preserve assignment even when exposure fails. Specify a fixed outcome window, follow users equally, log exposure and conversion times, and set a minimum duration covering complete weekly cycles. Do not stop on the first nominally significant result; use a fixed horizon or a prespecified sequential method.'),
 p('Guardrails and follow-up','Heading2'),p('Record spend, contribution margin, user complaints, opt-outs, reach and delivery failures. Test frequency caps or scheduling policies in separate randomized comparisons with a small prespecified set of contrasts and appropriate multiplicity control.')])
page('12 / Decision, limitations and reproducibility',[
 table([['Decision area','Evidence-supported conclusion','Next action'],['Conversion efficacy','Positive full-cohort ad-versus-PSA difference','Validate assignment and measurement'],['Campaign scale','Economic return is not observed','Obtain CPM and contribution margin'],['Frequency optimization','Exposure-associated conversion patterns','Randomize cap policies'],['Scheduling optimization','Peak-context patterns and uncertainty','Randomize schedule policies'],['Data quality','No missing or duplicate users in this file','Audit eligibility and logging upstream']],[112,205,194]),
 p('Material limitations','Heading2'),p('No experiment dates, assignment logs, prespecified allocation, conversion window, costs, revenue, baseline covariates, demographic segments or operational guardrails are supplied. No historical stability or long-term effect can be established. User-level independence, valid assignment and comparable measurement remain assumptions.'),
 p('Reproduce the work','Heading2'),p('Run marketing/src/analyze.py, then marketing/src/report.py from the repository root. The raw download is preserved. Cleaned records, SQLite tables, executed SQL, all query outputs, segment statistics, economic scenarios, sample-size plans, seeds and dashboard aggregates accompany the report. The dashboard uses an embedded aggregate snapshot and does not refresh directly from Kaggle.'),
 p('Source and method references','Heading2'),
 p('<link href="https://www.kaggle.com/datasets/faviovaz/marketing-ab-testing">Kaggle / Favio Vazquez: Marketing A/B Testing</link>','Small'),
 p('<link href="https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm">NIST: Wilson and related proportion confidence intervals</link>','Small'),
 p('<link href="https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/diffprci.htm">NIST: Difference of proportions hypothesis test</link>','Small'),
 p('<link href="https://www.statsmodels.org/dev/_modules/statsmodels/stats/proportion.html">Statsmodels source: independent-proportion intervals and power formulas</link>','Small'),
 p('Newcombe RG (1998). Interval estimation for the difference between independent proportions: comparison of eleven methods. Statistics in Medicine 17:873-890. Holm S (1979). A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics 6:65-70.','Small'),
 p('Raw CSV SHA-256: '+j['sha256'],'Small'),p('Analysis prepared 01 November 2026; final dashboard alignment updated 02 November 2026. The final five-page Power BI export is included as Marketing_AB_Dashboard_Final.pdf.','Small')])
page('13 / Final dashboard and decision view',[
 p('Final export: 02 November 2026','Deck'),
 Image(str(P/'output/previews/dashboard_page_1.png'),width=440,height=280),
 p('Read the decision before the descriptive charts','Heading2'),
 p('The final opening page prioritizes the full-cohort comparison: PSA conversion 1.79%, ad conversion 2.55%, absolute lift +0.769 percentage points and 4,343 modeled additional conversions. The interval chart spans +0.587 to +0.936 percentage points. Rounded cards reconcile with the higher-precision estimates in this report.'),
 p('Five pages, distinct analytical purposes','Heading2'),
 table([['Page','Purpose'],['1 / Decision & impact','Conversion evidence, modeled incrementality and business decision'],['2 / Experiment design simulator','Four selectable planning inputs; live sample-size recalculation'],['3 / Evidence','Primary p-value, risk ratio, allocation and holdout variance'],['4 / Exposure explorer','Observed frequency and concentration; explicitly non-causal'],['5 / Timing explorer','Descriptive peak-day/hour patterns and denominators']],[180,331]),
 p('Interpretation guardrail','Heading2'),
 p('Page 4 prominently states that more exposure does not prove more conversions. Engagement and targeting can affect both variables. Frequency and timing charts generate hypotheses for randomized policy trials; they do not authorize a causal dose or scheduling recommendation.'),
 p('The PDF is a fixed snapshot. Use the PBIX file for interactive controls and filtering.','Small')])
page('14 / Interactive experiment-design simulator',[
 Image(str(P/'output/previews/dashboard_page_2.png'),width=400,height=255),
 p('Inputs and default results','Heading2'),
 p('Baseline conversion, target relative lift, statistical power and allocation to ads are native single-selection dropdowns. Defaults are 1.8%, 20%, 80% and 50%, respectively. The two-sided significance level stays fixed at 5%. Required total, PSA and ad sample sizes recalculate immediately; the sensitivity curve varies lift from 5% to 50% while using the selected baseline, power and allocation.'),
 table([['Scenario (other inputs at defaults)','PSA users','Ad users','Total'],['Default','23,507','23,507','47,014'],['Power = 90%','31,469','31,469','62,938'],['Relative lift = 40%','6,399','6,399','12,798'],['Ad allocation = 96%','12,626','303,024','315,650'],['Baseline = 2.0%','21,109','21,109','42,218']],[229,94,94,94]),
 p('Why these differ from the earlier planning table','Heading2'),
 p('The report scenarios use the observed PSA rate of 1.7854%; the dashboard default uses the selectable rounded baseline of 1.8%. Both use the same normal-approximation formula. The dropdowns contain discrete values, not unrestricted numeric entry. This is prospective planning, not retrospective observed power.'),
 p('Assumptions: independent users, fixed horizon, equal follow-up, no attrition, clustering or repeated testing. Duration requires eligible traffic and follow-up inputs.','Small')])
build('Marketing_AB_Deep_Analysis_Report.pdf',story)

# The investigation workbook includes every executed SQL result, including all day-hour cells.
work=[p('Investigation workbook','Title'),p('Marketing A/B testing | exact SQL, complete outputs and interpretation','Deck'),
      p('How to use this workbook','Heading2'),p('This is an audit trail, not just a list of queries. Each investigation records the question, exact SQLite SQL, every returned row, and an interpretation. Derived effect tables are produced by the accompanying Python code before SQL reads them. No SQL is invented after the fact.'),
      p('Units and conventions','Heading2'),p('Rates in query outputs are proportions unless labeled lift_pp or ci_*_pp. One percentage point is 0.01 in probability units. PSA is control; product ads is treatment. Null signifies absent or undefined values. Exposure and peak-time fields are not assumed to be baseline covariates.'),
      p('Source','Heading2'),p(SOURCE),p('588,101 users; 14,843 conversions; zero excluded source rows. Downloaded 01 November 2026.','Deck'),
      p('Investigation index','Heading2'),p('<br/>'.join(f"{x['number']:02d}. {escape(x['title'])}" for x in inv),'Small'),PageBreak()]
for item in inv:
    work += [p(f"{item['number']:02d} / {item['title']}",'Heading1'),p(item['question'],'Deck'),
             Preformatted(item['sql'],ParagraphStyle('SQL',fontName='Courier',fontSize=8,leading=11),maxLineLength=94),Spacer(1,10),
             p('Interpretation','Heading2'),p(item['interpretation'])]
    cols=item['columns'];rows=[[str(c).replace('_',' ') for c in cols]]+[[fmt(v) for v in row] for row in item['rows']]
    # Wide effects tables are split into two vertically stacked panels, retaining every field.
    if len(cols)>7:
        pivot=4
        for ix in [list(range(pivot)),[0]+list(range(pivot,len(cols)))]:
            work += [table([[r[i] for i in ix] for r in rows]),Spacer(1,12)]
    else:work += [table(rows)]
    work.append(PageBreak())
work += [p('23 / Statistical methods and exact outputs','Heading1'),
         p('Primary comparison','Heading2'),Preformatted('pA = conversions_PSA / n_PSA\npB = conversions_ad / n_ad\nd = pB - pA\npool = (conversions_PSA + conversions_ad) / (n_PSA + n_ad)\nz = d / sqrt(pool*(1-pool)*(1/n_PSA + 1/n_ad))\np_two = 2 * norm.sf(abs(z))',ParagraphStyle('formula',fontName='Courier',fontSize=8,leading=12)),
         p('Newcombe interval','Heading2'),p('Compute 95% Wilson bounds (LA, UA) and (LB, UB) for PSA and ad. Lower difference = d - sqrt((pB-LB)^2 + (UA-pA)^2). Upper difference = d + sqrt((UB-pB)^2 + (pA-LA)^2). No continuity correction is applied.'),
         table([['Primary output','Value']]+[[k,fmt(v)] for k,v in s.items()]),PageBreak(),
         p('24 / Multiplicity, interaction and resampling','Heading1'),
         p('Holm procedure','Heading2'),p('Use two-sided Fisher exact p-values for all segment contrasts. Sort all 31 weekday/hour p-values ascending. Multiply the ith value by (31-i), with i starting at zero. Take the cumulative maximum and cap at 1, then restore the original order. The pointwise intervals are not multiplicity-adjusted.'),
         p('Interaction diagnostics','Heading2'),p('For each category variable, fit an aggregated binomial logistic model with intercept, treatment indicator and category dummy variables. Compare its likelihood with the saturated category-by-treatment model. LR = 2 x (logLik_full - logLik_restricted); degrees of freedom = categories - 1. Two interaction p-values receive a separate Holm adjustment.'),
         table([['Field','LR','df','p','Holm p']]+[[h['field'],fmt(h['lr']),h['df'],fmt(h['p']),fmt(h['holm_p'])] for h in j['heterogeneity']]),
         p('Resampling','Heading2'),p('Generate 100,000 independent binomial counts per arm using the observed conversion probabilities and fixed arm sizes. Convert to rates, subtract PSA from ad and take the 2.5th/97.5th percentiles. Seed: 20261101. This is an empirical-Bernoulli sampling check, not a randomization test under the null.'),
         p('Extreme-exposure sensitivity','Heading2'),table([['Output','Value']]+[[k,fmt(sen[k])] for k in ['n_psa','n_ad','delta','ci_low','ci_high','p_value']]),PageBreak(),
         p('25 / Planning and economic scenarios','Heading1'),
         p('Prospective normal-approximation sample sizes','Heading2'),p('Let r = n_ad/n_PSA, p0 = observed PSA rate, p1 = p0 x (1 + target relative lift), and pooled = (p0 + r*p1)/(1+r). Required PSA n = ceil([(z_.975*sqrt(pooled*(1-pooled)*(1+1/r)) + z_.8*sqrt(p0*(1-p0)+p1*(1-p1)/r))/(p1-p0)]^2). Round the ad count upward at the chosen ratio. No trial duration is estimated without eligible traffic rates.'),
         table([['Relative lift','Absolute pp','Split','PSA','Ad','Total']]+[[f'{r.relative_target:.0%}',f'{r.absolute_target_pp:.4f}',r.allocation,f'{r.n_psa:,}',f'{r.n_ad:,}',f'{r.total:,}'] for r in plan.itertuples()]),
         p('Economic scenario formulas','Heading2'),p('Modeled incremental conversions = n_ad x (p_ad-p_PSA). Contribution = incremental conversions x assumed margin. Ad cost = recorded ad-arm impressions / 1,000 x assumed CPM. Net = contribution - cost. Confidence limits scale the primary rate interval; they do not include uncertainty in cost, margin or causal assumptions.'),
         table([['Margin','CPM','Cost','Net point','Net low','Net high']]+[[f'{r.margin:g}',f'{r.cpm:g}',f'{r.ad_cost:,.0f}',f'{r.net:,.0f}',f'{r.net_low:,.0f}',f'{r.net_high:,.0f}'] for r in econ.itertuples()]),
         p('Validation','Heading2'),p('SQL group totals equal Python group totals. Clean users equal distinct IDs. Dashboard cube reconciles to 588,101 users, 14,843 conversions and the complete exposure sum. Welch-style or t-tests on exposure are not substituted for the binary primary outcome. All primary source users remain included.')]
work += [PageBreak(),p('26 / Final dashboard simulator audit','Heading1'),
 p('Four dynamic inputs; two distinct baseline conventions','Heading2'),
 p('The final dashboard uses selectable baseline 1.8%, relative lift 20%, power 80% and ad allocation 50% as defaults. The report planning queries retain the unrounded observed PSA baseline. Significance is fixed at 5%, two-sided. The final export is static; the PBIX is interactive.'),
 table([['Changed input','Expected total users'],['None / defaults','47,014'],['Power 90%','62,938'],['Target relative lift 40%','12,798'],['Ad allocation 96%','315,650'],['Baseline conversion 2%','42,218']],[320,191]),
 p('Formula audit','Heading2'),p('For p0, relative lift L, power W and ad share a: p1=p0*(1+L), r=a/(1-a), pooled=(p0+r*p1)/(1+r). Compute PSA n by the prospective formula in investigation 25 with z(W) replacing z(.8). Ad n=ceil(r*PSA n), total=PSA n+ad n. Ceiling is applied separately to the two arm counts.'),
 p('Exact native DAX','Heading2')]
dax=(P/'src/dashboard_measures.dax').read_text()
measures=[]
for block in dax.split('-- Table: '):
    if '\n' in block and ' = ' in block:
        definition=block.split('\n',1)[1].strip()
        name,expression=definition.split(' = ',1)
        measures.append({'name':name,'expression':expression})
for m in measures:
    if m['name'] in ['Required PSA users','Required ad users','Required experiment users','Curve total users']:
        if m['name']=='Curve total users':work += [PageBreak(),p('27 / Simulator sensitivity and interpretation','Heading1')]
        code='\n'.join(m['expression']) if isinstance(m['expression'],list) else m['expression']
        code='\n'.join('\n'.join(textwrap.wrap(line,width=91,replace_whitespace=False,drop_whitespace=False)) for line in code.splitlines())
        work += [p(m['name'],'Heading2'),Preformatted(code,ParagraphStyle('DAX',fontName='Courier',fontSize=8,leading=11)),Spacer(1,8)]
work += [p('Final exposure-page interpretation','Heading2'),p('The page labels frequency patterns as observational, removes subgroup-lift and average-frequency cards, and calls for randomized frequency-cap trials. Statistical primary results are unchanged. The final dashboard, PBIX, measure definitions, report and SQL workbook are versioned together.')]
build('Marketing_AB_Queries_and_Investigation.pdf',work)
print('Created in-depth analysis report and complete investigation workbook.')
