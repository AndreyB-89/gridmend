# 110 kV substation component library — explorer v0.3

This is an R&D demonstrator of a generic outdoor 110/10 kV substation. It contains a schematic 3D scene, ten equipment families and 36 component-type records. It is not a specific MODUS X, DTEK or GreenEnergy asset. No real station documents were used.

The confirmed next use case is phone-camera-assisted damage recognition followed by generation of dimensioned CAD for the specific replacement component and preparation for an appropriate manufacturing route: additive manufacturing, CNC machining/routing, sheet fabrication or specialist production. See `vision-prototype-brief.md` for the proposed camera-to-CAD workflow and `manufacturing-routing.md` for the expanded process/material classification. The camera, reconstruction and production workflow is not implemented yet. The original v0.1 ZIP remains the earlier model/catalog snapshot.

## Open the explorer

Open [substation-explorer.html](../substation-explorer.html) in a browser after cloning or downloading the repository. It is self-contained: no server, npm install, sponsor credentials or external JavaScript is needed. GitHub's file page shows source; download the HTML to run it locally.

- Rotate or separate the schematic parts; select a component from the model or accessible list.
- Filter by equipment, name/ID, 3D-print candidate, CNC candidate, fabrication candidate, supplier or engineered contractor.
- A component may have multiple candidate routes. Summary counts overlap and are not station quantities or reproducibility percentages.
- Details show actual process/material alternatives, required engineering evidence and whether AI-assisted replacement CAD is a roadmap candidate.
- Download a component JSON brief with route records and explicit unknowns. This is not a CAD download; manufacturing CAD is absent for these entries.
- Supplier-only markings mean no local manufacturing recommendation in this pilot. Procurement remains possible for candidate accessories too. Civil structures/earthing/supports retain a separate engineered-contractor disposition.

Rebuild only the explorer with `python3 reference/substation-library/build_explorer.py` from the repository root. To regenerate all source catalogs and the database, run `build.py` then `expand_manufacturing_routes.py`; both refresh the viewer. The full generator expects the committed route catalog to exist.

## Deliverables

- `substation-concept.gltf`: self-contained 3D model; component IDs are stored in node extras. Open in a glTF viewer or import into Blender. Arbitrary schematic proportions; not manufacturing CAD.
- `components.sqlite`: starter database with components, equipment families and sources.
- `components.json` and `components.csv`: portable catalog exports.
- `scene.json`: catalog plus the schematic mesh geometry used by the viewer.
- `build.py` and `viewer-template.html`: reproducible source.
- `manufacturing-routes.json` and `manufacturing-routes.csv`: draft process/material options linked to component IDs. These are also stored in the additional manufacturing tables in `components.sqlite`.
- `expand_manufacturing_routes.py`: run after `build.py` to regenerate the manufacturing extensions. Six process families, seven material families and twenty-seven draft route options are included. The explorer displays these routes alongside supplier and engineered-contractor dispositions.

## Meaning of the classifications

TRIAL means a proposed lower-consequence printing experiment. QUALIFY means that part-specific engineering and qualification are a substantial prerequisite. EXCLUDE means excluded from this first replacement pilot, not a universal statement that additive manufacturing is impossible. Every part has service_release = NOT_APPROVED.

The shortlist is an author screening proposal, not an OEM-approved spare list. Sources support the equipment taxonomy and the need for AM qualification; they do not prove the printability of any individual record. Detailed acceptance criteria must be set by the asset owner and responsible engineering authority, with OEM involvement where applicable. UL material recognition and the DNV AM framework are useful inputs, not substitutes for applicable electrical-equipment requirements or installation approval.

## Geometry and completeness

The model breaks equipment into selected visible accessories and simplified functional assemblies. Internal windings, interrupters, terminals and electronics are simplified blocks or assemblies, not individual manufacturing parts. Small accessories are exaggerated for selection. Civil structures are illustrative. Conductors between bays, protection circuits, complete MV/DC systems, fencing and other detailed design elements are omitted. Do not infer a valid single-line diagram, safe electrical clearances, a complete station BOM, equipment quantities, fault duties, power ratings or constructability.

The glTF colors encode screening: green = TRIAL, orange = QUALIFY, gray = EXCLUDE. The updated HTML viewer uses the same component IDs but colors by manufacturing/procurement route; the glTF retains historical AM screening colors.

## Turning this into an operational library

Maintain separate component types, equipment variants, installed instances, CAD revisions, AM build recipes, test reports, supplier qualifications and service releases. Approval must refer to an exact part revision + material grade + machine/process + build orientation and parameters + post-processing + acceptance plan, rather than to a generic part name.

The starter intentionally leaves OEM, part number, dimensions, material grade, approved process settings, CAD URI, test evidence, approver, lead time and cost blank. The illustrative glTF is not linked as manufacturing CAD. Obtain rights to OEM drawings or reverse-engineer an authorized intact sample; a damaged sample alone may not establish original geometry or tolerances.

Suggested stage gates:

1. Select one real station and one equipment variant; reconcile the asset register, single-line diagram, drawings and maintenance history.
2. Have maintenance and engineering screen failure consequences and select a few low-consequence accessories. Record conventional spare cost and lead time as the comparison.
3. Capture controlled geometry and tolerances, select material/process, print and inspect samples. Use the same process and orientation intended for the part.
4. Run part-specific functional and environmental acceptance tests, including relevant flame, temperature, UV, chemical, fatigue, ingress and electrical checks. Release only the exact qualified variant through the owner's engineering procedure.
5. Compare total delivered lead time, qualification cost, installed cost and field performance before extending to more consequential parts.

Initial exclusion scope includes primary HV insulation, live contacts and conductors, interruption chambers, protection electronics, operating/interlocking mechanisms, earthing paths, structural supports and oil/pressure containment. This preserves a manageable pilot; industrial AM research on these functions is a separate engineering program.

## Sources

- Hitachi Energy AIS portfolio: https://www.hitachienergy.com/products-and-solutions/high-voltage-switchgear-and-breakers/air-insulated-switchgear
- UL Blue Card: https://www.ul.com/services/ul-blue-card-plastics-additive-manufacturing
- DNV-ST-B203: https://www.dnv.com/energy/standards-guidelines/dnv-st-b203-additive-manufacturing

Consulted 2026-09-19. No source certifies this model or its component assessments.

## Verification

With Playwright available to Node and Chrome installed, run `node scripts/check_substation_explorer.cjs` from the repo root. It checks route/family/search filters, overlapping routes, supplier-only exclusions, reset/empty state, JSON download content, mobile overflow and browser errors. Screenshots and the downloaded brief are saved in a temporary directory printed by the check.
