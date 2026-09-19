import json, math, sqlite3, csv, struct, base64
from pathlib import Path

OUT = Path(__file__).parent
sources = [
 {'id':'S1','title':'Hitachi Energy AIS portfolio','url':'https://www.hitachienergy.com/products-and-solutions/high-voltage-switchgear-and-breakers/air-insulated-switchgear','scope':'Equipment-family taxonomy only; does not validate this geometry or the AM assessments.'},
 {'id':'S2','title':'UL Blue Card: plastics for additive manufacturing','url':'https://www.ul.com/services/ul-blue-card-plastics-additive-manufacturing','scope':'Process-specific polymer properties; material recognition does not approve this replacement part.'},
 {'id':'S3','title':'DNV-ST-B203 Additive manufacturing','url':'https://www.dnv.com/energy/standards-guidelines/dnv-st-b203-additive-manufacturing','scope':'Qualification framework; not evidence that a catalog entry is qualified for a substation.'}
]
families = [('TX','Power transformer',[-12,0,10]),('CB','110 kV circuit breaker',[-13,0,-3]),('DS','Disconnector / earth switch',[-13,0,-11]),('IT','Current / voltage transformers',[1,0,-3]),('SA','Surge arresters',[1,0,10]),('BUS','Busbars and supports',[0,0,-18]),('CTRL','Protection / control cabinets',[15,0,8]),('MV','10 kV switchgear',[15,0,-2]),('AUX','DC and auxiliary supply',[15,0,-11]),('CIV','Civil / earthing / cables',[0,0,0])]
parts=[]
def part(id,family,name,status,reason,process,checks):
    parts.append(dict(id=id,family_id=family,name=name,am_screening=status,rationale=reason,proposed_process=process,required_checks=checks,service_release='NOT_APPROVED',evidence_level='CONCEPT_SCREENING',assessment_basis='Author engineering screening; not an OEM finding',source_ids=['S2','S3'],oem=None,part_number=None,revision=None,dimensions_mm=None,material_grade=None,approved_machine=None,approved_build_parameters=None,cad_uri=None,acceptance_report=None,approved_by=None,approval_date=None,spare_lead_days=None,estimated_print_cost=None))
