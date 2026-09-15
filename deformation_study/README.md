# Branch deformation, node-order permutation, and GW initialization

## Main findings

**GW's objective is invariant to node order, while its nonconvex numerical solver is sensitive to initialization.** In this experiment, consistent permutation of both the target and initial transport gave exactly the same transport after undoing the permutation in all **84 paired runs**. Regenerating random starts in shuffled index order changes which physical nodes are initially paired, and often leads to different poor local solutions.

Mild deformation retained the true synthetic correspondences. At stronger deformations, recovery declined. A bend that preserves segment lengths is invisible to this particular tree metric even though its 3D geometry changes.

The table uses the lowest-loss result among 12 starts in the **shuffled/fresh** protocol; ordered and matched-shuffled protocols have the same best results here. “Match” is the fraction of total transport mass sent to each node's known original identity. With the permutation plans obtained here, it also equals exact node-match accuracy.

| Geometry | RMS ΔD | Best GW estimate | True-match mass | Match in branch regions | Median random-start match |
|---|---:|---:|---:|---:|---:|
| Rotation only | ≈0 | ≈0 | 100% | 100% | 14.85% |
| Length-preserving bend | ≈0 | ≈0 | 100% | 100% | 14.85% |
| Bow 2% | 0.2198 | 0.1099 | 100% | 100% | 14.85% |
| Bow 5% | 0.5334 | 0.2667 | 100% | 100% | 14.85% |
| Bow 10% | 1.0900 | 0.5416 | 98.02% | 95.51% | 9.90% |
| Bow 20% | 2.7025 | 1.3595 | 91.58% | 80.90% | 7.92% |
| Bow 40% | 8.5609 | 4.4243 | 80.69% | 60.67% | 10.89% |

Lengths are native source units, not established micrometres. These are conditional results for one neuron, one fixed permutation, three chosen branches, and these deformations/seeds; they do not establish a universal robustness threshold.

## Exact construction

Start from all 202 nodes of Ti8 and the previous 180° Z rotation through its node centroid. Three **disjoint** descendant subtrees anchored at original SWC IDs **23, 81, and 163** are selected. Together they contain 89 non-anchor nodes. Types, radii, node IDs, parent IDs, and topology remain unchanged.

For a node with path distance `s` from its selected anchor and maximum subtree path distance `L`, the bow is:

```text
X_bowed = X_rotated + a * L * sin(pi*s/L)^2 * u
```

Here `u` is a fixed unit direction transverse to the anchor-to-farthest-descendant direction. The anchors are fixed; the longest-path endpoint is also fixed. Intermediate branches bend smoothly. `a` is 0.02, 0.05, 0.10, 0.20, or 0.40. The quoted percentages are nominal bow-amplitude/path-length ratios, not percentage edge-length changes. Measured maximum edge-length changes are approximately 5.72%, 14.28%, 28.50%, 56.51%, and 107.45%, respectively. The high levels are explicit stress tests. The 89-node evaluation mask is the selected descendant region, including any endpoint whose displacement is zero.

The length-preserving control rebuilds each selected subtree parent-first, rotating each original edge vector about Z by up to 35°, with angle proportional to its child's path distance from the anchor. This preserves every vector length. Its maximum tree-distance difference is only numerical roundoff; its best GW distance is about 1.17e-14.

Every deformed target is written to an SWC, read back, and used to recompute adjacency and all-pairs tree distances. Separate shuffled SWCs reorder rows with NumPy permutation seed **20260915**, retaining IDs and valid parent references. Readers must resolve parents by ID, not assume parents precede children in the file.

## Three ordering/initialization protocols

Each geometry receives the same 12 start families: uniform product, root-distance linear OT, mean-distance linear OT, and random-cost linear OT with seeds 0–8.

