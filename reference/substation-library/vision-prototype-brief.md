# Camera-to-CAD-to-manufacture substation replacement prototype

Status: R&D demonstrator scope, updated 2026-09-19. Manufacturing scope now includes CNC and sheet fabrication; see `manufacturing-routing.md` for the process/material decision model. The camera/vision workflow below is proposed and has not been implemented. The existing interactive 3D concept and component database are implemented.

## Confirmed use case

Develop a prototype machine-vision app using phone-camera images to identify damage to substation components, determine candidate manufacturing routes, and generate a dimensioned 3D model of the specific replacement component for printing, machining or another qualified fabrication route. CAD generation and a physically manufactured replacement are central outcomes of the R&D demonstrator. Use an interactive 3D substation and a component database to explain and explore results.

The product question is: “What component is damaged, can its intended undamaged geometry be established to the required tolerance, and can we generate and manufacture a suitable replacement?” The output must reproduce nominal functional geometry and mating interfaces; damage such as melting or distortion must not be copied into the replacement. Exactness is assessed against specified dimensions and tolerances, never inferred from visual similarity.

## Proposed demonstrator journey

1. Capture or upload an equipment overview, component close-up, and nameplate or part marking when available. Store image provenance as REAL, SYNTHETIC or STAGED. Capture only under the site's access procedure; the app does not determine that equipment is safe to approach.
2. Check image quality and return a request for another view when blur, occlusion, scale or missing context prevents useful recognition.
3. Propose an equipment family and component matches using image regions, visible markings and catalog retrieval. Return alternatives and UNKNOWN where appropriate. Require user confirmation of the match in this first prototype. Do not describe model-generated confidence numbers as calibrated probabilities without evaluation.
4. Record visible observations such as soot/discoloration, apparent melting, visible cracking, deformation, a broken attachment, or a suspected missing part. Keep incident cause supplied by the user separate from observations made from imagery. Do not infer exposure temperature, hidden condition or remaining electrical/mechanical performance from appearance.
5. Retrieve the matched component's manufacturing-route screening, exact-variant evidence, CAD availability and release state from the database. A deterministic rule layer produces the candidate process/material combinations; the vision model does not author approval records.
6. Highlight the component in the existing 3D model. Show the image region beside the intact reference, the proposed identity, evidence, uncertainty, required checks and next action. These are linked selections, not spatially registered augmented reality in the first version.
7. Guide the user through additional views, a scale reference and critical measurements needed for reconstruction. Record which surfaces and interfaces are observed, referenced, inferred or unknown.
8. Generate nominal replacement CAD using a verified exact-part model, a dimension-constrained family template, or scan-based parametric reconstruction. Show the recovered geometry alongside observations and highlight inferred or unsupported features. Missing critical geometry yields a request for evidence, not a fabricated exact model.
9. Check dimensions, mating interfaces, geometric validity and manufacturing constraints for the selected process. Export editable CAD (STEP plus native parametric source where available), a dimensioned inspection specification and a print mesh (prefer 3MF; optional STL with explicit units). Retain source-to-feature provenance and revision identifiers.
10. Prepare the selected route: printer/material/slicer setup for AM; stock, tooling, workholding, CAM simulation and compatible machine postprocessor for CNC; flat patterns and forming/joining details for sheet fabrication. Generate a machine-specific job only once its setup is established. Inspect the manufactured specimen and perform a fit/function trial against an intact reference or fixture; keep this separate from operational release.
11. Export an assessment and manufacturing package with the photos, confirmed identity, damage observations, dimensional evidence, CAD and build revisions, qualification state and inspection results.

## Keep five decisions separate

| Decision | Evidence | Proposed output |
| --- | --- | --- |
| What is visible? | Image region and image quality | Equipment family, component hypothesis or unknown |
| What appears affected? | Observed features across supplied views | Visible damage observations; extent unknown where obscured |
| Can nominal geometry be reconstructed? | Calibrated capture, dimensions, interfaces and verified references | Dimensioned CAD with feature provenance, unresolved geometry or evidence request |
| How could a replacement be manufactured? | Catalog screening, exact variant, functional requirements and process constraints | Candidate process/material combinations, specialist route, excluded from local pilot, or insufficient information |
| Is this replacement released for use? | Part revision, qualified build process, acceptance evidence and authorized release | Release record or not approved |

