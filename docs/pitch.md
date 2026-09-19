# GridMend pitch: substation application, ring demonstration

**One sentence:** GridMend aims to help engineers turn damaged-part evidence into reviewed replacement CAD and candidate manufacturing routes, starting with accessories for legacy substations.

The customer problem is a hypothesis to validate: some legacy accessories lack usable CAD or timely spares. Do not claim all utilities need local fabrication or that OEM procurement is obsolete. Andrii adds a concrete maintenance example only if one is available and authorized to share.

## Five-minute script

| Time | Say / show | Evidence boundary |
| --- | --- | --- |
| **0:00–0:30** | Show the generic 110 kV substation model for a few seconds. “Legacy equipment has small parts that break, and often nobody has the CAD any more.” | Generic scene; availability problem is a hypothesis unless Andrii has a real example. |
| **0:30–0:50** | Hold up the half ring. “Only half of this part survives. You cannot measure the diameter of a half ring with a ruler.” | The ring is a lab proxy, not a substation part. |
| **0:50–2:30** | Photo with card → click card corners and surviving edges → fitted circles, missing arc in red. Ask by voice: “Thickness is … millimetres, there is a groove on the inside.” Show the proposal, then “Confirm”. | Real Nebius/SLNG calls; manual clicks are the designed input, say so. |
| **2:30–3:20** | Rotate the rebuilt ring: surviving part in yellow, **restored missing segment in red**. Download STEP/STL, show the passed checks. | No printer; fit is untested. Say it once. |
| **3:20–4:10** | Galtea: “We said ‘nine or nineteen, I haven't measured it’.” Show what the first version **really** did, the fix and the rerun. | Only the real result. If no failure was found, say so. |
| **4:10–5:00** | “Next: one real legacy accessory from a substation, and an inspected printed or machined specimen.” Show the route catalog for 10 seconds. | Catalog routes are draft proposals, not approved parts. |

Three-minute version: problem 0:00–0:20; half ring + photo/clicks/voice 0:20–1:30; rebuilt ring + downloads 1:30–2:10; Galtea fix 2:10–2:40; next step 2:40–3:00.

Say the limits (no printer, no fit test, draft routes) **once**, clearly. Do not repeat them on every slide.

## One roadmap visual

| Existing foundation | Today's build target | Next validation |
| --- | --- | --- |
| Generic 110 kV scene; 36 illustrative component records; 27 draft routes across 13 records. | Broken middle-ring photo + voice → checked CAD files. | One real legacy accessory → reviewed route → manufactured and inspected specimen. |

Use the existing [library](../reference/substation-library/README.md) and [route records](../reference/substation-library/manufacturing-routes.json). The complete [roadmap](roadmap.md) states stage gates and limitations. The ring build target becomes a demonstrated result only after a successful run is recorded.

## Answers to likely judge questions

| Question | Answer |
| --- | --- |
| “Why a ring if the product is about substations?” | It isolates geometry recovery in a simple physical example we can inspect. The substation catalog defines the intended application; industrial suitability is the next validation. |
| “Why AI rather than drawing it manually?” | “When half the part is gone, you cannot measure it directly. The app finds the full circle from the surviving arc and the card scale, and asks the engineer only for what the photo cannot show. Voice keeps the hands free for the caliper.” |
| “Does this mean you can print a transformer?” | No. The catalog separates candidate accessory routes from specialist/excluded functions. Each real part needs its own material, interface and engineering assessment. |
| “Why printing rather than CNC?” | The future route depends on actual material and functional requirements. The existing library records several options. This weekend exports ring CAD; it does not produce a validated process plan or toolpath. |
| “How much of a substation can be reproduced?” | We have no defensible percentage. The 36 records are an illustrative, mixed-granularity set, not a complete station BOM. |
| “Isn't the original model online?” | “For this toy, maybe. For a 30-year-old substation accessory, usually not. That is the real use case.” |
