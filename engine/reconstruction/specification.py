"""Required primitive parameters and independently supplied metric provenance."""
import math
import re
from api.schemas import ReferenceSpec, SuppliedMeasurement

NUMBER = r'(?:\d+(?:[.,]\d+)?|\.\d+)'
UNIT = r'(?:millimet(?:er|re)s?|mm|centimet(?:er|re)s?|cm|inches|inch|in)(?=$|[\s.,;:!?×)]|x(?=\s*\d))'
SECTION = re.compile(
    r'\b(?:(square|rectangular|rectangle)\s+)?(?:cross[\s-]+section|section)\s*(?:is|of|to|=|:)?\s*'
    r'('+NUMBER+r')\s*('+UNIT+r')?\s*[x×]\s*('+NUMBER+r')\s*('+UNIT+r')?', re.I)
FEATURES = ['outer_diameter', 'inner_diameter', 'diameter', 'bottom_diameter', 'top_diameter', 'height', 'length', 'width', 'wall_thickness', 'bottom_thickness', 'cavity_depth', 'groove_depth', 'groove_width']
CUP_THICKNESS_MM = 1.5
FRAME = {'origin': 'centre of bottom face', 'x': 'box length direction; ring radial zero',
         'y': 'box width direction', 'z': 'axial height, positive up', 'handedness': 'right', 'units': 'mm'}


def unit_scale(unit):
    unit = unit.lower()
    return 10 if unit.startswith(('cm', 'cent')) else 25.4 if unit.startswith('in') else 1


def section_measurements(text, message_id):
    match = SECTION.search(text)
    if not match:
        return None
    global_unit = re.search(r'\ball\s+(?:values?\s+)?(?:are\s+)?in\s+('+UNIT+r')', text, re.I)
    shared_unit = match[5] or match[3] or (global_unit[1] if global_unit else None)
    if not shared_unit:
        raise ValueError('Supply a unit for the cross section, for example "rectangular section 9 x 6 mm".')
    result = []
    for number, unit in ((match[2], match[3] or shared_unit), (match[4], match[5] or shared_unit)):
        value = float(number.replace(',', '.'))
        try:
            result.append(SuppliedMeasurement(value_mm=value*unit_scale(unit), original_value=value,
                original_unit=unit.lower(), source_text=text, message_id=message_id))
        except ValueError:
            raise ValueError('Cross-section sides must be positive and at most 2000 mm.') from None
    return result


def empty_spec():
    return ReferenceSpec(dimensions={k: SuppliedMeasurement() for k in FEATURES})


def required(spec):
    if spec.family == 'ring':
        fields = ['outer_diameter', 'inner_diameter', 'height']
    elif spec.family == 'cylinder':
        fields = ['diameter', 'height'] + (['inner_diameter'] if spec.cavity in ('through', 'blind') else [])
    elif spec.family == 'box':
        fields = ['length', 'width', 'height'] + (['wall_thickness'] if spec.cavity in ('through', 'blind') else [])
    elif spec.family == 'open_frustum':
        fields = ['bottom_diameter', 'top_diameter', 'height', 'wall_thickness', 'bottom_thickness']
    else:
        return []
    if spec.cavity == 'blind' and spec.family != 'open_frustum':
        fields += ['cavity_depth']
    if spec.profile == 'inner_groove':
        fields += ['groove_depth', 'groove_width']
    return fields


def values(spec):
    return {k: v.value_mm for k, v in spec.dimensions.items() if v.value_mm is not None}


def confirms_build(text: str, spec: ReferenceSpec, message_id: str) -> bool:
    if not re.match(r'\s*(?:please\s+)?(?:build|generate|create|reconstruct)\b', text, re.I):
        return False
    if '?' in text or re.search(r"\b(?:not|don['’]t|never|wait|hold|later|before|after|unless|until|without|preview|draft)\b", text, re.I):
        return False
    return not questions(spec) and all(
        spec.dimensions[k].source == 'operator'
        and spec.dimensions[k].message_id == message_id
        and bool(spec.dimensions[k].source_text)
        for k in required(spec)
    )


