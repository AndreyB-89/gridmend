"""Build the standalone explorer from the committed scene and route catalog."""
import json
from pathlib import Path

OUT = Path(__file__).parent
scene = json.loads((OUT / 'scene.json').read_text())
routes = json.loads((OUT / 'manufacturing-routes.json').read_text())
ids = {p['id'] for p in scene['parts']}
assert {d['component_id'] for d in routes['component_dispositions']} == ids
assert all(o['component_id'] in ids for o in routes['route_options'])
assert all(o['service_release'] == 'NOT_APPROVED' for o in routes['route_options'])
template = (OUT / 'viewer-template.html').read_text()
for marker, data in [('/*SCENE_DATA*/', scene), ('/*ROUTE_DATA*/', routes)]:
    template = template.replace(marker, json.dumps(data, separators=(',', ':')).replace('<', '\\u003c'))
(OUT.parent / 'substation-explorer.html').write_text(template)
print('Built standalone substation-explorer.html: %s components, %s candidate routes' % (len(ids), len(routes['route_options'])))
