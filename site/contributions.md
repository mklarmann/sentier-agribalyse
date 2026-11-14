# Contributions

A contribution is a proposal that goes beyond a single finding: a mapping, a model, a parameter scenario or a method variant. It comes with its evidence and with the checks it must pass.

A contribution never replaces ADEME's numbers. It stands beside ADEME's release under its own name.

<!-- contributions-list -->

## Kinds of contribution

- **Mapping.** A correspondence between flows, processes or methods, such as a curated link from an AGRIBALYSE input to its background process.
- **Variant.** A method variant or a data variant, such as a parameter scenario that answers a what-if question.
- **Model.** A model or a rebuilt inventory. It is a new inventory with its own tests.

A contribution keeps its own name, so that users choose it knowingly. It can be excellent and still not be ADEME's number.

This workspace serves no built database, because AGRIBALYSE 3.2 is built on a licensed ecoinvent background. A contribution is therefore code, a mapping or a record that each user applies in their own [build](build.md). A workaround in one user's own inventory does not belong in this workspace.

## How a contribution moves

A contribution is **proposed**, then **testing**, then **reviewing**. It ends as **accepted**, **rejected** or **superseded**.

1. **Propose.** Open a [contribution issue](https://github.com/sentier-dev/sentier-agribalyse/issues/new?template=community-contribution.yml). A record is added to the repository in a pull request. It names the AGRIBALYSE release the work is based on, the exact version of the code or files, and the checks the contribution must pass.
2. **Build beside, never in place.** ADEME's release and the changed version are built separately, from the same inputs.
3. **Test.** The checks that the record names are run, and each result is attached with a link. A check that failed or was not run stays visible on the contribution's page. [How builds are checked](../community/build-validation.md) describes the checks on a build.
4. **Review.** The record names the reviewers. They approve the exact version that was tested. Objections are recorded with their answers. A contribution without named reviewers cannot be accepted.
5. **Decide.** A contribution can be accepted only when every required check has passed and every named reviewer has approved. An accepted contribution may become a recommendation to ADEME. ADEME decides what it does with it.

## What review means here

- People approve. An automated check verifies the record, not the science.
- An approval names the AGRIBALYSE release and the exact version it covers. It does not carry over to a later version.
- Nobody is named as a reviewer or contact without their agreement. Silence is not consent.
- A merged pull request is not ADEME's endorsement.

The working document for contributors is [the contribution workflow](../community/workflow.md) in the repository. It describes the record, the commands and how a recommendation is recorded.