P='TRIAL'; Q='QUALIFY'; X='EXCLUDE'
part('TX01','TX','Tank and oil containment',X,'Oil-tight structural containment; conventional/OEM replacement in this pilot.','None in pilot','OEM design and transformer validation')
part('TX02','TX','HV / LV bushings',X,'Primary insulation and electric-field control.','None in pilot','OEM dielectric, thermal and mechanical qualification')
part('TX03','TX','Radiator and cooling circuit',X,'Heat transfer and oil containment.','None in pilot','OEM thermal and leak qualification')
part('TX04','TX','External identification plate',P,'Non-structural plate; proposed trial only where marking remains permanent and readable.','Polymer extrusion or powder bed fusion; grade TBD','Dimensions, attachment, UV/weathering, temperature, marking permanence; compare engraved stock plate')
part('TX05','TX','External sensor mounting bracket',Q,'Only a non-load-bearing accessory outside electrical clearances and oil boundary.','Polymer or metal AM; grade TBD','Loads, vibration, UV, thermal exposure, corrosion, sensor function, clearances')
part('TX06','TX','Core and windings',X,'Electromagnetic, thermal and dielectric performance.','None in pilot','Full OEM transformer design and tests')
part('CB01','CB','Poles / interrupters',X,'Arc interruption, pressure containment and primary insulation.','None in pilot','OEM type and routine tests')
part('CB02','CB','Drive and trip linkage',X,'Operating timing and protective switching function.','None in pilot','OEM mechanical endurance and interruption tests')
part('CB03','CB','Mechanism cabinet shell',Q,'Enclosure integrity, bonding and ingress protection must be retained.','Industrial metal AM study; compare formed sheet metal','Ingress, bonding, corrosion, temperature, impact and fit')
part('CB04','CB','Cabinet identification plate',P,'External non-structural identification only.','Polymer AM; grade TBD','Weathering, heat, attachment, legibility; no substitute for mandatory safety marking')
part('DS01','DS','Blades and live contacts',X,'Current path and short-circuit duty.','None in pilot','OEM electrical and mechanical tests')
part('DS02','DS','Post insulators',X,'110 kV primary insulation and mechanical support.','None in pilot','Dielectric, tracking, creepage and mechanical qualification')
part('DS03','DS','Drive / earthing linkage',X,'Isolation and earthing safety function.','None in pilot','OEM interlock and mechanical tests')
part('IT01','IT','CT active assembly and housing',X,'Measurement accuracy, insulation and containment.','None in pilot','OEM accuracy and dielectric qualification')
part('IT02','IT','VT active assembly and housing',X,'Measurement accuracy and primary insulation.','None in pilot','OEM accuracy and dielectric qualification')
part('IT03','IT','Secondary terminal-box lid',Q,'Lid can affect ingress, touch protection and bonding.','Polymer or metal AM study','Ingress, flame, impact, clearances, gasket interface and bonding if metallic')
part('SA01','SA','Arrester stack and housing',X,'Surge-energy absorption and primary insulation.','None in pilot','OEM surge and dielectric qualification')
part('SA02','SA','Counter mounting bracket',Q,'External accessory only; keep earthing path and clearances intact.','Metal or polymer AM study','Mechanical loads, corrosion, weathering, electrical clearances')
part('BUS01','BUS','Bus conductors and clamps',X,'Continuous current, fault force and thermal duty.','None in pilot','OEM electrical and mechanical qualification')
part('BUS02','BUS','Bus support insulation',X,'Primary dielectric and mechanical support.','None in pilot','OEM dielectric, pollution and mechanical qualification')
part('BUS03','BUS','Steel support structures',X,'Load-bearing structural system; outside pilot.','None in pilot','Structural design and connections')
part('CTRL01','CTRL','Cabinet enclosure',Q,'Enclosure affects fire, ingress and electromagnetic protection.','Industrial AM study; compare sheet-metal fabrication','Ingress, bonding, electromagnetic compatibility, fire, impact and fit')
part('CTRL02','CTRL','Relay / IED and terminals',X,'Protection electronics and certified electrical interfaces.','None in pilot','OEM replacement')
part('CTRL03','CTRL','Label carrier',P,'Internal, non-electrical identification accessory.','Polymer extrusion or powder bed fusion; grade TBD','Fit, flame behavior, temperature, durable identification and retention')
part('CTRL04','CTRL','Low-load cable guide',P,'Cable routing only; not cable restraint under fault loads or protective insulation.','Polymer AM; grade TBD','Flame, temperature, bend radius, abrasion, retention, no loss of clearances')
part('CTRL05','CTRL','Non-locking drawer pull',P,'Use only on an accessory drawer; not an interlock or energized-compartment door.','Polymer powder bed fusion or extrusion; grade TBD','Fit, pull cycles, flame, temperature and failure consequences')
part('CTRL06','CTRL','Ventilation grille / filter frame',Q,'Airflow and access protection can affect cabinet performance.','Polymer AM study','Airflow, thermal rise, flame, ingress, impact and touch protection')
part('MV01','MV','MV cubicle and arc containment',X,'Arc and electrical containment.','None in pilot','OEM switchgear qualification')
part('MV02','MV','Breaker / bus / insulators',X,'Primary electrical and interruption functions.','None in pilot','OEM switchgear qualification')
part('MV03','MV','Mechanical interlocks',X,'Personnel protection and switching sequence.','None in pilot','OEM mechanical and safety validation')
part('AUX01','AUX','Battery cells and charger',X,'Electrochemical and electrical function.','None in pilot','OEM replacement')
part('AUX02','AUX','Battery terminal protection cap',Q,'Touch protection, fault and chemical exposure.','Polymer AM study','Dielectric, flame, chemical resistance, fit and retention')
part('AUX03','AUX','Auxiliary panel label holder',P,'Internal identification accessory with no electrical function.','Polymer AM; grade TBD','Flame, temperature, fit, legibility and retention')
part('CIV01','CIV','Foundations and bund',X,'Structural and spill containment functions.','None in pilot','Civil design and inspection')
part('CIV02','CIV','Earthing conductor and bonds',X,'Fault-current and touch-voltage safety.','None in pilot','Electrical design, continuity and fault duty')
part('CIV03','CIV','Cable trench cover',X,'Load-bearing and access protection.','None in pilot','Structural and fire assessment')

