"""Generate an illustrative multi-asset explorer, not manufacturing CAD."""
import copy
import json
import math
from pathlib import Path

OUT = Path(__file__).parent
BASE = OUT.parent / 'substation-library'
substation = json.loads((BASE / 'scene.json').read_text())
manufacturing = json.loads((BASE / 'manufacturing-routes.json').read_text())
assets = [
    dict(id='SUB', name='Substation', subtitle='110/10 kV · existing component library', focus='Start with legacy substation accessories. The existing 36-record library is retained.', scene=substation),
    dict(id='BESS', name='BESS', subtitle='Battery storage · proposed extension', focus='Screen external monitoring accessories and maintenance tooling. Battery, protection and thermal-management functions stay with qualified suppliers.'),
    dict(id='PCS', name='PCS', subtitle='Power conversion · proposed extension', focus='Screen ancillary cabinet accessories and workshop fixtures. Power electronics, insulation and cooling assemblies remain supplier items.'),
    dict(id='SOLAR', name='Solar farm', subtitle='PV + monitoring · proposed extension', focus='Screen monitoring-station accessories and assembly tooling. Module retention, connectors and tracker duties need specialist solutions.'),
    dict(id='WIND', name='Wind farm', subtitle='Turbine + auxiliaries · proposed extension', focus='Screen ground-level monitoring accessories and workshop tooling. No blade, drivetrain, braking, lifting or fall-protection substitution.'),
    dict(id='THERMAL', name='Thermal plant', subtitle='Plant auxiliaries · proposed extension', focus='Screen control-room and cool-area accessories plus workshop tooling. Pressure boundaries, hot sections and rotating machinery remain specialist work.'),
]
new_asset_ids = [a['id'] for a in assets[1:]]
shared = []
def part(pid, name, family, reason, checks, role='INSTALLED_ACCESSORY'):
    return dict(id=pid, name=name, family_id=family, rationale=reason, required_checks=checks,
                application_role=role, asset_applicability=new_asset_ids, service_release='NOT_APPROVED',
                evidence_level='AUTHOR_DRAFT_SCREENING', oem=None, part_number=None, dimensions_mm=None,
                material_grade=None, cad_uri=None, engineering_label_verified=False)

def add(pid, name, reason, checks, routes, role='INSTALLED_ACCESSORY'):
    p=part(pid,name,'TOOL' if role=='TOOLING_ONLY' else 'BOP',reason,checks,role);shared.append(p)
    for process,material in routes:
        manufacturing['route_options'].append(dict(id=pid+'-'+process,component_id=pid,process_id=process,
            material_family_id=material,screening_status='CANDIDATE_FOR_REVIEW',application_role=role,
            reason=reason,exact_material_grade=None,required_tolerance_mm=None,engineering_label_verified=False,
            service_release='NOT_APPROVED',evidence_level='AUTHOR_DRAFT_SCREENING',source_ids=[]))
    manufacturing['component_dispositions'].append(dict(component_id=pid,disposition='COMPARE_CANDIDATE_ROUTES',service_release='NOT_APPROVED',reason=reason))