def questions(spec):
    q = []
    if spec.family is None:
        q.append('Is the intended intact object a ring, a cylinder, a box, or an open-top truncated cone (cup)?')
        return q
    if spec.cavity is None:
        q.append('Is the intact object solid, hollow all the way through, or a cavity closed at the bottom (blind/open top)?')
    if spec.family == 'ring' and spec.cavity != 'through':
        q.append('A ring retains its central through-hole. Please confirm that shape, or choose a cylinder.')
    if spec.family == 'open_frustum' and spec.cavity != 'blind':
        q.append('A cup is an open-top truncated cone with a closed bottom. Confirm that cavity before building.')
    if spec.profile is None:
        q.append('Is the reference profile plain, with no grooves or extra features? For a ring inner groove, give its radial depth and axial width.')
    for k in required(spec):
        if k not in spec.dimensions or spec.dimensions[k].value_mm is None:
            label = k.replace('_', ' ')
            if spec.family == 'open_frustum':
                label = {'bottom_diameter': 'bottom outer diameter', 'top_diameter': 'top outer diameter',
                         'wall_thickness': 'wall thickness (radial)', 'bottom_thickness': 'bottom thickness (along Z)'}.get(k, label)
            q.append(f'What is the intended intact object\'s {label}? Supply your measured value and unit.')
    d = values(spec)
    outer = d.get('outer_diameter', d.get('diameter'))
    if outer and d.get('inner_diameter') and outer <= d['inner_diameter']:
        q.append('Inner diameter must be smaller than outer diameter. Correct the conflicting measurement.')
    height = spec.dimensions.get('height')
    if spec.family == 'ring' and height and height.value_mm and outer and d.get('inner_diameter'):
        sides = section_measurements(height.source_text or '', height.message_id)
        if sides:
            expected = sorted([(outer-d['inner_diameter'])/2, height.value_mm])
            actual = sorted(s.value_mm for s in sides)
            if not all(math.isclose(a, b, abs_tol=1e-8) for a, b in zip(expected, actual)):
                q.append('The cross section conflicts with the supplied diameters or height. Correct the radii/diameters, or repeat the corrected cross section.')
    if spec.cavity == 'blind' and d.get('cavity_depth') and d.get('height') and d['cavity_depth'] >= d['height']:
        q.append('A blind cavity must be shallower than the height. Correct the depth or confirm a through cavity.')
    if spec.family == 'box' and d.get('wall_thickness') and all(d.get(k) for k in ('length', 'width')) and 2*d['wall_thickness'] >= min(d['length'], d['width']):
        q.append('Wall thickness must be less than half the length and width.')
    if spec.family == 'open_frustum':
        if d.get('bottom_thickness') and d.get('height') and d['bottom_thickness'] >= d['height']:
            q.append('Bottom thickness must be smaller than the height.')
        if all(d.get(k) for k in required(spec)) and d['bottom_thickness'] < d['height']:
            floor_diameter = d['bottom_diameter'] + (d['top_diameter']-d['bottom_diameter'])*d['bottom_thickness']/d['height']
            if 2*d['wall_thickness'] >= min(floor_diameter, d['top_diameter']):
                q.append('Wall thickness must leave a positive cavity radius at both the floor and the top.')
    if spec.profile == 'inner_groove' and spec.family != 'ring':
        q.append('Inner grooves are supported only on ring references. Clarify a plain reference or choose a ring.')
    return q


def readback(spec):
    dims = ', '.join(f'{"axial height" if k == "height" and spec.family == "ring" else k.replace("_", " ")} {spec.dimensions[k].value_mm:g} mm'
                     + (' (design default)' if spec.dimensions[k].source == 'design_default' else '')
                     for k in (required(spec) if spec.family else FEATURES) if spec.dimensions.get(k) and spec.dimensions[k].value_mm is not None)
    shape = 'open-top truncated cone (cup)' if spec.family == 'open_frustum' else spec.family or 'shape unknown'
    geometry = ' Diameters are external; wall thickness is radial. Axis Z; closed base at Z = 0, open top at Z = height.' if spec.family == 'open_frustum' else ''
    heading = 'Measurements and design parameters' if any(m.source == 'design_default' for m in spec.dimensions.values()) else 'Your measurements'
    return f'Intact reference: {shape}; cavity: {spec.cavity or "unknown"}; profile: {spec.profile or "unknown"}.{geometry} {heading}: {dims or "none yet"}. '
