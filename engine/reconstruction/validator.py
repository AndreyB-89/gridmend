"""Independent checks; no generated code runs here. No physical-fit guarantee.

Geometry: deterministic occupancy samples + analytic template containment.
Visual: conservative original-frame segmentation vs candidate camera projections.
Devin's surviving mesh/cameras are hypotheses, never independent ground truth.
"""
import json
from pathlib import Path
import cv2
import numpy as np
import trimesh
from api.schemas import ReferenceSpec
from cad.reference import in_reference
from engine.reconstruction.store import digest

TOLERANCES = {'containment_mm': .15, 'max_outside_fraction': .001, 'max_overlap_fraction': .01,
              'max_uncovered_fraction': .02, 'max_reference_volume_fraction': .98,
              'min_silhouette_iou': .85, 'min_missing_silhouette_iou': .75,
              'min_clear_views': 2, 'min_view_separation_s': .15, 'occupancy_samples': 12000,
              'max_faces': 100000, 'rigid_matrix_absolute': 1e-5, 'foreground_lab_distance': 40}
SUMMARY_FIELDS = ['status', 'units', 'supplied_dimensions', 'observed_geometry', 'assumptions', 'coordinate_frame',
                  'candidate_dimensions_mm', 'missing_inputs', 'changes_from_previous', 'artifacts']


def rigid(matrix):
    m = np.asarray(matrix, dtype=float)
    return m.shape == (4, 4) and np.isfinite(m).all() and np.allclose(m[3], [0, 0, 0, 1], atol=1e-5) and np.allclose(m[:3, :3].T@m[:3, :3], np.eye(3), atol=1e-5) and abs(np.linalg.det(m[:3, :3])-1) < 1e-5