poly=('AM_POLYMER','ENGINEERING_POLYMER');cncp=('CNC_MILL_TURN','ENGINEERING_POLYMER');cncm=('CNC_MILL_TURN','METAL_ALLOY');sheet=('SHEET_FABRICATION','METAL_ALLOY')
add('BOP01','Non-electrical label holder','Internal accessory identification only; mandatory safety markings require their own specified solution.','Fit, retention, legibility, temperature and flame behavior.',[poly,('CNC_ROUTING','ENGINEERING_POLYMER')])
add('BOP02','External monitoring-sensor bracket','For a non-protective monitoring sensor outside live, hot, pressure and hazardous-zone boundaries; not a support for safety instrumentation.','Known loads, vibration, corrosion, mounting interface and sensor performance.',[cncm,sheet])
add('BOP03','Low-load monitoring-cable guide','Cable guidance only; no fault restraint, protective insulation or structural duty.','Cable abrasion, bend radius, retention, UV, flame and temperature suitability.',[poly,cncp])
add('BOP04','Non-locking accessory drawer pull','A workshop or ancillary drawer pull, never an interlock or energized-compartment latch.','Pull loads/cycles, fit, temperature, flame and failure consequences.',[poly,cncp])
add('BOP05','Ancillary monitoring weather hood','An additional shield for non-safety monitoring equipment; not an enclosure seal, airflow component or protective barrier.','Wind loads, corrosion, drainage, attachment and unchanged ventilation/access.',[sheet])
add('BOP06','Inspection-camera mounting adapter','Mount for supplementary inspection imagery; not part of protection, fire detection or personnel safety.','Thread/interfaces, retention, vibration, temperature and camera orientation.',[cncm,cncp])
add('TOOL01','Workshop drilling template','Temporary jig used on an approved workpiece, away from energized equipment. Ordinary wood is only a workshop-tooling option.','Hole positions, repeatability, stock stability, clamp plan and removal after work.',[poly,('CNC_ROUTING','WORKSHOP_WOOD')],'TOOLING_ONLY')
add('TOOL02','Bench inspection cradle','Supports a small removed specimen for measurement on a bench; never a lifting or transport fixture.','Specimen mass, stability, contact protection and dimensional repeatability.',[poly,('CNC_ROUTING','WORKSHOP_WOOD')],'TOOLING_ONLY')
cores={
'BESS':[('Battery modules and racks','Electrochemical, insulation and structural functions.'),('Cooling and thermal management','Performance and failure response depend on the qualified system.'),('BMS, switching and fire protection','Electrical/protective functions require the approved system design.')],
'PCS':[('Power conversion modules','Semiconductors, DC link and electrical conversion assembly.'),('DC switching and protective insulation','Fault interruption, insulation and protective interfaces.'),('Cooling assembly','Power-stage cooling performance depends on the exact design.')],
'SOLAR':[('PV modules and connectors','Electrical insulation, current paths and environmental sealing.'),('Racking and tracker assemblies','Wind, structural, motion and module-retention duties.'),('Inverter and protection equipment','Power conversion and electrical protection functions.')],
'WIND':[('Rotor and blades','Aerodynamic, fatigue and structural functions.'),('Nacelle drivetrain and brakes','Rotating machinery, braking and control duties.'),('Tower and safety systems','Structural support, access and fall-protection functions.')],
'THERMAL':[('Turbine and generator','Rotating machinery, hot sections and electrical generation.'),('Boiler and pressure systems','Steam, temperature and pressure-containment duties.'),('Fuel valves and protective systems','Fuel containment, emergency isolation and protective functions.')],
}
meshes=[]
def box(pid,pos,size):
    x,y,z=pos;a,b,c=[n/2 for n in size]
    v=[[x+i*a,y+j*b,z+k*c] for i,j,k in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
    meshes.append(dict(part_id=pid,vertices=v,faces=[[0,3,2,1],[4,5,6,7],[0,1,5,4],[3,7,6,2],[0,4,7,3],[1,2,6,5]]))
def cylinder(pid,pos,r,h,n=12):
    x,y,z=pos;v=[[x+r*math.cos(i*2*math.pi/n),y+s*h/2,z+r*math.sin(i*2*math.pi/n)] for s in [-1,1] for i in range(n)]
    meshes.append(dict(part_id=pid,vertices=v,faces=[list(range(n)),list(reversed(range(n,2*n)))]+[[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)]))
for asset in assets[1:]:
    aid=asset['id'];meshes=[];core=[]
    for i,(name,why) in enumerate(cores[aid],1):
        p=part(f'{aid}{i:02}',name,'CORE',why,'Exact OEM/engineered variant, equipment-specific inspection and release.','SPECIALIST_ASSEMBLY');p['asset_applicability']=[aid];core.append(p)
        manufacturing['component_dispositions'].append(dict(component_id=p['id'],disposition='OEM_OR_SPECIALIST_REVIEW',service_release='NOT_APPROVED',reason='No local replacement route in this pilot. Obtain an OEM or engineered specialist solution.'))
    a,b,c=[p['id'] for p in core]
    if aid=='BESS':
        for x in [-6,3]:
            box(a,[x,3,-2],[7,6,5])
            for dx in [-2,0,2]:box(a,[x+dx,3,.6],[.12,5,.12])
            box(b,[x+3.8,3,-2],[1,4,3])
        box(c,[11,2,-2],[3,4,3])
    elif aid=='PCS':
        for x in [-6,0,6]:
            box(a,[x,3,-2],[4,6,4]);box(b,[x,3,.1],[2.8,4,.2])
            for y in [1,1.5,2]:box(c,[x,y,.3],[2.6,.2,.3])
    elif aid=='SOLAR':
        for x in [-8,-3,2,7]:
            for z in [-5,0]:
                box(a,[x,2,z],[4.5,.22,3.6]);box(b,[x,.9,z],[.3,1.8,.3])
        box(c,[13,2,-2],[2.5,4,3])
    elif aid=='WIND':
        for x in [-6,7]:
            cylinder(c,[x,5,-3],.4,10);box(b,[x,10,-3],[2,1.4,3])
            cylinder(a,[x,10,-1.4],.6,.6)
            for theta in [0,2*math.pi/3,4*math.pi/3]:
                verts=[[x,10,-1],[x+5*math.sin(theta),10+5*math.cos(theta),-1],[x+.7*math.sin(theta+.6),10+.7*math.cos(theta+.6),-1]]
                meshes.append(dict(part_id=a,vertices=verts,faces=[[0,1,2]]))
    else:
        box(a,[-5,2,-1],[8,4,4]);box(b,[5,4,-2],[6,8,5]);cylinder(b,[8,7,-5],.8,14);box(c,[-5,1,3],[7,1.8,1])
    # Accessories are deliberately enlarged and displayed separately, not mounted as a plant design.
    for i,p in enumerate(shared):
        x=-10+(i%4)*5;z=7+(i//4)*4
        if p['id']=='BOP02':
            box(p['id'],[x,.3,z],[2.6,.3,2]);box(p['id'],[x-1,1.2,z],[.3,2,2])
        elif p['id']=='BOP03':
            box(p['id'],[x,.3,z],[2,.3,1]);box(p['id'],[x-1,.8,z],[.3,1,1]);box(p['id'],[x+1,.8,z],[.3,1,1])
        elif p['id']=='BOP04':
            for dx in [-1,1]:box(p['id'],[x+dx,.6,z],[.4,1,.4])
            box(p['id'],[x,1.1,z],[2.4,.4,.4])
        else:box(p['id'],[x,.6,z],[2.6,.8,1.8])
    asset['scene']=dict(parts=core+copy.deepcopy(shared),meshes=meshes,families=[dict(id='CORE',name='Main equipment · supplier',center=[0,0,-3]),dict(id='BOP',name='Ancillary accessory examples',center=[0,0,7]),dict(id='TOOL',name='Workshop tooling only',center=[0,0,11])])
for p in substation['parts']:
    p['asset_applicability']=['SUB'];p['application_role']='INSTALLED_ACCESSORY' if any(o['component_id']==p['id'] for o in manufacturing['route_options']) else 'SPECIALIST_ASSEMBLY'
# One canonical record per component; repeated scene entries only reference its applicability.
unique={p['id']:p for asset in assets for p in asset['scene']['parts']}
for asset in assets:
    assert {m['part_id'] for m in asset['scene']['meshes']}=={p['id'] for p in asset['scene']['parts']}
assert len(unique)==59
assert all(p['service_release']=='NOT_APPROVED' for p in unique.values())
assert all(o['application_role']=='TOOLING_ONLY' for o in manufacturing['route_options'] if o['material_family_id']=='WORKSHOP_WOOD')
payload=dict(revision='0.1',status='ILLUSTRATIVE_ROADMAP_NOT_VERIFIED_PART_LIBRARY',assets=assets,unique_component_count=len(unique),manufacturing=manufacturing)
(OUT/'catalog.json').write_text(json.dumps(payload,indent=2))
html=(OUT/'viewer-template.html').read_text().replace('/*ASSET_DATA*/',json.dumps(payload,separators=(',',':')).replace('<','\\u003c'))
(OUT.parent/'energy-asset-explorer.html').write_text(html)
print(f'Built 6 asset views; {len(unique)} unique component types; {len(manufacturing["route_options"])} draft routes.')
