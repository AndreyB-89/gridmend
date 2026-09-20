"""Trusted intact primitives. Never runs provider-generated scripts."""
import math
from pathlib import Path
import cadquery as cq
import numpy as np
import trimesh
from api.schemas import Dimension, GenerateRequest, Groove, ReferenceSpec
from cad.ring import generate_ring
from engine.reconstruction.specification import FRAME, questions, required, values
from engine.reconstruction.store import atomic_json, digest


def build_reference(spec: ReferenceSpec, folder: Path, revision: int, video_hash: str):
    q = questions(spec)
    if q or not spec.confirmed or any(not spec.dimensions[k].confirmed for k in required(spec)):
        raise ValueError('Confirm the complete specification before building. ' + ' '.join(q))
    folder.mkdir(parents=True, exist_ok=True)
    d = values(spec)
    height = d['height']
    if spec.family == 'ring':
        dim = lambda k: Dimension(value_mm=d[k], source='MANUAL_MEASUREMENT', confirmed=True)
        groove = Groove(depth_mm=d['groove_depth'], width_mm=d['groove_width']) if spec.profile == 'inner_groove' else None
        req = GenerateRequest(outer_diameter=dim('outer_diameter'), inner_diameter=dim('inner_diameter'), thickness=dim('height'), groove=groove, profile_rz_mm=None, profile_basis='OBSERVED', profile_confirmed=True, missing_arc_deg=None, purpose='DEMO_CAD_ONLY')
        out = generate_ring(req, folder, 'reference_full')
        shape = cq.importers.importStep(str(out.step_path)).val()
        extents = [d['outer_diameter'], d['outer_diameter'], height]
    else:
        if spec.family == 'cylinder':
            solid = cq.Workplane('XY').circle(d['diameter']/2).extrude(height)
            extents = [d['diameter'], d['diameter'], height]
            if spec.cavity != 'solid':
                depth = height if spec.cavity == 'through' else d['cavity_depth']
                cavity = cq.Workplane('XY').workplane(offset=height-depth).circle(d['inner_diameter']/2).extrude(depth)
                solid = solid.cut(cavity)
        else:
            solid = cq.Workplane('XY').box(d['length'], d['width'], height, centered=(True, True, False))
            extents = [d['length'], d['width'], height]
            if spec.cavity != 'solid':
                depth = height if spec.cavity == 'through' else d['cavity_depth']
                cavity = cq.Workplane('XY').workplane(offset=height-depth).box(d['length']-2*d['wall_thickness'], d['width']-2*d['wall_thickness'], depth, centered=(True, True, False))
                solid = solid.cut(cavity)
        shape = solid.val()
        cq.exporters.export(solid, str(folder/'reference_full.step'))
        cq.exporters.export(solid, str(folder/'reference_full.stl'), tolerance=.02, angularTolerance=.1)
    mesh = trimesh.load_mesh(folder/'reference_full.stl')
    checks = {'solid': shape.isValid() and len(shape.Solids()) == 1, 'finite': bool(np.isfinite(mesh.vertices).all()),
              'closed': bool(mesh.is_watertight and mesh.is_winding_consistent), 'positive_volume': float(mesh.volume)>0,
              'dimensions': bool(np.allclose(mesh.extents, extents, atol=.1, rtol=0)),
              'volume': bool(abs(mesh.volume-shape.Volume())/shape.Volume() < .005)}
    reopened = cq.importers.importStep(str(folder/'reference_full.step')).val()
    checks['step_reimport'] = reopened.isValid() and abs(reopened.Volume()-shape.Volume())/shape.Volume() < .001
    if not all(checks.values()):
        raise ValueError('Reference validation failed: '+str(checks))
    sidecar = {'schema_version': 1, 'reference_revision': revision, 'units': 'mm', 'specification': spec.model_dump(),
        'coordinate_frame': FRAME, 'semantics': 'Complete intended intact object. Explicit cavities retained.',
        'provenance': 'Only independently supplied user measurements; no video-derived reference dimensions.',
        'video_sha256': video_hash, 'reference_sha256': digest(folder/'reference_full.stl'),
        'checks': checks, 'volume_mm3': float(mesh.volume), 'bounds_mm': mesh.bounds.tolist(),
        'tolerances': {'bounds_mm': .1, 'relative_mesh_volume': .005}, 'physical_fit_verified': False}
    atomic_json(folder/'specification.json', sidecar)
    return sidecar


def in_reference(points, spec, tolerance=0):
    """Analytic occupancy for all supported shapes, including holes and grooves."""
    d = values(spec)
    p = np.asarray(points)
    z = p[:, 2]
    inside = (z >= -tolerance) & (z <= d['height']+tolerance)
    if spec.family in ('ring', 'cylinder'):
        r = np.linalg.norm(p[:, :2], axis=1)
        outer = d['outer_diameter'] if spec.family == 'ring' else d['diameter']
        inside &= r <= outer/2+tolerance
        if spec.cavity != 'solid':
            void = r < d['inner_diameter']/2-tolerance
            if spec.cavity == 'blind':
                void &= z > d['height']-d['cavity_depth']+tolerance
            inside &= ~void
        if spec.profile == 'inner_groove':
            inside &= ~((r < d['inner_diameter']/2+d['groove_depth']-tolerance) & (np.abs(z-d['height']/2) < d['groove_width']/2-tolerance))
    else:
        inside &= (np.abs(p[:, 0]) <= d['length']/2+tolerance) & (np.abs(p[:, 1]) <= d['width']/2+tolerance)
        if spec.cavity != 'solid':
            void = (np.abs(p[:, 0]) < d['length']/2-d['wall_thickness']-tolerance) & (np.abs(p[:, 1]) < d['width']/2-d['wall_thickness']-tolerance)
            if spec.cavity == 'blind':
                void &= z > d['height']-d['cavity_depth']+tolerance
            inside &= ~void
    return inside
