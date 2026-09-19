import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

interface Props {
  ringUrl: string;
  segmentUrl: string | null;
}

/** Live 3D view of the generated STLs. Full ring in yellow, restored segment in red on top. */
export function RingViewer({ ringUrl, segmentUrl }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    setError(null);
    setLoading(true);
    let disposed = false;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setError("3D preview needs WebGL. The files are still ready to download.");
      setLoading(false);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 10000);
    camera.up.set(0, 0, 1); // CAD ring axis is +Z

    scene.add(new THREE.HemisphereLight(0xffffff, 0x2a2e36, 1.4));
    const key = new THREE.DirectionalLight(0xffffff, 2.2);
    key.position.set(60, -40, 120);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0xbcd2ff, 0.9);
    rim.position.set(-80, 70, 30);
    scene.add(rim);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.enablePan = false;
    controls.autoRotate = !reduce;
    controls.autoRotateSpeed = 0.9;

    const resize = () => {
      const w = host.clientWidth;
      const h = host.clientHeight;
      renderer.setSize(w, h);
      camera.aspect = w / Math.max(h, 1);
      camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(host);

    const loader = new STLLoader();
    const disposables: { dispose: () => void }[] = [];
    const load = (url: string) =>
      new Promise<THREE.BufferGeometry>((resolve, reject) => loader.load(url, resolve, undefined, reject));

    Promise.all([load(ringUrl), segmentUrl ? load(segmentUrl) : Promise.resolve(null)])
      .then(([ringGeo, segGeo]) => {
        if (disposed) return;
        ringGeo.computeBoundingBox();
        const box = ringGeo.boundingBox!;
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        ringGeo.translate(-center.x, -center.y, -center.z);
        ringGeo.computeVertexNormals();
        const ringMat = new THREE.MeshPhysicalMaterial({
          color: 0xffc400,
          roughness: 0.55,
          clearcoat: 0.15,
          clearcoatRoughness: 0.6,
          polygonOffset: true,
          polygonOffsetFactor: 1,
          polygonOffsetUnits: 1,
        });
        scene.add(new THREE.Mesh(ringGeo, ringMat));
        disposables.push(ringGeo, ringMat);

        if (segGeo) {
          segGeo.translate(-center.x, -center.y, -center.z);
          segGeo.computeVertexNormals();
          const segMat = new THREE.MeshPhysicalMaterial({ color: 0xe63b2e, roughness: 0.5, clearcoat: 0.2, clearcoatRoughness: 0.5 });
          const seg = new THREE.Mesh(segGeo, segMat);
          seg.scale.setScalar(1.004);
          scene.add(seg);
          disposables.push(segGeo, segMat);
        }

        const shadowGeo = new THREE.CircleGeometry(Math.max(size.x, size.y) * 0.62, 64);
        const shadowMat = new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.16 });
        const shadow = new THREE.Mesh(shadowGeo, shadowMat);
        shadow.position.z = -size.z / 2 - 0.6;
        scene.add(shadow);
        disposables.push(shadowGeo, shadowMat);

        const radius = Math.max(size.x, size.y, size.z) * 0.5 || 10;
        const dist = (radius / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2))) * 1.15;
        const dir = new THREE.Vector3(0.55, -0.65, 0.6).normalize();
        camera.position.copy(dir.multiplyScalar(dist));
        camera.near = dist / 100;
        camera.far = dist * 100;
        camera.updateProjectionMatrix();
        controls.minDistance = dist * 0.4;
        controls.maxDistance = dist * 2.5;
        controls.target.set(0, 0, 0);
        controls.update();
        setLoading(false);
      })
      .catch(() => {
        if (disposed) return;
        setError("Could not load the STL files from the API.");
        setLoading(false);
      });

    renderer.setAnimationLoop(() => {
      controls.update();
      renderer.render(scene, camera);
    });

    return () => {
      disposed = true;
      renderer.setAnimationLoop(null);
      ro.disconnect();
      controls.dispose();
      disposables.forEach((d) => d.dispose());
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [ringUrl, segmentUrl]);

  return (
    <>
      <div className="viewer-canvas" ref={hostRef} />
      {loading && !error && <div className="viewer-msg">Loading the 3D model…</div>}
      {error && <div className="viewer-msg">{error}</div>}
    </>
  );
}
