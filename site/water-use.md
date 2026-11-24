## Water-use gap

**Step 3, Regional water use, widens the median gap from +7.4% to +25.3% against ADEME.** The first rebuild already has the +7.4% gap. Matching identifiers and flows leaves it there. Step 3 changes how the build scores water withdrawn and returned in each region. The inventories and their exchange quantities are identical on either side of this step. The final integration leaves the median at +25.3%.

**The evidence supports keeping the patch.** On ADEME's full licensed export, all 2,451 foods fall within 5% of their published water-use scores with the patch. The earlier unpatched build had 727 foods in that range. The largest remaining difference is about 1.53%. We also checked all 3,992 water factors against the adapted EF 3.1 workbook, including their units and how the patch treats river and ocean returns.

| Input scored with the same water patch | Median difference from ADEME | Foods within 5% (of 2,451) |
|---|---:|---:|
| Full licensed export | -0.02% | 2,451 |
| Earlier export retaining the adapted processes | -0.54% | 2,296 |
| Current distributable export | +25.30% | 496 |

The earlier export retained 210 processes that ADEME had adapted from ecoinvent. Removing those processes reproduced the current distributable input byte for byte. With the same background database and scoring method, this moves the median from 0.54% below ADEME to 25.3% above. The test isolates the effect of replacing those inventories as a group. How much each replacement contributes is still open.

On the distributable input, Step 3 moves 977 foods closer to ADEME and 1,474 further away. Each percentage compares a food's score with its own ADEME reference before display rounding. The median weights each food equally.

[Explore Step 3](#sd.step=water) · [ADEME's guidance on source formats and regional water use](https://doc.agribalyse.fr/documentation-en/agribalyse-data/data-access) · [Reproduce this check](../scripts/audit_water_gap.py)

## Source of ADEME's values

Source: ADEME, AGRIBALYSE 3.2 food spreadsheet (*AGRIBALYSE3.2 Tableur produits alimentaires*, sheet *Synthese*), last updated 21 August 2025, [Licence Ouverte / Etalab Open Licence 2.0](https://www.etalab.gouv.fr/licence-ouverte-open-licence). The rebuilt scores are computed here from ADEME's foreground export on ecoinvent 3.9.1. They are not ADEME's results, and ADEME has not reviewed them. [ADEME's data access](https://doc.agribalyse.fr/documentation-en/agribalyse-data/data-access)
