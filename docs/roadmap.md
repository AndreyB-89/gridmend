# GridMend product roadmap

**Product direction:** help engineers identify damaged substation accessories, recover missing geometry and assess feasible replacement-manufacturing routes when usable CAD or timely spares are unavailable.

**The ring demonstrates the reconstruction step on a simple physical example.** The 110 kV substation library provides the intended application context and an initial structure for component and manufacturing knowledge. Both belong in the product story.

## What exists and what remains to prove

| Layer | Current evidence | Role |
| --- | --- | --- |
| Generic 110/10 kV substation model | Authored glTF geometry and scene data for 10 equipment families. | Explain where candidate components belong; future navigation/selection interface. Not an as-built survey or electrically validated station design. |
| Component library | 36 illustrative component-type records, mixing accessories and assemblies. | Starting taxonomy for typical equipment categories; not an exhaustive bill of materials or verified standard/OEM spare inventory. |
| Manufacturing screening | 27 draft process/material options across 13 component records, within 6 process families. All remain NOT_APPROVED. | Compare candidate 3D-printing, CNC, sheet-fabrication and specialist routes. Not manufacturing eligibility or training ground truth. |
| Ring reconstruction | Current hackathon build target: damaged middle ring + card scale + voice → checked STEP/STL. | Demonstrate geometric recovery and engineer interaction in a controlled example. Update implemented status only after actual evidence exists. |
| Industrial replacement | No qualified industrial part, physical fit result or validated lead-time improvement established here. | Next work must establish part identity, material, interfaces, process requirements and real operational value. |

Inventory source: [component records](../reference/substation-library/components.json), [manufacturing options](../reference/substation-library/manufacturing-routes.json), [library scope and limitations](../reference/substation-library/README.md).

**Do not convert 13/36 into a claim about the percentage of a typical substation that can be reproduced.** This is a deliberately selected, mixed-granularity demonstration catalog.

## Candidate categories to show

These examples summarize authored screening options already in the repository. They are candidates for review, not recommendations to fabricate or install parts.

| Example category | Draft route in the library | Evidence needed before an industrial pilot |
| --- | --- | --- |
| Label carriers and auxiliary label holders | Polymer AM or CNC routing | Actual material specification, marking durability, attachment and location requirements. |
| Low-load cable guides and non-locking accessory drawer pulls | Polymer AM or CNC machining | Exact use, interfaces, loads, material/environmental requirements and failure consequences. |
| External sensor/counter mounting brackets | CNC metal, sheet fabrication; specialist metal AM also listed | Design loads, dimensions, corrosion/bonding requirements and manufacturing inspection. |
| Cabinet shells and selected covers | Sheet fabrication; some cover records include polymer alternatives | Actual material, enclosure function, ingress/fire/electrical requirements and interfaces. |
| Workshop fixtures or drilling templates | CNC wood as a separate tooling example | Tooling use, dimensions and repeatability. Not an installed substation spare. |

Transformer-grade wood/pressboard examples remain specialist material cases. Ordinary workshop wood is not their substitute. Primary insulation, switching contacts and protection functions are not brought into the hackathon reproduction scope.

## Intended product journey

```text
Substation model / asset register
  → equipment and exact component identity
  → damage photos + engineer voice + available reference evidence
  → missing geometry recovery and explicit uncertainty
  → candidate manufacturing routes filtered by material, function and process requirements
  → engineer-reviewed CAD and inspection package
  → manufacture, inspect, test and asset-owner release
```

This is the target journey. The hackathon exercises the photo/voice-to-CAD segment with the ring. The current ring application does not yet recognize or reconstruct all library records, qualify materials, generate CNC toolpaths or authorize installation.

## Stages and gates

No post-hackathon dates or staffing commitments are assumed. Each stage starts when evidence and a responsible owner are available.

| Stage | Work | Gate / evidence to advance | Accountable owner |
| --- | --- | --- | --- |
| **0 — Existing foundation** | Retain the schematic and candidate component/process library. | Source/provenance disclosed; draft labels retained; no implied OEM approval. | Andrii |
| **1 — Hackathon ring demonstration** | Deliver the frozen ring workflow and three sponsor integrations. Use the existing substation scene/catalog as pitch material. | Real damaged input produces checked CAD; five cases exercised; actual sponsor evidence; no physical-fit claim. | Valentin + Mortaza; Andrii accepts |
| **2 — First industrial accessory** | Find one authorized legacy accessory with a concrete spare/CAD availability problem; obtain intact/reference evidence and select its shape family. Reconcile its catalog identity. | Engineer confirms requirements and suitability for a bounded pilot; baseline lead time and present workflow recorded. A ring result alone cannot pass this gate. | Andrii with maintenance/engineering counterpart |
| **3 — Manufactured and inspected specimen** | Select a process/material against actual requirements; manufacture and independently inspect the specimen. | Dimensional, fit and applicable functional results; discrepancies and total effort recorded. Engineering approval is separate from CAD export checks. | Named engineering/manufacturing partner, to be confirmed |
| **4 — Controlled substation workflow** | Link selected catalog records to verified templates, instances and inspection evidence; integrate asset identity and reviewed route selection. | Asset-owner acceptance, traceable approved revisions where required, and measured benefit versus the existing spare workflow. | Andrii + asset owner + implementation team, to be confirmed |

Metrics to collect later: time to reviewed CAD, measurement error against independent metrology, number of engineer corrections, manufacturing/inspection effort, and total replacement lead time. Do not advertise savings before measuring the baseline and outcome.

## This weekend's scope rule

The roadmap restores the industrial context; it adds no new reconstruction template, app screen, provider or manufacturing route to the ring implementation. Andrii prepares one existing-model/catalog visual and uses the [pitch script](pitch.md). An already-working schematic can be shown; otherwise use a clearly labeled existing-asset image or catalog excerpt. Do not spend integration time rebuilding the substation viewer.
