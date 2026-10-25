# CROW excavation: Kratos' wall results

These files hold the wall results that Kratos' own test checks its runs against. The
benchmarks in `benchmarks/cases.py` check the Styx runs of the same model
(`tests/models/crow.py`) against the same numbers.

| File | Benchmark | Soils and wall contacts |
|---|---|---|
| `linear_elastic.csv` | BM-CROW-LE | Linear elastic soils, linear elastic contacts |
| `mohr_coulomb.csv` | BM-CROW-MC | Mohr-Coulomb soils, Coulomb contacts |

## Source

- Kratos test: `applications/GeoMechanicsApplication/tests/test_CROW_case.py`:
  - `test_staged_construction_with_linear_elastic_behavior` (`linear_elastic.csv`)
  - `test_staged_construction_with_mohr_coulomb_clay_sand_using_linear_iteration`
    (`mohr_coulomb.csv`)
- Files: `tests/crow_validation/<case>/staged_construction/<stage>__expected_results_wall.csv`,
  with `<case>` = `linear_elastic` or `mohr_coulomb_clay-sand`, for the stages 3, 4, 6
  and 7 (the stages the Kratos test checks).
- Kratos commit of these files: `7f16946afac033415d1732673a2db7ca668bc709` (2026-08-11).

## What changed from the source

Kratos lists each value by node id in its own mesh, `crow_validation/common/model.mdpa`.
Styx makes its own mesh, so the node ids do not match. These files give the level `y` of
each node instead, read from that `model.mdpa`. The wall is at x = 5 m, so `y` alone
finds the node. The values are not changed.

## Columns

| Column | Unit | Kratos variable |
|---|---|---|
| `stage` | - | Kratos stage name |
| `y_in_m` | m | node level |
| `bending_moment_in_Nm_per_m` | N m/m | `BENDING_MOMENT` |
| `shear_force_in_N_per_m` | N/m | `SHEAR_FORCE` |
| `normal_force_in_N_per_m` | N/m | `AXIAL_FORCE` |
| `horizontal_total_displacement_in_m` | m | `TOTAL_DISPLACEMENT_X` |

## Updating

When Kratos changes its expected results, copy the new files and convert them again:
replace each node id with the `y` of that node in `model.mdpa`, sort by `y`, and update
the commit above.
