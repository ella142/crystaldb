# Diffraction Validation for 67 Experimental-XY RRUFF Samples

## Scope

本文件只处理现有 `diffraction_needed_160_xy_audit.csv` 中标记为 `experimental_xy_available` 的 67 条样品。
未处理 93 条 `calculated_only`，未重新搜索 COD、下载 CIF，未修改 807 curated、12 条 rescue-ready、177 条 DIF 外 final manifest、v2/v3、MongoDB 或正式 CrystalDB。

## Existing Pipeline Reused

- Frozen engine: `scripts/annotate_rruff_group_diffraction_v1.py`
- Existing wrapper/calibration logic: `scripts/review_high_priority_35_diffraction_v1.py`
- Calibration: `data/mappings/rruff_diffraction_calibration_v1.json`
- CIF -> theoretical reflections
- experimental XY -> peak detection
- one-to-one peak matching
- zero-shift correction
- median, weighted, maximum residual and residual slope
- candidate separability for multi-candidate samples

A compatibility shim was applied only for the installed Gemmi 0.7.5 API: the frozen no-argument space-group call was supplied its required order, and CIFs with an unrecognized setting suffix used the standard space group identified by the CIF IT number. This resolved a concrete runtime compatibility error without changing the diffraction algorithm, calibration, thresholds, or candidate inputs.

The existing calibration and core compatibility rule were reused unchanged: a candidate is `diffraction_compatible` when the matched fraction, median absolute residual, and weighted mean absolute residual are all inside the existing same-radiation positive-reference P95 envelope.

The 67-sample XY audit population is preserved exactly. RAW is preferred when a valid RAW profile exists; processed is used only as fallback. The original `DIFFRACTION SAMPLE DESCRIPTION` is retained, including experimental powder descriptions with mixture or contamination wording.

## Summary

| Metric | Samples |
|---|---:|
| 67 total | 67 |
| diffraction_supported_rescue | 12 |
| multiple_diffraction_compatible_candidates | 48 |
| diffraction_inconclusive | 7 |
| diffraction_incompatible | 0 |
| candidate calculation errors | 0 |
| samples with output | 67 |

## Sample Results

| sample_id | filename_sample_id | candidate_count | evaluable | compatible | final_status | compatible COD IDs | reason |
|---|---|---:|---:|---:|---|---|---|
| R040027 | R040027-1 | 60 | 60 | 41 | multiple_diffraction_compatible_candidates | 9006200,9006201,9006202,9006203,9006204,9006205,9006206,9006207,9006208,9006209,9006210,9006211,9006212,9006213,9006214,9006216,9006221,9006222,9006223,9006226,9006227,9006253,9006256,9006257,9006259,9006260,9006262,9006269,9006270,9007017,9007018,9007019,9007020,9007021,9007022,9007025,9007040,9007044,9007045,9013642,9015620 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R040036 | R040036-1 | 1 | 1 | 1 | diffraction_supported_rescue | 1010542 | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R040090 | R040090-1 | 8 | 8 | 6 | multiple_diffraction_compatible_candidates | 1514121,1514236,1514240,9001963,9001964,9001965 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R040091 | R040091-1 | 8 | 8 | 8 | multiple_diffraction_compatible_candidates | 1011262,1514120,1514121,1514236,1514240,9001963,9001964,9001965 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R040107 | R040107-1 | 15 | 15 | 12 | multiple_diffraction_compatible_candidates | 9000485,9001519,9001520,9001795,9001796,9001798,9008149,9013186,9013187,9013188,9013190,9013191 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R040128 | R040128-1 | 19 | 19 | 9 | multiple_diffraction_compatible_candidates | 9000642,9000643,9000644,9000646,9000647,9002000,9004009,9004010,9008207 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R040160 | R040160-9 | 2 | 2 | 0 | diffraction_inconclusive | null | Diffraction metrics were obtained, but no candidate met the existing core compatibility envelope and the result is not a zero-match rejection. |
| R040165 | R040165-1 | 3 | 3 | 3 | multiple_diffraction_compatible_candidates | 9009688,9009689,9009690 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R040171 | R040171-1 | 4 | 4 | 4 | multiple_diffraction_compatible_candidates | 9000129,9004739,9014585,9015844 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R040172 | R040172-1 | 6 | 6 | 2 | multiple_diffraction_compatible_candidates | 9009626,9009627 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R040173 | R040173-1 | 6 | 6 | 2 | multiple_diffraction_compatible_candidates | 9009626,9009627 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R040174 | R040174-1 | 4 | 4 | 2 | multiple_diffraction_compatible_candidates | 9004016,9009716 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R040181 | R040181-1 | 5 | 5 | 5 | multiple_diffraction_compatible_candidates | 9004387,9004388,9011171,9011172,9011399 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050014 | R050014-1 | 9 | 9 | 6 | multiple_diffraction_compatible_candidates | 9009305,9009661,9014472,9014807,9015939,9016278 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050024 | R050024-1 | 3 | 3 | 2 | multiple_diffraction_compatible_candidates | 9008105,9009404 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050035 | R050035-1 | 31 | 31 | 25 | multiple_diffraction_compatible_candidates | 1011221,9001022,9001038,9001499,9001500,9001501,9001502,9002336,9002337,9004081,9004082,9004083,9004256,9004257,9004258,9004259,9004477,9004478,9004529,9004768,9004769,9004770,9010614,9014245,9014836 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050056 | R050056-1 | 31 | 31 | 25 | multiple_diffraction_compatible_candidates | 9001022,9001038,9001499,9001501,9001502,9002335,9002336,9002337,9004081,9004082,9004083,9004256,9004257,9004258,9004259,9004443,9004477,9004478,9004529,9004768,9004769,9004770,9010614,9016909,9016939 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050075 | R050075-1 | 9 | 9 | 8 | multiple_diffraction_compatible_candidates | 9009305,9009661,9014082,9014472,9014807,9015212,9015939,9016278 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050089 | R050089-1 | 3 | 3 | 3 | multiple_diffraction_compatible_candidates | 9009688,9009689,9009690 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050092 | R050092-1 | 2 | 2 | 2 | multiple_diffraction_compatible_candidates | 9009851,9009852 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050094 | R050094-1 | 19 | 19 | 10 | multiple_diffraction_compatible_candidates | 9000642,9000643,9000644,9000646,9000647,9002000,9002001,9004009,9004010,9008207 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050149 | R050149-1 | 3 | 3 | 2 | multiple_diffraction_compatible_candidates | 9008105,9009404 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050233 | R050233-1 | 31 | 31 | 25 | multiple_diffraction_compatible_candidates | 1011221,9001022,9001038,9001499,9001500,9001501,9001502,9002336,9002337,9004081,9004082,9004083,9004256,9004257,9004258,9004259,9004442,9004477,9004478,9004529,9004768,9004769,9004770,9014836,9016939 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050279 | R050279-1 | 1 | 1 | 1 | diffraction_supported_rescue | 9009539 | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050355 | R050355-1 | 7 | 7 | 1 | diffraction_supported_rescue | 9009632 | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050385 | R050385-1 | 9 | 9 | 5 | multiple_diffraction_compatible_candidates | 9000473,9000532,9006541,9006542,9006543 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050388 | R050388-1 | 9 | 9 | 8 | multiple_diffraction_compatible_candidates | 9000473,9000532,9006541,9006542,9006543,9006544,9006546,9006547 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050390 | R050390-1 | 9 | 9 | 8 | multiple_diffraction_compatible_candidates | 9000473,9000532,9006541,9006542,9006543,9006544,9006545,9006546 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050399 | R050399-1 | 22 | 22 | 1 | diffraction_supported_rescue | 9012439 | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050403 | R050403-1 | 1 | 1 | 1 | diffraction_supported_rescue | 9000015 | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050414 | R050414-1 | 56 | 56 | 34 | multiple_diffraction_compatible_candidates | 9000893,9000894,9000895,9000896,9000897,9000898,9001536,9001537,9001539,9001544,9001545,9001546,9001559,9001560,9001561,9001858,9001860,9001861,9002289,9002294,9002295,9002296,9002297,9003693,9003697,9003698,9005094,9005095,9005096,9005097,9005099,9005130,9005131,9005132 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050442 | R050442-1 | 4 | 4 | 4 | multiple_diffraction_compatible_candidates | 9007517,9014090,9014599,9015642 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050489 | R050489-1 | 31 | 31 | 24 | multiple_diffraction_compatible_candidates | 1011221,9001022,9001499,9001500,9001501,9001502,9002336,9002337,9004082,9004083,9004256,9004257,9004258,9004259,9004477,9004478,9004529,9004768,9004769,9004770,9010614,9014245,9014836,9016939 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050501 | R050501-1 | 3 | 3 | 2 | multiple_diffraction_compatible_candidates | 1011170,9009404 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050532 | R050532-1 | 6 | 6 | 6 | multiple_diffraction_compatible_candidates | 1011121,9004387,9004388,9011171,9011172,9011399 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R050625 | R050625-1 | 1 | 1 | 1 | diffraction_supported_rescue | 9017614 | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060023 | R060023-1 | 19 | 19 | 14 | multiple_diffraction_compatible_candidates | 9000642,9000643,9000644,9000646,9000647,9002000,9002001,9002002,9004009,9004010,9008207,9008387,9009963,9015469 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060054 | R060054-1 | 36 | 36 | 31 | multiple_diffraction_compatible_candidates | 9000525,9000526,9000527,9000528,9000529,9000681,9000702,9000703,9000704,9001030,9001031,9001312,9002199,9002201,9002203,9005077,9005079,9016731,9016733,9016735,9016747,9016748,9016749,9016750,9016751,9016754,9016755,9016756,9016774,9016776,9016778 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060060 | R060060-1 | 8 | 8 | 6 | multiple_diffraction_compatible_candidates | 9000027,9000418,9000878,9000879,9001855,9001856 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060073 | R060073-1 | 3 | 3 | 3 | multiple_diffraction_compatible_candidates | 9000182,9013489,9013490 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060117 | R060117-1 | 1 | 1 | 1 | diffraction_supported_rescue | 9005584 | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060133 | R060133-1 | 1 | 1 | 1 | diffraction_supported_rescue | 9005584 | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060156 | R060156-1 | 2 | 2 | 2 | multiple_diffraction_compatible_candidates | 1011021,9009581 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060192 | R060192-1 | 2 | 2 | 0 | diffraction_inconclusive | null | Diffraction metrics were obtained, but no candidate met the existing core compatibility envelope and the result is not a zero-match rejection. |
| R060198 | R060198-1 | 1 | 1 | 0 | diffraction_inconclusive | null | Diffraction metrics were obtained, but no candidate met the existing core compatibility envelope and the result is not a zero-match rejection. |
| R060215 | R060215-1 | 10 | 10 | 10 | multiple_diffraction_compatible_candidates | 9002411,9002412,9002413,9002414,9002415,9002416,9002417,9002418,9002419,9002420 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060292 | R060292-1 | 1 | 1 | 1 | diffraction_supported_rescue | 9005443 | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060300 | R060300-1 | 15 | 15 | 12 | multiple_diffraction_compatible_candidates | 9000485,9001518,9001519,9001520,9001795,9001796,9013186,9013187,9013188,9013189,9013190,9013191 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060417 | R060417-1 | 6 | 6 | 3 | multiple_diffraction_compatible_candidates | 9009626,9009627,9009628 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060501 | R060501-1 | 1 | 1 | 0 | diffraction_inconclusive | null | Diffraction metrics were obtained, but no candidate met the existing core compatibility envelope and the result is not a zero-match rejection. |
| R060512 | R060512-1 | 8 | 8 | 8 | multiple_diffraction_compatible_candidates | 1011262,1514120,1514121,1514236,1514240,9001963,9001964,9001965 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060520 | R060520-1 | 1 | 1 | 1 | diffraction_supported_rescue | 9000033 | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060532 | R060532-1 | 31 | 31 | 27 | multiple_diffraction_compatible_candidates | 1011221,9001022,9001038,9001499,9001502,9002335,9002336,9002337,9004081,9004082,9004083,9004256,9004257,9004258,9004259,9004442,9004443,9004477,9004478,9004529,9004768,9004769,9004770,9010614,9014245,9014836,9016939 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060639 | R060639-9 | 2 | 2 | 0 | diffraction_inconclusive | null | Diffraction metrics were obtained, but no candidate met the existing core compatibility envelope and the result is not a zero-match rejection. |
| R060725 | R060725-1 | 14 | 14 | 9 | multiple_diffraction_compatible_candidates | 9000757,9000758,9001568,9010129,9010130,9010132,9010133,9013852,9013854 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060796 | R060796-1 | 22 | 22 | 4 | multiple_diffraction_compatible_candidates | 9006783,9007310,9007311,9012439 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060797 | R060797-1 | 22 | 22 | 1 | diffraction_supported_rescue | 9012439 | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R060901 | R060901-1 | 1 | 1 | 1 | diffraction_supported_rescue | 9015080 | Exactly one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R061020 | R061020-1 | 4 | 4 | 3 | multiple_diffraction_compatible_candidates | 9000089,9000090,9013941 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R061031 | R061031-1 | 7 | 7 | 6 | multiple_diffraction_compatible_candidates | 9000027,9000418,9000878,9001855,9001856,9017228 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R061043 | R061043-1 | 1 | 1 | 0 | diffraction_inconclusive | null | Diffraction metrics were obtained, but no candidate met the existing core compatibility envelope and the result is not a zero-match rejection. |
| R061076 | R061076-1 | 2 | 2 | 0 | diffraction_inconclusive | null | Diffraction metrics were obtained, but no candidate met the existing core compatibility envelope and the result is not a zero-match rejection. |
| R070137 | R070137-1 | 55 | 55 | 38 | multiple_diffraction_compatible_candidates | 9002487,9002488,9002489,9002490,9002491,9002492,9002498,9002499,9005102,9005103,9005104,9005105,9005106,9005107,9005108,9005109,9005110,9005111,9005112,9005113,9005114,9005295,9005395,9005396,9005397,9005398,9005399,9005400,9005401,9005402,9005403,9006893,9006897,9006898,9006899,9006904,9006907,9009894 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R070229 | R070229-1 | 11 | 11 | 9 | multiple_diffraction_compatible_candidates | 9001119,9001120,9001121,9001883,9001884,9001885,9001886,9001887,9007453 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R070686 | R070686-1 | 4 | 4 | 3 | multiple_diffraction_compatible_candidates | 9000129,9004739,9015844 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R080045 | R080045-1 | 5 | 5 | 3 | multiple_diffraction_compatible_candidates | 9005423,9005424,9005425 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |
| R090057 | R090057-1 | 2 | 2 | 2 | multiple_diffraction_compatible_candidates | 1524786,9000774 | More than one existing candidate is inside the calibrated same-radiation core compatibility envelope. |

## Candidate Metrics

