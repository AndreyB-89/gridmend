"""Required primitive parameters and independently supplied metric provenance."""
from api.schemas import ReferenceSpec, SuppliedMeasurement

FEATURES = ['outer_diameter', 'inner_diameter', 'diameter', 'height', 'length', 'width', 'wall_thickness', 'cavity_depth', 'groove_depth', 'groove_width']
FRAME = {'origin': 'centre of bottom face', 'x': 'box length direction; ring radial zero',
         'y': 'box width direction', 'z': 'axial height, positive up', 'handedness': 'right', 'units': 'mm'}


def empty_spec():
    return ReferenceSpec(dimensions={k: SuppliedMeasurement() for k in FEATURES})


def required(spec):
    if spec.family == 'ring':
        fields = ['outer_diameter', 'inner_diameter', 'height']
    elif spec.family == 'cylinder':
        fields = ['diameter', 'height'] + (['inner_diameter'] if spec.cavity in ('through', 'blind') else [])
    elif spec.family == 'box':
        fields = ['length', 'width', 'height'] + (['wall_thickness'] if spec.cavity in ('through', 'blind') else [])
    else:
        return []
    if spec.cavity == 'blind':
        fields += ['cavity_depth']
    if spec.profile == 'inner_groove':
        fields += ['groove_depth', 'groove_width']
    return fields


def values(spec):
    return {k: v.value_mm for k, v in spec.dimensions.items() if v.value_mm is not None}


def questions(spec):
    q = []
    if spec.family is None:
        q.append('Is the intended intact object a ring, a cylinder, or a box?')
        return q
    if spec.cavity is None:
        q.append('Is the intact object solid, hollow all the way through, or a cavity closed at the bottom (blind/open top)?')
    if spec.family == 'ring' and spec.cavity != 'through':
        q.append('A ring retains its central through-hole. Please confirm that shape, or choose a cylinder.')
    if spec.profile is None:
        q.append('Is the reference profile plain, with no grooves or extra features? For a ring inner groove, give its radial depth and axial width.')
    for k in required(spec):
        if k not in spec.dimensions or spec.dimensions[k].value_mm is None:
            q.append(f'What is the intended intact object\'s {k.replace("_", " ")}? Supply your measured value and unit.')
    d = values(spec)
    outer = d.get('outer_diameter', d.get('diameter'))
    if outer and d.get('inner_diameter') and outer <= d['inner_diameter']:
        q.append('Inner diameter must be smaller than outer diameter. Correct the conflicting measurement.')
    if spec.cavity == 'blind' and d.get('cavity_depth') and d.get('height') and d['cavity_depth'] >= d['height']:
        q.append('A blind cavity must be shallower than the height. Correct the depth or confirm a through cavity.')
    if spec.family == 'box' and d.get('wall_thickness') and all(d.get(k) for k in ('length', 'width')) and 2*d['wall_thickness'] >= min(d['length'], d['width']):
        q.append('Wall thickness must be less than half the length and width.')
    if spec.profile == 'inner_groove' and spec.family != 'ring':
        q.append('Inner grooves are supported only on ring references. Clarify a plain reference or choose a ring.')
    return q


def readback(spec):
    dims = ', '.join(f'{k.replace("_", " ")} {spec.dimensions[k].value_mm:g} mm' for k in required(spec) if spec.dimensions.get(k) and spec.dimensions[k].value_mm is not None)
    return f'Intact reference: {spec.family or "shape unknown"}; cavity: {spec.cavity or "unknown"}; profile: {spec.profile or "unknown"}. Your measurements: {dims or "none yet"}. '
