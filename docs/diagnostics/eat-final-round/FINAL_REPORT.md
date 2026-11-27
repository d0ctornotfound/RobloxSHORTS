# EAT final correction round — disposition

**Status: CLOSED — bite pose approved; full animation is a known limitation.** No MP4 was rendered or published.

## Reference classifier preflight

Workflow [45989006460](https://github.com/d0ctornotfound/RobloxSHORTS/actions/runs/45989006460), artifact 15192977216. The exact approved frame-17 transforms were preserved and the calibrated classifier passed:

- Arm/body intersections: 29; head/arm: 42
- Body contact pairs: 30; outside calibrated shoulder/torso envelope: 0
- Head contact pairs: 42; outside calibrated hand-at-face envelope: 0
- Central-face intersections/rays: 0/0
- Peripheral obstruction rays: 1, allowed at contact

The envelopes are derived from the approved frame-17 polygon-pair contact distribution with 0.025-unit padding. Contacts outside the envelopes, central-face intersections, and central-face obstruction remain hard failures.

## Final search and validation

Workflow [45989350758](https://github.com/d0ctornotfound/RobloxSHORTS/actions/runs/45989350758), artifact 15192704273. The run evaluated 72 combinations of forward/down carry offsets, elbow branch, hand surface point and blend window.

- 60 integer frames + 59 half-frames = 119 samples
- Best candidate: front offset 0.25, down offset 0.08, elbow branch -1, hand UV (0.15, 0.90), blend window 18
- Best result: 91/119 samples failed; 28 passed
- Phase totals: carry 1/1 failed; blend 79/80 failed; bite 11/38 flagged

### Failed gates and exact samples

| Gate | Samples | Count |
|---|---|---:|
| Food/body intersections | 1–4; 26.5–29; 31–32.5; 57–59.5 | 23 |
| Arm/body localization | 1–10.5; 22–37.5; 43–60 | 87 flagged |
| Head/arm localization | 6–11; 21.5–24.5; 35.5–38; 50–55 | 35 |
| Central-face clearance | 23.5 | 1 |
| Peripheral-face limit | 11.5; 21.5; 23–24.5; 35–36.5 | 10 |
| Exact transition IK | 1–8; 24–25.5; 26.5–32; 33.5–37; 52–60 | 56 |

**Classifier accounting caveat:** 11 bite samples, 43–48, were flagged by the arm/body localization gate because the implementation added one torso-accessory intersection to the arm/body count. Those samples have arm/body = 30, accessory = 1, and zero contacts outside the calibrated body zone. Under the supervisor's literal arm/body ≤30 rule, these 11 are not arm/body-threshold failures. The other 80 failed samples remain, so the full sequence still fails.

The transition solver could not reach the offset grip target at 56 samples. Those samples retained their original interpolated transforms and were marked failed; consequently the carry offset did not eliminate the food/body collisions across the path. Maximum measured food/body intersections remained 453; head/arm maximum was 52; arm/body maximum was 68.

### Gates that passed

Food/head = 0; food/arm = 0; food-tip lateral alignment and normal gap; grip gap (maximum 0.003001); end-cap alignment (minimum approximately 1.0); support clearance (minimum +0.002999); segment lengths; joint continuity; framing; opposite-arm clearance.

## Final disposition

The approved frame-17 bite pose remains the EAT standard. The 119-sample full animation failed the final targeted round. Independent replay and the 60-frame render were skipped by the workflow gate. No MP4, visual sign-off, or publication commit exists.

Per supervisor instruction, EAT is now closed as **bite-pose-approved / full-animation limitation**, like DRINK and HUG. No further EAT or DRINK work is authorized. Previously locked motions remain unchanged.

Full per-sample transforms, metrics and candidate search are retained in workflow artifact 15192704273.
