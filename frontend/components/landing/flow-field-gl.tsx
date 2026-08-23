"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

import { useReducedMotion } from "@/lib/motion";

/** Particles take their colour from the field-type scale, so even the one
 * decorative moment speaks the product's own language. Read from CSS at mount
 * so the field follows the viewer's theme. */
const HUE_TOKENS = ["--t-string", "--t-float", "--t-enum", "--t-object", "--t-integer"];

const LANES = 5;
const COUNT = 2400;

const VERTEX = /* glsl */ `
  attribute float aOffset;
  attribute float aLane;
  attribute float aSpeed;
  attribute float aSize;
  attribute vec3 aColor;

  uniform float uTime;
  uniform float uWidth;
  uniform float uHeight;
  uniform float uPixelRatio;

  varying vec3 vColor;
  varying float vAlpha;

  void main() {
    // The whole animation happens here rather than in a per-frame JS loop:
    // position is a pure function of time, so the CPU uploads nothing after
    // the first frame no matter how many particles there are.
    float progress = fract(aOffset + uTime * aSpeed);
    float x = progress * uWidth;
    float y = uHeight * (0.22 + (aLane / float(${LANES - 1})) * 0.56);

    // Fade in and out at the edges so records appear to enter and leave the
    // pipeline instead of visibly wrapping around.
    float edge = min(progress / 0.12, (1.0 - progress) / 0.12);
    vAlpha = clamp(edge, 0.0, 1.0) * 0.9;
    vColor = aColor;

    vec4 mv = modelViewMatrix * vec4(x, y, 0.0, 1.0);
    gl_PointSize = aSize * uPixelRatio;
    gl_Position = projectionMatrix * mv;
  }
`;

const FRAGMENT = /* glsl */ `
  precision mediump float;

  varying vec3 vColor;
  varying float vAlpha;

  void main() {
    // A soft round dot from the point's own coordinates — no texture upload,
    // and it stays crisp at any device pixel ratio.
    vec2 uv = gl_PointCoord - vec2(0.5);
    float dist = length(uv);
    float mask = 1.0 - smoothstep(0.35, 0.5, dist);
    if (mask <= 0.0) discard;
    gl_FragColor = vec4(vColor, vAlpha * mask);
  }
`;

/**
 * Records flowing left to right through the pipeline, in WebGL.
 *
 * The product's one decorative flourish, fenced off on the logged-out page —
 * inside the tool, motion has to be informational.
 *
 * Loaded only through `flow-field.tsx`'s dynamic import, so `three` lands in
 * its own chunk and never reaches the authenticated app bundle.
 */