The current catalog has 36 generic component types: 6 TRIAL, 7 QUALIFY and 23 EXCLUDE. All are NOT_APPROVED. Generic type recognition cannot establish an OEM part number or manufacturing geometry. No existing record can produce an “approved replacement” result.

## Proposed first demonstration scope

Use the current 110/10 kV schematic as the navigation context. Begin recognition experiments with the six lower-consequence catalog candidate types and a deliberately challenging negative set: bushings/insulators, live contacts, interlocks, unrelated objects and unknown equipment. Treat visually similar label carriers and plates as potential ambiguities requiring equipment context or markings. Expand recognition coverage after measuring results; database breadth is not evidence of recognition capability.

Demonstrate four paths:

- A known accessory with visible breakage: identify, confirm, retrieve trial status, generate dimensioned replacement CAD, print a bench specimen and verify its fit.
- A fire-affected component with obscured markings: show plausible matches and request evidence; do not invent an exact part identity.
- A missing component: use a verified equipment BOM or intact reference and user confirmation to identify a possible missing part; an empty region alone is insufficient.
- An excluded component such as an HV bushing: recognize it and show the catalog's exclusion even if the geometry could be represented by a printable mesh.

When geometry is destroyed, obtain nominal geometry from an authorized OEM drawing, controlled CAD or a measured intact equivalent. The present schematic model is for visualization and must never be passed to a printer as a functional replacement file.

## Reconstruction strategy

| Evidence available | Proposed generation route | Required validation |
| --- | --- | --- |
| Exact part/revision has verified CAD | Instantiate and export the exact model; preserve its nominal geometry | Variant identity, revision, mating interfaces and applicable manufacturing route |
| Recognized family with a controlled parametric template | Fit dimensions from capture and confirmed measurements, then generate a specific CAD instance | All functional parameters, template validity for this variant, independent critical measurements |
| No model, sufficient surviving geometry or an intact equivalent | Reconstruct a scaled scan, then rebuild dimensioned surfaces/features in CAD | Coverage, scan uncertainty, nominal geometry recovery and interface tolerances |
| Destroyed, hidden or missing critical features without a reliable reference | Generate an explicitly incomplete engineering draft if useful; request a drawing, intact equivalent or additional measurements | No functional manufacturing release until critical unknowns are resolved |

A generative model may propose symmetry, likely shapes or candidate CAD operations. Such proposals remain hypotheses until supported; it must not silently invent bolt spacing, wall thickness, thread geometry or hidden interfaces. A phone capture is the input modality, not a guarantee that every component or tolerance is recoverable. Provide a metrology/scanner escalation path when the required tolerance cannot be demonstrated using the available capture and measurements.

First end-to-end experiment: use one simple accessory family, such as a non-locking drawer pull. Establish dimensions from an intact sample, capture a staged damaged sample, generate its replacement CAD using a constrained template, print it, and measure/fit it against the original attachment fixture. Agree acceptance tolerances before testing. Clearly label staged damage and measure reconstruction and printed-part error separately. This tests a bounded camera-to-print capability; it does not establish arbitrary-part reconstruction.

## Data additions

Preserve the existing component-type catalog. Add linked records for:

- Equipment variants and installed assets: manufacturer, model, serial/asset identifiers, BOM and component type/variant relationship.
- Component variants and CAD revisions: part number, revision, nominal dimensions/tolerances, interfaces, material and drawing rights/provenance.
- Reconstruction jobs: calibrated/scaled inputs, reference/template revisions, nominal dimensions, uncertainty, per-feature provenance, inferred/unknown geometry, generated CAD, independent dimensional checks and reviewer decisions.
- Build jobs and printed specimens: CAD revision/hash, mesh units and tessellation settings, printer/material/process, slicer/build settings, output job, specimen identifier, measured dimensions and fit/function result.
- Reference images: component/variant ID, viewpoint, annotation, condition, provenance and permitted use.
- Inspection sessions and images: session/asset ID, original file hash, capture metadata, user-reported incident cause and provenance; no real photographs are present yet.
- Observations: image ID, bounding box or mask, proposed identities, score semantics, visible damage tags, unknowns and confirmed identity.
- Screening decisions: matched record and catalog revision, rule version, eligibility result, evidence and unresolved requirements.
- AM qualification and service release: exact CAD revision, material, machine/process, parameters, orientation, post-processing, test evidence and approving authority.

