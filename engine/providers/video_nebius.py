"""Nebius reference agent. Measurements come from operator text, never video."""
import json
import math
import os
import re
import time
from pathlib import Path
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, SecretStr
from api.schemas import ReferenceSpec, SuppliedMeasurement
from engine.providers.common import NEBIUS_BASE_URL, TIMEOUT_S, ProviderError, map_openai_error, nebius_key, nebius_text_model
from engine.reconstruction.specification import CUP_THICKNESS_MM, NUMBER, SECTION, UNIT, confirms_build, questions, readback, section_measurements, unit_scale

AGENT_PROMPT = Path(__file__).parents[1] / 'reconstruction/prompts/nebius-reference-v1.txt'
ALIASES = {
    'bottom_diameter': r'(?<!inner )(?<!inside )\b(?:bottom|base|basis|lower)\s+(?:outer\s+|outside\s+)?diame?ter',
    'top_diameter': r'(?<!inner )(?<!inside )\b(?:top|upper|rim)\s+(?:outer\s+|outside\s+)?diame?ter',
    'bottom_thickness': r'\b(?:bottom|base)\s+thickness',
    'outer_diameter': r'outer\s+diame?ter|outside\s+diame?ter|\bOD\b',
    'inner_diameter': r'inner\s+diame?ter|inside\s+diame?ter|\bID\b',
    'diameter': r'(?<!outer )(?<!inner )(?<!outside )(?<!inside )\bdiame?ter',
    'height': r'axial\s+height|height|(?<!wall )thickness',
    'length': r'length', 'width': r'(?<!groove )(?<!axial )width',
    'wall_thickness': r'wall\s+thickness', 'cavity_depth': r'cavity\s+depth|hole\s+depth',
    'groove_depth': r'groove\s+depth|radial\s+depth', 'groove_width': r'groove\s+width|axial\s+width',
}
RADIUS_ALIASES = {
    'outer_diameter': r'outer\s+radius|outside\s+radius',
    'inner_diameter': r'inner\s+radius|inside\s+radius',
}


class ReferenceToolInput(BaseModel):
    model_config = ConfigDict(extra='forbid')


def model():
    return os.getenv('NEBIUS_VIDEO_MODEL') or nebius_text_model()


def reference_model():
    key = nebius_key()
    if not key:
        raise ProviderError('PROVIDER_FAILED', 'Nebius is not configured for the LIVE reference agent.')
    return ChatOpenAI(model=model(), base_url=NEBIUS_BASE_URL, api_key=SecretStr(key),
        timeout=TIMEOUT_S, max_retries=0, temperature=0, max_completion_tokens=4096)


def run_reference_tool(store, job, function):
    tool = StructuredTool.from_function(function, args_schema=ReferenceToolInput)
    messages = [
        SystemMessage(content=AGENT_PROMPT.read_text()),
        HumanMessage(content=json.dumps({
            'user_request': job['user_goal'], 'state': job['spec'],
            'history': job['messages'][-30:], 'available_tool': tool.name,
        })),
    ]
    agent = reference_model().bind_tools([tool], tool_choice='required', parallel_tool_calls=False)
    for attempt in range(2):
        store.event(job, 'provider_request', provider='NEBIUS', mode='LIVE', request={
            'model': model(), 'messages': [message.model_dump() for message in messages],
            'tools': [convert_to_openai_tool(tool)], 'tool_choice': 'required',
            'parallel_tool_calls': False, 'max_completion_tokens': 4096, 'temperature': 0,
        })
        start = time.monotonic()
        try:
            response = agent.invoke(messages)
        except Exception as exc:
            store.event(job, 'provider_error', provider='NEBIUS', mode='LIVE', model=model(), error=type(exc).__name__,
                latency_ms=round((time.monotonic()-start)*1000))
            raise map_openai_error(exc) from None
        store.event(job, 'provider_response', provider='NEBIUS', mode='LIVE', model=model(), response=response.model_dump(),
            latency_ms=round((time.monotonic()-start)*1000), request_id=response.id,
            usage=response.usage_metadata if isinstance(response, AIMessage) else None, cost=None)
        try:
            if not isinstance(response, AIMessage) or response.invalid_tool_calls or len(response.tool_calls) != 1:
                raise ValueError('Expected exactly one reference tool call.')
            call = response.tool_calls[0]
            if call['name'] != tool.name:
                raise ValueError('The requested tool is unavailable at this stage.')
            arguments = ReferenceToolInput.model_validate(call['args']).model_dump()
        except ValueError as exc:
            store.event(job, 'invalid_reference_tool', provider_attempt=attempt+1, error=type(exc).__name__)
            messages.append(HumanMessage(content=f'Call {tool.name} exactly once with an empty JSON object. Do not supply measurements, code or confirmation.'))
            continue
        job['selected_models']['nebius'] = model()
        store.event(job, 'reference_tool_call', name=tool.name, arguments=arguments, tool_call_id=call['id'])
        result = tool.invoke(arguments)
        store.event(job, 'reference_tool_result', name=tool.name, result=result)
        return result
    raise ProviderError('PROVIDER_FAILED', 'Nebius returned invalid reference tool calls twice.')


