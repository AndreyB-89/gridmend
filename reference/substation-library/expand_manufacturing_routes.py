"""Add draft, multi-route manufacturing screening to the existing concept catalog.

Run after build.py. Does not train a model, generate CAM, or approve any route.
"""
import csv
import json
import sqlite3
from pathlib import Path

OUT = Path(__file__).parent
processes = [
    ('AM_POLYMER', 'Polymer additive manufacturing', 'Specify extrusion, powder bed or other exact process after requirements are known.'),
    ('AM_METAL', 'Metal additive manufacturing', 'Specialist process selection; heat treatment and finish machining may be required.'),
    ('CNC_MILL_TURN', 'CNC milling / turning', 'Separate exact milling and turning operations, stock, tooling, workholding and inspection in the process plan.'),
    ('CNC_ROUTING', 'CNC routing', 'Process suitability depends on the specific sheet/block material and required finish.'),
    ('SHEET_FABRICATION', 'Sheet cutting, bending and joining', 'Select cutting method and include forming, joints, surface treatment and assembly.'),
    ('SPECIALIST_PROCESS', 'Other specialist manufacturing', 'Specify casting, moulding, insulation manufacture or another process only with supporting engineering data.')
]
materials = [
    ('ENGINEERING_POLYMER', 'Engineering polymer', 'Exact grade, flame/thermal/chemical properties and applicable process evidence required.'),
    ('METAL_ALLOY', 'Metal alloy', 'Exact alloy, temper/heat treatment, finish, corrosion and electrical requirements required.'),
    ('ELECTRICAL_LAMINATE', 'Electrical insulation laminate', 'Exact grade, electrical duty, orientation and environmental properties required; no generic equivalence.'),
    ('TRANSFORMER_WOOD', 'Electrical-grade laminated densified wood', 'Specialist transformer material; exact grade and design approval required.'),
    ('TRANSFORMER_PRESSBOARD', 'Transformer-grade pressboard', 'Specialist insulation material; purity, moisture and processing requirements apply.'),
    ('WORKSHOP_WOOD', 'Ordinary workshop wood / wood-based board', 'For assessed tooling, templates or packaging in this pilot; not a generic installed electrical replacement.'),
    ('OTHER_SPECIFIED', 'Other specified material', 'Exact material and application evidence required before route selection.')
]
source_records = [
    {'id':'M1','title':'Roechling Lignostone Transformerwood','url':'https://www.roechling.com/industrial/electrical-industry/transformer/oil-filled-transformers/lignostone-transformerwood-for-transformers','scope':'Evidence that specialist densified wood and machined components exist for transformer applications; not approval of any catalog part.'},
    {'id':'M2','title':'Hitachi Energy transformer insulation pressboards','url':'https://www.hitachienergy.com/us/en/products-and-solutions/insulation-and-components/transformer-insulation-components/insulation-components-and-materials/pressboard','scope':'Specialist pressboard material/application evidence, not approval of ordinary wood as insulation.'},
    {'id':'M3','title':'Autodesk advanced manufacturing','url':'https://www.autodesk.com/solutions/advanced-manufacturing','scope':'Manufacturing process taxonomy and CAD/CAM capability context; does not validate part-route selections.'},
    {'id':'M4','title':'Autodesk manufacturing simulation','url':'https://help.autodesk.com/view/fusion360/ENU/?contextId=MFG-REF-SIMULATION','scope':'CAM simulation and verification context; not proof of manufacturing safety for an unverified machine setup.'}
]
options=[]
def add(pid,process,material,reason,status='CANDIDATE_FOR_REVIEW'):
    options.append(dict(id=f'{pid}-{process}',component_id=pid,process_id=process,material_family_id=material,screening_status=status,application_role='INSTALLED_REPLACEMENT',reason=reason,exact_material_grade=None,required_tolerance_mm=None,engineering_label_verified=False,service_release='NOT_APPROVED',evidence_level='AUTHOR_DRAFT_SCREENING',source_ids=['M3']))

for pid in ['TX04','CB04']:
    add(pid,'CNC_MILL_TURN','METAL_ALLOY','Screen engraving/cutting a specified metal identification plate; retain required marking durability.')
    add(pid,'AM_POLYMER','ENGINEERING_POLYMER','Alternative only if the exact material/process meets marking, weathering, temperature and retention requirements.')
