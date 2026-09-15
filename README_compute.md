# Ti8–Ti9 full-node weighted-tree Gromov–Wasserstein analysis

## Result

The two selected SWCs are **actual motor-class targets Ti8 and Ti9**, with **202 and 193 vertices**, respectively. Every source vertex and parent–child segment is retained. No resampling, tree simplification, branch pruning, or coordinate normalization is applied to the reported matrices.

The best result from 12 feasible initializations of unregularized, square-loss GW is:

| Quantity | Value |
|---|---:|
| Square-loss objective | 591.6945240365894 native units² |
| Conventional GW distance estimate, ½√objective | **12.162385909399001 native units** |
| RMS structural distortion, √objective | 24.324771818798002 native units |
| Transport shape | 202 × 193 |
| Positive transport entries | 394 |
| Maximum row marginal error | 0 |
| Maximum column marginal error | 2.5153490401663703 × 10⁻¹⁷ |

**The coordinate units are unverified native source units, not established micrometres.** The solver finds a stationary local solution to a nonconvex problem. The value above is the best found across 12 starts, an upper bound on the global minimum under the stated convention, not a certificate of the exact mathematical distance. The resulting coupling is a structural correspondence; it is not evidence of a biological node homology or synaptic connection.

## Data and provenance

Both files come from the existing curated motor dataset, whose `cell_class` crosswalk identifies them as `motor`. Each selected target has exactly one source-supported anatomical contributor with contributor weight 1.0. Choosing these files avoids the explicitly shared/ambiguous Ti2–Ti5 assignments and targets with multiple anatomical contributors. Selection was based on valid single-contributor provenance and manageable full-node size, not on the eventual distance result.

| | Ti8 | Ti9 |
|---|---|---|
| Curated root ID (decimal string) | 648518346477229768 | 648518346494055054 |
| Source supervoxel token | 72553200314029096 | 72482831636691164 |
| Original filename | fanc_production_mar2021_left_t1_skel_72553200314029096.swc | fanc_production_mar2021_left_t1_skel_72482831636691164.swc |
| Vertex / edge counts | 202 / 201 | 193 / 192 |
| Total cable length | 845.7347348038346 | 811.1824612010735 |
| Tree diameter | 191.6321723718167 | 239.91057178234396 |
| SHA256 | f2efb8323f7accb5507a06f6a1e0fb865aac0dbf1e03eaddf22cafe0fbf654b9 | a99cccee556f473d639b5a45573ecd866c17dae12d54dcc034d1a3601d1ea303 |

Local source files:

- `outputs/eight_panel_morphology/morphology/motor/native/motor_648518346477229768.swc`
- `outputs/eight_panel_morphology/morphology/motor/native/motor_648518346494055054.swc`

Evidence:

- `outputs/eight_panel_morphology/morphology/motor/target_neuron_swc_crosswalk.tsv`
- `outputs/eight_panel_morphology/morphology/motor/geometry_inventory.tsv`
- `outputs/eight_panel_morphology/morphology/motor/README.md`
- Exact selected crosswalk and inventory records are saved in `selected_provenance.json`.

The SWCs are headerless historical Tony/FANC native exports. The dataset records exact source mapping but no frozen segmentation release. Full-arbor biological completeness and the physical coordinate units were not independently established. This computation verifies complete retention of the vertices present in each source, not biological reconstruction completeness. Source copies in `sources/` are byte-identical to the curated files; source license terms are inherited and no new data license is asserted.

## Matrix construction

Matrix row/column order equals the source SWC file's row order. The corresponding original integer SWC IDs appear in CSV headers and `*_nodes.csv`.

1. **Weighted adjacency A**: `A[i,j] = ||XYZ[i]−XYZ[j]||₂` for each SWC parent–child pair, symmetrically; zero for nonedges and the diagonal. The weights represent segment lengths, not inverse lengths or neurite radii.
2. **Tree metric D**: `D[i,j]` is the sum of segment lengths on the unique tree path from node i to node j. This is the all-pairs weighted shortest-path matrix derived from A, not the direct 3D Euclidean distance matrix.
3. **Node masses**: `p[i]=1/202`, `q[j]=1/193`, so each tree has total mass 1. This choice weights original SWC vertices equally and is sensitive to source sampling density. It does not use radius, segment length, or anatomical contributor weight as node mass.
4. **Transport T**: nonnegative, with `T 1=p` and `Tᵀ 1=q`. Different vertex counts naturally produce split mass; it is not a one-to-one node assignment.

The square-loss objective is

```text
J(T) = Σᵢⱼₖₗ (D_Ti8[i,k] − D_Ti9[j,l])² T[i,j] T[k,l].
d_GW = ½ sqrt(min J(T)).
RMS distortion = sqrt(J(T)).
```

