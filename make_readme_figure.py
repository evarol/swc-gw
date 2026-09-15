"""Render the README figure from saved SWCs and the original GW solution."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import PowerNorm

ROOT = Path(__file__).resolve().parent
z = np.load(ROOT / 'matrices.npz')
t = z['transport']
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                     'axes.spines.top': False, 'axes.spines.right': False})
fig = plt.figure(figsize=(13, 10), facecolor='#fafbfe')
gs = fig.add_gridspec(2, 3, height_ratios=[1.4, 1], hspace=.36, wspace=.32,
                      left=.065, right=.96, bottom=.09, top=.88)
ax = fig.add_subplot(gs[0, :]); ax.set_facecolor('#fafbfe')
colors = ['#147d92', '#cb5b32']
xy = []; edges = []
# An orthographic view of native XYZ; identical projection and scale for both.
az, el = np.deg2rad([30, 20])
u = np.array([np.cos(az), np.sin(az), 0])
v = np.array([-np.sin(az)*np.sin(el), np.cos(az)*np.sin(el), np.cos(el)])
for label, ids in [('Ti8', z['node_ids_A']), ('Ti9', z['node_ids_B'])]:
    swc = np.loadtxt(ROOT / 'sources' / f'{label}.swc')
    lookup = {int(row[0]): row for row in swc}
    rows = np.array([lookup[int(i)] for i in ids])
    xyz = rows[:, 2:5]
    points = np.column_stack([xyz @ u, xyz @ v]); points -= points.mean(axis=0)
    index = {int(i): k for k, i in enumerate(ids)}
    edges.append([(k, index[int(p)]) for k, p in enumerate(rows[:, 6]) if int(p) in index])
    xy.append(points)
gap = 95
xy[0][:, 0] -= xy[0][:, 0].max() + gap/2
xy[1][:, 0] -= xy[1][:, 0].min() - gap/2
pairs = np.argwhere(t > 1e-12)
weights = np.array([t[i, j] for i, j in pairs]) / t.max()
segments = [[xy[0][i], xy[1][j]] for i, j in pairs]
rgba = np.tile([.36, .39, .57, 1.], (len(pairs), 1)); rgba[:, 3] = .045 + .18*weights
ax.add_collection(LineCollection(segments, colors=rgba, linewidths=.2+.65*weights, zorder=1))
for k, label in enumerate(['Ti8 · 202 nodes', 'Ti9 · 193 nodes']):
    ax.add_collection(LineCollection([[xy[k][i], xy[k][j]] for i, j in edges[k]], colors=colors[k], linewidths=1.4, zorder=3))
    ax.scatter(*xy[k].T, s=9, color=colors[k], edgecolors='white', linewidths=.15, zorder=4)
    ax.text(xy[k][:, 0].mean(), max(p[:, 1].max() for p in xy)+12, label,
            color=colors[k], ha='center', weight='bold', fontsize=12)
ax.autoscale(); ax.margins(.06, .14); ax.set_aspect('equal'); ax.axis('off')
ax.set_title('A   Spatial correspondences', loc='left', fontweight='bold', pad=15)
maxd = max(z['distance_A'].max(), z['distance_B'].max())
for k, (key, title, xlabel, ylabel) in enumerate([
    ('distance_A', 'B   Ti8 tree distances', 'Ti8 node index', 'Ti8 node index'),
    ('transport', 'C   GW transport plan', 'Ti9 node index', 'Ti8 node index'),
    ('distance_B', 'D   Ti9 tree distances', 'Ti9 node index', 'Ti9 node index')]):
    a = fig.add_subplot(gs[1, k]); a.set_title(title, loc='left', fontweight='bold', pad=12)
    kwargs = dict(cmap='magma', vmin=0, vmax=maxd) if key != 'transport' else dict(cmap='Blues', norm=PowerNorm(.5, vmin=0, vmax=t.max()))
    im = a.imshow(z[key], interpolation='nearest', **kwargs)
    a.set_xlabel(xlabel); a.set_ylabel(ylabel)
    cb = fig.colorbar(im, ax=a, orientation='horizontal', pad=.23, fraction=.05)
    cb.set_label('Path length · native units' if key != 'transport' else 'Transport mass · square-root color scale', fontsize=9)
    cb.ax.tick_params(labelsize=8)
fig.suptitle('Matching motor-neuron trees with Gromov–Wasserstein transport', x=.065, ha='left', y=.975, fontsize=18, fontweight='bold', color='#202d47')
fig.text(.065, .932, 'Ti8 ↔ Ti9  |  weighted tree-path metric  |  uniform node masses  |  dGW = 12.162 native units', fontsize=11, color='#52617a')
fig.text(.065, .023, f'Orthographic XYZ projection; trees translated apart for display. All {len(pairs)} positive transport entries shown as connectors.\nConnector opacity and width encode mass. Matrix indices follow the saved SWC order; distance panels share one color scale.', fontsize=9, color='#52617a', linespacing=1.6)
out = ROOT / 'assets'; out.mkdir(exist_ok=True)
fig.savefig(out / 'gw-demonstration.png', dpi=200, facecolor=fig.get_facecolor())
fig.savefig(out / 'gw-demonstration.svg', facecolor=fig.get_facecolor())
svg = out / 'gw-demonstration.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n')
print(f'Saved figure: {len(pairs)} connectors; transport mass={t.sum():.12f}')