for pid in ['TX05','SA02']:
    add(pid,'CNC_MILL_TURN','METAL_ALLOY','Screen machining an accessory bracket to verified dimensions and mechanical/environmental requirements.')
    add(pid,'SHEET_FABRICATION','METAL_ALLOY','Alternative if the actual bracket geometry and loads suit cut/bent sheet; verify joints, finish and bonding requirements.')
    add(pid,'AM_METAL','METAL_ALLOY','Specialist alternative if geometry or availability justifies qualification and post-processing.','SPECIALIST_REVIEW')
for pid in ['CB03','CTRL01']:
    add(pid,'SHEET_FABRICATION','METAL_ALLOY','Screen fabrication from specified sheet stock; validate enclosure interfaces, ingress, bonding, corrosion and applicable protection functions.')
for pid in ['IT03']:
    add(pid,'SHEET_FABRICATION','METAL_ALLOY','Metal variant only when consistent with the equipment design and verified gasket/bonding interfaces.')
    add(pid,'CNC_MILL_TURN','ENGINEERING_POLYMER','Polymer variant only with established design and material compatibility; not permission to substitute for metal.')
    add(pid,'AM_POLYMER','ENGINEERING_POLYMER','Print study conditional on appropriate material/process properties and enclosure acceptance tests.')
for pid in ['CTRL03','AUX03']:
    add(pid,'AM_POLYMER','ENGINEERING_POLYMER','Low-consequence internal label carrier; verify flame, temperature, fit and retention requirements.')
    add(pid,'CNC_ROUTING','ENGINEERING_POLYMER','Possible sheet/block fabrication route when the geometry and attachment suit the selected stock.')
for pid in ['CTRL04','CTRL05']:
    add(pid,'AM_POLYMER','ENGINEERING_POLYMER','Candidate for a controlled accessory trial under the catalog use restrictions.')
    add(pid,'CNC_MILL_TURN','ENGINEERING_POLYMER','Alternative machined-polymer route; preserve interfaces and assess grade, creep, heat and mechanical duty.')
add('CTRL06','SHEET_FABRICATION','METAL_ALLOY','For an established metal grille design; verify airflow, touch protection, ingress, edges and bonding.')
add('CTRL06','AM_POLYMER','ENGINEERING_POLYMER','For an established polymer frame variant; verify thermal rise, flame, impact and airflow.')
add('AUX02','AM_POLYMER','ENGINEERING_POLYMER','Specialist touch-protection part: electrical, chemical, flame and retention requirements must be established.','SPECIALIST_REVIEW')
add('AUX02','CNC_MILL_TURN','ENGINEERING_POLYMER','Machining is a candidate process only if the exact grade, geometry and function are validated.','SPECIALIST_REVIEW')

catalog=json.loads((OUT/'components.json').read_text())
dispositions=[]
for p in catalog['parts']:
    has=any(o['component_id']==p['id'] for o in options)
    d='COMPARE_CANDIDATE_ROUTES' if has else 'OEM_OR_SPECIALIST_REVIEW'
    if p['family_id']=='CIV' or p['id']=='BUS03':d='ENGINEERED_CONVENTIONAL_ROUTE'
    dispositions.append(dict(component_id=p['id'],disposition=d,service_release='NOT_APPROVED',reason='Draft candidates; no route selected until functional and manufacturing requirements are verified.' if has else 'No local manufacturing recommendation in the current pilot; obtain an engineered/OEM or specialist solution.'))

