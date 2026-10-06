# RRUFF Rescue-Ready 12 Audit

本文件只整理现有审计结果中已经确认的 12 条 rescue-ready 样品。
未重新检索 COD、下载 CIF、运行 diffraction，也未修改 807 curated、v2/v3、MongoDB 或正式 CrystalDB。

## Summary

- total_rescue_ready = 12
- structure_only_supported = 1
- diffraction_supported = 11
- duplicate_sample_id = 0
- missing_cod_id = 0
- missing_local_cif = 0

晶胞差异沿用 candidate details 中的原始字段：
`cell_length_difference` 为相对长度差（fraction），`cell_angle_difference` 为角度差（degree）。
没有 diffraction 的结构确认项，其 diffraction 相关字段均保留为 `null`。

## Rescue Links

| sample_id | COD ID | mineral_name | candidate_name | chemistry_status | space_group_status | cell_length_difference | cell_angle_difference | diffraction_status | matched_count | median_residual | weighted_residual | max_residual | zero_shift | rescue_basis |
|---|---:|---|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| R080124 | 9004354 | Khinite | Parakhinite | compatible | equivalent | 0.0022270474917879127 | 0.0 | null | null | null | null | null | null | structurally_ready_for_rescue |
| R040166 | 9009514 | Chenevixite | Luetheite | solid_solution_or_substitution_review | equivalent | 0.0 | 0.0 | diffraction_compatible | 17 | 0.024878736118232325 | 0.03293851906119936 | 0.14096892659141957 | 0.028130883182051036 | diffraction_supported_rescue |
| R050093 | 9005624 | Gormanite | Souzalite | solid_solution_or_substitution_review | equivalent | 0.0 | 0.0 | diffraction_compatible | 19 | 0.01626883725089101 | 0.016576627540929194 | 0.0948120151498415 | 0.040786909520765136 | diffraction_supported_rescue |
| R050548 | 9009702 | Curienite | Curienite | solid_solution_or_substitution_review | equivalent | 0.02135655908846868 | 0.0 | diffraction_compatible | 20 | 0.02099520337722538 | 0.021278251451717793 | 0.106055690697346 | 0.04783843027355772 | diffraction_supported_rescue |
| R060168 | 9009858 | Gmelinite-Na | Gmelinite-Na | solid_solution_or_substitution_review | equivalent | 0.02900326797385628 | 0.0 | diffraction_compatible | 20 | 0.04112754167507049 | 0.027491358841830286 | 0.1038545949996319 | 0.03474451572724124 | diffraction_supported_rescue |
| R060393 | 9004106 | Miserite | Miserite | solid_solution_or_substitution_review | equivalent | 0.01079781831103491 | 1.2743000000000109 | diffraction_compatible | 15 | 0.047451773028548416 | 0.042965756485983254 | 0.14452411467592796 | 0.003405937666300929 | diffraction_supported_rescue |
| R060683 | 9017577 | Philipsbornite | Philipsbornite | solid_solution_or_substitution_review | equivalent | 0.027450444292549565 | 0.0 | diffraction_compatible | 18 | 0.034310458970846724 | 0.035585665482228857 | 0.12101397974872441 | 0.13628749415807206 | diffraction_supported_rescue |
| R070093 | 9008075 | Meneghinite | Meneghinite | compatible | equivalent | 0.03050433328421473 | 0.0 | diffraction_compatible | 20 | 0.0286919137830548 | 0.03193947815021834 | 0.10735070250216694 | 0.027697064590000764 | diffraction_supported_rescue |
| R070204 | 9000000 | Grunerite | Grunerite | solid_solution_or_substitution_review | equivalent | 0.026880503292237942 | 0.7583000000000055 | diffraction_compatible | 15 | 0.04364059296757716 | 0.030068384615122346 | 0.14328563722118304 | 0.03397708131456767 | diffraction_supported_rescue |
| R070713 | 9000944 | Roeblingite | Roeblingite | solid_solution_or_substitution_review | equivalent | 0.003825406977445794 | 1.2616000000000014 | diffraction_compatible | 19 | 0.03335163431331267 | 0.04055579038702085 | 0.11680241856048923 | -0.001834930094714693 | diffraction_supported_rescue |
| R080044 | 9000221 | Allanite-(Ce) | Allanite-(Ce) | solid_solution_or_substitution_review | equivalent | 0.021340560950234927 | 0.9074000000000098 | diffraction_compatible | 17 | 0.04789087761654187 | 0.0408459756551072 | 0.1246728740123757 | -0.01701846202095325 | diffraction_supported_rescue |
| R130121 | 9012868 | Sussexite | Sussexite | solid_solution_or_substitution_review | equivalent | 0.03007557439170064 | 1.8330600000000032 | diffraction_compatible | 16 | 0.025161490442147993 | 0.03368167151715316 | 0.08987751303691738 | 0.058577248297794426 | diffraction_supported_rescue |

## Required Mapping List

- R080124 -> 9004354 -> structurally_ready_for_rescue
- R040166 -> 9009514 -> diffraction_supported_rescue
- R050093 -> 9005624 -> diffraction_supported_rescue
- R050548 -> 9009702 -> diffraction_supported_rescue
- R060168 -> 9009858 -> diffraction_supported_rescue
- R060393 -> 9004106 -> diffraction_supported_rescue
- R060683 -> 9017577 -> diffraction_supported_rescue
- R070093 -> 9008075 -> diffraction_supported_rescue
- R070204 -> 9000000 -> diffraction_supported_rescue
- R070713 -> 9000944 -> diffraction_supported_rescue
- R080044 -> 9000221 -> diffraction_supported_rescue
- R130121 -> 9012868 -> diffraction_supported_rescue

## Source Files

- `data/mappings/rescue_review_v1/high_priority_36_review.csv`
- `data/mappings/rescue_review_v1/high_priority_35_diffraction_validation.csv`
- `data/mappings/rescue_review_v1/rruff_rescue_candidate_details_v1.csv`
- corresponding local CIF files listed in the CSV `cif_file_path` and `source_files` columns

这些结果只是确认可补救的结构链接清单，不自动并入原 807，也不改变任何历史结果。