One image may contain several components; one component may have several image observations. Preserve raw predictions and user corrections separately. Absence from the catalog or missing qualification data yields UNKNOWN / NOT_APPROVED, never eligibility by default.

## Prototype architecture

Phone capture/upload → image-quality checks → component/damage recognition → confirmed identity and manufacturing-route screening → guided dimensional capture → nominal CAD reconstruction → geometry/interface validation → process-specific CAD/CAM preparation → physical manufacture → dimensional and fit/function verification. Link each stage to the component database and 3D explorer.

Keep the vision adapter replaceable. Select a hosted or local model after reviewing the image-handling requirements and the first labeled dataset. Sending real station images to an external provider is not part of this brief's implementation. A scripted demonstration must label predictions as simulated; a working vision integration must record actual model output and version.

## Evidence needed to evaluate the R&D hypothesis

Assemble authorized real photographs of intact and affected components, with maintenance/engineering labels. Synthetic renders and staged damage may support interface development and training experiments, but report them separately from real damage results. The existing coarse 3D model is insufficient evidence of recognition performance.

Evaluate recognition at equipment-family, component-type and exact-variant levels separately. Include soot, poor lighting, occlusion, different phone cameras, look-alike parts, missing components and out-of-catalog items. Split evaluation by physical asset and capture session so adjacent frames of the same object do not leak between training and testing; report any stronger generalization claim against separately held-out variants or sites.

Measure confirmed-match precision/recall, unknown-case handling, dangerous false eligibility, damage-observation agreement with experts, human correction rate, elapsed assessment time and traceability completeness. Choose numerical performance targets after the dataset and failure costs are agreed. An illustrative UI is not a successful recognition trial.

Also measure critical-dimension errors against independent references, geometric coverage, unsupported-feature rate, valid-solid/mesh export rate, printed-part dimensional error, physical fit/function, and total capture-to-verified-print time. Include different variants within the chosen family; do not count downloading a pre-existing mesh as evidence that unseen geometry was reconstructed. Report catalog retrieval, template fitting and scan-based reconstruction results separately.

## Current implementation boundary

Implemented: schematic 3D explorer, component selection, separation controls, 36-record SQLite/CSV/JSON catalog, proposed AM categories and source links.

The process/material taxonomy and draft multi-route database extension are now implemented; the viewer still shows AM-only screening.

Not implemented: phone capture, image upload workflow, trained or integrated vision model, annotated real-image dataset, automatic damage assessment, exact OEM variant matching, calibrated capture, CAD reconstruction/generation, manufacturing mesh export, slicer/printer integration, CNC CAM and machine integration, physical manufacturing, fit validation, spatial AR alignment, qualified build recipes or engineering releases.

## Technical basis

- UL Blue Card guidance explains that traditionally manufactured polymer ratings cannot simply be transferred to printed parts and records process-specific material information: https://www.ul.com/services/ul-blue-card-plastics-additive-manufacturing
- DNV-ST-B203 describes a framework for AM process and part qualification, production, testing and inspection: https://www.dnv.com/energy/standards-guidelines/dnv-st-b203-additive-manufacturing
- Autodesk describes rebuilding CAD from scan reference geometry using sketches, dimensions and parametric features: https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Reverse-engineering-of-3D-scan-into-CAD-model-using-Inventor.html
- The 3MF core specification defines manufacturing-model exchange including explicit model units; a model file alone is not a printer-specific machine job: https://github.com/3MFConsortium/spec_core/blob/master/3MF%20Core%20Specification.md

These sources support qualification boundaries. They do not validate this app, the component shortlist or any recognition/damage accuracy claim. The workflow, data design and evaluation plan above are proposed design choices.