def foreground(image):
    """Only supports a single distinct object on a simple background. Ambiguity fails closed."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(float)
    border = np.concatenate((lab[:4].reshape(-1, 3), lab[-4:].reshape(-1, 3), lab[:, :4].reshape(-1, 3), lab[:, -4:].reshape(-1, 3)))
    median = np.median(border, axis=0)
    if np.percentile(np.linalg.norm(border-median, axis=1), 90) > 20:
        return None, 'Background is not uniform; supply a clear view on a plain contrasting background.'
    mask = (np.linalg.norm(lab-median, axis=2) > TOLERANCES['foreground_lab_distance']).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    if n < 2:
        return None, 'No independently segmentable foreground.'
    areas = stats[1:, cv2.CC_STAT_AREA]
    largest = int(np.argmax(areas))+1
    area = int(areas.max())
    if not .02 < area/mask.size < .8 or (len(areas)>1 and sorted(areas)[-2] > .15*area):
        return None, 'Multiple/ambiguous foreground objects or insufficient visible material.'
    result = labels == largest
    if result[:3].any() or result[-3:].any() or result[:, :3].any() or result[:, -3:].any():
        return None, 'Object touches the frame boundary.'
    return result, None


def project(mesh, view, size):
    k, r, t = np.asarray(view['K'], float), np.asarray(view['R'], float), np.asarray(view['t_mm'], float)
    matrix = np.eye(4)
    matrix[:3, :3] = r
    matrix[:3, 3] = t
    if not rigid(matrix) or k.shape != (3, 3) or not np.isfinite(k).all() or not np.allclose(k[2], [0, 0, 1]) or k[0, 0] <= 0 or k[1, 1] <= 0:
        raise ValueError('Camera must have finite intrinsics and a proper rigid pose in mm.')
    camera = mesh.vertices@r.T+t
    if np.min(camera[:, 2]) <= 0:
        raise ValueError('Geometry lies behind the camera.')
    pixel = camera@k.T
    xy = pixel[:, :2]/pixel[:, 2:3]
    if not np.isfinite(xy).all() or np.max(np.abs(xy)) > 100000:
        raise ValueError('Unbounded projection.')
    mask = np.zeros(size, np.uint8)
    for triangle in np.rint(xy[mesh.faces]).astype(np.int32):
        cv2.fillConvexPoly(mask, triangle, 1)
    return mask.astype(bool)


def iou(a, b):
    return float(np.count_nonzero(a & b)/max(1, np.count_nonzero(a | b)))


def visual_checks(reference, repair, survivor, evidence, video, folder):
    results, stamps = [], []
    views = evidence.get('views', [])
    for view in views[:12]:
        idx = view.get('frame_index')
        if not isinstance(idx, int) or idx < 0 or idx >= len(video['frames']):
            continue
        frame = video['frames'][idx]
        if any(abs(frame['timestamp_s']-t) < TOLERANCES['min_view_separation_s'] for t in stamps):
            continue
        image = cv2.imread(frame['path'])
        observed, problem = foreground(image)
        if observed is None:
            results.append({'frame_index': idx, 'passed': False, 'reason': problem})
            continue
        try:
            expected = project(reference, view, observed.shape)
            surviving = project(survivor, view, observed.shape)
            missing = project(repair, view, observed.shape)
            silhouette_score = iou(observed, surviving)
            # Visible missing area excludes occluded areas of the survivor silhouette.
            missing_score = iou(expected & ~observed, missing & ~surviving)
            score = silhouette_score >= TOLERANCES['min_silhouette_iou'] and missing_score >= TOLERANCES['min_missing_silhouette_iou']
            overlay = image.copy()
            overlay[missing & ~surviving] = (0, 0, 255)
            cv2.imwrite(str(folder/f'validation-view-{idx}.jpg'), overlay)
            cv2.imwrite(str(folder/f'foreground-{idx}.png'), observed.astype(np.uint8)*255)
            results.append({'frame_index': idx, 'timestamp_s': frame['timestamp_s'], 'frame_sha256': frame['sha256'],
                'silhouette_iou': silhouette_score, 'missing_silhouette_iou': missing_score, 'passed': bool(score),
                'camera': view, 'independent_evidence': 'original pixels; deterministic foreground segmentation',
                'limitation': 'Camera pose and surviving mesh are provider hypotheses; hidden damage is not observable.'})
            if score:
                stamps.append(frame['timestamp_s'])
        except (ValueError, KeyError, IndexError) as exc:
            results.append({'frame_index': idx, 'passed': False, 'reason': str(exc)})
    return len(stamps) >= TOLERANCES['min_clear_views'], results


def validate(folder: Path, reference_folder: Path, job):
    checks = []
    def check(name, category, passed, measured, units, tolerance, detail=''):
        checks.append({'name': name, 'category': category, 'passed': bool(passed), 'measured': measured,
                       'units': units, 'tolerance': tolerance, 'detail': detail})
    report = {'validator_version': 1, 'job_id': job['job_id'], 'reference_revision': job['revision'],
              'attempt': job['attempt'], 'units': 'mm', 'thresholds': TOLERANCES, 'checks': checks,
              'alignment': None, 'accepted': False, 'mesh_validity': False, 'reference_consistency': False,
              'visual_reconstruction_confidence': 'UNRESOLVED', 'physical_fit_verified': False}
    try:
        required_files = ['repair_part.stl', 'surviving_estimate.stl', 'generation.py', 'requirements.txt', 'README.md', 'summary.json', 'evidence.json']
        absent = [n for n in required_files if not (folder/n).is_file() or (folder/n).stat().st_size == 0]
        check('artifacts_present', 'mesh', not absent, absent, None, [], 'Generation scripts are stored, never executed.')
        if absent:
            return report
        summary = json.loads((folder/'summary.json').read_text())
        evidence = json.loads((folder/'evidence.json').read_text())
        sidecar = json.loads((reference_folder/'specification.json').read_text())
        spec = ReferenceSpec.model_validate(sidecar['specification'])
        missing = [k for k in SUMMARY_FIELDS if k not in summary]
        check('summary_contract', 'reference', not missing and summary.get('status') == 'candidate_ready', missing, None, [])
        check('reference_unchanged', 'reference', digest(reference_folder/'reference_full.stl') == sidecar['reference_sha256'] == summary.get('reference_sha256') and summary.get('reference_revision') == job['revision'], summary.get('reference_sha256'), None, sidecar['reference_sha256'])
        check('units', 'reference', summary.get('units') == 'mm', summary.get('units'), None, 'mm', 'STL units are established by the fixed metric reference/sidecar, not STL metadata.')
        supplied = {k: v.value_mm for k, v in spec.dimensions.items() if v.value_mm is not None}
        check('supplied_dimensions_unchanged', 'reference', summary.get('supplied_dimensions') == supplied, summary.get('supplied_dimensions'), 'mm', supplied)
        check('candidate_attempt', 'reference', summary.get('attempt') == job['attempt'], summary.get('attempt'), None, job['attempt'])
        uncertainty = summary.get('unresolved_uncertainty')
        check('damage_resolved', 'visual', uncertainty == [] and summary.get('missing_inputs') == [], uncertainty, None, [], 'Provider statement alone cannot establish visual confidence.')
        decode = evidence.get('video_decode', {})
        check('video_decode_report', 'visual', decode.get('sha256') == job['video']['sha256'] and isinstance(decode.get('decoded_frame_count'), int) and decode['decoded_frame_count'] > 0 and bool(decode.get('decoder')) and bool(decode.get('frames')) and abs(float(decode.get('duration_s', -1))-job['video']['duration_s']) < .2,
              decode, None, {'sha256': job['video']['sha256'], 'duration_tolerance_s': .2}, 'Reported sandbox decoding is checked against original media; live API activity must corroborate it.')
        transform = summary.get('coordinate_frame', {}).get('artifact_to_reference', np.eye(4).tolist())
        valid_transform = rigid(transform)
        check('rigid_alignment', 'reference', valid_transform, transform, 'mm', 'rotation + translation, unit scale')
        report['alignment'] = transform
        if not valid_transform:
            return report
        meshes = []
        for name in ('repair_part.stl', 'surviving_estimate.stl'):
            mesh = trimesh.load_mesh(folder/name, file_type='stl', process=True)
            valid = isinstance(mesh, trimesh.Trimesh) and 0 < len(mesh.faces) <= TOLERANCES['max_faces'] and bool(np.isfinite(mesh.vertices).all()) and mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0
            check(name+'_solid', 'mesh', valid, {'faces': len(mesh.faces), 'closed': bool(mesh.is_watertight), 'volume_mm3': float(mesh.volume) if np.isfinite(mesh.volume) else None}, 'mm3', '>0, finite, closed, consistent winding')
            if not valid:
                return report
            mesh.apply_transform(transform)
            samples = np.vstack((mesh.vertices, mesh.triangles_center, mesh.triangles[:, :2].mean(axis=1)))
            outside = float(np.mean(~in_reference(samples, spec, TOLERANCES['containment_mm'])))
            check(name+'_containment', 'reference', outside <= TOLERANCES['max_outside_fraction'], outside, 'fraction', TOLERANCES['max_outside_fraction'], 'Vertices, face centres and edge midpoints against analytic primitive with explicit cavities.')
            meshes.append(mesh)
        repair, survivor = meshes
        reference = trimesh.load_mesh(reference_folder/'reference_full.stl')
        ratio = float(repair.volume/reference.volume)
        check('not_entire_reference', 'reference', 0 < ratio < TOLERANCES['max_reference_volume_fraction'], ratio, 'fraction', TOLERANCES['max_reference_volume_fraction'])
        rng = np.random.default_rng(7931)
        samples = rng.uniform(reference.bounds[0], reference.bounds[1], (TOLERANCES['occupancy_samples'], 3))
        samples = samples[in_reference(samples, spec)]
        if len(samples) < 300:
            check('sampling_support', 'reference', False, len(samples), 'samples', '>=300')
            return report
        a, b = repair.contains(samples), survivor.contains(samples)
        overlap, uncovered = float(np.mean(a & b)), float(np.mean(~(a | b)))
        check('surviving_overlap', 'reference', overlap <= TOLERANCES['max_overlap_fraction'], overlap, 'fraction of reference', TOLERANCES['max_overlap_fraction'], 'Conditional on provider survivor estimate; not independent truth.')
        check('missing_region_coverage', 'reference', uncovered <= TOLERANCES['max_uncovered_fraction'], uncovered, 'fraction of reference', TOLERANCES['max_uncovered_fraction'], 'Deterministic volume occupancy samples; conditional on survivor estimate.')
        visual_ok, views = visual_checks(reference, repair, survivor, evidence, job['video'], folder)
        report['visual_evidence'] = views
        check('original_video_silhouettes', 'visual', visual_ok, views, 'IoU', {'survivor': .85, 'missing': .75, 'views': 2})
        report['mesh_validity'] = all(c['passed'] for c in checks if c['category'] == 'mesh')
        report['reference_consistency'] = all(c['passed'] for c in checks if c['category'] == 'reference')
        visual_pass = all(c['passed'] for c in checks if c['category'] == 'visual')
        report['visual_reconstruction_confidence'] = 'SUPPORTED_BY_SAMPLED_VIEWS' if visual_pass else 'UNRESOLVED'
        report['accepted'] = all(c['passed'] for c in checks)
        report['limitations'] = ['No physical fit verified.', 'Silhouette checks cannot certify hidden surfaces.', 'Provider camera and survivor hypotheses are constrained by sampled original pixels, not independent 3D ground truth.']
        if report['accepted']:
            repair.export(folder/'repair_part_aligned.stl')
    except Exception as exc:
        check('readable_artifacts', 'mesh', False, type(exc).__name__, None, 'readable finite typed artifacts', str(exc)[:400])
    return report