wood_examples=[
    dict(example='Workshop positioning fixture or drilling template',process_id='CNC_ROUTING',material_family_id='WORKSHOP_WOOD',application_role='TOOLING_ONLY',status='ILLUSTRATIVE_NOT_A_CATALOG_PART',note='Verify loads, repeatability and workshop conditions. Never identify this as an installed substation spare.'),
    dict(example='Transformer design using a machined densified-wood support',process_id='CNC_ROUTING',material_family_id='TRANSFORMER_WOOD',application_role='INSTALLED_REPLACEMENT',status='SPECIALIST_EXAMPLE_NOT_A_CATALOG_PART',note='Actual process, grade, orientation, geometry and transformer design approval remain to be specified.',source_ids=['M1']),
    dict(example='Transformer-grade pressboard insulation component',process_id='CNC_ROUTING',material_family_id='TRANSFORMER_PRESSBOARD',application_role='INSTALLED_REPLACEMENT',status='SPECIALIST_EXAMPLE_NOT_A_CATALOG_PART',note='Routing is an engineering screening hypothesis for suitable shapes; verify material processing, cleanliness, moisture and insulation design.',source_ids=['M2'])
]
payload=dict(revision='0.2',status='DRAFT_ENGINEERING_SCREENING_NOT_TRAINING_GROUND_TRUTH',processes=[dict(id=i,name=n,notes=s) for i,n,s in processes],material_families=[dict(id=i,name=n,notes=s) for i,n,s in materials],route_options=options,component_dispositions=dispositions,wood_examples=wood_examples,sources=source_records,selection_policy='Identify component, retrieve verified requirements, generate candidate routes, filter by engineering/process constraints, then compare qualified alternatives. Unknown evidence prevents release; no material grade inferred from an image alone.')
(OUT/'manufacturing-routes.json').write_text(json.dumps(payload,indent=2))
with (OUT/'manufacturing-routes.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=options[0]);w.writeheader();w.writerows(options)
with sqlite3.connect(OUT/'components.sqlite') as db:
    db.execute('PRAGMA foreign_keys=ON')
    for table in ['manufacturing_route_options','component_manufacturing_dispositions','manufacturing_processes','material_families','manufacturing_sources']:
        db.execute('DROP TABLE IF EXISTS '+table)
    db.execute('CREATE TABLE manufacturing_processes (id TEXT PRIMARY KEY,name TEXT NOT NULL,notes TEXT NOT NULL)')
    db.executemany('INSERT INTO manufacturing_processes VALUES (?,?,?)',processes)
    db.execute('CREATE TABLE material_families (id TEXT PRIMARY KEY,name TEXT NOT NULL,notes TEXT NOT NULL)')
    db.executemany('INSERT INTO material_families VALUES (?,?,?)',materials)
    db.execute('CREATE TABLE manufacturing_sources (id TEXT PRIMARY KEY,title TEXT,url TEXT,scope TEXT)')
    db.executemany('INSERT INTO manufacturing_sources VALUES (:id,:title,:url,:scope)',source_records)
    db.execute('CREATE TABLE component_manufacturing_dispositions (component_id TEXT PRIMARY KEY REFERENCES components(id),disposition TEXT,service_release TEXT,reason TEXT)')
    db.executemany('INSERT INTO component_manufacturing_dispositions VALUES (:component_id,:disposition,:service_release,:reason)',dispositions)
    db.execute('CREATE TABLE manufacturing_route_options (id TEXT PRIMARY KEY,component_id TEXT REFERENCES components(id),process_id TEXT REFERENCES manufacturing_processes(id),material_family_id TEXT REFERENCES material_families(id),screening_status TEXT,application_role TEXT,reason TEXT,exact_material_grade TEXT,required_tolerance_mm REAL,engineering_label_verified INTEGER CHECK(engineering_label_verified IN (0,1)),service_release TEXT,evidence_level TEXT,source_ids TEXT)')
    for o in options:
        db.execute('INSERT INTO manufacturing_route_options VALUES ('+','.join('?' for _ in o)+')',[json.dumps(v) if isinstance(v,list) else v for v in o.values()])
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    assert db.execute('SELECT COUNT(*) FROM component_manufacturing_dispositions').fetchone()[0]==36
    assert db.execute("SELECT COUNT(*) FROM manufacturing_route_options WHERE service_release != 'NOT_APPROVED' OR engineering_label_verified != 0").fetchone()[0]==0
    assert db.execute("SELECT COUNT(*) FROM manufacturing_route_options WHERE material_family_id='WORKSHOP_WOOD' AND application_role='INSTALLED_REPLACEMENT'").fetchone()[0]==0
print(json.dumps(dict(components_with_dispositions=len(dispositions),route_options=len(options),component_types_with_candidates=len({o['component_id'] for o in options}),processes=len(processes),material_families=len(materials),integrity='passed',all_routes_unapproved=True)))
