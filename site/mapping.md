# Mapping the inventory

A food inventory brings together ingredients, energy, transport and emissions. The import resolves each supplier input against the product and activity catalogues. For an emission, it looks for a flow in the appropriate environmental compartment so the impact method can characterize it.

## What changed during linking

In the recorded run, the import corrected 53,992 input labels and applied 2,116 unit conversions in supplier matching. Its report counts 132,585 linked exchanges out of 135,252 at that matching stage. The final scoring package retains 392,852 exchanges and records 3,917 drops across the assembled inventory. Those counts refer to different stages and populations.

[Open the Link stage of the run](build.md#run-step-4).

## The mapping rules

- [`agribalyse-3.2-delete-aggregated-ecoinvent-processes.json`](../source/agribalyse-3.2-delete-aggregated-ecoinvent-processes.json) and [`agribalyse-3.2-delete-aggregated-ecoinvent-products.json`](../source/agribalyse-3.2-delete-aggregated-ecoinvent-products.json) take out the aggregated ecoinvent processes that the export carries, and their products. Your own ecoinvent takes their place.
- [`agribalyse-3.2-correct-ecoinvent-edge-labels.json`](../source/agribalyse-3.2-correct-ecoinvent-edge-labels.json) corrects the labels of inputs that name such a process, so that they link to ecoinvent.
- [`agribalyse-3.2-extra-unit-conversions.json`](../source/agribalyse-3.2-extra-unit-conversions.json) holds unit conversions that inputs of AGRIBALYSE need and the general list does not have.
- [`curated_overrides.json`](../source/curated_overrides.json) holds hand-curated synonyms for elementary flows that link by no other rule.
- [`agribalyse-3.2-activity-location-overrides.json`](../source/agribalyse-3.2-activity-location-overrides.json) names the location of a few activities whose name in the export gives another one than ADEME's reference results use. Each entry says why.

A mapping can resolve an identifier while leaving a question about the product, geography or unit. [Inventory quality](../community/build-validation.md) describes how to examine that question in the finished inventory.
