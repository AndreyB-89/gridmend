# Energy asset explorer — preview v0.1

Open [energy-asset-explorer.html](../energy-asset-explorer.html) locally in a browser. It is a standalone offline HTML file with no service or package installation required.

## Included

- Six asset views: substation, BESS, PCS, solar, wind and thermal.
- Existing 36 substation component records retained in the substation view.
- Eight shared accessory/tooling types, reused by stable ID across the five extension views.
- Three illustrative supplier assemblies in each extension view.
- 59 unique component types, with 42 draft manufacturing routes in total. These are mixed-granularity catalog records, not a complete plant BOM or a replacement percentage.
- Route filters, application-role filter, search, rotatable schematic scenes and downloadable component briefs.
- Separate installed-accessory candidates, workshop-tooling-only candidates and specialist assemblies. Ordinary wood routes are tooling-only.

The new scenes are authored concept geometry. Accessories are deliberately enlarged and shown separately; their scene positions are not proposed installation locations. No plant design, dimensions, material grades, manufacturing CAD or service approval is inferred from these shapes.

All additions are AUTHOR_DRAFT_SCREENING, not verified training labels. Supplier markings mean no local replacement recommendation in this pilot. A non-safety accessory still requires its actual interfaces, duty, environment, material and acceptance checks to be reviewed. Applicability across asset classes is a screening hypothesis, not interchangeability across installed variants.

The spinner remains the only reconstruction demo target. This preview broadens the application story without claiming five new reconstruction pipelines or changing the team's freezes and submission schedule.

## Source and build

`build.py` reuses the committed substation scene and manufacturing catalog, adds the explicitly authored accessory/assembly examples, and emits `catalog.json` and the HTML from `viewer-template.html`.

From the repository root:

```sh
python3 reference/energy-asset-library/build.py
```

The original substation-only HTML and its catalog are preserved. Changes to that catalog require rebuilding this preview too.

For browser verification, with Playwright available to Node and Chrome installed:

```sh
node scripts/check_energy_explorer.cjs
```

The check exercises all six views and their route counts, supplier exclusions, shared applicability, tooling-only JSON exports, filter reset on asset changes, search, mobile overflow and browser errors. Screenshots and the sample brief are saved in a temporary directory printed by the check.

## Context sources

The example assignments are our screening proposals, not vendor endorsements. The underlying substation source list remains in `reference/substation-library/README.md`. Industrial context discussed for the broader roadmap:

- [DOE wind manufacturing and supply chain](https://www.energy.gov/cmei/systems/wind-manufacturing-and-supply-chain): manufacturing/tooling context.
- [Siemens Energy additive manufacturing onsite repair](https://www.siemens-energy.com/global/en/home/products-services/service/am-onsite-repair.html): specialist repair context; not evidence that turbine components belong in this local accessory pilot.
