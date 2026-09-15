"""Independent full-export audit using tree traversal, not the generating code."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
OUT=HERE/'deformation_study'

def read_tree(path):
    rows=[line.split() for line in path.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]
    ids=[int(r[0]) for r in rows];lookup={node:i for i,node in enumerate(ids)}
    xyz=np.array([[float(v) for v in r[2:5]] for r in rows]);parents=[int(r[6]) for r in rows]
    neighbors=[[] for _ in rows];a=np.zeros((len(rows),len(rows)))
    for i,parent in enumerate(parents):
        if parent<0:continue
        j=lookup[parent];w=np.sqrt(sum((xyz[i]-xyz[j])**2));a[i,j]=a[j,i]=w
        neighbors[i].append((j,w));neighbors[j].append((i,w))
    d=np.zeros_like(a)
    for source in range(len(rows)):
        visited=set();stack=[(source,-1,0.)]
        while stack:
            i,parent,distance=stack.pop();assert i not in visited;visited.add(i);d[source,i]=distance
            stack.extend((j,i,distance+w) for j,w in neighbors[i] if j!=parent)
        assert len(visited)==len(rows)
    return ids,xyz,parents,a,d

def main():
    report=json.loads((OUT/'report.json').read_text());source=read_tree(HERE/'sources/Ti8.swc')
    records=[];summary=[];global_error=0.
    for case in report['cases']:
        key=case['key'];folder=OUT/key;z=np.load(folder/'matrices.npz');perm=z['permutation'];inv=np.argsort(perm)
        target=read_tree(folder/f'Ti8_{key}_ordered.swc');shuffled=read_tree(folder/f'Ti8_{key}_shuffled.swc')
        assert target[0]==source[0] and target[2]==source[2]
        assert shuffled[0]==list(np.array(source[0])[perm])
        assert np.array_equal(target[1][perm],shuffled[1])
        assert np.allclose(z['coordinates_B'],target[1],atol=1e-14,rtol=0)
        matrix_error=max(np.max(abs(source[3]-z['adjacency_A'])),np.max(abs(target[3]-z['adjacency_B'])),
            np.max(abs(source[4]-z['distance_A'])),np.max(abs(target[4]-z['distance_B'])),np.max(abs(shuffled[4]-target[4][np.ix_(perm,perm)])))
        assert matrix_error<1e-10
        for suffix,expected in [('delta_distance',target[4]-source[4]),('delta_adjacency',target[3]-source[3])]:
            table=np.loadtxt(folder/(suffix+'.csv'),delimiter=',',skiprows=1)[:,1:]
            assert np.max(abs(table-expected))<1e-10
        data=json.loads((folder/'runs.json').read_text());n=len(source[0]);p=z['mass'];max_error=0.;max_margin=0.
        for k,protocol in enumerate(data['protocols']):
            order=np.arange(n) if k==0 else perm;truth=np.argsort(order);db=target[4][np.ix_(order,order)]
            for j,run in enumerate(protocol['runs']):
                t=z['all_transports'][k,j];g=z['all_initial_plans'][k,j]
                assert min(t.min(),g.min())>=0
                margin=max(np.max(abs(t.sum(0)-p)),np.max(abs(t.sum(1)-p)),np.max(abs(g.sum(0)-p)),np.max(abs(g.sum(1)-p)))
                assert margin<1e-12;max_margin=max(max_margin,float(margin))
                ii,jj=np.nonzero(t);mass=t[ii,jj]
                diff=source[4][ii[:,None],ii[None,:]]-db[jj[:,None],jj[None,:]]
                loss=float(np.sum(diff**2*mass[:,None]*mass[None,:]))
                error=abs(loss-run['objective']);assert error<1e-7;max_error=max(max_error,error)
                correct=t[np.arange(n),truth]
                assert abs(correct.sum()-run['matchedIdMass'])<1e-12
                affected=z['affected_indices'];assert abs(correct[affected].sum()/(len(affected)/n)-run['affectedMatchedMass'])<1e-12
                if 'permutation' in run['plan']:
                    compact=np.zeros_like(t);compact[np.arange(n),run['plan']['permutation']]=p
                else:
                    compact=np.zeros_like(t)
                    for i,col,w in run['plan']['entries']:compact[i,col]=w
                assert np.array_equal(compact,t)
            assert protocol['bestRunIndex']==int(np.argmin([r['objective'] for r in protocol['runs']]))
        initial_err=float(abs(z['all_initial_plans'][0]-z['all_initial_plans'][1][:,:,inv]).max())
        plan_err=float(abs(z['all_transports'][0]-z['all_transports'][1][:,:,inv]).max())
        assert initial_err==0 and plan_err<1e-12
        if key in ['rotation','bend_isometric']:assert np.max(abs(target[4]-source[4]))<1e-10
        for filekey,hashkey in [('sourceFile','sourceSha256'),('shuffledFile','shuffledSha256')]:
            assert hashlib.sha256((HERE/case['stats'][filekey]).read_bytes()).hexdigest()==case['stats'][hashkey]
        best=data['protocols'][2]['runs'][data['protocols'][2]['bestRunIndex']]
        summary.append(dict(case=key,bowAmplitude=case['stats']['amplitude'],rmsDeltaD=case['stats']['rmsTreeDistanceDifference'],
            bestGW=best['dGW'],knownCorrespondenceGW=case['stats']['rmsTreeDistanceDifference']/2,
            trueMatchMass=best['matchedIdMass'],affectedMatchMass=best['affectedMatchedMass'],meanPathError=best['meanCorrespondencePathError'],
            randomMedianMatch=float(np.median([r['matchedIdMass'] for r in data['protocols'][2]['runs'][3:]])),
            maxMatchedStartTransportDifference=plan_err))
        records.append(dict(case=key,checkedRuns=36,maxGraphMatrixError=float(matrix_error),maxObjectiveError=max_error,maxMarginalError=max_margin,
            matchedInitialDifference=initial_err,matchedTransportDifference=plan_err))
        global_error=max(global_error,max_error)
    audit=dict(passed=True,nRuns=252,checks=records,maxObjectiveError=global_error,summary=summary)
    (OUT/'independent_verification.json').write_text(json.dumps(audit,indent=2))
    with (OUT/'summary.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(summary[0]));writer.writeheader();writer.writerows(summary)
    print(json.dumps(audit,indent=2))

if __name__=='__main__':main()
