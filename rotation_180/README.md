# Ti8 180-degree rotation control

## Construction and results

All 202 source Ti8 vertices, original IDs, parent IDs, SWC types, and radii are retained. The duplicate is a synthetic copy of the same neuron, not an additional biological neuron. The rotation is 180° around Z through the arithmetic centroid of the source node coordinates:

```text
c = [74.39085643564358, 438.8853267326731, 117.79329207920793]
R = diag(-1, -1, 1)
XYZ_rotated = (XYZ_original - c) @ R.T + c
```

The rotated SWC is written with 17 significant digits and read back before computing its weighted adjacency and shortest-path distances. Edge weights are Euclidean parent–child segment lengths. Both node measures are uniform, with mass 1/202 per node.

| Quantity | Result |
|---|---:|
| GW distance, ½√loss | 7.34278807814224 × 10⁻¹⁵ native units |
| Squared GW loss | 2.1566614704203126 × 10⁻²⁸ native units² |
| Maximum adjacency difference | 1.199040866595169 × 10⁻¹⁴ |
| Maximum tree-distance difference | 8.526512829121202 × 10⁻¹⁴ |
| Transport shape | 202 × 202 |
| Positive transport entries | 202 |
| Same-original-ID transport mass | 100% to roundoff |
| Maximum difference from I/202 | 0 |
| Row / column marginal errors | 0 / 0 |

Rotation preserves all segment lengths and hence all shortest-path tree distances. Therefore the exact mathematical GW distance is zero; the reported residual comes from floating-point arithmetic. The transport matrix was computed by the solver, not replaced with an identity matrix. Node IDs are used to validate recovery afterward, not as a transport constraint. Straight 3D connectors identify corresponding points even though their XYZ locations differ after rotation; GW has no spatial-coordinate penalty in this experiment.

## Same optimization method

The POT conditional-gradient solver, square loss, no entropy regularization, common diameter scaling, 1,000-iteration limit, 1e-12 stopping tolerances, and 12 starts match the original Ti8–Ti9 experiment. Starts are the independent product plan, root-distance and mean-distance linear-OT plans, and nine random-cost linear-OT plans with seeds 0–8. The first three recover the identity plan; random starts give distance estimates from 12.3482 to 17.9129. This exposes the importance of initialization in nonconvex GW even when the exact optimum is known.

Near zero, the primary objective is evaluated by the direct nonnegative double sum over transport support. The equivalent subtractive matrix expansion and POT's reported objective can have cancellation at this scale. All selected-plan marginals, the direct objective, the rigid transform, and the identity recovery were checked again in `independent_verification.json`.

## Files and reproduction

- `Ti8_rotated_180_z.swc`: actual synthetic rotated SWC.
- `analysis.json`: interactive payload for the rotation experiment.
- `matrices.npz`: full float64 adjacency/distance matrices, selected transport, masses, XYZ, rotation matrix/centroid, node IDs, and all 12 run transports.
- `transport.csv`: selected coupling with original node IDs on both axes.
- `*_weighted_adjacency.csv`, `*_tree_distance.csv`: complete matrices.
- `runs.json`: all numerical results and full solver loss histories.
- `verification.json`, `independent_verification.json`: construction, invariance, correspondence, and numerical checks.

From the repository root:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv/bin/python compute_rotation.py
python3 build_viewer.py
python3 export_browser.py
node checks/rotation_browser_check.cjs
```

The visualizer can show the source-frame rotation using **Native coordinates · shared frame**, or separate the two trees for readability with a common display scale. Both layouts retain the 180° orientation difference and use the same computed coupling.