| sample_id | COD ID | candidate status | matched_count | median_residual | weighted_residual | max_residual | residual_slope | zero_shift | core P95 | separability | calculation error |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|
| R040027 | 9006200 | diffraction_compatible | 17 | 0.05939446798301162 | 0.034758194011311264 | 0.10003334528970242 | 0.0006651179314114276 | -0.006344421042829396 | true | true | null |
| R040027 | 9006201 | diffraction_compatible | 17 | 0.05755377545688134 | 0.034674878844193235 | 0.1011754233761053 | 0.0006979762794214842 | -0.0055508315170840206 | true | true | null |
| R040027 | 9006202 | diffraction_compatible | 17 | 0.05387282775006952 | 0.034520442873607615 | 0.10345934771460463 | 0.0007636919048762857 | -0.003963774838076972 | true | true | null |
| R040027 | 9006203 | diffraction_compatible | 17 | 0.04843728846030615 | 0.03398114021300419 | 0.11415592287153231 | 0.0008458344298787618 | -0.00982228773956706 | true | true | null |
| R040027 | 9006204 | diffraction_compatible | 17 | 0.04738943768867898 | 0.03414185375487663 | 0.11087996775580677 | 0.0009772578336638665 | 0.0011930328011793279 | true | true | null |
| R040027 | 9006205 | diffraction_compatible | 17 | 0.05385419232602828 | 0.03281008655140796 | 0.11237681084168116 | 0.00016281163173654682 | -0.006517506037624798 | true | true | null |
| R040027 | 9006206 | diffraction_compatible | 17 | 0.05939446798301162 | 0.034492430737410214 | 0.10003334528970242 | 0.0006651179314114276 | -0.006344421042829396 | true | true | null |
| R040027 | 9006207 | diffraction_compatible | 17 | 0.05755377545688134 | 0.03446544191313871 | 0.1011754233761053 | 0.0006979762794214842 | -0.0055508315170840206 | true | true | null |
| R040027 | 9006208 | diffraction_compatible | 17 | 0.05387282775006952 | 0.03423895952374896 | 0.10345934771460463 | 0.0007636919048762857 | -0.003963774838076972 | true | true | null |
| R040027 | 9006209 | diffraction_compatible | 17 | 0.04843728846030615 | 0.03361743217308186 | 0.11415592287153231 | 0.0008458344298787618 | -0.00982228773956706 | true | true | null |
| R040027 | 9006210 | diffraction_compatible | 17 | 0.04738943768867898 | 0.033769417049571586 | 0.11087996775580677 | 0.0009772578336638665 | 0.0011930328011793279 | true | true | null |
| R040027 | 9006211 | diffraction_compatible | 17 | 0.05939446798301162 | 0.034084690107191784 | 0.10003334528970242 | 0.0006651179314114276 | -0.006344421042829396 | true | true | null |
| R040027 | 9006212 | diffraction_compatible | 17 | 0.05755377545688134 | 0.03390498243215083 | 0.1011754233761053 | 0.0006979762794214842 | -0.0055508315170840206 | true | true | null |
| R040027 | 9006213 | diffraction_compatible | 17 | 0.05387282775006952 | 0.03402579900588214 | 0.10345934771460463 | 0.0007636919048762857 | -0.003963774838076972 | true | true | null |
| R040027 | 9006214 | diffraction_compatible | 17 | 0.04843728846030615 | 0.03324859305716945 | 0.11415592287153231 | 0.0008458344298787618 | -0.00982228773956706 | true | true | null |
| R040027 | 9006216 | diffraction_compatible | 17 | 0.050192463038200685 | 0.034011990451133345 | 0.10574296299778041 | 0.0008294061032303327 | -0.0023768813010676126 | true | true | null |
| R040027 | 9006221 | diffraction_compatible | 17 | 0.05939446798301162 | 0.034551547256566645 | 0.10003334528970242 | 0.0006651179314114276 | -0.006344421042829396 | true | true | null |
| R040027 | 9006222 | diffraction_compatible | 17 | 0.05755377545688134 | 0.03452180670494266 | 0.1011754233761053 | 0.0006979762794214842 | -0.0055508315170840206 | true | true | null |
| R040027 | 9006223 | diffraction_compatible | 17 | 0.05387282775006952 | 0.03429567567056274 | 0.10345934771460463 | 0.0007636919048762857 | -0.003963774838076972 | true | true | null |
| R040027 | 9006226 | diffraction_compatible | 17 | 0.05939446798301162 | 0.03418237559925567 | 0.10003334528970242 | 0.0006651179314114276 | -0.006344421042829396 | true | true | null |
| R040027 | 9006227 | diffraction_compatible | 17 | 0.05755377545688134 | 0.03402443404276751 | 0.1011754233761053 | 0.0006979762794214842 | -0.0055508315170840206 | true | true | null |
| R040027 | 9006253 | diffraction_compatible | 17 | 0.05939446798301162 | 0.03458869728016791 | 0.10003334528970242 | 0.0006651179314114276 | -0.006344421042829396 | true | true | null |
| R040027 | 9006256 | diffraction_compatible | 17 | 0.04843728846030615 | 0.03373190407290174 | 0.11415592287153231 | 0.0008458344298787618 | -0.00982228773956706 | true | true | null |
| R040027 | 9006257 | diffraction_compatible | 17 | 0.04738943768867898 | 0.03381811696431015 | 0.11087996775580677 | 0.0009772578336638665 | 0.0011930328011793279 | true | true | null |
| R040027 | 9006259 | diffraction_compatible | 17 | 0.05755377545688134 | 0.03457779408024326 | 0.1011754233761053 | 0.0006979762794214842 | -0.0055508315170840206 | true | true | null |
| R040027 | 9006260 | diffraction_compatible | 17 | 0.05387282775006952 | 0.034312450682365485 | 0.10345934771460463 | 0.0007636919048762857 | -0.003963774838076972 | true | true | null |
| R040027 | 9006262 | diffraction_compatible | 17 | 0.04738943768867898 | 0.033899826264757314 | 0.11087996775580677 | 0.0009772578336638665 | 0.0011930328011793279 | true | true | null |
| R040027 | 9006269 | diffraction_compatible | 17 | 0.036130236457559306 | 0.017671379459110723 | 0.12386976354244439 | -0.0009503811029197274 | 0.03733165288078055 | true | true | null |
| R040027 | 9006270 | diffraction_compatible | 17 | 0.04738943768867898 | 0.03388291581950481 | 0.11087996775580677 | 0.0009772578336638665 | 0.0011930328011793279 | true | true | null |
| R040027 | 9007017 | diffraction_compatible | 17 | 0.04670828519486747 | 0.029212963586543548 | 0.11869716518251039 | 7.081601463272851e-05 | 0.007025788845304248 | true | true | null |
| R040027 | 9007018 | diffraction_compatible | 17 | 0.05426783270387148 | 0.03328269198554481 | 0.11173298262286835 | 0.00018414892877631755 | -0.005903827340496548 | true | true | null |
| R040027 | 9007019 | diffraction_compatible | 17 | 0.04581636545638901 | 0.03436630028513649 | 0.09567152865308515 | 0.00018705015728588377 | -0.019523968936432823 | true | true | null |
| R040027 | 9007020 | diffraction_compatible | 17 | 0.04915797683115386 | 0.03059217126534241 | 0.12350491570970235 | 0.00031769627012763767 | -0.03525887379845116 | true | true | null |
| R040027 | 9007021 | diffraction_compatible | 17 | 0.027020333907366023 | 0.031053554258221466 | 0.145998902848973 | -0.0006416295716782253 | -0.0680516289077353 | true | true | null |
| R040027 | 9007022 | diffraction_compatible | 15 | 0.034624208168523296 | 0.02749614800385328 | 0.147625369442423 | -0.0016455030471853862 | -0.10027528295018939 | true | true | null |
| R040027 | 9007023 | diffraction_inconclusive | 14 | 0.08315296593528032 | 0.061934976500141674 | 0.14235926328607462 | 0.0005078043371359494 | -0.09085053450166924 | false | true | null |
| R040027 | 9007024 | diffraction_inconclusive | 12 | 0.06459866966764594 | 0.03398143434477394 | 0.1444356264492228 | 0.0033775724018390626 | 0.17244644076474458 | false | true | null |
| R040027 | 9007025 | diffraction_compatible | 14 | 0.05159331382999355 | 0.038084358709485906 | 0.1337522084984073 | 0.0022018938092576113 | 0.10186260561476956 | true | true | null |
| R040027 | 9007026 | diffraction_inconclusive | 10 | 0.04157714771953991 | 0.02978142482145955 | 0.14248761132026289 | 0.0003057322788051092 | 0.0011710781335310116 | false | true | null |
| R040027 | 9007027 | diffraction_inconclusive | 9 | 0.05621049131945455 | 0.044451127988394706 | 0.10134043630993972 | -0.0019365220058934329 | -0.03829052196097393 | false | true | null |
| R040027 | 9007028 | diffraction_inconclusive | 10 | 0.05814102176108449 | 0.03952672435176661 | 0.12417521096394069 | 0.000502084715230811 | -0.12264006359763258 | false | true | null |
| R040027 | 9007029 | diffraction_inconclusive | 10 | 0.03718176810956564 | 0.04121196269714746 | 0.11846265276741264 | 0.00018997933741877492 | -0.11431933262247185 | false | true | null |
| R040027 | 9007030 | diffraction_inconclusive | 10 | 0.05257058429242534 | 0.018873136235626194 | 0.1449763327068183 | -0.0010911541980475963 | 0.05633326016299023 | false | true | null |
| R040027 | 9007031 | diffraction_inconclusive | 10 | 0.06109481572869058 | 0.02448664252723549 | 0.148904786890796 | 0.0006088393003942231 | 0.008070640294633336 | false | true | null |
| R040027 | 9007032 | diffraction_inconclusive | 10 | 0.04109102381863039 | 0.02178881509271014 | 0.1445251996912731 | 0.0012719943183174224 | -0.02104929385771115 | false | true | null |
| R040027 | 9007033 | diffraction_inconclusive | 10 | 0.0632786072651399 | 0.02353976467997765 | 0.13322204968791596 | -0.0002125098655278836 | -0.057119828751364565 | false | true | null |
| R040027 | 9007034 | diffraction_inconclusive | 10 | 0.06955416175059526 | 0.030468908586040913 | 0.1428026937727651 | 0.00037704402875291687 | -0.07999195621797739 | false | true | null |
| R040027 | 9007035 | diffraction_inconclusive | 8 | 0.06772277480163424 | 0.07990725362980887 | 0.12327664367050417 | -0.0011195054524014388 | -0.009238427606973687 | false | true | null |
| R040027 | 9007036 | diffraction_inconclusive | 9 | 0.07796541329516771 | 0.08655452779194954 | 0.1434535774026955 | 0.0005151872484422283 | -0.02850956746794253 | false | true | null |
| R040027 | 9007037 | diffraction_inconclusive | 6 | 0.03894434249639289 | 0.03654452694623599 | 0.14950675971364547 | -0.0008244127501172773 | -0.01435077291722564 | false | true | null |
| R040027 | 9007038 | diffraction_inconclusive | 7 | 0.08711289811638778 | 0.08071304980180993 | 0.13533821397660262 | -0.0012895680889261722 | -0.1500508203057649 | false | true | null |
| R040027 | 9007039 | diffraction_inconclusive | 10 | 0.04550068236056859 | 0.06151877602924219 | 0.10133044699672666 | 0.0005160038533542357 | 0.16548092655825997 | false | true | null |
| R040027 | 9007040 | diffraction_compatible | 11 | 0.03390342048281525 | 0.05628815176070862 | 0.08207776446101889 | 0.0003267866839675567 | 0.08678428734668842 | true | true | null |
| R040027 | 9007041 | diffraction_inconclusive | 13 | 0.059265819868230096 | 0.06034306023198026 | 0.13990221519865997 | -0.0011119296056019271 | -0.03712532608412289 | false | true | null |
| R040027 | 9007042 | diffraction_inconclusive | 9 | 0.05443169795647407 | 0.07881180464601456 | 0.12565197935779082 | 0.0005905684185716279 | -0.014808400126597121 | false | true | null |
| R040027 | 9007043 | diffraction_inconclusive | 8 | 0.05882179761999495 | 0.07340017604069243 | 0.14549036440597263 | 0.0025873131514238174 | -0.09632138581233107 | false | true | null |
| R040027 | 9007044 | diffraction_compatible | 11 | 0.054596950315712434 | 0.04078234511887141 | 0.13410947966761455 | 0.0012373972419843877 | 0.08455260375740892 | true | true | null |
| R040027 | 9007045 | diffraction_compatible | 10 | 0.04427981124455371 | 0.03046076888044416 | 0.10113241935663098 | -0.0005113713845624418 | -0.04280556107551092 | true | true | null |
| R040027 | 9013642 | diffraction_compatible | 17 | 0.060479116269362976 | 0.03364250972466778 | 0.09375053403555 | 0.0006389980613926138 | -0.010709892731703974 | true | true | null |
| R040027 | 9015620 | diffraction_compatible | 17 | 0.05808495498794741 | 0.03476236980299675 | 0.09226516414626929 | 0.0005962705055054764 | -0.01174191186652962 | true | true | null |
| R040036 | 1010542 | diffraction_compatible | 19 | 0.03956952785757295 | 0.039909831360074345 | 0.12116774125414054 | -0.0009461993493337086 | -0.041925661679499626 | true | false | null |
| R040090 | 1011262 | diffraction_inconclusive | 17 | 0.05623326888004243 | 0.06169942948111984 | 0.10350315333812432 | 8.857368927699852e-05 | 0.005659622527431907 | false | true | null |
| R040090 | 1514120 | diffraction_inconclusive | 17 | 0.07015445308486434 | 0.05262699696380351 | 0.14236783700164324 | 0.0006738733458576437 | -0.01557533113868459 | false | true | null |
| R040090 | 1514121 | diffraction_compatible | 20 | 0.018865607403352413 | 0.01459711911530229 | 0.135705191604643 | 0.0010543251213564146 | 0.05514470608052591 | true | true | null |
| R040090 | 1514236 | diffraction_compatible | 17 | 0.04531243876608215 | 0.04441629384860217 | 0.10869843464845985 | 0.0007576049775517097 | 0.04192749432089116 | true | true | null |
| R040090 | 1514240 | diffraction_compatible | 17 | 0.05144123975008341 | 0.045686573839598704 | 0.11376469229076491 | 0.0003467492548787498 | 0.04058948520763295 | true | true | null |
| R040090 | 9001963 | diffraction_compatible | 17 | 0.05239280407782587 | 0.040744539246946446 | 0.12985928258542856 | -0.00033209191723104103 | -0.031208130061386896 | true | true | null |
| R040090 | 9001964 | diffraction_compatible | 16 | 0.052610064657219624 | 0.03747954122664883 | 0.1396301775257598 | 0.0007869230507233179 | -0.020532158947112578 | true | true | null |
| R040090 | 9001965 | diffraction_compatible | 19 | 0.03953023359746055 | 0.030276838981882714 | 0.13706468039767117 | -0.00036939595052642006 | -0.008844999271069298 | true | true | null |
| R040091 | 1011262 | diffraction_compatible | 20 | 0.028551511367005844 | 0.026400629683008815 | 0.10269410187260064 | -0.0006994705595830647 | 0.02878220368666007 | true | true | null |
| R040091 | 1514120 | diffraction_compatible | 20 | 0.01903198957762342 | 0.015131747848167251 | 0.07319631103293034 | -0.0009083786299691357 | 0.038860520826737854 | true | true | null |
| R040091 | 1514121 | diffraction_compatible | 20 | 0.033823835222325016 | 0.026784394451965874 | 0.09604969053455648 | 0.000383639395434514 | -0.005006195925215451 | true | true | null |
| R040091 | 1514236 | diffraction_compatible | 20 | 0.024269030005466874 | 0.02127864993256073 | 0.07987417622373982 | -0.001034678022559454 | 0.024719856127077833 | true | true | null |
| R040091 | 1514240 | diffraction_compatible | 20 | 0.02345403297601223 | 0.01905887458474246 | 0.07640957230643863 | -0.0009098783021877154 | 0.030763749804840756 | true | true | null |
| R040091 | 9001963 | diffraction_compatible | 20 | 0.03056335724335213 | 0.0244110097156706 | 0.0671266833488886 | 0.0002532933102619742 | 0.0563103477809932 | true | true | null |
| R040091 | 9001964 | diffraction_compatible | 20 | 0.038665521747528686 | 0.04170235359111748 | 0.09742320858080689 | -0.00021123738147054254 | 0.029319250805009744 | true | true | null |
| R040091 | 9001965 | diffraction_compatible | 18 | 0.05130681778587842 | 0.047637023173648374 | 0.14700805395416694 | 0.0011339252327857044 | 0.0011550007289287123 | true | true | null |
| R040107 | 9000485 | diffraction_compatible | 18 | 0.012443787687995922 | 0.01583717744464021 | 0.057996691794578226 | 0.000864863930532345 | 0.0602645100714021 | true | true | null |
| R040107 | 9001518 | diffraction_inconclusive | 19 | 0.06766575489146476 | 0.06449933742442332 | 0.12087397245143805 | -0.0014059932990633391 | 0.03353928775949555 | false | true | null |
| R040107 | 9001519 | diffraction_compatible | 18 | 0.04508438001322368 | 0.03391276931481969 | 0.11924716702257498 | -0.0017638993615686322 | -0.04269863957071962 | true | true | null |
| R040107 | 9001520 | diffraction_compatible | 18 | 0.04837532892528351 | 0.051253804005012296 | 0.12460336534012129 | -0.0015349675054951556 | -0.06070065833578653 | true | true | null |
| R040107 | 9001795 | diffraction_compatible | 18 | 0.018484963045102276 | 0.01685498932251035 | 0.0799823989996753 | -0.002206451251630927 | -0.006018359127740069 | true | true | null |
| R040107 | 9001796 | diffraction_compatible | 14 | 0.05243023416212367 | 0.04416282057361239 | 0.12321112821570068 | -0.004248144858496271 | 0.05049392923391949 | true | true | null |
| R040107 | 9001797 | diffraction_inconclusive | 7 | 0.08389446347712948 | 0.04319462085167178 | 0.11200484019757084 | -0.0033505020965703476 | 0.041842408639436 | false | true | null |
| R040107 | 9001798 | diffraction_compatible | 14 | 0.04325233726750888 | 0.04809933951084889 | 0.12156979696014147 | -0.006594668788481344 | 0.02749529973299758 | true | true | null |
| R040107 | 9008149 | diffraction_compatible | 13 | 0.059537061131322844 | 0.033343472736372906 | 0.12717945108474282 | -0.0011164506919405116 | -0.04857884529237566 | true | true | null |
| R040107 | 9013186 | diffraction_compatible | 18 | 0.007262886522713785 | 0.010034513108738331 | 0.03080784658867941 | 0.00014285956617627606 | 0.06128273026227049 | true | true | null |
| R040107 | 9013187 | diffraction_compatible | 18 | 0.022624621183336302 | 0.02254666447982283 | 0.045378245852049304 | 0.0006603360783623915 | 0.05570395278538598 | true | true | null |
| R040107 | 9013188 | diffraction_compatible | 18 | 0.023000942925952117 | 0.013832658703747785 | 0.07109895145013212 | 6.970978678627551e-06 | -0.00977434127421617 | true | true | null |
| R040107 | 9013189 | diffraction_inconclusive | 19 | 0.06706195769906387 | 0.049301453889786864 | 0.13941581664255054 | 0.0023943836748217717 | 0.009427163812688377 | false | true | null |
| R040107 | 9013190 | diffraction_compatible | 15 | 0.028009086678139283 | 0.02588901503920685 | 0.14915059216561133 | 0.0007988205524612667 | 0.019980654970364498 | true | true | null |
| R040107 | 9013191 | diffraction_compatible | 18 | 0.013488487030056007 | 0.018937613084390643 | 0.07512417778031022 | -0.0010712223233663907 | 0.019284975186998565 | true | true | null |
| R040128 | 9000642 | diffraction_compatible | 14 | 0.019189515049705896 | 0.0169783689293965 | 0.07485174047990029 | -0.0004739935134464867 | 0.008514224901357892 | true | true | null |
| R040128 | 9000643 | diffraction_compatible | 14 | 0.02164038191138573 | 0.016686993757690033 | 0.06714795918601624 | -0.00026144617422273685 | 0.0162144679009657 | true | true | null |
| R040128 | 9000644 | diffraction_compatible | 12 | 0.012763374455522225 | 0.040224945070182636 | 0.13003279906059362 | -0.0007875744815894106 | -0.009583652527844322 | true | true | null |
| R040128 | 9000645 | diffraction_inconclusive | 7 | 0.0037439291943393016 | 0.005053464525880725 | 0.01134924505210222 | -4.324718815307202e-06 | 0.02401226915539567 | false | true | null |
| R040128 | 9000646 | diffraction_compatible | 13 | 0.009816783131583406 | 0.03850542667731301 | 0.14266807972172302 | -0.0008991017310503246 | 0.0065884440497399055 | true | true | null |
| R040128 | 9000647 | diffraction_compatible | 12 | 0.011807178434708021 | 0.028682657039529956 | 0.14274957817782052 | -0.0010105857762092855 | 0.006245013608726424 | true | true | null |
| R040128 | 9000648 | diffraction_inconclusive | 8 | 0.006359458709994215 | 0.007495867633988665 | 0.034637697551481494 | -0.0008769377334224975 | 0.026195206282896066 | false | true | null |
| R040128 | 9002000 | diffraction_compatible | 13 | 0.013012882409901394 | 0.01020873363339523 | 0.05762942044585628 | -0.0013529415590783414 | 0.021024780769501206 | true | true | null |
| R040128 | 9002001 | diffraction_inconclusive | 10 | 0.06603684606358762 | 0.03836841226859839 | 0.14021609998196993 | -0.005461733642813128 | -0.04249305919947588 | false | true | null |
| R040128 | 9002002 | diffraction_inconclusive | 7 | 0.05916346189609456 | 0.0463148168943742 | 0.1455507357802155 | -0.005296118548299697 | -0.09050319706471477 | false | true | null |
| R040128 | 9004009 | diffraction_compatible | 17 | 0.024540855472672263 | 0.01680262646085336 | 0.09588185855176334 | -0.0005774903981577905 | -0.028632343676317618 | true | true | null |
| R040128 | 9004010 | diffraction_compatible | 17 | 0.029123627962235332 | 0.018584720700909073 | 0.10732805087842223 | -0.00010322462357169608 | -0.04445653679952244 | true | true | null |
| R040128 | 9004011 | diffraction_inconclusive | 5 | 0.0227444183261305 | 0.01673937358481442 | 0.14729096482428616 | 0.003496164157661013 | 0.10860958837565704 | false | true | null |
| R040128 | 9004012 | diffraction_inconclusive | 5 | 0.02150178744023279 | 0.02027193044797811 | 0.050436774068591816 | 0.0020916922982478327 | 0.0016316003707039783 | false | true | null |
| R040128 | 9004013 | diffraction_inconclusive | 4 | 0.014901547570048024 | 0.01024822996737647 | 0.043398578188140746 | 0.0030870110348828004 | -0.10943088739189477 | false | true | null |
| R040128 | 9008207 | diffraction_compatible | 16 | 0.01144836841190866 | 0.009738224487562388 | 0.06983247399936232 | -0.0012013162774989 | 0.021419320582282353 | true | true | null |
| R040128 | 9008387 | diffraction_inconclusive | 9 | 0.05529980326604189 | 0.06483626320111044 | 0.13939874434893262 | -0.00032102449820555065 | 0.005681152315830218 | false | true | null |
| R040128 | 9009963 | diffraction_inconclusive | 4 | 0.08002533888727292 | 0.04628444527157253 | 0.14519289132710966 | -0.0033043792986517917 | 0.026140239497962625 | false | true | null |
| R040128 | 9015469 | diffraction_inconclusive | 8 | 0.025899672936086304 | 0.02629314478200228 | 0.060333709496289245 | 0.0007434367570012519 | 0.0654723575822942 | false | true | null |
| R040160 | 9009511 | diffraction_inconclusive | 8 | 0.10157352501838623 | 0.07550107585280098 | 0.1473895845029567 | -0.0010318750193087703 | -0.14499042074923274 | false | true | null |
| R040160 | 9017834 | diffraction_inconclusive | 6 | 0.05247766611099092 | 0.05796537475272671 | 0.14784995195529582 | 0.0028016080658112997 | -0.054873270878815106 | false | true | null |
| R040165 | 9009688 | diffraction_compatible | 18 | 0.03779230921576726 | 0.02679868249210399 | 0.10761457682627196 | -0.00020191218843640998 | 0.0692271956134114 | true | true | null |
| R040165 | 9009689 | diffraction_compatible | 18 | 0.058547470549903835 | 0.033543444263775125 | 0.11239503734242362 | 0.00041284951054722474 | 0.021734505912295532 | true | true | null |
| R040165 | 9009690 | diffraction_compatible | 18 | 0.058547470549903835 | 0.03360558644624311 | 0.11239503734242362 | 0.00041284951054722474 | 0.021734505912295532 | true | true | null |
| R040171 | 9000129 | diffraction_compatible | 19 | 0.031176123977644465 | 0.018534767000803917 | 0.1088238760223561 | -0.0007012575778196407 | 0.007175876830718408 | true | true | null |
| R040171 | 9004739 | diffraction_compatible | 20 | 0.019056254067981726 | 0.02035906176806344 | 0.13207342021625834 | -0.0004570120210878075 | 0.050569963925983785 | true | true | null |
| R040171 | 9014585 | diffraction_compatible | 16 | 0.02352888064329761 | 0.02109659861717002 | 0.08396279432614762 | -0.001180418691786811 | 0.001632078966139261 | true | true | null |
| R040171 | 9015844 | diffraction_compatible | 20 | 0.014455673211074327 | 0.019193776751902442 | 0.14956225169709825 | -0.0010402057259760653 | 0.011207377809810737 | true | true | null |
| R040172 | 9009626 | diffraction_compatible | 18 | 0.019687416698403126 | 0.017707337950549632 | 0.13937030011675233 | -0.0007996852921913891 | 0.01423913960260137 | true | true | null |
| R040172 | 9009627 | diffraction_compatible | 18 | 0.019687416698403126 | 0.01729458101456994 | 0.13937030011675233 | -0.0007996852921913891 | 0.01423913960260137 | true | true | null |
| R040172 | 9009628 | diffraction_inconclusive | 15 | 0.08454891884304772 | 0.06984990971645484 | 0.14372802330505863 | -7.394740931525624e-05 | -0.06332749843879881 | false | true | null |
| R040172 | 9009629 | diffraction_inconclusive | 7 | 0.07312021980347794 | 0.0507832328662231 | 0.10590538526115267 | -0.003962968241344537 | 0.04617326339762684 | false | true | null |
| R040172 | 9009630 | diffraction_inconclusive | 6 | 0.06608943968370973 | 0.05822366348658904 | 0.1343640858859132 | -0.0005095986194094544 | -0.07858514474453315 | false | true | null |
| R040172 | 9009631 | diffraction_inconclusive | 7 | 0.06341861572481378 | 0.04678788280246901 | 0.13284898467820483 | 0.0013204929512299114 | -0.17930555531881964 | false | true | null |
| R040173 | 9009626 | diffraction_compatible | 17 | 0.019261112844645822 | 0.018722927533125634 | 0.14338015423918193 | 0.0007420748688959226 | 0.03412995233049898 | true | true | null |
| R040173 | 9009627 | diffraction_compatible | 17 | 0.019261112844645822 | 0.01810483169529227 | 0.14338015423918193 | 0.0007420748688959226 | 0.03412995233049898 | true | true | null |
| R040173 | 9009628 | diffraction_inconclusive | 15 | 0.06983220926518996 | 0.06630885359799205 | 0.13872206048067426 | 0.0008946194181356624 | -0.0533274984388008 | false | true | null |
| R040173 | 9009629 | diffraction_inconclusive | 11 | 0.03751871840578502 | 0.06675882379912279 | 0.13620787740801887 | 1.0766293040687942e-05 | -0.004465674811640952 | false | true | null |
| R040173 | 9009630 | diffraction_inconclusive | 8 | 0.0760129969478438 | 0.03818795077503104 | 0.1453352761513429 | 0.002233777483164163 | -0.05858514474453003 | false | true | null |
| R040173 | 9009631 | diffraction_inconclusive | 6 | 0.04265791930827767 | 0.05095550880817171 | 0.08411637720190868 | -0.0011735791308748365 | 0.046578067479273955 | false | true | null |
| R040174 | 9004016 | diffraction_compatible | 18 | 0.014267236580355558 | 0.010809327688942974 | 0.10781981087421855 | -0.0013768164282149848 | 0.0289277591548327 | true | true | null |
| R040174 | 9004017 | diffraction_inconclusive | 8 | 0.05462889064304299 | 0.043636794453476756 | 0.11872590987034215 | -0.003001396558187883 | 0.0420497988823314 | false | true | null |
| R040174 | 9004018 | diffraction_inconclusive | 7 | 0.06179485705442289 | 0.03661847732349196 | 0.14247009665470856 | -0.0006459670103560268 | 0.013704966944031227 | false | true | null |
| R040174 | 9009716 | diffraction_compatible | 18 | 0.017977195782124866 | 0.018335785035788924 | 0.11340671705622896 | 0.0006213757939098139 | 0.04766888583953488 | true | true | null |
| R040181 | 9004387 | diffraction_compatible | 18 | 0.024064577158142697 | 0.02320963879234255 | 0.08017734165471069 | -0.0010474467630589126 | -0.02261911657217297 | true | true | null |
| R040181 | 9004388 | diffraction_compatible | 15 | 0.02216500251899589 | 0.025539291525249117 | 0.14804415169712115 | 0.0003907389582903207 | -0.01415689314753621 | true | true | null |
| R040181 | 9011171 | diffraction_compatible | 17 | 0.013898644866776166 | 0.025117975086727334 | 0.1447789773573831 | 0.0006517584203009384 | 0.07671179916563631 | true | true | null |
| R040181 | 9011172 | diffraction_compatible | 17 | 0.013898644866776166 | 0.025929258709834663 | 0.1447789773573831 | 0.0006517584203009384 | 0.07671179916563631 | true | true | null |
| R040181 | 9011399 | diffraction_compatible | 16 | 0.019379634100019416 | 0.024618327559673275 | 0.12712884923631051 | 0.0006495073792428843 | -0.036525638498758894 | true | true | null |
| R050014 | 9009305 | diffraction_compatible | 20 | 0.023854153989152138 | 0.017976103470971797 | 0.05005785832342369 | -0.00023106431998287056 | 0.04302732124202713 | true | true | null |
| R050014 | 9009306 | diffraction_inconclusive | 8 | 0.022908070839345207 | 0.016152159151792262 | 0.075393562828598 | -0.0010931670111301243 | 0.03721036496557595 | false | true | null |
| R050014 | 9009661 | diffraction_compatible | 19 | 0.03167571019895021 | 0.03415356007805032 | 0.09017860213588591 | -0.0020672985602366656 | -0.03811570167297518 | true | true | null |
| R050014 | 9014082 | diffraction_inconclusive | 20 | 0.05492292676362531 | 0.05766087066350072 | 0.14005880634051238 | 0.0007023634308623047 | 0.04232467920653704 | false | true | null |
| R050014 | 9014472 | diffraction_compatible | 20 | 0.021922456668540313 | 0.020015328811528527 | 0.07648998871729518 | 8.21638654301092e-05 | 0.05952322901595153 | true | true | null |
| R050014 | 9014807 | diffraction_compatible | 20 | 0.03261668025310982 | 0.02989967026597366 | 0.09747681527579743 | 0.0011901569881719188 | 0.0675609987298671 | true | true | null |
| R050014 | 9015212 | diffraction_inconclusive | 19 | 0.0670123047042317 | 0.0623436112156717 | 0.13066889752592203 | 0.001364596725768816 | 0.031529627051511966 | false | true | null |
| R050014 | 9015939 | diffraction_compatible | 20 | 0.013285857910322996 | 0.017822380560586538 | 0.07468866974429034 | -0.00048115995646544444 | 0.04916132296109055 | true | true | null |
| R050014 | 9016278 | diffraction_compatible | 20 | 0.019894013230262075 | 0.014423334443446274 | 0.09827274659262031 | -0.0011880702434639788 | 0.043636160813607106 | true | true | null |
| R050024 | 1011170 | diffraction_inconclusive | 18 | 0.06065072796353732 | 0.09320087424146008 | 0.1490572414421507 | -0.0009177300577750618 | 0.035170737520651585 | false | true | null |
| R050024 | 9008105 | diffraction_compatible | 19 | 0.028320989345182568 | 0.04038432992397488 | 0.13468435049357197 | -0.00035518883111647847 | -0.019721625933058817 | true | true | null |
| R050024 | 9009404 | diffraction_compatible | 19 | 0.03418137620264616 | 0.035045376430739746 | 0.14000000000000057 | -0.001062547470443511 | 0.003973578347199691 | true | true | null |
| R050035 | 1011221 | diffraction_compatible | 18 | 0.02804103464866259 | 0.034542251689802565 | 0.09715960576664173 | 0.0011307232806393142 | 0.127579539637372 | true | true | null |
| R050035 | 9001022 | diffraction_compatible | 19 | 0.03365188543839537 | 0.03945892186490541 | 0.12936390662179065 | 1.1779047749907705e-05 | 0.019538159678337053 | true | true | null |
| R050035 | 9001038 | diffraction_compatible | 16 | 0.04398448554305645 | 0.053643680232144594 | 0.12248069731399625 | -0.0005848492156907706 | 0.003460384676969852 | true | true | null |
| R050035 | 9001070 | diffraction_inconclusive | 10 | 0.10223682507978982 | 0.09234947756215507 | 0.14661289574156733 | -0.0014466965062968499 | 0.10247053231632819 | false | true | null |
| R050035 | 9001499 | diffraction_compatible | 20 | 0.04565425066995488 | 0.05088934469520262 | 0.14099285729881217 | -0.00018802653038257314 | 0.003831310170831159 | true | true | null |
| R050035 | 9001500 | diffraction_compatible | 18 | 0.0146368287303833 | 0.014905577564486718 | 0.09297830183488998 | 0.0010385143655168053 | 0.11011010960292111 | true | true | null |
| R050035 | 9001501 | diffraction_compatible | 18 | 0.01122026374138052 | 0.015789834686076736 | 0.08651399327598774 | -0.0007953925527144159 | 0.07271300016821058 | true | true | null |
| R050035 | 9001502 | diffraction_compatible | 18 | 0.03599342949084772 | 0.0309364784720644 | 0.08281922658080987 | -0.0002407674406906016 | 0.02806946877040417 | true | true | null |
| R050035 | 9002335 | diffraction_inconclusive | 19 | 0.053372571798016466 | 0.0625612000244311 | 0.13000913361643995 | -0.0016582644355825683 | -0.030685503373589995 | false | true | null |
| R050035 | 9002336 | diffraction_compatible | 13 | 0.029830728196404976 | 0.029374414807842343 | 0.08247366909097309 | -0.002466527887180178 | 0.018491989771224127 | true | true | null |
| R050035 | 9002337 | diffraction_compatible | 14 | 0.010778652585480941 | 0.018569106261772005 | 0.051486793738718006 | -0.0022676040256768846 | 0.04995270462919699 | true | true | null |
| R050035 | 9004081 | diffraction_compatible | 20 | 0.04900370302715018 | 0.05317947754132082 | 0.1466329266058608 | -0.0002911929308779007 | -0.003971562312138133 | true | true | null |
| R050035 | 9004082 | diffraction_compatible | 18 | 0.01442167327687116 | 0.02269868303196991 | 0.08981576422041648 | -0.0008742204528269232 | 0.0380816301815301 | true | true | null |
| R050035 | 9004083 | diffraction_compatible | 18 | 0.03099945465639209 | 0.03347485796693908 | 0.12532129905671496 | -0.00011393141204635253 | 0.03103705475828278 | true | true | null |
| R050035 | 9004256 | diffraction_compatible | 19 | 0.04096164577839545 | 0.04499284029051051 | 0.1465634903938806 | 0.0004178644189528259 | 0.009070333650601725 | true | true | null |
| R050035 | 9004257 | diffraction_compatible | 18 | 0.01909502947828301 | 0.02422378285316095 | 0.1372867742481958 | -0.0015143232976631209 | 0.04595656402707604 | true | true | null |
| R050035 | 9004258 | diffraction_compatible | 18 | 0.026403216283474862 | 0.023710600157505625 | 0.1291479237607973 | -0.0010491763564943986 | 0.05190207442479178 | true | true | null |
| R050035 | 9004259 | diffraction_compatible | 18 | 0.04116109375197041 | 0.034038221110066755 | 0.11642273340533649 | 0.0015787162390389412 | 0.025812322858566716 | true | true | null |
| R050035 | 9004442 | diffraction_inconclusive | 17 | 0.06869593353849268 | 0.052868730350401814 | 0.1243188808651503 | 0.0005520128108734165 | 0.20409566866504036 | false | true | null |
| R050035 | 9004443 | diffraction_inconclusive | 17 | 0.06916448597395686 | 0.052540862185293066 | 0.1272648626735453 | -0.00016750825297870157 | 0.196203519240024 | false | true | null |
| R050035 | 9004477 | diffraction_compatible | 16 | 0.038886599981605485 | 0.04312987319148439 | 0.14046081925855702 | 0.000529122392715549 | 0.03677054517351763 | true | true | null |
| R050035 | 9004478 | diffraction_compatible | 16 | 0.033638817915466745 | 0.04045140604397421 | 0.132757463333256 | -0.0009367792867298986 | 0.04447390109881866 | true | true | null |
| R050035 | 9004529 | diffraction_compatible | 19 | 0.03760449468603255 | 0.03928430432046248 | 0.13545100183840475 | 0.0012072454966522085 | 0.020584193528591754 | true | true | null |
| R050035 | 9004768 | diffraction_compatible | 19 | 0.04493345344994282 | 0.03993027275998398 | 0.13553263085864842 | 0.0010758408690502853 | 0.023721479004368717 | true | true | null |
| R050035 | 9004769 | diffraction_compatible | 19 | 0.04785921521878578 | 0.04228521952031422 | 0.12502098400356232 | 0.00048820055241621964 | 0.016399241679820875 | true | true | null |
| R050035 | 9004770 | diffraction_compatible | 20 | 0.04817818978356048 | 0.05183047643193727 | 0.13653357465498317 | -0.00048230149583709933 | -0.00036236468158890034 | true | true | null |
| R050035 | 9010614 | diffraction_compatible | 16 | 0.0415789468204153 | 0.04264967719625301 | 0.13969424830750654 | -0.0005741717735313185 | 0.1623571601653122 | true | true | null |
| R050035 | 9014245 | diffraction_compatible | 18 | 0.021160994368919717 | 0.025300960660439728 | 0.10215376417841782 | -0.0009086619427756431 | 0.07499890862770542 | true | true | null |
| R050035 | 9014836 | diffraction_compatible | 18 | 0.03045651772390201 | 0.03290801147091098 | 0.09928835956595705 | 0.00021968781623025956 | 0.07652407424648544 | true | true | null |
| R050035 | 9016909 | diffraction_inconclusive | 16 | 0.07702120891330644 | 0.061444263736666144 | 0.1499405660655171 | -0.00032234196980940766 | 0.17952182741473877 | false | true | null |
| R050035 | 9016939 | diffraction_inconclusive | 16 | 0.07610188619421265 | 0.05570832395446406 | 0.13950600287521553 | 0.0009353682776753224 | 0.196203519240024 | false | true | null |
| R050056 | 1011221 | diffraction_inconclusive | 17 | 0.05717556515603661 | 0.057240189027946475 | 0.1368098658377619 | -0.0015826973547877362 | 0.054231384316510756 | false | true | null |
| R050056 | 9001022 | diffraction_compatible | 17 | 0.038219941763333765 | 0.04156253336105591 | 0.10001625056133889 | -0.0003148455058358556 | -0.011054399595494147 | true | true | null |
| R050056 | 9001038 | diffraction_compatible | 15 | 0.015479576330790223 | 0.03581441667409538 | 0.13213301653358656 | -0.0013359327759780832 | -0.026539615323031285 | true | true | null |
| R050056 | 9001070 | diffraction_inconclusive | 10 | 0.08606721813288143 | 0.059071517219067074 | 0.1293971770258011 | -0.0019916443901910543 | 0.04607256451039721 | false | true | null |
| R050056 | 9001499 | diffraction_compatible | 17 | 0.044125309967213866 | 0.04187511076736458 | 0.07902903325532407 | 0.0014815865982083691 | -0.006168689829170404 | true | true | null |
| R050056 | 9001500 | diffraction_inconclusive | 16 | 0.05404477207323488 | 0.06336399190913944 | 0.14318121315331922 | 0.0028859967446805113 | 0.08657896473222237 | false | true | null |
| R050056 | 9001501 | diffraction_compatible | 17 | 0.037797846676312474 | 0.050213693167604496 | 0.12892153619183233 | 0.0018968361306652623 | 0.06271300016820902 | true | true | null |
| R050056 | 9001502 | diffraction_compatible | 19 | 0.019970299700400318 | 0.03699634459257248 | 0.11458351886088991 | 0.0002471021197371446 | 0.024170264513625028 | true | true | null |
| R050056 | 9002335 | diffraction_compatible | 17 | 0.03722131648401472 | 0.03544119156968437 | 0.07873487265925405 | -0.0007085617721767269 | -0.07347332050601096 | true | true | null |
| R050056 | 9002336 | diffraction_compatible | 14 | 0.017249786424280877 | 0.03508952916687538 | 0.13224615559885677 | -0.0017848903800820179 | 0.008491989771222563 | true | true | null |
| R050056 | 9002337 | diffraction_compatible | 14 | 0.04795348426236146 | 0.044967629380421155 | 0.08309442546596557 | 0.00035728358791952764 | 0.026338192396838878 | true | true | null |
| R050056 | 9004081 | diffraction_compatible | 17 | 0.03244423566417254 | 0.04262942820026836 | 0.10431380715618843 | 0.0010857129766309952 | -0.007216903789679208 | true | true | null |
| R050056 | 9004082 | diffraction_compatible | 18 | 0.020374781222674443 | 0.03571702098292826 | 0.08325710783226903 | 0.000543057516924697 | 0.02826586596111369 | true | true | null |
| R050056 | 9004083 | diffraction_compatible | 18 | 0.020570086456648262 | 0.03716709213332399 | 0.10971476969445604 | -0.0004986478488481466 | 0.01505379594376599 | true | true | null |
| R050056 | 9004256 | diffraction_compatible | 19 | 0.028533817928440897 | 0.03537347248617346 | 0.13842890653234718 | -0.0009161316302441325 | -0.02499950828750741 | true | true | null |
| R050056 | 9004257 | diffraction_compatible | 18 | 0.017150569080660816 | 0.03777193546736673 | 0.09168214094300176 | -0.0011925170281649792 | 0.03669089907184642 | true | true | null |
| R050056 | 9004258 | diffraction_compatible | 18 | 0.013806034769121567 | 0.03813140772627552 | 0.09322677301519633 | -0.0006674329059643007 | 0.041902074424790214 | true | true | null |
| R050056 | 9004259 | diffraction_compatible | 18 | 0.030903255884975778 | 0.03927457726122476 | 0.09715315108624623 | -0.00033530452828588626 | 0.011657822371466509 | true | true | null |
| R050056 | 9004442 | diffraction_inconclusive | 14 | 0.06379880707831731 | 0.0790673492222469 | 0.1304490535873235 | 0.000713959248423519 | 0.010598112230034928 | false | true | null |
| R050056 | 9004443 | diffraction_compatible | 13 | 0.045666131764964035 | 0.053778666335255465 | 0.14272982420088454 | -0.0019343615416858582 | 0.06620351924002499 | true | true | null |
| R050056 | 9004477 | diffraction_compatible | 15 | 0.014935741420483595 | 0.036584050621616154 | 0.12344903801322715 | -0.00038466293374767995 | 0.00953815967833549 | true | true | null |
| R050056 | 9004478 | diffraction_compatible | 16 | 0.010234369008593092 | 0.03595680208457527 | 0.12813504887509453 | 9.975171027526909e-05 | 0.014224170540202863 | true | true | null |
| R050056 | 9004529 | diffraction_compatible | 18 | 0.027644068134905275 | 0.037694627446881145 | 0.09042208830256726 | 0.00010221474942481074 | 0.0018491217520733016 | true | true | null |
| R050056 | 9004768 | diffraction_compatible | 17 | 0.044180947520434444 | 0.04132627197246413 | 0.10676459416487916 | -0.0012799077739370456 | -0.011038931743335922 | true | true | null |
| R050056 | 9004769 | diffraction_compatible | 17 | 0.04714608071270021 | 0.04261138468417291 | 0.09762642141290456 | 0.0006028533028606861 | -0.018595462388695694 | true | true | null |
| R050056 | 9004770 | diffraction_compatible | 17 | 0.03760544210224026 | 0.04074914561215713 | 0.08405260633623612 | 0.0011866030225922855 | -0.011610650057001237 | true | true | null |
| R050056 | 9010614 | diffraction_compatible | 14 | 0.028962268194156593 | 0.05022201188838512 | 0.12143235188993984 | -0.0023127929835521704 | 0.03940027092430398 | true | true | null |
| R050056 | 9014245 | diffraction_inconclusive | 16 | 0.048686748953143066 | 0.05811719290720838 | 0.12152591459159723 | 0.0008731123835347017 | 0.04437105904088412 | false | true | null |
| R050056 | 9014836 | diffraction_inconclusive | 15 | 0.06811351054724923 | 0.05875021213212702 | 0.1350743162721031 | 0.001333822086999739 | -0.028060783107232368 | false | true | null |
| R050056 | 9016909 | diffraction_compatible | 14 | 0.05444003464144309 | 0.04880394012200308 | 0.13570452438674963 | 0.0010512039910985289 | 0.04952182741473976 | true | true | null |
| R050056 | 9016939 | diffraction_compatible | 15 | 0.04230507952043894 | 0.05051761720602193 | 0.14272982420088454 | -0.0013594708412883153 | 0.06620351924002499 | true | true | null |
| R050075 | 9009305 | diffraction_compatible | 19 | 0.02308754564946014 | 0.019577802883595122 | 0.08737764717540131 | -0.00015968592774435824 | 0.0030273212420279805 | true | true | null |
| R050075 | 9009306 | diffraction_inconclusive | 9 | 0.01969698056361402 | 0.026834983986281747 | 0.14632368704737786 | 0.0007596023319294398 | 0.004684281428044557 | false | true | null |
| R050075 | 9009661 | diffraction_compatible | 19 | 0.061356590685448964 | 0.05330428941051041 | 0.11939614653817898 | 0.0009263540837879693 | -0.024699606993738854 | true | true | null |
| R050075 | 9014082 | diffraction_compatible | 20 | 0.025928439622756372 | 0.024669786630504238 | 0.10618478605051251 | 0.0010502362267862807 | 0.056198699496544435 | true | true | null |
| R050075 | 9014472 | diffraction_compatible | 20 | 0.02705752636172143 | 0.02871003121588343 | 0.08875504354047337 | -1.6952010947814933e-05 | 0.005922129676427801 | true | true | null |
| R050075 | 9014807 | diffraction_compatible | 20 | 0.02536947591772787 | 0.027587296683142474 | 0.07337189052437765 | 0.0009964214252668982 | 0.042598581012047276 | true | true | null |
| R050075 | 9015212 | diffraction_compatible | 19 | 0.011279991692212832 | 0.01510359499030364 | 0.06488471894200742 | 0.0009279283477228628 | 0.05530894820944354 | true | true | null |
| R050075 | 9015939 | diffraction_compatible | 20 | 0.025557758534084485 | 0.027951302031987268 | 0.08189201570490923 | -0.0007553244911748665 | 0.002632114994316481 | true | true | null |
| R050075 | 9016278 | diffraction_compatible | 18 | 0.01197852641000452 | 0.009379117532602869 | 0.07216605978268831 | -0.0005323317236610762 | 0.003636160813607958 | true | true | null |
| R050089 | 9009688 | diffraction_compatible | 15 | 0.03553365922756768 | 0.020229972408201766 | 0.09779591541417432 | -0.0010174680205628536 | 0.029045857025518984 | true | true | null |
| R050089 | 9009689 | diffraction_compatible | 16 | 0.053901889098217026 | 0.03292835814868415 | 0.13760496265757638 | 0.0006103750779130052 | -0.018265494087707168 | true | true | null |
| R050089 | 9009690 | diffraction_compatible | 16 | 0.053901889098217026 | 0.032906695891199 | 0.13760496265757638 | 0.0006103750779130052 | -0.018265494087707168 | true | true | null |
| R050092 | 9009851 | diffraction_compatible | 18 | 0.023404651490892547 | 0.01839880771996357 | 0.12937921400791197 | -0.0007946690317455322 | 0.023797856210055812 | true | true | null |
| R050092 | 9009852 | diffraction_compatible | 18 | 0.023404651490892547 | 0.01695275195723315 | 0.12937921400791197 | -0.0007946690317455322 | 0.023797856210055812 | true | true | null |
| R050094 | 9000642 | diffraction_compatible | 17 | 0.024714287830455817 | 0.03185158664999945 | 0.13916444399779238 | -0.0003206644986130947 | -0.012096541103558067 | true | true | null |
| R050094 | 9000643 | diffraction_compatible | 17 | 0.02597573032684153 | 0.029918484420501858 | 0.13538885716757676 | -0.00014598777492599906 | -0.008320954273335346 | true | true | null |
| R050094 | 9000644 | diffraction_compatible | 14 | 0.012226354560090691 | 0.016362429193443294 | 0.14540698128662655 | 0.0009766347037336305 | -0.006347567941247689 | true | true | null |
| R050094 | 9000645 | diffraction_inconclusive | 8 | 0.0015702529052301628 | 0.008923610200653855 | 0.13305786980608758 | -0.0028773567163872475 | -0.004029184194376256 | false | true | null |
| R050094 | 9000646 | diffraction_compatible | 13 | 0.003998737400571883 | 0.011387243130350583 | 0.1438181402422387 | -0.0008615372223209764 | -0.005585021954420455 | true | true | null |
| R050094 | 9000647 | diffraction_compatible | 12 | 0.0063133404960673545 | 0.010031135279065722 | 0.10121721565879938 | 0.0007446581938272834 | 0.001417696396249113 | true | true | null |
| R050094 | 9000648 | diffraction_inconclusive | 9 | 0.004925013998267502 | 0.00894940638199427 | 0.12039228338031194 | -0.0016690439347282922 | -0.0015164883342837499 | false | true | null |
| R050094 | 9002000 | diffraction_compatible | 16 | 0.015757117575581958 | 0.013276553873643147 | 0.11031075984599426 | 0.0010914897484549184 | -0.005531727068209591 | true | true | null |
| R050094 | 9002001 | diffraction_compatible | 12 | 0.05132866921892898 | 0.029496085392189522 | 0.13021609998196482 | -0.0026036640558928298 | -0.07249305919947524 | true | true | null |
| R050094 | 9002002 | diffraction_inconclusive | 8 | 0.061801118712574876 | 0.03930493501203438 | 0.14433442329587365 | -0.00011917900198212191 | -0.12050319706471413 | false | true | null |
| R050094 | 9004009 | diffraction_compatible | 18 | 0.03619507946288891 | 0.0207924948170874 | 0.09737808531004788 | -0.00037332772907744047 | -0.04329804942319271 | true | true | null |
| R050094 | 9004010 | diffraction_compatible | 18 | 0.043769774555272534 | 0.022109828478492365 | 0.1021555914571195 | 0.0016042916568780217 | -0.05604498726835416 | true | true | null |
| R050094 | 9004011 | diffraction_inconclusive | 5 | 0.11822980541911932 | 0.03965438489451848 | 0.1486039136886852 | 0.015280716988771792 | 0.015831810057839846 | false | true | null |
| R050094 | 9004012 | diffraction_inconclusive | 6 | 0.032039584641690766 | 0.021170862586437758 | 0.08893498662835597 | 0.00019552402340186476 | 0.010129812930468773 | false | true | null |
| R050094 | 9004013 | diffraction_inconclusive | 8 | 0.03938416337279449 | 0.041220850246885016 | 0.11401034361245976 | 0.0005427103452671851 | -0.06881912196757511 | false | true | null |
| R050094 | 9008207 | diffraction_compatible | 17 | 0.005377384283043796 | 0.009240962990315767 | 0.13156255599458433 | -0.00025840528641908936 | 0.0012006416201302272 | true | true | null |
| R050094 | 9008387 | diffraction_inconclusive | 7 | 0.09602918846509745 | 0.06593203268429502 | 0.1222556134571775 | -0.0029962835247125726 | 0.08575676976927937 | false | true | null |
| R050094 | 9009963 | diffraction_inconclusive | 8 | 0.09324988702928572 | 0.062208710139320895 | 0.14086530031396904 | -0.004926498044318284 | 0.0013331308250705831 | false | true | null |
| R050094 | 9015469 | diffraction_inconclusive | 9 | 0.03656967103543707 | 0.07620893571138726 | 0.149989807288069 | 0.0013395486822907804 | -0.007957971382271722 | false | true | null |
| R050149 | 1011170 | diffraction_inconclusive | 15 | 0.051483082191666085 | 0.05986696814794977 | 0.12338551808097975 | -0.0011514205942710915 | 0.05611349607849547 | false | true | null |
| R050149 | 9008105 | diffraction_compatible | 19 | 0.03632308951559793 | 0.029621849736966476 | 0.11874895863762447 | -0.0004420750964281445 | 0.0049224529277225315 | true | true | null |
| R050149 | 9009404 | diffraction_compatible | 18 | 0.037451685854275496 | 0.02966319951927335 | 0.12841567947276644 | 1.7398502657113932e-05 | 0.015557898874433818 | true | true | null |
| R050233 | 1011221 | diffraction_compatible | 18 | 0.04610857953124903 | 0.03915629160861594 | 0.10050776108750625 | 0.0012837347721368555 | 0.054231384316510756 | true | true | null |
| R050233 | 9001022 | diffraction_compatible | 17 | 0.04139532342441754 | 0.04244158912563075 | 0.14856114247119478 | -0.0005059401869750485 | -0.029659076171075327 | true | true | null |
| R050233 | 9001038 | diffraction_compatible | 15 | 0.026131305969766316 | 0.044309998541622854 | 0.1414429262835597 | -0.002190960909880883 | -0.06475789634047402 | true | true | null |
| R050233 | 9001070 | diffraction_inconclusive | 12 | 0.056212580507220444 | 0.06596821222525988 | 0.13199184457536361 | 0.0011351858318849684 | 0.03607256451039742 | false | true | null |
| R050233 | 9001499 | diffraction_compatible | 18 | 0.04037950088230602 | 0.041062778798848835 | 0.14885530151373416 | -0.0009961923469159674 | -0.05487733160103758 | true | true | null |
| R050233 | 9001500 | diffraction_compatible | 18 | 0.047592634595025274 | 0.051293888368313244 | 0.14153838609777125 | 0.0019071354288385071 | 0.038756035447995885 | true | true | null |
| R050233 | 9001501 | diffraction_compatible | 18 | 0.04119632097491799 | 0.04383606676542148 | 0.11678414545548321 | 9.268719571823975e-05 | 0.01692927680205969 | true | true | null |
| R050233 | 9001502 | diffraction_compatible | 19 | 0.028604575881823635 | 0.03534735348887883 | 0.1452172139868253 | -0.0016424408743980065 | -0.02519604036044143 | true | true | null |
| R050233 | 9002335 | diffraction_inconclusive | 18 | 0.05439822340772338 | 0.06825424789711076 | 0.1297517047872958 | -0.00021560305155998775 | -0.030446341777327746 | false | true | null |
| R050233 | 9002336 | diffraction_compatible | 15 | 0.03766275400108299 | 0.04535299046571935 | 0.14488106378711052 | 0.001035560825282885 | -0.009808148274249362 | true | true | null |
| R050233 | 9002337 | diffraction_compatible | 16 | 0.03556913931787076 | 0.04875761401615087 | 0.12956899844040493 | -0.0027544338927215106 | 0.0021803352401015275 | true | true | null |
| R050233 | 9004081 | diffraction_compatible | 18 | 0.04447883235303962 | 0.04347316606360544 | 0.1416375870705906 | -0.0014462371426413392 | -0.05656032729289606 | true | true | null |
| R050233 | 9004082 | diffraction_compatible | 19 | 0.0257753386131796 | 0.03451787805469715 | 0.11321634137431857 | -0.0012142530959594203 | -0.023055498209629377 | true | true | null |
| R050233 | 9004083 | diffraction_compatible | 17 | 0.032342729618385135 | 0.035876250847520844 | 0.10755577911462666 | -0.0010138416798903711 | -0.011197425299624086 | true | true | null |
| R050233 | 9004256 | diffraction_compatible | 18 | 0.032886192465514164 | 0.03571029022863509 | 0.08769186402255968 | -0.0007903281752475123 | -0.046465690359067224 | true | true | null |
| R050233 | 9004257 | diffraction_compatible | 17 | 0.0230137921765472 | 0.03566283673782899 | 0.12405005062467467 | -0.0021897642137091175 | 0.002719840403550222 | true | true | null |
| R050233 | 9004258 | diffraction_compatible | 17 | 0.02029551929477691 | 0.03602561538917922 | 0.12211508787310521 | -0.0018242605684810765 | 0.014869238537094986 | true | true | null |
| R050233 | 9004259 | diffraction_compatible | 18 | 0.03762855513148189 | 0.04023589153831034 | 0.10182081670949827 | -0.0009647139079386951 | -0.019585760445600897 | true | true | null |
| R050233 | 9004442 | diffraction_compatible | 14 | 0.05837182197506152 | 0.05563830795651798 | 0.11771114410179706 | -0.001546458286556032 | 0.014698169951664397 | true | true | null |
| R050233 | 9004443 | diffraction_inconclusive | 14 | 0.07007476969203807 | 0.060133556129393834 | 0.10932762376936012 | -0.002361521976677869 | 0.0018696510049878157 | false | true | null |
| R050233 | 9004477 | diffraction_compatible | 15 | 0.01986224207621845 | 0.034898178908931765 | 0.13063332205605604 | -0.0011446229386135956 | -0.04269669990837954 | true | true | null |
| R050233 | 9004478 | diffraction_compatible | 16 | 0.019995927593862817 | 0.032277037914173544 | 0.13000000000000256 | -0.002375052736305816 | -0.04333002196443658 | true | true | null |
| R050233 | 9004529 | diffraction_compatible | 18 | 0.03691901881076376 | 0.03775439983150924 | 0.0960816344542863 | -0.00039685589740361853 | -0.02797963579081042 | true | true | null |
| R050233 | 9004768 | diffraction_compatible | 17 | 0.03820956331430736 | 0.03941762504951147 | 0.10387492930196274 | 0.0001750688419020485 | -0.022942645449763432 | true | true | null |
| R050233 | 9004769 | diffraction_compatible | 18 | 0.04056433900692191 | 0.04248939909927903 | 0.14568543972320924 | -0.0004769228401511394 | -0.034698728732426076 | true | true | null |
| R050233 | 9004770 | diffraction_compatible | 18 | 0.0428466467361055 | 0.04128182316051221 | 0.1463913664414207 | -0.0012905690183243582 | -0.06161065005700195 | true | true | null |
| R050233 | 9010614 | diffraction_inconclusive | 15 | 0.044574962784530214 | 0.06379622113388247 | 0.13847546264893396 | -0.0010600856530103505 | 0.04235716016531299 | false | true | null |
| R050233 | 9014245 | diffraction_inconclusive | 18 | 0.05486278053410665 | 0.05749488495868837 | 0.13018046189582577 | -0.00025664829082648193 | 0.003025606345111953 | false | true | null |
| R050233 | 9014836 | diffraction_compatible | 18 | 0.05662706214424418 | 0.054603608685838065 | 0.11302694211573794 | -0.0003418992954027171 | -0.01806078310723258 | true | true | null |
| R050233 | 9016909 | diffraction_inconclusive | 13 | 0.08137724766360321 | 0.07972579053552349 | 0.13597429843958508 | -0.00043900287685008746 | 0.00200854907047443 | false | true | null |
| R050233 | 9016939 | diffraction_compatible | 15 | 0.04772295806298388 | 0.055845755698449275 | 0.1244367642058819 | 0.00023213475306402642 | 0.03864535023967264 | true | true | null |
| R050279 | 9009539 | diffraction_compatible | 14 | 0.05016659762240039 | 0.03742239129279014 | 0.12257776864080938 | 0.0017296071543924673 | -0.0360698323819193 | true | false | null |
| R050355 | 9009632 | diffraction_compatible | 20 | 0.04667175944263846 | 0.02558022411255816 | 0.12690367568040983 | 0.00015608487431848327 | 0.0008637007749570103 | true | true | null |
| R050355 | 9009633 | diffraction_inconclusive | 11 | 0.04858082006072806 | 0.029507057197676587 | 0.11141917993927564 | -0.0016354144251690412 | 0.09137474036655391 | false | true | null |
| R050355 | 9009634 | diffraction_inconclusive | 11 | 0.08782166899832333 | 0.039818791221591994 | 0.14441895368572943 | 0.002823371863287695 | -0.03212498330353597 | false | true | null |
| R050355 | 9009635 | diffraction_inconclusive | 5 | 0.023499537653897562 | 0.0893688802004083 | 0.11883140432547634 | -0.00100513650404307 | 0.020901733165246128 | false | true | null |
| R050355 | 9009636 | diffraction_inconclusive | 6 | 0.016470673544395353 | 0.02432304960609138 | 0.1307069276769326 | 0.0007691589175566462 | 0.07694652200521901 | false | true | null |
| R050355 | 9009637 | diffraction_inconclusive | 5 | 0.04827466170647199 | 0.026222123784833944 | 0.1457349005093178 | 0.0021204647636314444 | -0.010977150385816259 | false | true | null |
| R050355 | 9009638 | diffraction_inconclusive | 5 | 0.05075250659206887 | 0.018038882895863768 | 0.09172109292734376 | -0.0003298127179078706 | -0.07611837349461936 | false | true | null |
| R050385 | 9000473 | diffraction_compatible | 16 | 0.0142467968636808 | 0.010512925831720685 | 0.06185532802462035 | -0.00018985566895369154 | 0.03768060617718305 | true | true | null |
| R050385 | 9000532 | diffraction_compatible | 14 | 0.0412430991432835 | 0.026168930562388844 | 0.09925631458308715 | 0.0018251663800119987 | -0.041162440555730484 | true | true | null |
| R050385 | 9006541 | diffraction_compatible | 15 | 0.019121903514175642 | 0.013374246213807308 | 0.09941900754968103 | -0.0007254641485319826 | 0.02015561055314663 | true | true | null |
| R050385 | 9006542 | diffraction_compatible | 15 | 0.01930094890883538 | 0.013642132138128888 | 0.09870635278227624 | -0.0007173068110976153 | 0.020021020692546188 | true | true | null |
| R050385 | 9006543 | diffraction_compatible | 14 | 0.028084451566400048 | 0.021565839966607606 | 0.08856151642306642 | 0.0016995651417793481 | -0.06519368140553894 | true | true | null |
| R050385 | 9006544 | diffraction_inconclusive | 11 | 0.04442421398402985 | 0.04177366400302595 | 0.11499890083970143 | -0.000651868451267036 | 0.038281073175326696 | false | true | null |
| R050385 | 9006545 | diffraction_inconclusive | 11 | 0.021529062132991328 | 0.011187515082196925 | 0.11639988492155595 | -0.00044395375407477015 | -0.024089312170900712 | false | true | null |
| R050385 | 9006546 | diffraction_inconclusive | 11 | 0.0528854035988644 | 0.02393766019163411 | 0.11509215235922454 | -0.0022791846778254473 | -0.08337810257907563 | false | true | null |
| R050385 | 9006547 | diffraction_inconclusive | 9 | 0.03362371709786771 | 0.01839373396135343 | 0.14533121659441406 | -6.98338094353289e-05 | 0.019392931567814742 | false | true | null |
| R050388 | 9000473 | diffraction_compatible | 18 | 0.013018531498055097 | 0.013646654997880073 | 0.091900194553034 | -0.0001340057227527338 | 0.06398224349469928 | true | true | null |
| R050388 | 9000532 | diffraction_compatible | 17 | 0.04651164917919459 | 0.03063692336462248 | 0.10813287325166243 | 0.00019446902251991658 | -0.011162440555729347 | true | true | null |
| R050388 | 9006541 | diffraction_compatible | 17 | 0.02571373723039727 | 0.01857506300850695 | 0.08876314950759934 | -0.0014652863532533425 | 0.05015561055314777 | true | true | null |
| R050388 | 9006542 | diffraction_compatible | 17 | 0.02656801906805839 | 0.01835064218222853 | 0.08779597419747631 | -0.0014539639493285077 | 0.050021020692547324 | true | true | null |
| R050388 | 9006543 | diffraction_compatible | 17 | 0.05105216043705951 | 0.027502646881716292 | 0.1161874131331615 | -0.0003471245375913607 | -0.0351936814055378 | true | true | null |
| R050388 | 9006544 | diffraction_compatible | 14 | 0.0288744747404035 | 0.024003765137161057 | 0.12413102823437328 | 0.0018504002710350844 | 0.0974132005700028 | true | true | null |
| R050388 | 9006545 | diffraction_inconclusive | 16 | 0.082810170140867 | 0.04452252583284843 | 0.13870821247258291 | 0.0015439032889971662 | -0.0040893121708975855 | false | true | null |
| R050388 | 9006546 | diffraction_compatible | 14 | 0.06140515114951839 | 0.0387516328415368 | 0.13232588335993967 | 0.0018408533811458939 | -0.0633781025790725 | true | true | null |
| R050388 | 9006547 | diffraction_compatible | 13 | 0.043623717097858616 | 0.027079172501966255 | 0.10056973442092243 | -2.8200587119257775e-06 | -0.17060706843218298 | true | true | null |
| R050390 | 9000473 | diffraction_compatible | 19 | 0.029148570116390715 | 0.018829897594406248 | 0.08346833183395574 | 0.0007079953417026071 | 0.06768060617718419 | true | true | null |
| R050390 | 9000532 | diffraction_compatible | 18 | 0.040671087890029156 | 0.0247617977531192 | 0.09152494851607429 | -0.0003725460147636796 | -0.011162440555729347 | true | true | null |
| R050390 | 9006541 | diffraction_compatible | 18 | 0.02801058034519599 | 0.018717390798050938 | 0.08834216813037443 | 0.0006746570365251707 | 0.04444187332274652 | true | true | null |
| R050390 | 9006542 | diffraction_compatible | 18 | 0.028837619887340793 | 0.019274145102867835 | 0.08629608955590129 | 0.0006846138864120708 | 0.043453001624484955 | true | true | null |
| R050390 | 9006543 | diffraction_compatible | 18 | 0.041582559675351405 | 0.0292103282301074 | 0.10105216043705667 | -0.0011909794442731996 | -0.0351936814055378 | true | true | null |
| R050390 | 9006544 | diffraction_compatible | 18 | 0.046417351283949415 | 0.033599594580257464 | 0.1400948297056459 | -0.000684952532769931 | -0.08181375653031608 | true | true | null |
| R050390 | 9006545 | diffraction_compatible | 13 | 0.050635987445829755 | 0.03249813486480579 | 0.1416803786423415 | 0.0006673597996008097 | 0.03591068782910156 | true | true | null |
| R050390 | 9006546 | diffraction_compatible | 12 | 0.038770236189890284 | 0.027968576553225103 | 0.14416990541354124 | 0.0009444027152598947 | -0.023378102579073357 | true | true | null |
| R050390 | 9006547 | diffraction_inconclusive | 9 | 0.024668783405587646 | 0.012425047654085685 | 0.09025617012795095 | 0.001587126230728762 | -0.0006070684321883846 | false | true | null |
| R050399 | 9006180 | diffraction_inconclusive | 14 | 0.09133751435860837 | 0.050368086499253305 | 0.1260581951587838 | -0.0006951725212485617 | -0.012215121974072929 | false | true | null |
| R050399 | 9006181 | diffraction_inconclusive | 14 | 0.09107437183846301 | 0.05018329200425239 | 0.1263686357748668 | -0.0006794178153391635 | -0.011771921667758534 | false | true | null |
| R050399 | 9006182 | diffraction_inconclusive | 14 | 0.09186382476869248 | 0.050027463694042006 | 0.12543728508327234 | 0.0004490573299483385 | -0.013101556152683713 | false | true | null |
| R050399 | 9006185 | diffraction_inconclusive | 14 | 0.09133751435860837 | 0.05013892282889893 | 0.1260581951587838 | -0.0006951725212485617 | -0.012215121974072929 | false | true | null |
| R050399 | 9006186 | diffraction_inconclusive | 14 | 0.09107437183846301 | 0.050350046037783334 | 0.1263686357748668 | -0.0006794178153391635 | -0.011771921667758534 | false | true | null |
| R050399 | 9006187 | diffraction_inconclusive | 14 | 0.09186382476869248 | 0.05004052257655987 | 0.12543728508327234 | 0.0004490573299483385 | -0.013101556152683713 | false | true | null |
| R050399 | 9006195 | diffraction_inconclusive | 14 | 0.09133751435860837 | 0.05025174993503418 | 0.1260581951587838 | -0.0006951725212485617 | -0.012215121974072929 | false | true | null |
| R050399 | 9006196 | diffraction_inconclusive | 14 | 0.09107437183846301 | 0.050359528709934424 | 0.1263686357748668 | -0.0006794178153391635 | -0.011771921667758534 | false | true | null |
| R050399 | 9006197 | diffraction_inconclusive | 14 | 0.09186382476869248 | 0.0502233284973506 | 0.12543728508327234 | 0.0004490573299483385 | -0.013101556152683713 | false | true | null |
| R050399 | 9006219 | diffraction_inconclusive | 14 | 0.09186382476869248 | 0.050055349822721605 | 0.12543728508327234 | 0.0004490573299483385 | -0.013101556152683713 | false | true | null |
| R050399 | 9006236 | diffraction_inconclusive | 14 | 0.09107437183846301 | 0.050154184610905386 | 0.1263686357748668 | -0.0006794178153391635 | -0.011771921667758534 | false | true | null |
| R050399 | 9006238 | diffraction_inconclusive | 14 | 0.09133751435860837 | 0.05022636563961696 | 0.1260581951587838 | -0.0006951725212485617 | -0.012215121974072929 | false | true | null |
| R050399 | 9006239 | diffraction_inconclusive | 14 | 0.09107437183846301 | 0.05031110421965839 | 0.1263686357748668 | -0.0006794178153391635 | -0.011771921667758534 | false | true | null |
| R050399 | 9006240 | diffraction_inconclusive | 14 | 0.09186382476869248 | 0.05019513088305409 | 0.12543728508327234 | 0.0004490573299483385 | -0.013101556152683713 | false | true | null |
| R050399 | 9006245 | diffraction_inconclusive | 14 | 0.09186382476869248 | 0.050109715706190175 | 0.12543728508327234 | 0.0004490573299483385 | -0.013101556152683713 | false | true | null |
| R050399 | 9006248 | diffraction_inconclusive | 14 | 0.09133751435860837 | 0.05016354786414639 | 0.1260581951587838 | -0.0006951725212485617 | -0.012215121974072929 | false | true | null |
| R050399 | 9006249 | diffraction_inconclusive | 14 | 0.09107437183846301 | 0.05031173612952755 | 0.1263686357748668 | -0.0006794178153391635 | -0.011771921667758534 | false | true | null |
| R050399 | 9006250 | diffraction_inconclusive | 14 | 0.09186382476869248 | 0.050171146038374616 | 0.12543728508327234 | 0.0004490573299483385 | -0.013101556152683713 | false | true | null |
| R050399 | 9006783 | diffraction_inconclusive | 14 | 0.09196482319151222 | 0.04432509322351367 | 0.12171101681499152 | 0.00025979710694657836 | -0.018421101252563687 | false | true | null |
| R050399 | 9007310 | diffraction_inconclusive | 14 | 0.09215018900277272 | 0.05003470457280404 | 0.12233215771395578 | 0.0002913412826224402 | -0.017534398477209834 | false | true | null |
| R050399 | 9007311 | diffraction_inconclusive | 14 | 0.09205750755746855 | 0.050106579099728585 | 0.12202159207471652 | 0.00027556923505290675 | -0.01797774426782439 | false | true | null |
| R050399 | 9012439 | diffraction_compatible | 16 | 0.05195706173910786 | 0.02875529515512523 | 0.14146148437218642 | 0.0001800326242196283 | -0.006740129006868045 | true | true | null |
| R050403 | 9000015 | diffraction_compatible | 15 | 0.03139251243287333 | 0.029029378282121328 | 0.0759048399069755 | -0.000786311224236433 | 0.004262423940325277 | true | false | null |
| R050414 | 9000893 | diffraction_compatible | 17 | 0.03844040815719296 | 0.0567344296163439 | 0.1406977081970311 | -0.0014988130315954137 | -0.018539829761614612 | true | true | null |
| R050414 | 9000894 | diffraction_compatible | 18 | 0.052433203799468586 | 0.055595474959086864 | 0.1473782977347753 | 0.00046643968486199835 | -0.018014008066742804 | true | true | null |
| R050414 | 9000895 | diffraction_compatible | 17 | 0.03223012709437256 | 0.04086198727118331 | 0.08552199625956547 | 0.001897662850547225 | -0.00086594708842469 | true | true | null |
| R050414 | 9000896 | diffraction_compatible | 16 | 0.029418567907500304 | 0.03434663698735437 | 0.11496471796545649 | -1.6681026774327515e-05 | 0.033101162363117 | true | true | null |
| R050414 | 9000897 | diffraction_compatible | 16 | 0.03152985523716367 | 0.03445403769765255 | 0.12987929670138953 | 0.0009210568943545321 | 0.04830288379259429 | true | true | null |
| R050414 | 9000898 | diffraction_compatible | 19 | 0.02979524329577643 | 0.041347575462952625 | 0.12329324548522891 | 0.0016246903622794983 | -0.008757369738482623 | true | true | null |
| R050414 | 9000899 | diffraction_inconclusive | 16 | 0.06876026314989936 | 0.06798593997654574 | 0.1469530667797727 | 0.0009682593850129683 | -0.006557461818555765 | false | true | null |
| R050414 | 9000900 | diffraction_inconclusive | 15 | 0.07812357626118427 | 0.07550382649952024 | 0.13253980743807148 | 0.0017305992822144829 | 0.009039744047981912 | false | true | null |
| R050414 | 9000901 | diffraction_inconclusive | 13 | 0.07246348789663415 | 0.0776266443767517 | 0.13941732469253765 | 0.0009112283815733133 | 0.046277285630779375 | false | true | null |
| R050414 | 9001536 | diffraction_compatible | 17 | 0.043303641165763906 | 0.05558029402256223 | 0.11599889668681129 | 0.00141274877278938 | 0.023533945648161136 | true | true | null |
| R050414 | 9001537 | diffraction_compatible | 17 | 0.0574428783870129 | 0.0527887180256496 | 0.12155513678218455 | 0.001002482084713921 | -0.030847848570356717 | true | true | null |
| R050414 | 9001538 | diffraction_inconclusive | 18 | 0.040961530807187785 | 0.05804278456038072 | 0.14270780946925754 | 0.00046620500539464727 | -0.005793869066778257 | false | true | null |
| R050414 | 9001539 | diffraction_compatible | 18 | 0.048502573926867854 | 0.055897588420976224 | 0.14771530974700653 | -0.00030375114619514215 | -0.023819693744378867 | true | true | null |
| R050414 | 9001540 | diffraction_inconclusive | 17 | 0.0643596100257895 | 0.05291215736509725 | 0.13478369994227535 | 0.0008546700542921322 | -0.040040158846476714 | false | true | null |
| R050414 | 9001541 | diffraction_inconclusive | 18 | 0.05271575127537531 | 0.0707400615542913 | 0.1253667396727991 | -9.42575917005948e-05 | 0.020463477774953276 | false | true | null |
| R050414 | 9001542 | diffraction_inconclusive | 17 | 0.05570088567227671 | 0.05773885782594406 | 0.10187252566811367 | -0.0019176790942581096 | 0.004813476032001773 | false | true | null |
| R050414 | 9001543 | diffraction_inconclusive | 18 | 0.05211946521439348 | 0.05898600651227698 | 0.12110127842463925 | -0.001370858335531997 | -0.007997280129053763 | false | true | null |
| R050414 | 9001544 | diffraction_compatible | 17 | 0.052043166518647155 | 0.05706779845801017 | 0.1290568389269211 | -0.0013768236213313565 | -0.012200145844381893 | true | true | null |
| R050414 | 9001545 | diffraction_compatible | 16 | 0.06111060545776503 | 0.049649829564857105 | 0.11447250639437101 | 0.0034576172530214303 | -0.017826567649912306 | true | true | null |
| R050414 | 9001546 | diffraction_compatible | 14 | 0.04478001209118965 | 0.03217320874239181 | 0.14345576285052886 | -0.00010039345353451031 | -0.026156405620344714 | true | true | null |
| R050414 | 9001558 | diffraction_inconclusive | 16 | 0.05879764125486986 | 0.06342579444638555 | 0.13022418866719931 | -0.00033860642276342293 | 0.008910844692600506 | false | true | null |
| R050414 | 9001559 | diffraction_compatible | 16 | 0.034589735949214884 | 0.051127166440423095 | 0.10905409952903256 | 0.0013690324437759885 | 0.03025093564223269 | true | true | null |
| R050414 | 9001560 | diffraction_compatible | 17 | 0.048509018695689576 | 0.049469882573626674 | 0.10821446906440713 | 0.0007703085070718745 | 0.012237955867433925 | true | true | null |
| R050414 | 9001561 | diffraction_compatible | 16 | 0.030677744791583805 | 0.0472590808536203 | 0.1237657397523364 | 9.268660374682273e-05 | -0.026504881399475266 | true | true | null |
| R050414 | 9001562 | diffraction_inconclusive | 16 | 0.053086008143234054 | 0.059324582652806455 | 0.10291722665002823 | -0.0003320063297639455 | -0.011355423441624879 | false | true | null |
| R050414 | 9001563 | diffraction_inconclusive | 17 | 0.06849914067852936 | 0.06700629860801476 | 0.1489618744730805 | -0.00025494347597367995 | -0.00771908664874843 | false | true | null |
| R050414 | 9001858 | diffraction_compatible | 17 | 0.043303641165763906 | 0.049967455276741596 | 0.13386979829400758 | 0.0017817232190008162 | 0.023533945648161136 | true | true | null |
| R050414 | 9001859 | diffraction_inconclusive | 19 | 0.07063924652237574 | 0.06708190702412574 | 0.14435196402865813 | 0.0005173263169457213 | -0.013346783762845149 | false | true | null |
| R050414 | 9001860 | diffraction_compatible | 19 | 0.03380218180562622 | 0.03996652828904597 | 0.13979524051575254 | 0.00039033942892716973 | 0.06106074209853851 | true | true | null |
| R050414 | 9001861 | diffraction_compatible | 19 | 0.02062136191711872 | 0.021776056141232892 | 0.1434886739764636 | -0.00040889019996512516 | 0.06275023128345225 | true | true | null |
| R050414 | 9002155 | diffraction_inconclusive | 15 | 0.05353605455873378 | 0.06519025908329139 | 0.13321932228446798 | 0.0016349578623862536 | 0.005514567350786592 | false | true | null |
| R050414 | 9002289 | diffraction_compatible | 18 | 0.04916041549257244 | 0.05625182514737227 | 0.12361345805194546 | 0.0008409823410348892 | 0.013043166165715547 | true | true | null |
| R050414 | 9002290 | diffraction_inconclusive | 17 | 0.05284447041072582 | 0.06038153461414838 | 0.13475492723909355 | 0.001084343171081046 | -0.03396574622021831 | false | true | null |
| R050414 | 9002291 | diffraction_inconclusive | 18 | 0.06306883213385017 | 0.0610629583857095 | 0.14435576673111328 | -0.0019611269682808913 | 0.031947793209397446 | false | true | null |
| R050414 | 9002292 | diffraction_inconclusive | 18 | 0.06156898209811956 | 0.06096418675102187 | 0.14061532586364223 | -0.0019029357617184389 | 0.034597965152492804 | false | true | null |
| R050414 | 9002293 | diffraction_inconclusive | 18 | 0.056588231007637546 | 0.06205038140202889 | 0.11451006283855492 | 0.0008294197867170583 | 0.009634253284758643 | false | true | null |
| R050414 | 9002294 | diffraction_compatible | 18 | 0.055145824299450474 | 0.055200162231632266 | 0.12171861340332413 | -0.000329144326958566 | 0.03382723366148355 | true | true | null |
| R050414 | 9002295 | diffraction_compatible | 17 | 0.04603477449899884 | 0.047911550186457263 | 0.14898493245637923 | 0.0008503852388875252 | -0.05174649232101203 | true | true | null |
| R050414 | 9002296 | diffraction_compatible | 17 | 0.05673738298919062 | 0.057006505539290174 | 0.10911118862597036 | 0.0015407465966879124 | -0.00530972688285658 | true | true | null |
| R050414 | 9002297 | diffraction_compatible | 14 | 0.02520032255302418 | 0.04722908744271456 | 0.12005084308422909 | 0.0005242669623697691 | 0.0046706724803655675 | true | true | null |
| R050414 | 9002298 | diffraction_inconclusive | 18 | 0.05968012346280105 | 0.05845719334201483 | 0.1372840576840204 | 0.0007575137511677213 | 0.020026388468529888 | false | true | null |
| R050414 | 9003693 | diffraction_compatible | 19 | 0.04058276163333119 | 0.05085825331566664 | 0.13871143912501083 | 0.0011468835208775625 | 0.03395656038061645 | true | true | null |
| R050414 | 9003696 | diffraction_inconclusive | 9 | 0.06800115793262407 | 0.06721368426577651 | 0.14543120935717013 | -0.0012509494251110949 | 0.018951772991051996 | false | true | null |
| R050414 | 9003697 | diffraction_compatible | 12 | 0.04561079519607336 | 0.04553522027178355 | 0.11254261889904882 | -0.00037092716926870214 | 0.009526427782997615 | true | true | null |
| R050414 | 9003698 | diffraction_compatible | 12 | 0.05250383882292731 | 0.04694771626209147 | 0.1351801269758397 | -0.0002817476860844654 | 0.05863682719523666 | true | true | null |
| R050414 | 9005094 | diffraction_compatible | 18 | 0.048358166274312 | 0.0504222032232051 | 0.13930886938868525 | -0.0006183378533371249 | 0.02975222639337005 | true | true | null |
| R050414 | 9005095 | diffraction_compatible | 19 | 0.03274148868211668 | 0.03744638437252276 | 0.13580061317279046 | 0.00021345814161741083 | 0.04409459220597434 | true | true | null |
| R050414 | 9005096 | diffraction_compatible | 19 | 0.028606559229185535 | 0.030345965030340056 | 0.11951531757749478 | 0.0018313604581430502 | 0.057858540865611374 | true | true | null |
| R050414 | 9005097 | diffraction_compatible | 20 | 0.044009562118896284 | 0.044459500776842714 | 0.14219341670980157 | -0.0016960050103155717 | 0.052679136618614564 | true | true | null |
| R050414 | 9005098 | diffraction_inconclusive | 17 | 0.053950797222164226 | 0.06414174189203195 | 0.10595422722451175 | -0.0010698903781737369 | 0.006383606907107264 | false | true | null |
| R050414 | 9005099 | diffraction_compatible | 17 | 0.05114067008057077 | 0.05522299751420335 | 0.1308423692832683 | -0.0015645851843496665 | 0.05704267592842882 | true | true | null |
| R050414 | 9005100 | diffraction_inconclusive | 17 | 0.04708228774908463 | 0.06251930352259387 | 0.1489081433596411 | 0.001566609226280158 | -0.029689155371904974 | false | true | null |
| R050414 | 9005101 | diffraction_inconclusive | 18 | 0.050920190349179606 | 0.06232548336276994 | 0.13108792038238448 | 0.0012937728973014195 | -0.019701354470221588 | false | true | null |
| R050414 | 9005130 | diffraction_compatible | 17 | 0.043303641165763906 | 0.05557827197555748 | 0.11599889668681129 | 0.00141274877278938 | 0.023533945648161136 | true | true | null |
| R050414 | 9005131 | diffraction_compatible | 15 | 0.03518876791898151 | 0.05066054940296434 | 0.14744211904521975 | -0.0006173272706520603 | -0.03052556456674438 | true | true | null |
| R050414 | 9005132 | diffraction_compatible | 14 | 0.03460820491722494 | 0.05128336700934267 | 0.12443406653095934 | 0.0020510514246203735 | 0.021642788594455453 | true | true | null |
| R050442 | 9007517 | diffraction_compatible | 14 | 0.011315694840554613 | 0.026013543461074443 | 0.12405242562492091 | -0.0002764276646865221 | -0.015029649811289403 | true | true | null |
| R050442 | 9014090 | diffraction_compatible | 16 | 0.05360175851122406 | 0.04591072239438037 | 0.14675461741568796 | 0.001273245113049898 | 0.05456243098650759 | true | true | null |
| R050442 | 9014599 | diffraction_compatible | 12 | 0.04578067269370223 | 0.02955880753456209 | 0.07272613208537138 | 0.0003729302230247957 | -0.02411518855245376 | true | true | null |
| R050442 | 9015642 | diffraction_compatible | 13 | 0.009601679737876623 | 0.021297144218389803 | 0.13317684481344472 | 0.0006765041876397321 | 0.015508309005099363 | true | true | null |
| R050489 | 1011221 | diffraction_compatible | 18 | 0.043688263945441896 | 0.032575542633525065 | 0.09774267828766625 | -1.7463591924779983e-05 | 0.024231384316511395 | true | true | null |
| R050489 | 9001022 | diffraction_compatible | 16 | 0.03908070939863251 | 0.03475624263264975 | 0.1013978089827603 | -0.0010463073164193861 | -0.05283445783215868 | true | true | null |
| R050489 | 9001038 | diffraction_inconclusive | 17 | 0.04901788993035794 | 0.06169568419687177 | 0.14572103894250432 | 0.0012306687239618138 | -0.06474135157953143 | false | true | null |
| R050489 | 9001070 | diffraction_inconclusive | 11 | 0.0769651043546773 | 0.0703640631727392 | 0.14376569337969158 | -0.0002423318934337514 | -0.023927435489603077 | false | true | null |
| R050489 | 9001499 | diffraction_compatible | 18 | 0.04553673678635839 | 0.0561127622405371 | 0.1499706371401146 | -0.002010193483860078 | -0.05514646967047021 | true | true | null |
| R050489 | 9001500 | diffraction_compatible | 18 | 0.018849974159849125 | 0.021661795126200502 | 0.12671235802401526 | -1.9477503319434454e-05 | 0.010110109602921469 | true | true | null |
| R050489 | 9001501 | diffraction_compatible | 17 | 0.020604828815532272 | 0.019200764321987702 | 0.06382557905949682 | 0.00023360407408333161 | -0.006682171016260341 | true | true | null |
| R050489 | 9001502 | diffraction_compatible | 18 | 0.031827791238368874 | 0.03094657500953896 | 0.08205881954371108 | -0.00032476724152821345 | -0.03380061624226549 | true | true | null |
| R050489 | 9002335 | diffraction_inconclusive | 19 | 0.06552043040793798 | 0.06438694119412769 | 0.12734430548110254 | 0.00011883677411550987 | -0.07731293157557317 | false | true | null |
| R050489 | 9002336 | diffraction_compatible | 14 | 0.04062329110640217 | 0.030511500466720225 | 0.1408498934877187 | -0.00037921385185737185 | -0.044831572807467523 | true | true | null |
| R050489 | 9002337 | diffraction_compatible | 15 | 0.012790783685524332 | 0.024619045782518393 | 0.14138396361467898 | -0.0009583914437272645 | -0.034324872795050254 | true | true | null |
| R050489 | 9004081 | diffraction_inconclusive | 18 | 0.06728980871869972 | 0.05643050392934423 | 0.14854532813814814 | -0.0007728218118934364 | -0.05588396384442085 | false | true | null |
| R050489 | 9004082 | diffraction_compatible | 18 | 0.02969611148192186 | 0.026200455035990385 | 0.07654174538728142 | 4.182246527542988e-05 | -0.024991241871155978 | true | true | null |
| R050489 | 9004083 | diffraction_compatible | 16 | 0.035405250525219145 | 0.02757665003794216 | 0.07737110200250186 | -0.0010468927481650481 | -0.03640670897098275 | true | true | null |
| R050489 | 9004256 | diffraction_compatible | 18 | 0.053744315735381853 | 0.042000064152166394 | 0.11353907699797361 | -0.001087617255058873 | -0.05146043128953437 | true | true | null |
| R050489 | 9004257 | diffraction_compatible | 16 | 0.02829586759592484 | 0.022595562326474927 | 0.07695272911798412 | -0.0009348296628190638 | -0.024991241871155978 | true | true | null |
| R050489 | 9004258 | diffraction_compatible | 16 | 0.02698339720892662 | 0.02228413825763757 | 0.07544643133341111 | -0.0010301365368046334 | -0.021324698590406754 | true | true | null |
| R050489 | 9004259 | diffraction_compatible | 17 | 0.034188938584570394 | 0.02963407879478163 | 0.08627907945086832 | -0.000891334924087354 | -0.03968112947794822 | true | true | null |
| R050489 | 9004442 | diffraction_inconclusive | 16 | 0.05260459843646714 | 0.07822799306628304 | 0.13959765363002674 | -0.000677823527260846 | 0.011577680783837252 | false | true | null |
| R050489 | 9004443 | diffraction_inconclusive | 20 | 0.07298579731617494 | 0.0563659127656088 | 0.14869332574608762 | -0.0015758150976270609 | 0.09620351924002435 | false | true | null |
| R050489 | 9004477 | diffraction_compatible | 14 | 0.03775013802967031 | 0.03298906572409519 | 0.09649449588648906 | -0.002111423738476397 | -0.044095509544403555 | true | true | null |
| R050489 | 9004478 | diffraction_compatible | 15 | 0.03831968008461217 | 0.03307316116575291 | 0.09649449588648906 | -0.000915635067539295 | -0.044095509544403555 | true | true | null |
| R050489 | 9004529 | diffraction_compatible | 18 | 0.03655775290680552 | 0.032685036668371074 | 0.08681083330749573 | -0.0010444930516790851 | -0.05134004494043154 | true | true | null |
| R050489 | 9004768 | diffraction_compatible | 17 | 0.02865625989468157 | 0.03371255374960893 | 0.11724369776084131 | -0.0012976382453041902 | -0.04685798422289977 | true | true | null |
| R050489 | 9004769 | diffraction_compatible | 16 | 0.046685185719166356 | 0.039534624865010644 | 0.1222137596861188 | -0.0014077979597228348 | -0.046303985144815485 | true | true | null |
| R050489 | 9004770 | diffraction_compatible | 18 | 0.05287027354997065 | 0.05697455107953079 | 0.14426822966984787 | 0.00012705116327907037 | -0.058097019696447205 | true | true | null |
| R050489 | 9010614 | diffraction_compatible | 18 | 0.036518419934784774 | 0.03543986135315009 | 0.1451407172439545 | 0.0002712988181164532 | 0.062357160165312564 | true | true | null |
| R050489 | 9014245 | diffraction_compatible | 17 | 0.017735680742887894 | 0.015757495383746267 | 0.08223878011098407 | -0.0004019739403237084 | -0.010619815527565635 | true | true | null |
| R050489 | 9014836 | diffraction_compatible | 17 | 0.016973057884268172 | 0.015733456087733102 | 0.12400563998265213 | 0.0007512650694408413 | 0.0019392168927669928 | true | true | null |
| R050489 | 9016909 | diffraction_inconclusive | 16 | 0.0771068518320348 | 0.0507379056159815 | 0.1332178027310178 | 0.00014136229321673103 | 0.09522635180148953 | false | true | null |
| R050489 | 9016939 | diffraction_compatible | 20 | 0.054712304608218076 | 0.05300839454042527 | 0.14569435951248266 | -0.0007299929918031476 | 0.09620351924002435 | true | true | null |
| R050501 | 1011170 | diffraction_compatible | 17 | 0.03152058411168923 | 0.033455185841926804 | 0.1154364776128034 | 0.0004904701754279184 | 0.11682972073693065 | true | true | null |
| R050501 | 9008105 | diffraction_inconclusive | 19 | 0.06325389437743922 | 0.028932369760750858 | 0.11628781557531909 | 0.0005520114027862603 | 0.0049224529277225315 | false | true | null |
| R050501 | 9009404 | diffraction_compatible | 18 | 0.04359165881079008 | 0.02702044070985036 | 0.11581862379735242 | 6.168551125749235e-05 | 0.008154954549844717 | true | true | null |
| R050532 | 1011121 | diffraction_compatible | 19 | 0.021900652732107062 | 0.02943573581199044 | 0.13760115654661575 | -0.0011907438740254481 | -0.0012108526591969593 | true | true | null |
| R050532 | 9004387 | diffraction_compatible | 18 | 0.05636558906036271 | 0.040686879176748285 | 0.12357750675729307 | 0.00019390322923644462 | -0.01933783269383582 | true | true | null |
| R050532 | 9004388 | diffraction_compatible | 17 | 0.05345168892089447 | 0.04166034382229436 | 0.1342770401243527 | -0.0018357867134569912 | -0.019633970059690142 | true | true | null |
| R050532 | 9011171 | diffraction_compatible | 16 | 0.022625161293628793 | 0.027900348339673073 | 0.10477897735738395 | -0.00034782623014074823 | 0.04671179916563517 | true | true | null |
| R050532 | 9011172 | diffraction_compatible | 16 | 0.022625161293628793 | 0.02825270955845006 | 0.10477897735738395 | -0.00034782623014074823 | 0.04671179916563517 | true | true | null |
| R050532 | 9011399 | diffraction_compatible | 17 | 0.06078849450900492 | 0.04123109307442643 | 0.12036698572043036 | -0.0013669024002294454 | -0.016946673926600653 | true | true | null |
| R050625 | 9017614 | diffraction_compatible | 19 | 0.03728067334983365 | 0.02040051839063327 | 0.14426824371281555 | -0.0003727232931625981 | -0.022698309121263804 | true | false | null |
| R060023 | 9000642 | diffraction_compatible | 16 | 0.024976174651868632 | 0.03070235665834876 | 0.11832925053485965 | 0.0010986094572710207 | 0.003037208724606444 | true | true | null |
| R060023 | 9000643 | diffraction_compatible | 16 | 0.027451852251983766 | 0.028547559677282657 | 0.12319067236150616 | 0.00130081668674581 | 0.013272569531615375 | true | true | null |
| R060023 | 9000644 | diffraction_compatible | 12 | 0.023696102768585803 | 0.02852832821416731 | 0.12875936844893232 | 0.00042786493927437374 | 0.021527045622978136 | true | true | null |
| R060023 | 9000645 | diffraction_inconclusive | 9 | 0.028656040462886168 | 0.03229620771607445 | 0.14175437285774706 | 0.00286937704400855 | 0.027314775342738074 | false | true | null |
| R060023 | 9000646 | diffraction_compatible | 13 | 0.017826533995837224 | 0.010959875166303552 | 0.02727520326469346 | -0.0006912431812382096 | 0.04658844404973905 | true | true | null |
| R060023 | 9000647 | diffraction_compatible | 12 | 0.012765360801478387 | 0.008710275652782007 | 0.028671778502094014 | -0.0003647635059996401 | 0.046245013608729124 | true | true | null |
| R060023 | 9000648 | diffraction_inconclusive | 10 | 0.026167541384916504 | 0.032105591446249866 | 0.14664082528465627 | 0.0019775251291325228 | 0.031171817589388695 | false | true | null |
| R060023 | 9002000 | diffraction_compatible | 15 | 0.032995937143148524 | 0.035255329973044376 | 0.14659410892179636 | -0.0012963070858296388 | 0.011102575934888392 | true | true | null |
| R060023 | 9002001 | diffraction_compatible | 15 | 0.0438583047945329 | 0.03374301719966383 | 0.12176571211951881 | 0.00020497379884453282 | -0.012493059199474743 | true | true | null |
| R060023 | 9002002 | diffraction_compatible | 16 | 0.0491471279610014 | 0.04118405865914158 | 0.1400979369467379 | 0.00019505940610992109 | -0.06050319706471363 | true | true | null |
| R060023 | 9004009 | diffraction_compatible | 19 | 0.026630241448197367 | 0.016550222996815474 | 0.10815314799133802 | -7.997937845023397e-05 | 0.015601834134223225 | true | true | null |
| R060023 | 9004010 | diffraction_compatible | 19 | 0.029656261222037017 | 0.018498918693964028 | 0.10202723710597184 | -0.0002191972811058103 | 0.003955012731644558 | true | true | null |
| R060023 | 9004011 | diffraction_inconclusive | 15 | 0.0629095133647013 | 0.08540419381130437 | 0.13190086191193728 | -0.000512525145777925 | -0.04586197406985093 | false | true | null |
| R060023 | 9004012 | diffraction_inconclusive | 8 | 0.037713777682968797 | 0.033165795131269646 | 0.14013681654058274 | -0.0043807490715816605 | -0.0178103136724701 | false | true | null |
| R060023 | 9004013 | diffraction_inconclusive | 10 | 0.030883104983972842 | 0.029717867758635205 | 0.0816295155713469 | -0.0014611150856310583 | 0.030569112608102245 | false | true | null |
| R060023 | 9008207 | diffraction_compatible | 17 | 0.010776570065750946 | 0.008813970753301818 | 0.07480867150891868 | -0.00027001045754766994 | 0.06198662754896844 | true | true | null |
| R060023 | 9008387 | diffraction_compatible | 12 | 0.05320345727788123 | 0.05388386819977128 | 0.14933797800546422 | -0.0006051481458586344 | -0.020934440690353995 | true | true | null |
| R060023 | 9009963 | diffraction_compatible | 16 | 0.05222708479610816 | 0.04892622834122652 | 0.12212344697177357 | -0.0018579523168107367 | 0.02345657779684629 | true | true | null |
| R060023 | 9015469 | diffraction_compatible | 12 | 0.05142980961307764 | 0.054312386900432816 | 0.14218431502836104 | 0.0016828831531052238 | 0.0018175228148198386 | true | true | null |
| R060054 | 9000525 | diffraction_compatible | 18 | 0.04448971468546503 | 0.045216806084165874 | 0.09926967298656209 | -0.0012694470017582094 | 0.05002021358682285 | true | true | null |
| R060054 | 9000526 | diffraction_compatible | 18 | 0.039584809778197894 | 0.041528950368707906 | 0.10055290243457193 | -0.0006847764630378007 | -0.03747630446614281 | true | true | null |
| R060054 | 9000527 | diffraction_compatible | 18 | 0.022772540595250135 | 0.02480946795923141 | 0.0882355355751443 | 0.00010335008876155527 | 0.0066035907389583315 | true | true | null |
| R060054 | 9000528 | diffraction_compatible | 18 | 0.03434486951182869 | 0.0396695588731446 | 0.13622172087121243 | -0.0005418263738254759 | 0.012928772931331878 | true | true | null |
| R060054 | 9000529 | diffraction_compatible | 16 | 0.040705595576341125 | 0.0456022185252753 | 0.11156135488017327 | 0.0005935557996130694 | 0.035887729279014735 | true | true | null |
| R060054 | 9000681 | diffraction_compatible | 17 | 0.03579023175205265 | 0.040610375449023524 | 0.06434808420252836 | 0.0005304002616698159 | 0.013539228800674152 | true | true | null |
| R060054 | 9000702 | diffraction_compatible | 18 | 0.04538320211517721 | 0.04697930149255272 | 0.0998739785483238 | -0.0008225400258126695 | 0.061571990809046184 | true | true | null |
| R060054 | 9000703 | diffraction_compatible | 18 | 0.03614628067501524 | 0.03446142275802463 | 0.10349485880215781 | -7.26762686741813e-05 | 0.001763202936107433 | true | true | null |
| R060054 | 9000704 | diffraction_compatible | 17 | 0.02272622206658781 | 0.03298723971239302 | 0.14705886971003324 | 0.0007845423926954145 | 0.012468128864746575 | true | true | null |
| R060054 | 9000705 | diffraction_inconclusive | 16 | 0.04885526458185652 | 0.05746648826746599 | 0.10933899414574455 | 0.0024609306380102905 | -0.041336747032795884 | false | true | null |
| R060054 | 9001030 | diffraction_compatible | 17 | 0.034445067094566184 | 0.051240464923262515 | 0.14154233422907936 | 0.0020548594822940827 | -0.040022789371896295 | true | true | null |
| R060054 | 9001031 | diffraction_compatible | 17 | 0.034445067094566184 | 0.05110502726684258 | 0.14154233422907936 | 0.0020548594822940827 | -0.040022789371896295 | true | true | null |
| R060054 | 9001312 | diffraction_compatible | 14 | 0.05189472635051651 | 0.03791442729456677 | 0.10242409925518103 | 0.0017812576990677332 | 0.01385628274284656 | true | true | null |
| R060054 | 9002199 | diffraction_compatible | 18 | 0.039612554763341024 | 0.05465341139684099 | 0.13041036441283893 | -0.002667855823492934 | 0.00045253525015098717 | true | true | null |
| R060054 | 9002201 | diffraction_compatible | 18 | 0.038441357756978434 | 0.054851581794401756 | 0.147731813792209 | -0.003925640318245251 | 0.0026717306537769048 | true | true | null |
| R060054 | 9002202 | diffraction_inconclusive | 18 | 0.048602605350446026 | 0.060901336249145586 | 0.14292643099286195 | -0.0026614410927205227 | 0.02324334509272674 | false | true | null |
| R060054 | 9002203 | diffraction_compatible | 16 | 0.055248252465844416 | 0.04098718170541021 | 0.11320772344949503 | 0.001413782259652188 | 0.05805495195961896 | true | true | null |
| R060054 | 9005077 | diffraction_compatible | 15 | 0.029758276678204965 | 0.03717606711780075 | 0.11312320585522428 | -0.0004027866048532167 | -0.0071760845124408945 | true | true | null |
| R060054 | 9005078 | diffraction_inconclusive | 15 | 0.06209026056598432 | 0.07551514420281755 | 0.1427188136633788 | 0.0034440375544891586 | -0.014786648799702817 | false | true | null |
| R060054 | 9005079 | diffraction_compatible | 17 | 0.044177022747238226 | 0.05592342096093896 | 0.12393149576209694 | -0.0015434026088833334 | 0.08461641170120515 | true | true | null |
| R060054 | 9016731 | diffraction_compatible | 15 | 0.023835713698161953 | 0.05069328968716651 | 0.12289386561828408 | 0.00019047402550725255 | 0.0027693658120355735 | true | true | null |
| R060054 | 9016733 | diffraction_compatible | 18 | 0.031199601536064492 | 0.031032835545942494 | 0.07594439228441274 | -0.000896876694332136 | 0.04398875759497756 | true | true | null |
| R060054 | 9016735 | diffraction_compatible | 18 | 0.04760346137539173 | 0.03188830741150432 | 0.12511765209858794 | -0.0006654066986046157 | -0.008959624825077839 | true | true | null |
| R060054 | 9016747 | diffraction_compatible | 18 | 0.043820082892588985 | 0.04546724401249244 | 0.09890328967750861 | -0.001269265935075884 | 0.050020213586819295 | true | true | null |
| R060054 | 9016748 | diffraction_compatible | 18 | 0.039584809778197894 | 0.04153371354158468 | 0.10055290243457193 | -0.0006847764630378007 | -0.03747630446614281 | true | true | null |
| R060054 | 9016749 | diffraction_compatible | 18 | 0.022832777398312132 | 0.024879919592303984 | 0.08808467333332004 | 0.00010424242402560453 | 0.0066035907389583315 | true | true | null |
| R060054 | 9016750 | diffraction_compatible | 18 | 0.03434486951182869 | 0.039674728138245664 | 0.13622172087121243 | -0.0005418263738254759 | 0.012928772931331878 | true | true | null |
| R060054 | 9016751 | diffraction_compatible | 16 | 0.040705595576341125 | 0.04564411756377192 | 0.11156135488017327 | 0.0005935557996130694 | 0.035887729279014735 | true | true | null |
| R060054 | 9016754 | diffraction_compatible | 18 | 0.04538320211517721 | 0.046980456163847314 | 0.0998739785483238 | -0.0008225400258126695 | 0.061571990809046184 | true | true | null |
| R060054 | 9016755 | diffraction_compatible | 18 | 0.03614628067501524 | 0.03446533837753732 | 0.10349485880215781 | -7.26762686741813e-05 | 0.001763202936107433 | true | true | null |
| R060054 | 9016756 | diffraction_compatible | 17 | 0.02272622206658781 | 0.032981335533690405 | 0.14705886971003324 | 0.0007845423926954145 | 0.012468128864746575 | true | true | null |
| R060054 | 9016757 | diffraction_inconclusive | 16 | 0.04885526458185652 | 0.05747212345123361 | 0.10933899414574455 | 0.0024609306380102905 | -0.041336747032795884 | false | true | null |
| R060054 | 9016774 | diffraction_compatible | 18 | 0.039612554763341024 | 0.054673624459926524 | 0.13041036441283893 | -0.002667855823492934 | 0.00045253525015098717 | true | true | null |
| R060054 | 9016776 | diffraction_compatible | 18 | 0.038441357756978434 | 0.05479502719946904 | 0.147731813792209 | -0.003925640318245251 | 0.0026717306537769048 | true | true | null |
| R060054 | 9016777 | diffraction_inconclusive | 18 | 0.048602605350446026 | 0.06089708449728903 | 0.14292643099286195 | -0.0026614410927205227 | 0.02324334509272674 | false | true | null |
| R060054 | 9016778 | diffraction_compatible | 16 | 0.055248252465844416 | 0.04101374734328271 | 0.11320772344949503 | 0.001413782259652188 | 0.05805495195961896 | true | true | null |
| R060060 | 9000027 | diffraction_compatible | 17 | 0.03310877207204044 | 0.03646660183050305 | 0.11878104266362755 | 0.0009273156931753481 | -0.018311493539275858 | true | true | null |
| R060060 | 9000418 | diffraction_compatible | 17 | 0.015163776080687086 | 0.015843689732859295 | 0.07803724776842103 | -0.0015722313471197835 | 0.01463673679191757 | true | true | null |
| R060060 | 9000878 | diffraction_compatible | 17 | 0.01566706017728592 | 0.01624085103328775 | 0.08041678832829291 | -0.0016256703792035167 | 0.013351172337927153 | true | true | null |
| R060060 | 9000879 | diffraction_compatible | 16 | 0.041085752342846504 | 0.047248864771343484 | 0.10466818108052678 | 0.000864581801408387 | -0.024912558888132708 | true | true | null |
| R060060 | 9001855 | diffraction_compatible | 17 | 0.03456083072809513 | 0.02721158350494826 | 0.07639460141606236 | 0.0008278870304615347 | 0.05059827036103215 | true | true | null |
| R060060 | 9001856 | diffraction_compatible | 12 | 0.05285409749722625 | 0.05140768095448458 | 0.1317268824171407 | -0.0018588614545351097 | -0.09509199252357092 | true | true | null |
| R060060 | 9017228 | diffraction_inconclusive | 11 | 0.06914102994691262 | 0.05973156233552827 | 0.13512715879690518 | -0.0015185545263112252 | -0.05600374693665344 | false | true | null |
| R060060 | 9017229 | diffraction_inconclusive | 9 | 0.057505640821347015 | 0.05005207265069032 | 0.10968796525343194 | -0.000153199616661679 | 0.05922051041972409 | false | true | null |
| R060073 | 9000182 | diffraction_compatible | 19 | 0.026823813999570234 | 0.03959613070879137 | 0.1323076987978098 | 0.0016561094399903927 | -0.012030803101879428 | true | true | null |
| R060073 | 9013489 | diffraction_compatible | 20 | 0.019005503026498616 | 0.033394890410543686 | 0.12609872435775316 | -0.0009302710195349611 | 0.04078889074784797 | true | true | null |
| R060073 | 9013490 | diffraction_compatible | 20 | 0.019005503026498616 | 0.0333456238876019 | 0.12609872435775316 | -0.0009302710195349611 | 0.04078889074784797 | true | true | null |
| R060117 | 9005584 | diffraction_compatible | 18 | 0.005463536873189234 | 0.013808271315638242 | 0.14601772427356607 | 0.000739151725942523 | 0.045902904132468336 | true | false | null |
| R060133 | 9005584 | diffraction_compatible | 17 | 0.018600349089147983 | 0.018978779475244834 | 0.13511127242759358 | 0.0008655876244960374 | 0.05842785248987781 | true | false | null |
| R060156 | 1011021 | diffraction_compatible | 17 | 0.01860911726095793 | 0.021051681783465323 | 0.14396708900514454 | -0.0011608366435729798 | -0.015444116746706982 | true | true | null |
| R060156 | 9009581 | diffraction_compatible | 16 | 0.00255358209137313 | 0.005109497060092976 | 0.14917414708816068 | -0.00039481780945243623 | 0.035082134033707746 | true | true | null |
| R060192 | 9001263 | diffraction_inconclusive | 10 | 0.08119206198582418 | 0.07617288472752323 | 0.11972669325146512 | 0.0018268756269534624 | -0.003230028353939929 | false | true | null |
| R060192 | 9002434 | diffraction_inconclusive | 6 | 0.03770568321595036 | 0.04961485599658665 | 0.11742444769413041 | 0.0009816801156222886 | -0.047869747512123695 | false | true | null |
| R060198 | 9004867 | diffraction_inconclusive | 16 | 0.06518806475803807 | 0.06533168921854107 | 0.14419793420945837 | -0.0014307913877733619 | -0.05171267684752934 | false | false | null |
| R060215 | 9002411 | diffraction_compatible | 17 | 0.04313317372404413 | 0.042420232111272424 | 0.136592295657735 | -0.0021691615659765765 | 0.03394215905459674 | true | true | null |
| R060215 | 9002412 | diffraction_compatible | 18 | 0.03143885517509304 | 0.044293282232735584 | 0.1322294538692006 | -0.0009382903369756448 | 0.03837547682677567 | true | true | null |
| R060215 | 9002413 | diffraction_compatible | 17 | 0.04271922575158982 | 0.047279556237807954 | 0.10672049534273143 | -0.0003279305558671337 | 0.00695060301414685 | true | true | null |
| R060215 | 9002414 | diffraction_compatible | 17 | 0.042287028207194766 | 0.03854297972367168 | 0.10259736387810392 | -0.0009682522178213838 | 0.044062404179694425 | true | true | null |
| R060215 | 9002415 | diffraction_compatible | 17 | 0.04263531583328728 | 0.04092635285257267 | 0.11899129851353507 | 0.0008200734641694705 | 0.04871204346175517 | true | true | null |
| R060215 | 9002416 | diffraction_compatible | 17 | 0.01712315626215144 | 0.029191890193538485 | 0.10076018537679232 | -0.0015545913653328028 | 0.03896680738296254 | true | true | null |
| R060215 | 9002417 | diffraction_compatible | 17 | 0.043473693017851645 | 0.04613107970308343 | 0.10218154992652018 | -0.0016758410698266104 | 0.022599835016769987 | true | true | null |
| R060215 | 9002418 | diffraction_compatible | 17 | 0.027368758776404434 | 0.039636317342127414 | 0.1148529298801435 | -0.0008322769823775714 | 0.026227218942747044 | true | true | null |
| R060215 | 9002419 | diffraction_compatible | 17 | 0.032820650955674324 | 0.033225342977904956 | 0.09177504358073207 | -0.0011041161570097024 | 0.04412219213993751 | true | true | null |
| R060215 | 9002420 | diffraction_compatible | 17 | 0.04622675288184119 | 0.049404604511659914 | 0.1127546056109523 | -0.0014545480404941392 | 0.013967526171818179 | true | true | null |
| R060292 | 9005443 | diffraction_compatible | 18 | 0.04252209667752993 | 0.024903780579828 | 0.09240773458884988 | -0.0007879400522594436 | 0.018310155860230992 | true | false | null |
| R060300 | 9000485 | diffraction_compatible | 19 | 0.03744058470390854 | 0.035966267575564294 | 0.12234436810641469 | 0.0006834271709801076 | 0.04784220186927968 | true | true | null |
| R060300 | 9001518 | diffraction_compatible | 20 | 0.0606550006495894 | 0.055114522970399385 | 0.141708706779756 | -0.0014992270752162392 | 0.06270455343117831 | true | true | null |
| R060300 | 9001519 | diffraction_compatible | 17 | 0.0565782709609195 | 0.04742564457196564 | 0.14634207339143046 | -0.0031266111438204586 | -0.03269863957072161 | true | true | null |
| R060300 | 9001520 | diffraction_compatible | 18 | 0.047160376305994234 | 0.053491899297789365 | 0.1171480207497595 | -0.001468273255014732 | -0.028156002926145618 | true | true | null |
| R060300 | 9001795 | diffraction_compatible | 19 | 0.011513040901483862 | 0.01229910918310662 | 0.14036039595084304 | -0.0019960329008389026 | 0.013981640872259504 | true | true | null |
| R060300 | 9001796 | diffraction_compatible | 13 | 0.025146819623444117 | 0.024236676546404937 | 0.12066757063737299 | -0.001515686108348871 | -0.0016520707593699058 | true | true | null |
| R060300 | 9001797 | diffraction_inconclusive | 7 | 0.04200484019757056 | 0.04399155774358753 | 0.11007198668383467 | 0.0006984046715441008 | 0.051842408639437565 | false | true | null |
| R060300 | 9001798 | diffraction_inconclusive | 14 | 0.07204356163870962 | 0.07539725662729464 | 0.12592550293985738 | 0.003178564262041454 | 0.023831889588741717 | false | true | null |
| R060300 | 9008149 | diffraction_inconclusive | 13 | 0.07400759656087175 | 0.06182903878444223 | 0.13122619690958004 | -0.0010008553496780135 | -0.011717382878252636 | false | true | null |
| R060300 | 9013186 | diffraction_compatible | 19 | 0.009093555626400018 | 0.008884475645123128 | 0.1283998426718469 | 0.000641542174256716 | 0.07544450472945385 | true | true | null |
| R060300 | 9013187 | diffraction_compatible | 19 | 0.037874701221404905 | 0.03879565009820485 | 0.11725488982046528 | 0.000870176211758706 | 0.05786214856574645 | true | true | null |
| R060300 | 9013188 | diffraction_compatible | 18 | 0.01800225864359639 | 0.01820349139782488 | 0.07611141517994469 | -0.000344847829124066 | 0.009784965200744011 | true | true | null |
| R060300 | 9013189 | diffraction_compatible | 17 | 0.057462355194182635 | 0.04752010484387766 | 0.14110951307795716 | 0.0019217599325920993 | 0.019427163812686388 | true | true | null |
| R060300 | 9013190 | diffraction_compatible | 16 | 0.04653117294390974 | 0.034805664631529 | 0.14459233833812135 | 0.0008667472520132999 | 0.009980654970366487 | true | true | null |
| R060300 | 9013191 | diffraction_compatible | 18 | 0.015160425804049638 | 0.027311825056960566 | 0.0997020794508714 | -0.0012196436245288697 | 0.0378661453477207 | true | true | null |
| R060417 | 9009626 | diffraction_compatible | 16 | 0.022145980532279452 | 0.017124065400405078 | 0.11714201040035022 | -0.0001257211945517395 | -0.005760860397401757 | true | true | null |
| R060417 | 9009627 | diffraction_compatible | 16 | 0.022145980532279452 | 0.016622583953273026 | 0.11714201040035022 | -0.0001257211945517395 | -0.005760860397401757 | true | true | null |
| R060417 | 9009628 | diffraction_compatible | 18 | 0.054759069406493666 | 0.044658966703987245 | 0.1369997810679351 | -0.00046357115055958674 | -0.1590493399874049 | true | true | null |
| R060417 | 9009629 | diffraction_inconclusive | 3 | 0.026184330574587023 | 0.012239749535771933 | 0.03531054318952087 | -0.0007386184867540343 | 0.026173263397627267 | false | true | null |
| R060417 | 9009630 | diffraction_inconclusive | 4 | 0.04659292403381521 | 0.02799247621229858 | 0.12125733749864764 | 0.0014019509662639026 | -0.09858514474453273 | false | true | null |
| R060417 | 9009631 | diffraction_inconclusive | 2 | 0.06320562362967053 | 0.011099393601179761 | 0.12641124725934105 | -0.01188476491936255 | 0.17069444468118178 | false | true | null |
| R060501 | 9000032 | diffraction_inconclusive | 18 | 0.05900185995254503 | 0.05772729902097976 | 0.11468095768852749 | -2.8902305414672453e-05 | 0.013676383502733813 | false | false | null |
| R060512 | 1011262 | diffraction_compatible | 16 | 0.03768050936230338 | 0.030316659797170204 | 0.10707982537151395 | 0.001325436397272999 | -0.011420202844085736 | true | true | null |
| R060512 | 1514120 | diffraction_compatible | 16 | 0.03621517639691518 | 0.025229933014268006 | 0.08829382218675619 | -4.73338943717822e-06 | 0.01778940016890118 | true | true | null |
| R060512 | 1514121 | diffraction_compatible | 16 | 0.051290551821068675 | 0.04083070524810308 | 0.1225566180370734 | -0.00014602808774214567 | -0.024855293919472388 | true | true | null |
| R060512 | 1514236 | diffraction_compatible | 16 | 0.04017527498274376 | 0.03166905916914108 | 0.08212737690181626 | -0.0005721324996270467 | -0.005280143872923304 | true | true | null |
| R060512 | 1514240 | diffraction_compatible | 16 | 0.043388366708036585 | 0.03081129703913494 | 0.0869408380135468 | -0.0004259302625508708 | 0.0007637498048396196 | true | true | null |
| R060512 | 9001963 | diffraction_compatible | 16 | 0.013530416930041866 | 0.012410504626195008 | 0.05939631921454236 | -0.00012997359657273907 | 0.055795385075327886 | true | true | null |
| R060512 | 9001964 | diffraction_compatible | 16 | 0.04007429512394012 | 0.04269586307307827 | 0.10656629349089286 | 0.0005108611482727806 | 0.055664312069545474 | true | true | null |
| R060512 | 9001965 | diffraction_compatible | 12 | 0.04301819694580544 | 0.048021643081670534 | 0.12368260409589027 | -0.0012503079916775192 | 0.061656718294415214 | true | true | null |
| R060520 | 9000033 | diffraction_compatible | 18 | 0.041896015899089534 | 0.02932941214435486 | 0.10616445345770842 | -4.566366494449078e-05 | -0.030960036795566026 | true | false | null |
| R060532 | 1011221 | diffraction_compatible | 16 | 0.052603444334317295 | 0.04971761192927768 | 0.1302112673311555 | 0.0020171849107741137 | 0.07082998282311337 | true | true | null |
| R060532 | 9001022 | diffraction_compatible | 16 | 0.03151242969378831 | 0.036874428302928336 | 0.08909968690423042 | 6.567330437580888e-05 | 0.00894560040450898 | true | true | null |
| R060532 | 9001038 | diffraction_compatible | 16 | 0.025925263790192332 | 0.043891153020046696 | 0.1353577669399968 | -0.001631255356487371 | -0.018672736996911965 | true | true | null |
| R060532 | 9001070 | diffraction_inconclusive | 5 | 0.10698913645250308 | 0.06094910302906107 | 0.11303489564532043 | 0.003966219897869366 | 0.026072564510397633 | false | true | null |
| R060532 | 9001499 | diffraction_compatible | 17 | 0.03798101934609832 | 0.03170518471204715 | 0.0851733238764325 | -0.0003761946295440722 | -0.02721670373838947 | true | true | null |
| R060532 | 9001500 | diffraction_inconclusive | 18 | 0.0777795403639594 | 0.057453858242414245 | 0.14903248581305917 | 0.0011411710355737107 | 0.04644059153473279 | false | true | null |
| R060532 | 9001501 | diffraction_inconclusive | 19 | 0.06730590182527862 | 0.04512056372324815 | 0.13974642930804038 | 0.0006754456848612729 | 0.013384630089937843 | false | true | null |
| R060532 | 9001502 | diffraction_compatible | 19 | 0.023272401628936734 | 0.03341373360445523 | 0.08350467228682135 | 0.00013747214132836356 | 0.02309141793955405 | true | true | null |
| R060532 | 9002335 | diffraction_compatible | 18 | 0.045827638711010366 | 0.03893054672968248 | 0.1352775580012846 | -0.0008270814574417651 | -0.05546420806307495 | true | true | null |
| R060532 | 9002336 | diffraction_compatible | 15 | 0.023749830162248742 | 0.03452584216195765 | 0.135075338646665 | -0.002771930558289718 | 0.022045874766035922 | true | true | null |
| R060532 | 9002337 | diffraction_compatible | 17 | 0.05129308163833457 | 0.05191529898142403 | 0.1433532780019391 | -0.0014029438159419544 | 0.004536848569207663 | true | true | null |
| R060532 | 9004081 | diffraction_compatible | 17 | 0.049343423503216854 | 0.046416302099517616 | 0.14922169158661802 | -0.0008616539589300632 | -0.0065603272928953515 | true | true | null |
| R060532 | 9004082 | diffraction_compatible | 20 | 0.054552276655991605 | 0.045469645529580216 | 0.131280597712788 | 0.0006213131688716933 | -0.004991241871156404 | true | true | null |
| R060532 | 9004083 | diffraction_compatible | 16 | 0.041805044357106524 | 0.03502332660557593 | 0.09957734914993921 | -0.000580750067549275 | -0.005984058120922953 | true | true | null |
| R060532 | 9004256 | diffraction_compatible | 19 | 0.019914025716168737 | 0.031111682166263394 | 0.11897626458051036 | -0.0017330021246933793 | -0.014452150239343098 | true | true | null |
| R060532 | 9004257 | diffraction_compatible | 17 | 0.042288917725294084 | 0.03804316500152814 | 0.13435817562512398 | -0.00213835024142324 | -0.004991241871156404 | true | true | null |
| R060532 | 9004258 | diffraction_compatible | 17 | 0.044553568666593435 | 0.037598236686688734 | 0.1290040362887268 | -0.0012313521362260788 | -0.0013246985904071806 | true | true | null |
| R060532 | 9004259 | diffraction_compatible | 17 | 0.03133895184941515 | 0.03276884350286307 | 0.10581020449156853 | -0.0013134739836938045 | -0.019681129477948645 | true | true | null |
| R060532 | 9004442 | diffraction_compatible | 12 | 0.04757556865811452 | 0.04037300788849366 | 0.13386701812904533 | 0.0001760260342705218 | 0.12409566866504029 | true | true | null |
| R060532 | 9004443 | diffraction_compatible | 13 | 0.052896178468991195 | 0.03474749652103713 | 0.14684153685870882 | 0.0019653880493383288 | 0.11620351924002392 | true | true | null |
| R060532 | 9004477 | diffraction_compatible | 16 | 0.021807965777050242 | 0.0412692908776073 | 0.12576867871744213 | -0.0018824815440757264 | 0.015178673286541766 | true | true | null |
| R060532 | 9004478 | diffraction_compatible | 17 | 0.02503318342966665 | 0.03979899244946059 | 0.12000000000000455 | -0.0019993901862621994 | 0.009409994569104185 | true | true | null |
| R060532 | 9004529 | diffraction_compatible | 18 | 0.030583718068141863 | 0.032253698008461174 | 0.08806244633152716 | -0.0010677635059900385 | 0.010039552331942758 | true | true | null |
| R060532 | 9004768 | diffraction_compatible | 17 | 0.03309880564764711 | 0.03423619515363401 | 0.08727975316808312 | -0.0008194006763896183 | -0.004137737390983887 | true | true | null |
| R060532 | 9004769 | diffraction_compatible | 17 | 0.05430861653533725 | 0.0374152113687004 | 0.09289443099161332 | 0.0007447587510883687 | 0.0020906251444827717 | true | true | null |
| R060532 | 9004770 | diffraction_compatible | 17 | 0.05374510390086584 | 0.03455212350221899 | 0.07065249089008674 | -9.673543283651435e-05 | -0.021918152492368392 | true | true | null |
| R060532 | 9010614 | diffraction_compatible | 12 | 0.02732913917811075 | 0.016197457627386544 | 0.11588404048365675 | -0.0009410904390193931 | 0.08235716016531214 | true | true | null |
| R060532 | 9014245 | diffraction_compatible | 18 | 0.05006990941231493 | 0.045360548143814725 | 0.1414703879086865 | 0.00030400878958932435 | 0.01492620137731926 | true | true | null |
| R060532 | 9014836 | diffraction_compatible | 17 | 0.054643023024908643 | 0.0499780639848605 | 0.13133484282866448 | 0.0008703412201914154 | 0.021939216892766567 | true | true | null |
| R060532 | 9016909 | diffraction_inconclusive | 11 | 0.03280248911097772 | 0.027190152775689286 | 0.14790678867047546 | 0.0004667930546096193 | 0.10394103930136822 | false | true | null |
| R060532 | 9016939 | diffraction_compatible | 13 | 0.02303928641447328 | 0.019299462285480025 | 0.12800506679376156 | 3.3081489939455905e-05 | 0.11620351924002392 | true | true | null |
| R060639 | 9008069 | diffraction_inconclusive | 12 | 0.05000477829016514 | 0.048622510804331394 | 0.09200886881469472 | -0.0015919888597761011 | -0.0072812161884243665 | false | true | null |
| R060639 | 9008070 | diffraction_inconclusive | 14 | 0.05810011495763412 | 0.056571121202937016 | 0.1408756886817102 | -0.002141791536779346 | -0.07140461302594048 | false | true | null |
| R060725 | 9000115 | diffraction_inconclusive | 11 | 0.04568175634233462 | 0.0385180304062589 | 0.08446343989140814 | -0.0009396911180611568 | -0.0321104385905393 | false | true | null |
| R060725 | 9000757 | diffraction_compatible | 15 | 0.03437229439840195 | 0.02355475344355327 | 0.09740733341176622 | -0.0012067460055319552 | 0.04272211842258855 | true | true | null |
| R060725 | 9000758 | diffraction_compatible | 16 | 0.031058162104471876 | 0.020588604583992597 | 0.058956731741332646 | -0.0009484852809384249 | 0.05674623387358224 | true | true | null |
| R060725 | 9001568 | diffraction_compatible | 15 | 0.04047578541737096 | 0.043714933555948 | 0.12331713941011202 | 0.0011836840388816214 | -0.057441816511303756 | true | true | null |
| R060725 | 9002229 | diffraction_inconclusive | 14 | 0.06872745861680762 | 0.0385631034223697 | 0.1431019705034231 | -0.0012634899667598168 | -0.02646707050937458 | false | true | null |
| R060725 | 9010129 | diffraction_compatible | 15 | 0.04515986942236694 | 0.04001651104003972 | 0.13401954469342314 | 0.0014979020073732383 | 0.04523912097864624 | true | true | null |
| R060725 | 9010130 | diffraction_compatible | 14 | 0.05654108908839106 | 0.05186640442069443 | 0.13236037164983827 | -0.00022432026428433413 | -0.020706230109918344 | true | true | null |
| R060725 | 9010131 | diffraction_inconclusive | 13 | 0.07740100786675619 | 0.06020322410246895 | 0.1303399892693875 | -0.0003653999530966253 | 0.021411407393888027 | false | true | null |
| R060725 | 9010132 | diffraction_compatible | 12 | 0.052449583758670926 | 0.05173998670379135 | 0.14032845959587092 | 0.0020985970308145595 | 0.003793070540808685 | true | true | null |
| R060725 | 9010133 | diffraction_compatible | 16 | 0.02827830469862569 | 0.03685481591644714 | 0.14046008359055406 | 0.0008962924431582994 | -0.05343735280962747 | true | true | null |
| R060725 | 9013852 | diffraction_compatible | 14 | 0.03913966436891059 | 0.03393712730333203 | 0.10879167914682597 | 0.0013120319523298274 | 0.051044720040820835 | true | true | null |
| R060725 | 9013853 | diffraction_inconclusive | 17 | 0.0654566635710907 | 0.060048487950989014 | 0.14193042992140903 | 0.0018501947687797453 | -0.005601223542115008 | false | true | null |
| R060725 | 9013854 | diffraction_compatible | 15 | 0.051316985353201616 | 0.054009708745476705 | 0.10883021239571633 | -0.0004970959669632727 | -0.022083754790529042 | true | true | null |
| R060725 | 9013855 | diffraction_inconclusive | 17 | 0.055664038565236496 | 0.05982209826332227 | 0.14740693467626897 | -0.001437520921131717 | -0.0025968925600352577 | false | true | null |
| R060796 | 9006180 | diffraction_inconclusive | 14 | 0.07431092097967174 | 0.07934764228651112 | 0.1284728275108762 | -0.0004319489792737734 | -0.012107771165766223 | false | true | null |
| R060796 | 9006181 | diffraction_inconclusive | 14 | 0.07439745594142622 | 0.07924184770103064 | 0.1280285953928626 | -0.00041619256516977867 | -0.011560164041249266 | false | true | null |
| R060796 | 9006182 | diffraction_inconclusive | 14 | 0.0741378450562511 | 0.07959152337269881 | 0.12936133918215376 | 0.0003921072342399881 | -0.013203027966739 | false | true | null |
| R060796 | 9006185 | diffraction_inconclusive | 14 | 0.07431092097967174 | 0.07953703546703633 | 0.1284728275108762 | -0.0004319489792737734 | -0.012107771165766223 | false | true | null |
| R060796 | 9006186 | diffraction_inconclusive | 14 | 0.07439745594142622 | 0.07947542425963362 | 0.1280285953928626 | -0.00041619256516977867 | -0.011560164041249266 | false | true | null |
| R060796 | 9006187 | diffraction_inconclusive | 14 | 0.0741378450562511 | 0.07957833416947392 | 0.12936133918215376 | 0.0003921072342399881 | -0.013203027966739 | false | true | null |
| R060796 | 9006195 | diffraction_inconclusive | 14 | 0.07431092097967174 | 0.07952708716674214 | 0.1284728275108762 | -0.0004319489792737734 | -0.012107771165766223 | false | true | null |
| R060796 | 9006196 | diffraction_inconclusive | 14 | 0.07439745594142622 | 0.07939303743733368 | 0.1280285953928626 | -0.00041619256516977867 | -0.011560164041249266 | false | true | null |
| R060796 | 9006197 | diffraction_inconclusive | 14 | 0.0741378450562511 | 0.07960672944053701 | 0.12936133918215376 | 0.0003921072342399881 | -0.013203027966739 | false | true | null |
| R060796 | 9006219 | diffraction_inconclusive | 14 | 0.0741378450562511 | 0.07959686402997788 | 0.12936133918215376 | 0.0003921072342399881 | -0.013203027966739 | false | true | null |
| R060796 | 9006236 | diffraction_inconclusive | 14 | 0.07439745594142622 | 0.07929583705962902 | 0.1280285953928626 | -0.00041619256516977867 | -0.011560164041249266 | false | true | null |
| R060796 | 9006238 | diffraction_inconclusive | 14 | 0.07431092097967174 | 0.07940049466553621 | 0.1284728275108762 | -0.0004319489792737734 | -0.012107771165766223 | false | true | null |
| R060796 | 9006239 | diffraction_inconclusive | 14 | 0.07439745594142622 | 0.07929053435810961 | 0.1280285953928626 | -0.00041619256516977867 | -0.011560164041249266 | false | true | null |
| R060796 | 9006240 | diffraction_inconclusive | 14 | 0.0741378450562511 | 0.07945028857648516 | 0.12936133918215376 | 0.0003921072342399881 | -0.013203027966739 | false | true | null |
| R060796 | 9006245 | diffraction_inconclusive | 14 | 0.0741378450562511 | 0.0795086480429487 | 0.12936133918215376 | 0.0003921072342399881 | -0.013203027966739 | false | true | null |
| R060796 | 9006248 | diffraction_inconclusive | 14 | 0.07431092097967174 | 0.07939944650703334 | 0.1284728275108762 | -0.0004319489792737734 | -0.012107771165766223 | false | true | null |
| R060796 | 9006249 | diffraction_inconclusive | 14 | 0.07439745594142622 | 0.07928927052839194 | 0.1280285953928626 | -0.00041619256516977867 | -0.011560164041249266 | false | true | null |
| R060796 | 9006250 | diffraction_inconclusive | 14 | 0.0741378450562511 | 0.07949405997511524 | 0.12936133918215376 | 0.0003921072342399881 | -0.013203027966739 | false | true | null |
| R060796 | 9006783 | diffraction_compatible | 16 | 0.029632272268564464 | 0.040683692738433114 | 0.1480799154246597 | 2.8978384101691753e-05 | 0.0906397620638657 | true | true | null |
| R060796 | 9007310 | diffraction_compatible | 16 | 0.03058276131308446 | 0.03539630560129379 | 0.14658769048493525 | 6.045716765393112e-05 | 0.09138544972168106 | true | true | null |
| R060796 | 9007311 | diffraction_compatible | 16 | 0.030107524993045587 | 0.03538534360853658 | 0.14724235208591097 | 4.471781573874888e-05 | 0.09101261053163512 | true | true | null |
| R060796 | 9012439 | diffraction_compatible | 15 | 0.012785891333223276 | 0.015599857446352589 | 0.14721410866678042 | -0.0005925242931638583 | 0.009562366763091745 | true | true | null |
| R060797 | 9006180 | diffraction_inconclusive | 13 | 0.07460111027593541 | 0.041728529120461016 | 0.11352622898878906 | 0.0005856586726411431 | -0.02221512197407094 | false | true | null |
| R060797 | 9006181 | diffraction_inconclusive | 13 | 0.07414530693044696 | 0.041665652784896645 | 0.11415144767305208 | 0.0006004050359384033 | -0.021771921667756544 | false | true | null |
| R060797 | 9006182 | diffraction_inconclusive | 13 | 0.07551276196033996 | 0.041377127391073215 | 0.11227572504110128 | 0.0005561657969694237 | -0.023101556152681724 | false | true | null |
| R060797 | 9006185 | diffraction_inconclusive | 13 | 0.07460111027593541 | 0.041418094600431755 | 0.11352622898878906 | 0.0005856586726411431 | -0.02221512197407094 | false | true | null |
| R060797 | 9006186 | diffraction_inconclusive | 13 | 0.07414530693044696 | 0.04157901939209572 | 0.11415144767305208 | 0.0006004050359384033 | -0.021771921667756544 | false | true | null |
| R060797 | 9006187 | diffraction_inconclusive | 13 | 0.07551276196033996 | 0.04130804811965367 | 0.11227572504110128 | 0.0005561657969694237 | -0.023101556152681724 | false | true | null |
| R060797 | 9006195 | diffraction_inconclusive | 13 | 0.07460111027593541 | 0.04148251596723972 | 0.11352622898878906 | 0.0005856586726411431 | -0.02221512197407094 | false | true | null |
| R060797 | 9006196 | diffraction_inconclusive | 13 | 0.07414530693044696 | 0.04160052845850781 | 0.11415144767305208 | 0.0006004050359384033 | -0.021771921667756544 | false | true | null |
| R060797 | 9006197 | diffraction_inconclusive | 13 | 0.07551276196033996 | 0.04140523892435573 | 0.11227572504110128 | 0.0005561657969694237 | -0.023101556152681724 | false | true | null |
| R060797 | 9006219 | diffraction_inconclusive | 13 | 0.07551276196033996 | 0.041327668462728805 | 0.11227572504110128 | 0.0005561657969694237 | -0.023101556152681724 | false | true | null |
| R060797 | 9006236 | diffraction_inconclusive | 13 | 0.07414530693044696 | 0.041596377235219285 | 0.11415144767305208 | 0.0006004050359384033 | -0.021771921667756544 | false | true | null |
| R060797 | 9006238 | diffraction_inconclusive | 13 | 0.07460111027593541 | 0.04152102709518931 | 0.11352622898878906 | 0.0005856586726411431 | -0.02221512197407094 | false | true | null |
| R060797 | 9006239 | diffraction_inconclusive | 13 | 0.07414530693044696 | 0.041632910957830165 | 0.11415144767305208 | 0.0006004050359384033 | -0.021771921667756544 | false | true | null |
| R060797 | 9006240 | diffraction_inconclusive | 13 | 0.07551276196033996 | 0.04147277517191525 | 0.11227572504110128 | 0.0005561657969694237 | -0.023101556152681724 | false | true | null |
| R060797 | 9006245 | diffraction_inconclusive | 13 | 0.07551276196033996 | 0.04136516318900925 | 0.11227572504110128 | 0.0005561657969694237 | -0.023101556152681724 | false | true | null |
| R060797 | 9006248 | diffraction_inconclusive | 13 | 0.07460111027593541 | 0.041516107415426 | 0.11352622898878906 | 0.0005856586726411431 | -0.02221512197407094 | false | true | null |
| R060797 | 9006249 | diffraction_inconclusive | 13 | 0.07414530693044696 | 0.04164237507959388 | 0.11415144767305208 | 0.0006004050359384033 | -0.021771921667756544 | false | true | null |
| R060797 | 9006250 | diffraction_inconclusive | 13 | 0.07551276196033996 | 0.04146310690753239 | 0.11227572504110128 | 0.0005561657969694237 | -0.023101556152681724 | false | true | null |
| R060797 | 9006783 | diffraction_inconclusive | 13 | 0.08093913668357189 | 0.04330799542442475 | 0.10828898318500535 | 0.0003792043676076971 | -0.028421101252561698 | false | true | null |
| R060797 | 9007310 | diffraction_inconclusive | 13 | 0.0800719204611795 | 0.041295738512100756 | 0.1076678422860482 | 0.00040869843634055867 | -0.027534398477207844 | false | true | null |
| R060797 | 9007311 | diffraction_inconclusive | 13 | 0.08052791883763177 | 0.04137306019347386 | 0.10797840792525903 | 0.00039395142683778275 | -0.027977744267822402 | false | true | null |
| R060797 | 9012439 | diffraction_compatible | 17 | 0.039682246835404555 | 0.022011740196565963 | 0.08866687024894304 | 0.0004898660960520429 | 0.07956236676308492 | true | true | null |
| R060901 | 9015080 | diffraction_compatible | 20 | 0.030253482848280555 | 0.04548805208249468 | 0.12977305267692785 | 0.00020998390760157385 | 0.0014672610901591554 | true | false | null |
| R061020 | 9000088 | diffraction_inconclusive | 3 | 0.0641845322852248 | 0.03344285121498572 | 0.08792924915708511 | -0.0012733970100977199 | 0.028223868393332907 | false | true | null |
| R061020 | 9000089 | diffraction_compatible | 3 | 0.01760550136553718 | 0.02898895675384692 | 0.09779339080113658 | 0.001608962790289321 | -0.024286379718290618 | true | true | null |
| R061020 | 9000090 | diffraction_compatible | 3 | 0.036142037599390164 | 0.019480801043307502 | 0.05190610184975242 | -0.0017695385436950642 | -0.04939385284328068 | true | true | null |
| R061020 | 9013941 | diffraction_compatible | 8 | 0.024435178204875285 | 0.028991099259490786 | 0.11887478666277218 | 0.001115394116288678 | -0.02258663471423006 | true | true | null |
| R061031 | 9000027 | diffraction_compatible | 18 | 0.039804844873611245 | 0.03579851628479376 | 0.14849200973147703 | -0.001158630465335854 | -0.04494088101208149 | true | true | null |
| R061031 | 9000418 | diffraction_compatible | 18 | 0.01663324055940585 | 0.018166437663512273 | 0.08442766816533265 | -0.0005507349656157491 | 0.012171820858149829 | true | true | null |
| R061031 | 9000878 | diffraction_compatible | 18 | 0.01648481599941931 | 0.018455599293734543 | 0.08217328383845768 | -0.0006037454721945067 | 0.010761100171158944 | true | true | null |
| R061031 | 9000879 | diffraction_inconclusive | 17 | 0.05778246805454046 | 0.06666199920930019 | 0.14361491683089866 | -0.0014184852254169266 | -0.028505870852306714 | false | true | null |
| R061031 | 9001855 | diffraction_compatible | 18 | 0.03449027665380555 | 0.030946337506941764 | 0.08639460141607458 | 0.00040791463432322047 | 0.04059827036103414 | true | true | null |
| R061031 | 9001856 | diffraction_compatible | 12 | 0.040304815866369026 | 0.02644859875261179 | 0.10900973486987198 | -0.0010901109379980655 | 0.022039411068991654 | true | true | null |
| R061031 | 9017228 | diffraction_compatible | 12 | 0.02734232718496976 | 0.045472394051568776 | 0.11497565301147006 | -0.0005905408603598301 | -0.0008765881397501118 | true | true | null |
| R061043 | 9004100 | diffraction_inconclusive | 19 | 0.0701778715769592 | 0.07337878080357547 | 0.1452487433562908 | -3.6264739436643715e-06 | 0.06924369984734824 | false | false | null |
| R061076 | 9011956 | diffraction_inconclusive | 20 | 0.06111053069582084 | 0.07818321505669966 | 0.11851157539391899 | 0.0011350287489964835 | -0.08429288342413344 | false | true | null |
| R061076 | 9017253 | diffraction_inconclusive | 19 | 0.062288115382621356 | 0.07599333672857317 | 0.13555027877319148 | 8.691597951799747e-06 | -0.08537665301658848 | false | true | null |
| R070137 | 9002487 | diffraction_compatible | 19 | 0.04857952743844862 | 0.02697078860308645 | 0.11766499735146851 | 6.851833968998919e-05 | -0.07802439795568361 | true | true | null |
| R070137 | 9002488 | diffraction_compatible | 18 | 0.05251626400876219 | 0.028523987225922122 | 0.10856000803792654 | 0.000713202473809707 | -0.026577169372366427 | true | true | null |
| R070137 | 9002489 | diffraction_compatible | 19 | 0.007663516933590131 | 0.009370210138385732 | 0.14819148661466386 | -0.0006679905176391608 | 0.0325949927209237 | true | true | null |
| R070137 | 9002490 | diffraction_compatible | 18 | 0.024737857230704208 | 0.012844096881413256 | 0.08672213188901878 | 3.346111332551401e-05 | 0.06620844652012181 | true | true | null |
| R070137 | 9002491 | diffraction_compatible | 18 | 0.04322258206173757 | 0.02040256288194721 | 0.08824623671260667 | 0.0006986350705953076 | 0.07984642768123251 | true | true | null |
| R070137 | 9002492 | diffraction_compatible | 19 | 0.04543344934018734 | 0.03322826298599241 | 0.13631265236877255 | 8.351690783552108e-05 | 0.08511783241645077 | true | true | null |
| R070137 | 9002493 | diffraction_inconclusive | 18 | 0.0726061800435609 | 0.07422828437783534 | 0.13492733247343836 | -0.001348347172777479 | -0.015824383993049196 | false | true | null |
| R070137 | 9002494 | diffraction_inconclusive | 18 | 0.060646122962076277 | 0.07491538744145244 | 0.12307202401831319 | -0.0016341737019308262 | 0.014483215019474471 | false | true | null |
| R070137 | 9002495 | diffraction_inconclusive | 18 | 0.031636810989784436 | 0.07439813672157995 | 0.1325683108159339 | -0.0005550221672829007 | 0.04157404285083999 | false | true | null |
| R070137 | 9002496 | diffraction_inconclusive | 15 | 0.08325498839077738 | 0.038492640161156694 | 0.13650137733802126 | -0.0003783813491809858 | 0.003177907988273887 | false | true | null |
| R070137 | 9002497 | diffraction_inconclusive | 13 | 0.0786006994980113 | 0.02884919506133429 | 0.11393424667089391 | -0.002148435994187135 | 0.04128293502228786 | false | true | null |
| R070137 | 9002498 | diffraction_compatible | 14 | 0.06158438985378467 | 0.042403567366985896 | 0.14796825970058336 | -0.0015303143268852902 | 0.05554879707567295 | true | true | null |
| R070137 | 9002499 | diffraction_compatible | 13 | 0.029874265988937054 | 0.01329629140901474 | 0.12329011146368885 | 1.6477512328178852e-05 | 0.008279798926011495 | true | true | null |
| R070137 | 9005102 | diffraction_compatible | 19 | 0.050371812291700735 | 0.026755324360272576 | 0.12007942354027534 | 0.0001159166672469363 | -0.07693563113867441 | true | true | null |
| R070137 | 9005103 | diffraction_compatible | 19 | 0.050371812291700735 | 0.026732548181299862 | 0.12007942354027534 | 0.0001159166672469363 | -0.07693563113867441 | true | true | null |
| R070137 | 9005104 | diffraction_compatible | 19 | 0.050371812291700735 | 0.02673535308222632 | 0.12007942354027534 | 0.0001159166672469363 | -0.07693563113867441 | true | true | null |
| R070137 | 9005105 | diffraction_compatible | 18 | 0.050876310381212875 | 0.0267585326305937 | 0.12007942354027534 | 0.0001305858169609747 | -0.07693563113867441 | true | true | null |
| R070137 | 9005106 | diffraction_compatible | 18 | 0.050876310381212875 | 0.026729139488991388 | 0.12007942354027534 | 0.0001305858169609747 | -0.07693563113867441 | true | true | null |
| R070137 | 9005107 | diffraction_compatible | 18 | 0.050876310381212875 | 0.026620876075577803 | 0.12007942354027534 | 0.0001305858169609747 | -0.07693563113867441 | true | true | null |
| R070137 | 9005108 | diffraction_compatible | 18 | 0.050876310381212875 | 0.026735345497726982 | 0.12007942354027534 | 0.0001305858169609747 | -0.07693563113867441 | true | true | null |
| R070137 | 9005109 | diffraction_compatible | 18 | 0.050876310381212875 | 0.02664742377451058 | 0.12007942354027534 | 0.0001305858169609747 | -0.07693563113867441 | true | true | null |
| R070137 | 9005110 | diffraction_compatible | 18 | 0.050876310381212875 | 0.02672135407446707 | 0.12007942354027534 | 0.0001305858169609747 | -0.07693563113867441 | true | true | null |
| R070137 | 9005111 | diffraction_compatible | 18 | 0.050876310381212875 | 0.026737204037239636 | 0.12007942354027534 | 0.0001305858169609747 | -0.07693563113867441 | true | true | null |
| R070137 | 9005112 | diffraction_compatible | 18 | 0.050876310381212875 | 0.026723030516403845 | 0.12007942354027534 | 0.0001305858169609747 | -0.07693563113867441 | true | true | null |
| R070137 | 9005113 | diffraction_compatible | 18 | 0.050876310381212875 | 0.026723028756217827 | 0.12007942354027534 | 0.0001305858169609747 | -0.07693563113867441 | true | true | null |
| R070137 | 9005114 | diffraction_compatible | 18 | 0.050876310381212875 | 0.02669044073153572 | 0.12007942354027534 | 0.0001305858169609747 | -0.07693563113867441 | true | true | null |
| R070137 | 9005295 | diffraction_compatible | 19 | 0.051467740848700316 | 0.03294980992470869 | 0.14392419828830327 | -0.001011233269679095 | -0.02325507195522647 | true | true | null |
| R070137 | 9005395 | diffraction_compatible | 18 | 0.026082567223006947 | 0.024374348213057687 | 0.13841044703370642 | -0.0003908720239765386 | 0.007381124841693065 | true | true | null |
| R070137 | 9005396 | diffraction_compatible | 18 | 0.03174748996872978 | 0.01863403438124744 | 0.13364819256043603 | -0.0005945954770157645 | 0.0026894191243691523 | true | true | null |
| R070137 | 9005397 | diffraction_compatible | 19 | 0.052493832929563666 | 0.027017249294389444 | 0.130538922286334 | 0.00032130056774398665 | -0.0722185675908591 | true | true | null |
| R070137 | 9005398 | diffraction_compatible | 18 | 0.0532561128308231 | 0.028932680488943197 | 0.1281256265096289 | 0.00028853326092540796 | -0.0733069871822174 | true | true | null |
| R070137 | 9005399 | diffraction_compatible | 18 | 0.05261742004393355 | 0.027026408771348757 | 0.125712069948122 | 0.0002411499278930449 | -0.07439548688763864 | true | true | null |
| R070137 | 9005400 | diffraction_compatible | 18 | 0.017903842692222227 | 0.00888725150007556 | 0.14607614773314026 | -0.0006262849007384053 | 0.01964468803540953 | true | true | null |
| R070137 | 9005401 | diffraction_compatible | 18 | 0.050315322358017056 | 0.028854028168922685 | 0.14694947741266162 | 4.0299286375007275e-06 | -0.06061374114094065 | true | true | null |
| R070137 | 9005402 | diffraction_compatible | 19 | 0.0492497548955555 | 0.027432014183773563 | 0.13583564455490205 | -0.0008680551937804642 | -0.019388113372841076 | true | true | null |
| R070137 | 9005403 | diffraction_compatible | 19 | 0.0492497548955555 | 0.027236057644104555 | 0.13583564455490205 | -0.0008680551937804642 | -0.019388113372841076 | true | true | null |
| R070137 | 9006893 | diffraction_compatible | 19 | 0.044994430064534185 | 0.02739719207348246 | 0.11283536195102783 | -2.6280614712471584e-05 | -0.0802021720573407 | true | true | null |
| R070137 | 9006894 | diffraction_inconclusive | 15 | 0.057626144024169434 | 0.060530157554349553 | 0.1068782738136278 | -3.938156082100691e-05 | -0.0032860488807422428 | false | true | null |
| R070137 | 9006895 | diffraction_inconclusive | 15 | 0.0675924346413268 | 0.0443590945684826 | 0.1235945707135997 | 0.0017210796140171617 | -0.07021146429992342 | false | true | null |
| R070137 | 9006896 | diffraction_inconclusive | 15 | 0.06526193138403613 | 0.06384749577869812 | 0.12767173054496084 | -0.0017411945993813834 | -0.021739831012979494 | false | true | null |
| R070137 | 9006897 | diffraction_compatible | 14 | 0.029353827323070902 | 0.01343845669231281 | 0.1296248755427598 | 4.590212105751101e-05 | -0.015134500751756264 | true | true | null |
| R070137 | 9006898 | diffraction_compatible | 12 | 0.028656761704944245 | 0.0322690838892155 | 0.13668808260341336 | -0.0008749078242073926 | 0.046350828964037305 | true | true | null |
| R070137 | 9006899 | diffraction_compatible | 13 | 0.055968025821542255 | 0.03512688935194491 | 0.10056544165556147 | 0.0013188005363469302 | 0.026817535839903428 | true | true | null |
| R070137 | 9006900 | diffraction_inconclusive | 13 | 0.06381739795067176 | 0.04519951476734798 | 0.13682698498148227 | 0.0001692418589332541 | -0.05593547587798753 | false | true | null |
| R070137 | 9006901 | diffraction_inconclusive | 13 | 0.0706231829364441 | 0.08927031804067963 | 0.12937681706355875 | 0.0013266196924288144 | -0.011543391137678327 | false | true | null |
| R070137 | 9006902 | diffraction_inconclusive | 12 | 0.04603346701968292 | 0.0764412361051728 | 0.11609051392461822 | 0.0008003029635155509 | -0.07438052345105461 | false | true | null |
| R070137 | 9006903 | diffraction_inconclusive | 11 | 0.03535667254143959 | 0.08700443489737562 | 0.14658518675938836 | 0.0025469192704676994 | -0.10955308356696492 | false | true | null |
| R070137 | 9006904 | diffraction_compatible | 12 | 0.03709185150876948 | 0.03599630534254474 | 0.12969967679903505 | 0.00020995702691393225 | -0.07572174142275401 | true | true | null |
| R070137 | 9006905 | diffraction_inconclusive | 12 | 0.04547425300508223 | 0.06255834408169955 | 0.14406629173485896 | 0.002033420234135382 | -0.09919101191555768 | false | true | null |
| R070137 | 9006906 | diffraction_inconclusive | 13 | 0.0722994438812492 | 0.039309770061373414 | 0.12865817623709574 | -0.0029110460640600416 | 0.017273749731380406 | false | true | null |
| R070137 | 9006907 | diffraction_compatible | 12 | 0.04950449594664974 | 0.038072441252407614 | 0.13999999999997925 | 0.00017586498483747174 | 0.10413254691522411 | true | true | null |
| R070137 | 9009894 | diffraction_compatible | 19 | 0.05268863783165045 | 0.026224862453466204 | 0.1273211366342224 | 0.00025810705315492674 | -0.07366981151535157 | true | true | null |
| R070137 | 9012441 | diffraction_inconclusive | 15 | 0.05620443672559361 | 0.059676687190264734 | 0.11614795667951228 | 0.00045173963490289615 | 0.008040851072816935 | false | true | null |
| R070137 | 9012442 | diffraction_inconclusive | 15 | 0.06837616508710198 | 0.0522523049796559 | 0.14702979337015165 | 0.0016662923232596536 | -0.004941211958907843 | false | true | null |
| R070137 | 9012443 | diffraction_inconclusive | 16 | 0.07111292855641693 | 0.051054155856448645 | 0.14434185131759136 | 0.0016599414356668414 | 0.02082376424554866 | false | true | null |
| R070229 | 9001023 | diffraction_inconclusive | 19 | 0.05428112849411093 | 0.059987641501716676 | 0.13924476563446575 | -0.0012026146125525814 | 0.011267012496688267 | false | true | null |
| R070229 | 9001119 | diffraction_compatible | 19 | 0.040843406058669984 | 0.04693595927916916 | 0.12261244004130134 | -0.0012690419961821175 | 0.02511297304668858 | true | true | null |
| R070229 | 9001120 | diffraction_compatible | 19 | 0.060230810731724205 | 0.050138522536878616 | 0.1406563766149418 | -0.0009303798275070493 | 0.023311427274016694 | true | true | null |
| R070229 | 9001121 | diffraction_compatible | 19 | 0.04185856209251426 | 0.04123058556926731 | 0.14840543118073413 | -0.00025716737869926464 | -0.0006604497244993013 | true | true | null |
| R070229 | 9001883 | diffraction_compatible | 19 | 0.047349802272858454 | 0.0506766969413888 | 0.13926781811730393 | -0.001244164610265266 | -0.00292680505820897 | true | true | null |
| R070229 | 9001884 | diffraction_compatible | 18 | 0.03877061456379938 | 0.04605934950964007 | 0.1272190414545804 | -0.000837024822539658 | 0.004666693509836506 | true | true | null |
| R070229 | 9001885 | diffraction_compatible | 18 | 0.038412375197832915 | 0.043030325461633684 | 0.12705794905068046 | -0.0012291302544329068 | -0.01968441065820059 | true | true | null |
| R070229 | 9001886 | diffraction_compatible | 19 | 0.04466439397170774 | 0.05566860037371202 | 0.13826585291694826 | -0.002660090290895489 | 0.013035508677056384 | true | true | null |
| R070229 | 9001887 | diffraction_compatible | 19 | 0.04697301708745272 | 0.04763168291556366 | 0.13195247110111552 | -0.001074707693354589 | -0.001968526213556032 | true | true | null |
| R070229 | 9001888 | diffraction_inconclusive | 19 | 0.05072287503011097 | 0.05761805964735436 | 0.14038107832384839 | -0.0016447182837761557 | 0.0024554522451119 | false | true | null |
| R070229 | 9007453 | diffraction_compatible | 18 | 0.03301830102985548 | 0.03180174400542476 | 0.1254401182039402 | -0.0012974553343290296 | -0.027676374535673176 | true | true | null |
| R070686 | 9000129 | diffraction_compatible | 15 | 0.033836001835609864 | 0.015938486611921595 | 0.0834211735175856 | -0.0003820758582830616 | -6.926432912024438e-05 | true | true | null |
| R070686 | 9004739 | diffraction_compatible | 17 | 0.00949199364130493 | 0.012319076463748779 | 0.12103008432629991 | 0.0014082735413526509 | 0.04056996392598222 | true | true | null |
| R070686 | 9014585 | diffraction_inconclusive | 8 | 0.03371643578491845 | 0.02814427363176073 | 0.1362254223226813 | 0.0003218254670540249 | -0.03598440319215612 | false | true | null |
| R070686 | 9015844 | diffraction_compatible | 17 | 0.009647272512612659 | 0.007866558560021743 | 0.07198227129305934 | -0.0003934126957058324 | -0.00033714518034955177 | true | true | null |
| R080045 | 9005422 | diffraction_inconclusive | 17 | 0.04820452201033376 | 0.05911195366157755 | 0.12865581015497796 | -0.0006056721515517435 | -0.009613999777730697 | false | true | null |
| R080045 | 9005423 | diffraction_compatible | 17 | 0.03928274669061693 | 0.03957676802192718 | 0.1152155776431627 | -0.0006630875340004556 | -0.04033704697885909 | true | true | null |
| R080045 | 9005424 | diffraction_compatible | 17 | 0.05587063150827376 | 0.04893805685048989 | 0.08459309954885086 | 0.0002564229709773018 | -0.010923558266554778 | true | true | null |
| R080045 | 9005425 | diffraction_compatible | 18 | 0.041278009262320836 | 0.05613756552186533 | 0.1454280782051356 | -0.000305838139939463 | 0.035079462216028645 | true | true | null |
| R080045 | 9005426 | diffraction_inconclusive | 17 | 0.036699814591855784 | 0.0636845087078957 | 0.13768963204811868 | -0.0015807874352516775 | 0.020556723294475887 | false | true | null |
| R090057 | 1524786 | diffraction_compatible | 17 | 0.01659621222687946 | 0.014656950637220771 | 0.12421763263015606 | -0.0010528465837176012 | 0.06637496898029838 | true | true | null |
| R090057 | 9000774 | diffraction_compatible | 16 | 0.02233060953055066 | 0.01821841029748702 | 0.10034198245640624 | 0.0003983185990276072 | 0.06637496898029838 | true | true | null |

## Exact Sources

- XY population: `data/mappings/rescue_review_v1/diffraction_needed_160_xy_audit.csv` filtered by `xy_origin_status=experimental_xy_available`.
- Existing candidate details and local CIF paths: `data/mappings/rescue_review_v1/rruff_rescue_candidate_details_v1.csv`.
- Experimental XY: read-only MongoDB `rruff.xy_raw` and `rruff.xy_processed`.
- Radiation provenance: read-only MongoDB `rruff.dif`, used only by the existing wavelength-derivation function.
- Calibration: `data/mappings/rruff_diffraction_calibration_v1.json`.

All results are audit outputs only. No candidate was written as a final record and no historical mapping was changed.