meshes=[]
def box(pid,pos,size):
    x,y,z=pos;a,b,c=[v/2 for v in size]
    vertices=[[x+i*a,y+j*b,z+k*c] for i,j,k in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
    meshes.append(dict(part_id=pid,vertices=vertices,faces=[[0,3,2,1],[4,5,6,7],[0,1,5,4],[3,7,6,2],[0,4,7,3],[1,2,6,5]]))
def cyl(pid,pos,r,h,n=12):
    x,y,z=pos;v=[[x+r*math.cos(i*2*math.pi/n), y+sign*h/2,z+r*math.sin(i*2*math.pi/n)] for sign in [-1,1] for i in range(n)]
    faces=[list(range(n)),list(reversed(range(n,2*n)))]+[[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)]
    meshes.append(dict(part_id=pid,vertices=v,faces=faces))
def ins(pid,x,y,z,h=3,r=.35):
    cyl(pid,[x,y,z],r*.65,h)
    for i in range(9):cyl(pid,[x,y-h/2+h*(i+.5)/9,z],r,.11)

box('TX01',[-12,2.6,10],[6,4,4]);box('TX06',[-12,2.7,10],[4,2.7,2.7])
for dx in [-1.8,0,1.8]:ins('TX02',-12+dx,5.7,9.3,2.5)
for dz in [-2.5,2.5]:
    for dx in [-2,-1,0,1,2]:box('TX03',[-12+dx,2.5,10+dz],[.32,3.4,1])
box('TX04',[-12,3,12.08],[1.3,.65,.15]);box('TX05',[-8.7,3,10],[.65,.2,.8])
for x in [-16,-13,-10]:
    ins('CB01',x,3.4,-3,4.3,.5);box('CB02',[x,.8,-3],[.8,1.2,.8])
box('CB03',[-13,1.5,-1.5],[1.7,1.7,.85]);box('CB04',[-13,1.7,-1.03],[.7,.35,.1])
for x in [-16,-13,-10]:
    for z in [-12,-10]:ins('DS02',x,2,z,2.8)
    box('DS01',[x,3.55,-11],[.16,.16,2.4]);box('DS03',[x,.5,-11],[.14,.15,3])
for x in [-2,1,4]:
    ins('IT01',x,2.7,-4,3.8,.5);cyl('IT01',[x,4.6,-4],.7,.65)
    ins('IT02',x,2.7,1,4,.45);box('IT03',[x,1,1.4],[.55,.5,.15])
    ins('SA01',x,2.7,10,4.3,.35);box('SA02',[x,.55,10.6],[.55,.15,.5])
for x in [-19,8]:
    box('BUS03',[x,3.2,-18],[.4,6.2,.4]);box('BUS03',[x,6.3,-18],[.5,.3,8])
    for z in [-21,-18,-15]:ins('BUS02',x,7,z,1.3)
for z in [-21,-18,-15]:box('BUS01',[-5.5,7.9,z],[27,.15,.15])
box('CTRL01',[15,2.4,8],[5,4,2]);box('CTRL02',[15,3,9.04],[3,1.3,.16]);box('CTRL03',[15,4.05,9.15],[1.4,.32,.15]);box('CTRL04',[17.65,2.2,8],[.4,.25,1.2]);box('CTRL05',[13.25,1.25,9.22],[.8,.18,.2]);box('CTRL06',[16.5,1.3,9.12],[1,.8,.2])
box('MV01',[15,2.4,-2],[6,4,3]);box('MV02',[15,2.5,-2],[4,2,1.6]);box('MV03',[15,2,-.42],[.6,.6,.16])
box('AUX01',[15,1.7,-11],[4,2.5,2.4]);box('AUX02',[13.8,3.05,-11],[.5,.3,.5]);box('AUX03',[15,2.1,-9.73],[1.2,.35,.12])
for x,z,w,d in [(-12,10,9,8),(-13,-3,10,4),(-13,-11,10,5),(1,-2,10,11),(1,10,10,5),(15,8,7,4),(15,-2,8,5),(15,-11,6,4)]:box('CIV01',[x,.12,z],[w,.24,d])
box('CIV02',[0,.2,0],[42,.12,.12]);box('CIV03',[6,.22,-3],[1.7,.25,31])
data=dict(title='110/10 kV substation: component screening demonstrator',revision='0.1',geometry_basis='Generic authored schematic; arbitrary proportions; not an as-built survey, electrical layout or manufacturing CAD. Major equipment and selected subcomponents only; connections and complete engineering bill of materials are not represented.',screening_basis='Proposed pilot scope, not a universal claim of printability. No replacement is approved for service.',families=[dict(id=i,name=n,center=c) for i,n,c in families],parts=parts,meshes=meshes,sources=sources)
(OUT/'components.json').write_text(json.dumps({k:v for k,v in data.items() if k!='meshes'},indent=2))
(OUT/'scene.json').write_text(json.dumps(data,separators=(',',':')))
with (OUT/'components.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=parts[0].keys());w.writeheader();w.writerows(parts)
db=sqlite3.connect(OUT/'components.sqlite');db.executescript('DROP TABLE IF EXISTS components; DROP TABLE IF EXISTS equipment_families; DROP TABLE IF EXISTS sources;')
db.execute('CREATE TABLE equipment_families (id TEXT PRIMARY KEY, name TEXT NOT NULL)');db.executemany('INSERT INTO equipment_families VALUES (?,?)',[(i,n) for i,n,c in families])
db.execute('CREATE TABLE sources (id TEXT PRIMARY KEY,title TEXT,url TEXT,scope TEXT)');db.executemany('INSERT INTO sources VALUES (:id,:title,:url,:scope)',sources)
columns=', '.join(k+' TEXT'+(' PRIMARY KEY' if k=='id' else '') for k in parts[0])
db.execute('CREATE TABLE components ('+columns+', FOREIGN KEY(family_id) REFERENCES equipment_families(id))')
for p in parts:db.execute('INSERT INTO components VALUES ('+','.join('?' for _ in p)+')',[json.dumps(v) if isinstance(v,list) else v for v in p.values()])
db.commit();assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';db.close()
# Standard glTF with component IDs on every mesh node; all geometry is schematic.
binary=bytearray();views=[];accessors=[];gmeshes=[];nodes=[]
colors={P:[.1,.7,.5,1],Q:[.95,.55,.12,1],X:[.45,.5,.58,1]};statuses=[P,Q,X]
def accessor(values,fmt,typ,count,target,mins=None,maxs=None):
    while len(binary)%4:binary.append(0)
    offset=len(binary);binary.extend(struct.pack('<'+fmt*len(values),*values));views.append(dict(buffer=0,byteOffset=offset,byteLength=len(binary)-offset,target=target))
    a=dict(bufferView=len(views)-1,componentType=5126 if fmt=='f' else 5123,count=count,type=typ)
    if mins is not None:a.update(min=mins,max=maxs)
    accessors.append(a);return len(accessors)-1
for m in meshes:
    v=m['vertices'];idx=[j for f in m['faces'] for i in range(1,len(f)-1) for j in [f[0],f[i],f[i+1]]]
    pa=accessor([x for p in v for x in p],'f','VEC3',len(v),34962,[min(p[i] for p in v) for i in range(3)],[max(p[i] for p in v) for i in range(3)])
    ia=accessor(idx,'H','SCALAR',len(idx),34963);p=next(p for p in parts if p['id']==m['part_id'])
    gmeshes.append(dict(primitives=[dict(attributes=dict(POSITION=pa),indices=ia,material=statuses.index(p['am_screening']))]));nodes.append(dict(name=p['id']+' '+p['name'],mesh=len(gmeshes)-1,extras=dict(component_id=p['id'],service_release='NOT_APPROVED',geometry='SCHEMATIC')))
gltf=dict(asset=dict(version='2.0',generator='Substation R&D concept; NOT manufacturing CAD'),scene=0,scenes=[dict(nodes=list(range(len(nodes))))],nodes=nodes,meshes=gmeshes,materials=[dict(name=s,doubleSided=True,pbrMetallicRoughness=dict(baseColorFactor=colors[s],metallicFactor=0,roughnessFactor=.85)) for s in statuses],buffers=[dict(byteLength=len(binary),uri='data:application/octet-stream;base64,'+base64.b64encode(binary).decode())],bufferViews=views,accessors=accessors,extras=dict(geometry_basis=data['geometry_basis']))
(OUT/'substation-concept.gltf').write_text(json.dumps(gltf,separators=(',',':')))
import runpy
runpy.run_path(str(OUT/'build_explorer.py'))
assert len({p['id'] for p in parts})==len(parts)
assert {m['part_id'] for m in meshes}=={p['id'] for p in parts}
print(json.dumps(dict(components=len(parts),families=len(families),meshes=len(meshes),screening={s:sum(p['am_screening']==s for p in parts) for s in statuses})))