def bind_measurements(spec, feature, candidates, text, issues):
    if not candidates:
        return
    if any(not math.isclose(c.value_mm, candidates[0].value_mm, abs_tol=1e-8) for c in candidates[1:]):
        spec.dimensions[feature] = SuppliedMeasurement(source_text=text, message_id=candidates[0].message_id)
        issues.append(f'Conflicting {feature.replace("_", " ")} values. Say "correct {feature.replace("_", " ")} to ... mm".')
        return
    old = spec.dimensions.get(feature)
    if old and old.source != 'design_default' and old.value_mm is not None and not math.isclose(old.value_mm, candidates[0].value_mm, abs_tol=1e-8) and not re.search(r'\b(?:correct|change|instead|replace)\b', text, re.I):
        spec.dimensions[feature] = SuppliedMeasurement(source_text=text, message_id=candidates[0].message_id)
        issues.append(f'You previously supplied {feature.replace("_", " ")} {old.value_mm:g} mm. Confirm a correction by saying "correct {feature.replace("_", " ")} to ... mm".')
        return
    spec.dimensions[feature] = candidates[0]


def supplied_edit(spec: ReferenceSpec, text: str, message_id: str):
    """Deterministic binding of a named feature, numeric literal and explicit unit.

    The LLM has no write access to these fields. No image/observation text enters this function.
    Ambiguity is a question, never a guess. Replacements require the word 'correct/change/instead'.
    """
    spec = spec.model_copy(deep=True)
    spec.confirmed = False
    for measurement in spec.dimensions.values():
        measurement.confirmed = False
    issues = []
    lower = text.lower()
    families = [f for f in ('ring', 'cylinder', 'box') if re.search(r'\b'+f+r'\b', lower)]
    if re.search(r'\bcup\b|\btruncated\s+cone\b|\b(?:open[-_ ](?:top[-_ ])?)?frustum\b', lower):
        families.append('open_frustum')
    if len(families) == 1:
        if spec.family and spec.family != families[0]:
            spec = ReferenceSpec(dimensions={})
        spec.family = families[0]
    elif len(families) > 1:
        issues.append('Choose one reference shape: ring, cylinder, box, or open-top truncated cone (cup).')
    cavity_conflict = bool(re.search(r'\bsolid\b', lower) and not re.search(r'\bnot\s+solid\b', lower) and re.search(r'hollow|\bcavity\b|through|blind', lower))
    if cavity_conflict:
        spec.cavity = None
        issues.append('Solid and hollow descriptions conflict. Clarify the intended cavity before confirming.')
    elif spec.family == 'ring':
        spec.cavity = 'through'
    elif re.search(r'\bsolid\b', lower) and not re.search(r'\bnot\s+solid\b', lower):
        spec.cavity = 'solid'
    elif re.search(r'through|open both ends', lower):
        spec.cavity = 'through'
    elif re.search(r'blind|open.top|closed.*bottom', lower):
        spec.cavity = 'blind'
    elif spec.family == 'open_frustum' and spec.cavity is None:
        spec.cavity = 'blind'
    elif re.search(r'hollow|cavity', lower) and spec.cavity is None:
        issues.append('Does the cavity pass all the way through, or is its bottom closed?')
    profile_text = re.sub(r'\b(?:not|no)\s+(?:plain|rectangular|rectangle|square|inner groove)\b', '', lower)
    if re.search(r'inner groove', profile_text):
        spec.profile = 'inner_groove'
    elif re.search(r'\bplain\b|no grooves?|no extra features|\brectang(?:ular|le)\b|\bsquare\s+(?:cross[\s-]+)?section', profile_text):
        spec.profile = 'plain'
    elif profile_text != lower:
        spec.profile = None
        issues.append('Describe the required ring profile and features explicitly.')
    if spec.family in ('cylinder', 'box') or (spec.family == 'open_frustum' and spec.profile is None):
        spec.profile = 'plain'
    if re.search(r'\bmaybe\b|\babout\b|\bapprox|\bor\s+\d|not measured|not sure|\bguess(?:ed)?\b', lower):
        if spec.family == 'open_frustum':
            for feature in ('wall_thickness', 'bottom_thickness'):
                if re.search(ALIASES[feature], text, re.I):
                    spec.dimensions[feature] = SuppliedMeasurement(source_text=text, message_id=message_id)
        return spec, issues + ['Please give one independently measured value per feature, with a unit; resolve uncertain measurements first.']
    global_unit = re.search(r'\ball\s+(?:values?\s+)?(?:are\s+)?in\s+('+UNIT+r')', lower)
    updates = {}
    named_spans = [match.span() for feature in ('bottom_diameter', 'top_diameter', 'wall_thickness', 'bottom_thickness')
                   for match in re.finditer(ALIASES[feature], text, re.I)]
    for feature, aliases in ALIASES.items():
        if feature == 'diameter' and spec.family == 'ring':
            continue
        radius_alias = RADIUS_ALIASES.get(feature) if spec.family == 'ring' else None
        if radius_alias:
            aliases += '|'+radius_alias
        pattern = r'(?:'+aliases+r')\s*(?:is|of|=|:|to)?\s*('+NUMBER+r')\s*('+UNIT+r')?'
        found = list(re.finditer(pattern, text, re.I))
        if feature in ('diameter', 'outer_diameter', 'height'):
            found = [match for match in found if not any(start <= match.start() < end for start, end in named_spans)]
        if not found:
            continue
        candidates = []
        for match in found:
            unit = (match.group(2) or (global_unit.group(1) if global_unit else '')).lower()
            if not unit:
                issues.append(f'What unit applies to {feature.replace("_", " ")}? Repeat the feature, value and unit.')
                continue
            n = float(match.group(1).replace(',', '.'))
            factor = unit_scale(unit) * (2 if radius_alias and re.match(radius_alias, match[0], re.I) else 1)
            try:
                candidates.append(SuppliedMeasurement(value_mm=n*factor, original_value=n, original_unit=unit,
                    source_text=match.group(0), message_id=message_id, confirmed=False))
            except ValueError:
                issues.append(f'{feature.replace("_", " ")} must be positive and at most 2000 mm.')
        updates[feature] = candidates
        if not candidates and spec.family == 'open_frustum' and feature in ('wall_thickness', 'bottom_thickness'):
            spec.dimensions[feature] = SuppliedMeasurement(source_text=text, message_id=message_id)
        if feature != 'height':
            bind_measurements(spec, feature, candidates, text, issues)
    section_text, section_id = text, message_id
    previous_height = spec.dimensions.get('height')
    if not SECTION.search(text) and previous_height and previous_height.value_mm is None and previous_height.source_text:
        section_text, section_id = previous_height.source_text, previous_height.message_id
    if spec.family == 'ring' and SECTION.search(section_text):
        try:
            if len(list(SECTION.finditer(section_text))) != 1:
                raise ValueError('Supply one cross section at a time, with its two sides and units.')
            sides = section_measurements(section_text, section_id)
            square = re.search(r'\bsquare\s+(?:cross[\s-]+)?section', section_text, re.I)
            if square and not math.isclose(sides[0].value_mm, sides[1].value_mm, abs_tol=1e-8) and not re.search(r'\brectang(?:ular|le)\b', text, re.I):
                spec.profile = None
                issues.append(f'A {sides[0].value_mm:g} x {sides[1].value_mm:g} mm section is rectangular, not square. Say "rectangular section" if that is intended, or correct the two sides.')
            outer, inner = spec.dimensions.get('outer_diameter'), spec.dimensions.get('inner_diameter')
            if not outer or not inner or outer.value_mm is None or inner.value_mm is None:
                spec.dimensions['height'] = SuppliedMeasurement(source_text=section_text, message_id=section_id)
                issues.append('Supply both ring radii or diameters to identify the radial side of the cross section.')
            else:
                radial = (outer.value_mm-inner.value_mm)/2
                matching = [i for i, side in enumerate(sides) if math.isclose(side.value_mm, radial, abs_tol=1e-8)]
                if not matching:
                    raise ValueError(f'The radii/diameters give a radial thickness of {radial:g} mm, which matches neither cross-section side. Correct the radii or cross section.')
                updates.setdefault('height', []).append(sides[1-matching[0]])
        except ValueError as exc:
            spec.dimensions['height'] = SuppliedMeasurement(source_text=section_text, message_id=section_id)
            updates.pop('height', None)
            issues.append(str(exc))
    bind_measurements(spec, 'height', updates.get('height', []), text, issues)
    if spec.family == 'open_frustum':
        for feature in ('wall_thickness', 'bottom_thickness'):
            measurement = spec.dimensions.get(feature)
            if feature not in updates and (measurement is None or (measurement.value_mm is None and not measurement.source_text)):
                spec.dimensions[feature] = SuppliedMeasurement(value_mm=CUP_THICKNESS_MM, source='design_default',
                    source_text=f'Cup design default: {feature.replace("_", " ")} {CUP_THICKNESS_MM:g} mm.')
    return spec, issues


