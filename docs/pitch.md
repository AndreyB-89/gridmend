# GridMend pitch: substation application, ring demonstration

**One sentence:** GridMend aims to help engineers turn damaged-part evidence into reviewed replacement CAD and candidate manufacturing routes, starting with accessories for legacy substations.

The customer problem is a hypothesis to validate: some legacy accessories lack usable CAD or timely spares. Do not claim all utilities need local fabrication or that OEM procurement is obsolete. Andrii adds a concrete maintenance example only if one is available and authorized to share.

## Five-minute script

| Time | Say / show | Evidence boundary |
| --- | --- | --- |
| **0:00–0:35** | Show the existing generic 110 kV substation model and point to an accessory category. “Our application is maintenance of legacy substation equipment, where a replacement accessory or its CAD may be difficult to obtain.” | Label the scene generic and the availability problem a hypothesis unless supported by a real example. |
| **0:35–0:55** | Hold up the broken middle ring. “This simple specimen lets us demonstrate one essential step: recovering missing geometry from photos and an engineer's answers.” | The ring is a lab proxy. It is not a substation-qualified part. |
| **0:55–2:40** | Run damaged image + card calibration. Say “The inside has a groove”; show the highlighted cross-section, make one explicit profile correction, preview it and say “Confirm”. Show surviving arcs and the restored segment. | Real Nebius/SLNG calls if working; mark replay/manual corrections openly. |
| **2:40–3:20** | Rotate the generated ring; show restored geometry and actual STEP/STL downloads. | Show independent export checks and any profile approximation. No printer is available; fit and motion are untested. |
| **3:20–4:00** | Show a genuine Galtea-discovered failure, the fix and rerun. | If no failure was discovered, report that rather than fabricating a story. |
| **4:00–4:40** | Return to the catalog: “We already have an illustrative component library and draft manufacturing routes. The next stage connects this reconstruction workflow to one verified industrial accessory.” Show polymer AM, CNC metal and sheet-fabrication candidates. | Library records are authored screening proposals, not approved replacements or implemented reconstruction coverage. |
| **4:40–5:00** | “Our next validation is one real accessory, a reviewed material/process choice and an independently inspected specimen.” Name the partner/evidence sought. | No invented customer commitment, savings, accuracy or deployment claim. |

Three-minute version: substation application 0:00–0:25; ring photo/voice 0:25–1:25; CAD/download 1:25–2:00; actual failure/fix 2:00–2:30; industrial roadmap and next validation 2:30–3:00.

## One roadmap visual

| Existing foundation | Today's build target | Next validation |
| --- | --- | --- |
| Generic 110 kV scene; 36 illustrative component records; 27 draft routes across 13 records. | Broken middle-ring photo + voice → checked CAD files. | One real legacy accessory → reviewed route → manufactured and inspected specimen. |

Use the existing [library](../reference/substation-library/README.md) and [route records](../reference/substation-library/manufacturing-routes.json). The complete [roadmap](roadmap.md) states stage gates and limitations. The ring build target becomes a demonstrated result only after a successful run is recorded.

## Answers to likely judge questions

| Question | Answer |
| --- | --- |
| “Why a ring if the product is about substations?” | It isolates geometry recovery in a simple physical example we can inspect. The substation catalog defines the intended application; industrial suitability is the next validation. |
| “Why AI rather than drawing it manually?” | Test whether photo interpretation and spoken clarification reduce the manual work to establish a model. This demo must show actual geometry extraction and correction; do not assert time savings without a comparison. |
| “Does this mean you can print a transformer?” | No. The catalog separates candidate accessory routes from specialist/excluded functions. Each real part needs its own material, interface and engineering assessment. |
| “Why printing rather than CNC?” | The future route depends on actual material and functional requirements. The existing library records several options. This weekend exports ring CAD; it does not produce a validated process plan or toolpath. |
| “How much of a substation can be reproduced?” | We have no defensible percentage. The 36 records are an illustrative, mixed-granularity set, not a complete station BOM. |
