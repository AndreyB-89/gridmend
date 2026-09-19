# Manufacturing route selection — R&D catalog v0.2

The app's scope is now camera-assisted identification and damage assessment, nominal replacement CAD generation, and selection/preparation of an appropriate manufacturing route. Printing, machining and sheet fabrication are candidate routes. Producing a spare can require several sequential processes. Some cases should resolve to OEM procurement, specialist engineering or insufficient evidence.

## Classification model

Keep these attributes separate rather than making a single mutually exclusive “3D print / metal CNC / wood CNC” label:

1. Component identity and exact equipment variant.
2. Functional role and consequence of failure.
3. Material family, followed by a verified exact grade/condition.
4. Candidate process or sequence of processes.
5. Application role: installed replacement, tooling only, or demonstration specimen.
6. Geometric evidence, tolerances, interfaces and reconstruction status.
7. Route feasibility and qualification/release status.

The same component may have several candidate routes. A similar shape may need entirely different materials or release requirements in different equipment. A manufacturing process does not establish the acceptability of a material substitution.

## Proposed route families

| Process family | Illustrative candidates to screen | Manufacturing deliverables |
| --- | --- | --- |
| Polymer additive manufacturing | Label carriers, selected cable guides, non-locking accessory pulls | Nominal CAD, 3MF, material/process specification and printer-specific build preparation |
| Metal additive manufacturing | Specialist accessory geometries where justified by shape or supply constraints | CAD, build preparation, post-processing and inspection plan; machining may follow printing |
| CNC milling / turning | Specified metal brackets, machined polymer accessories; other parts only after engineering screening | STEP/native CAD, dimensions/tolerances, stock/material condition, CAM setup and machine-specific program |
| CNC routing | Suitable polymer/laminate sheet parts; workshop wood fixtures; specialist transformer materials under separate qualification | CAD/DXF as appropriate, material/orientation, routing/tooling setup and inspection specification |
| Sheet cutting, bending and joining | Cabinet shells, certain covers, grilles and brackets | Sheet-metal CAD, flat pattern/DXF, bend and joining information, finishing and assembly requirements |
| Other specialist processes | Applications needing casting, moulding or specialist insulation manufacture | Process-specific engineering package; no automatic local production recommendation |

These are draft examples, not approved process/material specifications. Laser cutting, waterjet, routing, milling and turning can all involve CNC control; distinguish their physical operations instead of treating CNC as one manufacturing method.

## Wood and wood-derived materials

Separate ordinary workshop wood/wood-based board from electrical-grade laminated densified wood and transformer-grade pressboard.

- Ordinary workshop wood: proposed for assessed jigs, patterns, templates or packaging. The current pilot assigns it no installed electrical replacement route.
- Laminated densified transformer wood: a real specialist material family; Roechling lists electrical grades and machined components. Its suitability depends on the exact grade, orientation, design and application.
- Transformer-grade pressboard: a separate specialist insulation material. Hitachi Energy describes its purity, strength and oil-impregnation characteristics. It is not interchangeable with generic board, plywood or MDF.

The routing examples for specialist wood and pressboard are examples for future catalog expansion, not records of identified parts in the current 36-component schematic. Some transformer parts are inaccessible to an external phone capture; their identity and nominal geometry may require equipment records or inspection during an authorized disassembly.

## ML and engineering responsibilities

Use vision to propose component identity, visible damage, readable markings and geometric features. Use retrieval and an engineering constraint layer to propose manufacturing routes. Do not train a single image classifier to declare an exact alloy, polymer grade, wood grade or release status from appearance.

First filter candidate routes by verified requirements: electrical role, mechanical duty, temperature, fire behavior, chemical/oil exposure, weathering, interfaces, tolerances, finish, material condition and applicable qualification. Unknown requirements yield an evidence request. Then compare feasible routes on total delivered lead time, cost, available machines/stock, quantity, post-processing and inspection. Do not invent costs or availability for the demonstration.

Allow multi-label process alternatives and ordered operation chains. A metal print followed by heat treatment and CNC finish machining is one route sequence. A cut/bent/welded enclosure is another. Preserve the original observed shape and the nominal functional CAD separately from process-specific stock, supports and compensation.

Current route labels are AUTHOR_DRAFT_SCREENING with engineering_label_verified = false. They are design hypotheses and must not be treated as verified supervised-learning labels. Training/evaluation labels require engineering review and provenance. Independently evaluate recognition, route feasibility, reconstruction accuracy and manufactured-part fit.

## CAM and output preparation

CNC output requires a selected machine/controller, stock, cutters, workholding, coordinate system, toolpaths and compatible postprocessor. Validate reachability, collisions, remaining stock and setup assumptions before a manufacturing release. A generic STEP file is a design exchange file, not a complete machine program. For printing, use the corresponding printer/material/build setup. A prototype bench specimen and an installed spare have distinct release states.

## Catalog v0.2 / explorer v0.3

- Six manufacturing process families and seven material families.
- Twenty-seven draft component-route options across thirteen component types.
- A manufacturing disposition for each of the thirty-six existing component types.
- Separate SQLite tables linked to component IDs, plus JSON/CSV route exports.
- Three wood/material examples, explicitly separate from installed component records.

All routes remain NOT_APPROVED. No vision model, CAD generator, CAM engine or machine connection was added. The standalone explorer now loads this catalog: route filters, component badges, material/process details, supplier/contractor dispositions and downloadable JSON briefs. The glTF export retains its historical AM screening colors. Substation manufacturing CAD generation remains roadmap work.

To regenerate the catalog, run `build.py` followed by `expand_manufacturing_routes.py`. The v0.1 ZIP remains the historical original snapshot.

## Sources and boundaries

- Roechling Lignostone Transformerwood: https://www.roechling.com/industrial/electrical-industry/transformer/oil-filled-transformers/lignostone-transformerwood-for-transformers
- Hitachi Energy transformer insulation pressboards: https://www.hitachienergy.com/us/en/products-and-solutions/insulation-and-components/transformer-insulation-components/insulation-components-and-materials/pressboard
- Autodesk manufacturing process context: https://www.autodesk.com/solutions/advanced-manufacturing
- Autodesk CAM simulation: https://help.autodesk.com/view/fusion360/ENU/?contextId=MFG-REF-SIMULATION

These sources support the process/material distinctions. Part-route assignments and the proposed app design are author screening hypotheses, not vendor endorsements or qualification evidence.