def dialogue(store, job, text, message_id):
    def prepare_complete_reference() -> str:
        """Prepare the complete intact reference from operator measurements, retaining holes and asking for missing or conflicting values."""
        spec, issues = supplied_edit(ReferenceSpec.model_validate(job['spec']), text, message_id)
        job['spec'] = spec.model_dump()
        job['questions'] = list(dict.fromkeys(issues + questions(spec)))
        if job['questions']:
            return readback(spec) + ' '.join(job['questions'])
        if confirms_build(text, spec, message_id):
            return readback(spec) + 'Your build request confirms these measurements and the shape.'
        return readback(spec) + 'Confirm these values and the shape to build the complete reference and start reconstruction.'

    if job['mode'] == 'LIVE':
        canonical = run_reference_tool(store, job, prepare_complete_reference)
        return 'I will first prepare the complete intact reference for the missing-part reconstruction.\n\n' + canonical
    return 'MOCK dialogue. ' + prepare_complete_reference()


def construct_reference(store, job, builder):
    def build_complete_reference() -> dict:
        """Build and independently check the complete intact CadQuery STL and STEP using only the operator-confirmed specification."""
        spec = ReferenceSpec.model_validate(job['spec'])
        if job['status'] != 'QUEUED' or job['questions'] or not spec.confirmed:
            raise ValueError('Confirm the complete specification before building.')
        if job.get('media_kind') == 'photo':
            return builder(spec, store.revision_dir(job)/'reference', job['revision'], job['video']['sha256'], media_kind='photo')
        return builder(spec, store.revision_dir(job)/'reference', job['revision'], job['video']['sha256'])

    if job['mode'] == 'LIVE':
        return run_reference_tool(store, job, build_complete_reference)
    return build_complete_reference()
