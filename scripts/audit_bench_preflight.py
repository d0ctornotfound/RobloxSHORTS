#!/usr/bin/env python3
"""Audit actual The Bench preflight manifests; evidence only, not visual approval."""
import argparse,json,math
from pathlib import Path
REPRESENTATIVE={2,16,23,31,35,48}
HEROES={2:('Milo','Dad'),31:('Milo',),35:('Milo',),48:('Milo','Dad')}
def check(root,full=False):
    shots={}
    for path in sorted(Path(root).rglob('manifest.json')):
        m=json.loads(path.read_text())
        if 'shot' not in m or 'records' not in m:continue
        n=int(m['shot']['id']);assert n not in shots,f'duplicate shot {n}'
        rows=m['records'];first=round(m['shot']['start']*24)+1;last=round(m['shot']['end']*24)
        issues=[]
        if m['mode']!='preflight':issues.append('not a preflight manifest')
        if [r['global_frame'] for r in rows]!=[first,first+(last-first+1)//2,last]:issues.append('missing designated samples')
        if m['resolution']!=[540,960] or m['fps']!=24 or m['engine']!='EEVEE' or m['denoising'] is not False:issues.append('profile mismatch')
        near=max((r['near_black_percent'] for r in rows),default=math.inf)
        if near>10:issues.append('preflight darkness >10%')
        garments=[g for r in rows for g in r.get('garments',{}).values()]
        if any(not g['pass_tracking'] for g in garments):issues.append('garment tracking failure')
        coverage={};bounds={}
        for actor in HEROES.get(n,()):
            ps=[p for r in rows for p in r['projection'] if p['actor']==actor]
            coverage[actor]=min((p['coverage'] for p in ps),default=0.)
            bounds[actor]=all(0<=p['bounds'][0]<=p['bounds'][1]<=1 and 0<=p['bounds'][2]<=p['bounds'][3]<=1 for p in ps) and len(ps)==len(rows)
            if coverage[actor]<.45:issues.append(actor+' projected height <45%')
            if not bounds[actor]:issues.append(actor+' projected body out of frame')
        contact=[c for r in rows for c in r.get('contacts',[])]
        if n==23:
            feet=[c for c in contact if c['event']=='pigeon_feet']
            if not feet:issues.append('no measured pigeon foot support')
            elif any(len(c['vertical_gaps'])!=2 or any(g is None or abs(g)>.015 for g in c['vertical_gaps']) for c in feet):issues.append('pigeon support gap > provisional .015 tolerance')
        if n==48:
            transfers=[c for c in contact if c['event']=='bag' and c.get('handoff')]
            if not transfers:issues.append('no sampled bag transfer')
            elif any(c.get('giver_receiver_target_error',math.inf)>.035 for c in transfers):issues.append('bag handoff target error > provisional .035 tolerance or unmeasured')
        shots[n]={'act':m['shot']['act'],'samples':len(rows),'max_near_black_percent':near,'max_shell_source_gap':max((g['max_source_gap'] for g in garments),default=None),'min_projected_hero_height':coverage,'body_projection_in_frame':bounds,'contacts':contact,'render_seconds':[r['render_seconds'] for r in rows],'issues':issues,'manifest':str(path)}
    required=set(range(1,49)) if full else REPRESENTATIVE
    missing=sorted(required-shots.keys())
    return {'scope':'all 48 shots' if full else 'six representative shots','required_shots':len(required),'observed_shots':len(shots),'missing_shots':missing,'numerical_pass':not missing and all(not v['issues'] for v in shots.values()),'visual_approval':False,'limitations':['No rendered object-ID visibility measurement in the source manifests; 69% actual visibility not established.','Projection cannot prove visibility or physical contact.','Contact tolerances are story-local diagnostics, not changes to locked chapter gates.','Full mode checks completeness for 48 shots; projection/contact checks presently cover only the representative subset. All shots require actual pixel inspection.'],'shots':shots}
def main():
    p=argparse.ArgumentParser();p.add_argument('--chunks',required=True);p.add_argument('--output',required=True);p.add_argument('--full',action='store_true');p.add_argument('--enforce',action='store_true');a=p.parse_args()
    result=check(a.chunks,a.full);Path(a.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='shots'},indent=2))
    for n,s in result['shots'].items():print(n,':','; '.join(s['issues']) or 'no numerical issue in measured checks')
    if a.enforce and not result['numerical_pass']:raise SystemExit(1)
if __name__=='__main__':main()