export default function FlowFieldGL() {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const reduced = useReducedMotion();

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: false });
    } catch {
      // No WebGL context (a locked-down browser, a software renderer that
      // refuses). The page reads fine without the field, so fail silently
      // rather than throwing under a hero heading.
      return;
    }

    const styles = getComputedStyle(document.documentElement);
    const palette = HUE_TOKENS.map((token) =>
      new THREE.Color(styles.getPropertyValue(token).trim() || "#63b3d9")
    );

    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(0, 1, 1, 0, -1, 1);

    const offsets = new Float32Array(COUNT);
    const lanes = new Float32Array(COUNT);
    const speeds = new Float32Array(COUNT);
    const sizes = new Float32Array(COUNT);
    const colors = new Float32Array(COUNT * 3);

    for (let i = 0; i < COUNT; i += 1) {
      const lane = Math.floor(Math.random() * LANES);
      offsets[i] = Math.random();
      lanes[i] = lane;
      speeds[i] = 0.012 + Math.random() * 0.05;
      sizes[i] = 1.6 + Math.random() * 2.6;
      const hue = palette[lane % palette.length];
      colors[i * 3] = hue.r;
      colors[i * 3 + 1] = hue.g;
      colors[i * 3 + 2] = hue.b;
    }

    const geometry = new THREE.BufferGeometry();
    // `position` is required by three's shader plumbing but unused — the vertex
    // shader derives x and y from the attributes above.
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(COUNT * 3), 3));
    geometry.setAttribute("aOffset", new THREE.BufferAttribute(offsets, 1));
    geometry.setAttribute("aLane", new THREE.BufferAttribute(lanes, 1));
    geometry.setAttribute("aSpeed", new THREE.BufferAttribute(speeds, 1));
    geometry.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));
    geometry.setAttribute("aColor", new THREE.BufferAttribute(colors, 3));

    const uniforms = {
      uTime: { value: 0 },
      uWidth: { value: 1 },
      uHeight: { value: 1 },
      uPixelRatio: { value: 1 },
    };

    const material = new THREE.ShaderMaterial({
      uniforms,
      vertexShader: VERTEX,
      fragmentShader: FRAGMENT,
      transparent: true,
      depthTest: false,
      depthWrite: false,
      blending: THREE.NormalBlending,
    });

    const points = new THREE.Points(geometry, material);
    // Frustum culling uses `position`, which is all zeros here, so three would
    // decide the whole system is off-screen and skip drawing it.
    points.frustumCulled = false;
    scene.add(points);

    // The lanes themselves: faint rails the particles ride.
    const railGeometry = new THREE.BufferGeometry();
    const railPositions = new Float32Array(LANES * 2 * 3);
    const railColors = new Float32Array(LANES * 2 * 3);
    railGeometry.setAttribute("position", new THREE.BufferAttribute(railPositions, 3));
    railGeometry.setAttribute("color", new THREE.BufferAttribute(railColors, 3));
    const rails = new THREE.LineSegments(
      railGeometry,
      new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.16 })
    );
    rails.frustumCulled = false;
    scene.add(rails);

    let width = 0;
    let height = 0;

    const layout = () => {
      const box = host.getBoundingClientRect();
      width = Math.max(1, box.width);
      height = Math.max(1, box.height);
      const ratio = Math.min(window.devicePixelRatio || 1, 2);

      renderer.setPixelRatio(ratio);
      renderer.setSize(width, height, false);

      camera.left = 0;
      camera.right = width;
      camera.top = height;
      camera.bottom = 0;
      camera.updateProjectionMatrix();

      uniforms.uWidth.value = width;
      uniforms.uHeight.value = height;
      uniforms.uPixelRatio.value = ratio;

      for (let lane = 0; lane < LANES; lane += 1) {
        const y = height * (0.22 + (lane / (LANES - 1)) * 0.56);
        const base = lane * 6;
        railPositions[base] = 0;
        railPositions[base + 1] = y;
        railPositions[base + 3] = width;
        railPositions[base + 4] = y;
        const hue = palette[lane % palette.length];
        for (const slot of [base, base + 3]) {
          railColors[slot] = hue.r;
          railColors[slot + 1] = hue.g;
          railColors[slot + 2] = hue.b;
        }
      }
      railGeometry.attributes.position.needsUpdate = true;
      railGeometry.attributes.color.needsUpdate = true;
    };

    renderer.domElement.setAttribute("aria-hidden", "true");
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    renderer.domElement.style.display = "block";
    host.appendChild(renderer.domElement);

    layout();

    let frame = 0;
    const clock = new THREE.Clock();

    const render = () => {
      uniforms.uTime.value = clock.getElapsedTime();
      renderer.render(scene, camera);
      frame = requestAnimationFrame(render);
    };

    if (reduced) {
      // A still frame of the same picture, not the animation paused at zero:
      // particles are already spread along every lane by their random offsets.
      uniforms.uTime.value = 0;
      renderer.render(scene, camera);
    } else {
      frame = requestAnimationFrame(render);
    }

    const onResize = () => {
      layout();
      if (reduced) renderer.render(scene, camera);
    };
    window.addEventListener("resize", onResize);

    // A lost context leaves a blank canvas and a dead rAF loop otherwise.
    const onContextLost = (event: Event) => {
      event.preventDefault();
      cancelAnimationFrame(frame);
    };
    const onContextRestored = () => {
      layout();
      if (!reduced) frame = requestAnimationFrame(render);
    };
    renderer.domElement.addEventListener("webglcontextlost", onContextLost);
    renderer.domElement.addEventListener("webglcontextrestored", onContextRestored);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", onResize);
      renderer.domElement.removeEventListener("webglcontextlost", onContextLost);
      renderer.domElement.removeEventListener("webglcontextrestored", onContextRestored);
      // GPU memory is not garbage collected — every buffer and program has to
      // be released by hand, or navigating away leaks the whole scene.
      geometry.dispose();
      material.dispose();
      railGeometry.dispose();
      (rails.material as THREE.Material).dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [reduced]);

  return <div ref={hostRef} aria-hidden className="absolute inset-0 h-full w-full" />;
}