POT's `gw_dist` is the square-loss objective, not its square root. This artifact reports the half-root convention and the root distortion separately to make the factor explicit. See the [official POT GW implementation documentation](https://pythonot.github.io/_modules/ot/gromov/_gw.html).

For numerical conditioning only, both distance matrices are divided by the **same** constant 239.91057178234396 before optimization. This multiplication of the objective by one positive constant preserves its minimizers and retains differences in tree size. Reported matrices, objective, and distances are restored to native units. The two trees are not normalized independently.

## Optimization and validation

Implementation: POT 0.9.7.post1, `ot.gromov.gromov_wasserstein`, `loss_fun="square_loss"`, `symmetric=True`, conditional gradient with closed-form line search (`armijo=False`), no entropy regularization, at most 1,000 iterations, relative/absolute tolerances `1e-12`, float64 computation and one BLAS/EMD thread.

The 12 feasible starts are the independent product coupling, two linear-OT plans based on root distance and mean tree distance, and nine random-cost linear-OT plans from NumPy seeds 0–8. Root distance only constructs one initialization; it is not an additional constraint or penalty, and roots are not forced to match. The winning root-distance initialization stops after 13 iterations. Other starts give conventional distance estimates between 12.163579154697743 and 14.022507455030373; the product start gives 12.611791386138892. All runs and tolerances are recorded in `summary.json` and `computation.log`.

Checks performed during computation:

- Seven-column parse, unique integer SWC IDs, finite XYZ/radius, nonnegative radii, valid parents, one root, n−1 edges, no zero-length edges, and connected graph; together these verify each graph is a tree.
- Source SHA256 equals both the inventory and crosswalk hash.
- Finite symmetric shortest-path matrices, zero diagonal, and metric value equals every direct tree-edge weight.
- Feasible initial and final transport plans, nonnegativity, and marginals to within `1e-12`.
- Each objective agrees with both POT's logged value (rescaled) and an independent direct double sum over all pairs of positive transport entries.
- Objective history is nonincreasing within floating-point tolerance.
- Winning plan's normalized Frank–Wolfe stationarity gap is zero at machine precision (this is a stationarity check, not a global-optimality proof).
- Identity coupling on Ti8 gives zero self-distortion to roundoff (`−3.64e-12` from floating-point cancellation).
- `verify_exports.py` round-trips the compact browser payload and checks it against all authoritative float64 matrices, source copies, node CSVs, and transport CSVs.

## Files and precision

- `analysis.json`: compact interactive-viewer payload, approximately 291 KB. Includes all nodes and edges, source metadata, compressed distance matrices, sparse coupling and numeric results.
- `summary.json`: readable results and methods without bulk matrix arrays.
- `matrices.npz`: authoritative float64 `adjacency_A`, `adjacency_B`, `distance_A`, `distance_B`, `transport`, `mass_A`, `mass_B`, plus original integer `node_ids_A` and `node_ids_B`; A=Ti8 and B=Ti9.
- `Ti8_weighted_adjacency.csv`, `Ti9_weighted_adjacency.csv`: full weighted adjacency matrices with node IDs on both axes.
- `Ti8_tree_distance.csv`, `Ti9_tree_distance.csv`: full tree distance matrices with node IDs on both axes.
- `transport.csv`: full rectangular coupling with Ti8 rows and Ti9 columns.
- `transport_sparse.csv`: all positive transport entries, using zero-based matrix indices i and j.
- `Ti8_nodes.csv`, `Ti9_nodes.csv`: row-to-node mapping, native coordinates and masses.
- `sources/Ti8.swc`, `sources/Ti9.swc`: byte-identical selected source copies.
- `selected_provenance.json`, `computation.log`, `verification.json`: provenance and computation/check records.
- `compute_gw.py`, `verify_exports.py`, `requirements.txt`: reproduction.

For compact browser storage only, `trees[k].distanceUpperF32` encodes the **strict upper triangle**, ordered `(i=0,j=1..n−1), (i=1,j=2..n−1), ...`, as base64 little-endian float32. Set diagonal entries to zero and reflect to reconstruct the lower triangle. The maximum float32 display error is less than `7.63e-6` native units. Full CSV/NPZ distances retain float64 precision. Adjacency is reconstructed exactly from `trees[k].edges = [[i,j,length], ...]`. `gw.coupling = [{i,j,mass}, ...]` contains every positive entry; unspecified entries are zero.

## Reproduce

From the repository root, with Python 3.11 or newer:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python compute_gw.py > computation.log
.venv/bin/python verify_exports.py
```

The bundled source SWCs in `sources/` and selected records in `selected_provenance.json` are sufficient; the historical dataset paths above are provenance references.