1. **Ordered:** source row order in the target; baseline initial couplings.
2. **Shuffled, matched starts:** target nodes and distance matrix are permuted; every initial coupling receives the identical column permutation. This isolates numerical dependence on ordering. All 84 final plans agree exactly after undoing the shuffle.
3. **Shuffled, fresh starts:** the same initialization recipes are regenerated in shuffled index order. A same-seed random cost array now pairs different physical nodes. This measures changed initialization, not pure ordering invariance.

For the order-only comparison, the distance matrix is an exact permutation of the computed ordered matrix. Independently recomputing the shuffled SWC's distances agrees within 1e-10. This avoids conflating floating-point traversal order with index permutation.

All **252** calls use POT's unregularized square-loss conditional-gradient GW, uniform mass 1/202, a common diameter scaling, at most 1,000 iterations, and relative/absolute tolerances 1e-12. The best run is chosen by objective, never by recovery accuracy. True node identity is used only in evaluation and aligned difference plots; it is not a matching cost or constraint.

## Separating geometry from optimization failure

The known correspondence has diagnostic cost `GW_known = 0.5 * RMS(ΔD)` for uniform masses. It is evaluated afterward and is not an oracle initialization.

- At 10%, the inferred coupling has slightly lower GW cost than the true correspondence (0.541565 vs 0.545001), so minimizing structural distortion can favor a few identity swaps.
- At 20%, the best solver result is **worse** than the feasible known correspondence (1.359453 vs 1.351235).
- At 40%, the same issue appears (4.424258 vs 4.280435).

Thus the loss of correspondence at high deformation cannot be interpreted purely as a limit of the mathematical GW objective: optimization failure also contributes. The displayed values are solver estimates, not certified global distances. These differences are materially larger than numerical roundoff.

## Reading the visualizer

- **Experiment** picks geometry; **Target order & initialization protocol** picks one of the three protocols; **GW initialization** shows the actual saved transport for any start or the best-loss run.
- The target matrices and transport retain their selected row/column order. A shuffled distance matrix looks scrambled even when geometry is unchanged.
- **Δ tree distance** and **Δ edge length** first align the target by known original node ID, then subtract the source. These isolate physical deformation. Alignment is explicitly diagnostic and does not use the inferred transport.
- Difference matrices use signed colors and suppress differences below 1e-10 for display only. Raw float64 deltas are saved.
- Incorrect synthetic node-ID transport connectors are emphasized in a separate color. Selecting a node or cell highlights the relevant nodes and connections throughout the view.
- The summary table reports the currently selected ordering protocol across all seven geometries. The selected run also shows known-correspondence cost and transport-weighted source-tree path error, which distinguishes small local swaps from distant mismatches.

## Files and verification

Each case directory contains ordered and shuffled SWCs, complete target/difference CSV matrices, `runs.json` with every result and loss history, and `matrices.npz`. The NPZ includes full source/target metrics, XYZ, permutation, masses, affected-node indices, and `all_transports` / `all_initial_plans` with shape **(3 protocols, 12 starts, 202, 202)**. Protocol axis order is ordered, matched-shuffled, fresh-shuffled; initialization order matches `runs.json`. A shuffled plan's target columns map to original identities via `permutation`.

`report.json` records construction and all numerical results. `summary.csv` is a compact comparison. `viewer_data.json` stores every run's plan losslessly as a permutation when possible, or sparse entries otherwise; the shared source tree is deduplicated in the final browser payload.

`independent_verification.json` checks all 252 plans against archived full arrays, source/target SWCs, independent tree traversal, matrix CSVs, nonnegative marginals, direct support-sum objectives, true and region correspondence metrics, source hashes, compact encoding, and matched permutation equivalence. `../checks/deformation_browser_check.json` records offline browser interaction tests for every geometry and ordering controls, run selection, shuffled node picking, matrix-difference alignment, and mobile layout.

Reproduce from the repository root:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python compute_deformations.py
.venv/bin/python verify_deformations.py
python3 build_viewer.py
python3 export_browser.py
node checks/deformation_browser_check.cjs
```
