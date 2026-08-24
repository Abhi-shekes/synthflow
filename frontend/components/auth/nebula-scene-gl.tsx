"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

import { useReducedMotion } from "@/lib/motion";

/** The gas takes its colour from the field-type scale — the same categorical
 * system that colours every schema in the product, so even the one purely
 * decorative screen speaks the product's own language. */
const COOL_TOKEN = "--t-object";
const MID_TOKEN = "--t-string";
const WARM_TOKEN = "--t-enum";
const CORE_TOKEN = "--brand";
/** Motes are drawn from the wider scale, so the field reads as many types
 * of record drifting rather than one. */
const MOTE_TOKENS = [
  "--t-string",
  "--t-integer",
  "--t-float",
  "--t-enum",
  "--t-boolean",
  "--brand",
];

const MOTE_COUNT_DESKTOP = 2600;
const MOTE_COUNT_MOBILE = 1300;

/** How far the cursor may push each layer. The two differ on purpose: the
 * gas moves less than the motes in front of it, and that difference is what
 * the eye reads as depth. Both stay small for the reason `useTilt` documents
 * (lib/motion.ts) — past a modest budget a 3D flourish reads as a gimmick. */
const NEBULA_PARALLAX = 0.09;
const CAMERA_PARALLAX = 0.62;

/** The frame the still image holds under reduced motion. Chosen because the
 * warp has developed real structure by then; t=0 is a comparatively flat
 * field, and holding it would look like a broken render rather than a
 * deliberate picture. */
const STILL_TIME = 26.0;

const NEBULA_VERTEX = /* glsl */ `
  void main() {
    // The quad is authored directly in clip space, so no camera transform is
    // involved and one plane covers the viewport at every aspect ratio.
    gl_Position = vec4(position.xy, 0.0, 1.0);
  }
`;

const NEBULA_FRAGMENT = /* glsl */ `
  precision highp float;

  uniform vec2 uResolution;
  uniform float uTime;
  uniform vec2 uPointer;
  uniform vec3 uGround;
  uniform vec3 uCool;
  uniform vec3 uMid;
  uniform vec3 uWarm;
  uniform vec3 uCore;
  uniform float uDensity;

  float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
  }

  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    // Hermite interpolation — the smooth first derivative is what keeps the
    // octaves from showing their grid once they are stacked.
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
  }

  float fbm(vec2 p) {
    float value = 0.0;
    float amp = 0.5;
    // Rotating between octaves breaks up the axis alignment that otherwise
    // makes stacked value noise look like a plaid weave.
    mat2 rot = mat2(0.80, 0.60, -0.60, 0.80);
    for (int i = 0; i < 4; i++) {
      value += amp * noise(p);
      p = rot * p * 2.02;
      amp *= 0.5;
    }
    return value;
  }

  void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.y;
    uv *= 1.35;
    uv += uPointer * ${NEBULA_PARALLAX.toFixed(3)};

    float t = uTime * 0.03;

    // Domain warping. The field is not sampled at uv but at a position that
    // is itself displaced by two further noise fields — that is the whole
    // trick, and it is what turns smooth fbm into filaments, sheets and
    // voids that read as gas instead of as fog.
    vec2 q = vec2(
      fbm(uv + t),
      fbm(uv + vec2(5.2, 1.3) - t)
    );
    vec2 r = vec2(
      fbm(uv + 2.4 * q + vec2(1.7, 9.2) + t * 1.4),
      fbm(uv + 2.4 * q + vec2(8.3, 2.8) - t * 1.1)
    );
    float f = fbm(uv + 2.6 * r);

    // A ramp keyed to depth in the field, each stop gated by a smoothstep
    // rather than a raw multiply: thin gas stays cool, and the warm and core
    // hues appear only where the field is genuinely dense. Multiplying
    // instead would tint every pixel a little, which reads as one muddy
    // wash rather than as hot cores inside cold gas.
    vec3 col = uCool;
    col = mix(col, uMid, smoothstep(0.30, 0.58, f));
    col = mix(col, uWarm, smoothstep(0.56, 0.76, f));
    col = mix(col, uCore, smoothstep(0.70, 0.88, f) * 0.9);
    // A trace of the warp itself, for hue variation that does not track
    // density — without it the ramp reads as a set of concentric bands.
    col = mix(col, uMid, clamp((length(q) - 0.6) * 0.5, 0.0, 0.3));

    // Contrast the density hard enough to open real voids. Without this the
    // field never reaches zero and the frame is uniformly full of gas.
    float density = pow(smoothstep(0.20, 0.64, f), 1.1) * uDensity;

    // Wide on purpose. A tight vignette concentrates the gas dead centre,
    // which is exactly where the sign-in panel covers it — all the cost of
    // rendering a nebula and none of it visible. This only pulls the extreme
    // corners back to the ground colour, so the canvas still has no visible
    // edge against the layout around it.
    float vignette = smoothstep(1.85, 0.25, length(uv));

    gl_FragColor = vec4(mix(uGround, col, density * vignette), 1.0);
  }
`;

const MOTE_VERTEX = /* glsl */ `
  attribute float aSize;
  attribute vec3 aColor;
  attribute float aPhase;

  uniform float uTime;
  uniform float uPixelRatio;

  varying vec3 vColor;
  varying float vTwinkle;

  // A smooth, slowly-turning vector field. Sampling a field rather than
  // integrating a path is what makes this cheap enough to do for every mote
  // in the vertex shader with no CPU work and no ping-pong buffers — and
  // because the field is continuous, neighbouring motes move together the
  // way particles in a fluid do, instead of each running its own orbit.
  vec3 flow(vec3 p, float t) {
    return vec3(
      sin(p.y * 1.3 + t) + 0.5 * sin(p.z * 2.1 - t * 0.7),
      sin(p.z * 1.1 - t * 0.8) + 0.5 * sin(p.x * 1.9 + t * 0.6),
      sin(p.x * 1.5 + t * 0.6) + 0.5 * sin(p.y * 2.3 - t * 0.5)
    );
  }

  void main() {
    vColor = aColor;
    // A per-mote phase, not a shared clock, so a still frame still shows a
    // varied field of brightness rather than one flat value.
    vTwinkle = 0.55 + 0.45 * sin(uTime * 1.3 + aPhase);

    vec3 p = position + flow(position * 0.42, uTime * 0.16) * 0.72;

    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    // The depth floor stops a mote that drifts close to the camera from
    // ballooning into a blown-out disc.
    gl_PointSize = aSize * uPixelRatio * (54.0 / max(1.5, -mv.z));
    gl_Position = projectionMatrix * mv;
  }
`;

const MOTE_FRAGMENT = /* glsl */ `
  precision mediump float;

  uniform float uGlow;
  uniform float uAlpha;

  varying vec3 vColor;
  varying float vTwinkle;

  void main() {
    // A soft round dot derived from the point's own coordinates — no texture
    // upload, and it stays crisp at any device pixel ratio.
    vec2 uv = gl_PointCoord - vec2(0.5);
    float mask = 1.0 - smoothstep(0.0, 0.5, length(uv));
    if (mask <= 0.0) discard;
    float glow = pow(mask, 1.7);
    // Pushing colour past 1.0 is what gives an additively-blended mote its
    // hot centre. Under normal blending — the light theme — the same push
    // only clips to white, so uGlow drops to 1.0 there.
    gl_FragColor = vec4(vColor * glow * vTwinkle * uGlow, glow * vTwinkle * uAlpha);
  }
`;

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

/**
 * The auth pages' backdrop: a domain-warped nebula with a field of motes
 * drifting through it.
 *
 * Two passes over one canvas. The gas is a single full-screen quad whose
 * fragment shader does the warping; the motes are real 3D points in front of
 * it, advected by a smooth vector field and parallaxed harder by the cursor,
 * so moving the mouse separates the two layers in depth.
 *
 * Same lifecycle discipline as flow-field-gl.tsx: read the palette from CSS
 * custom properties so it themes for free, fail silently with no WebGL, hold
 * one representative frame under reduced motion, recover from a lost
 * context, and release every GPU resource by hand on unmount.
 */
export default function NebulaSceneGL() {
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
      // refuses). The form reads fine without the backdrop, so fail silently
      // rather than throwing behind a sign-in panel.
      return;
    }

    const styles = getComputedStyle(document.documentElement);
    const read = (token: string, fallback: string) =>
      new THREE.Color(styles.getPropertyValue(token).trim() || fallback);

    const ground = read("--ground", "#0a0d13");
    // A light theme needs markedly less gas: the same density that glows on
    // a near-black ground turns into muddy smears on a near-white one.
    const groundLuma = 0.2126 * ground.r + 0.7152 * ground.g + 0.0722 * ground.b;
    const isLight = groundLuma > 0.5;
    // Light is a second design, not an inversion (see globals.css). Gas that
    // reads as luminous on near-black reads as a dirty smear on near-white,
    // so the light theme gets a far thinner, paler version of it.
    const densityScale = isLight ? 0.3 : 1.0;

    // --- Pass 1: the gas ------------------------------------------------
    const bgScene = new THREE.Scene();
    const bgCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    const nebulaUniforms = {
      uResolution: { value: new THREE.Vector2(1, 1) },
      uTime: { value: reduced ? STILL_TIME : 0 },
      uPointer: { value: new THREE.Vector2(0, 0) },
      uGround: { value: ground },
      uCool: { value: read(COOL_TOKEN, "#8a93ad") },
      uMid: { value: read(MID_TOKEN, "#63b3d9") },
      uWarm: { value: read(WARM_TOKEN, "#e8925c") },
      uCore: { value: read(CORE_TOKEN, "#e7b45c") },
      uDensity: { value: densityScale },
    };
    const nebulaMaterial = new THREE.ShaderMaterial({
      uniforms: nebulaUniforms,
      vertexShader: NEBULA_VERTEX,
      fragmentShader: NEBULA_FRAGMENT,
      depthTest: false,
      depthWrite: false,
    });
    const nebulaGeometry = new THREE.PlaneGeometry(2, 2);
    const nebulaQuad = new THREE.Mesh(nebulaGeometry, nebulaMaterial);
    nebulaQuad.frustumCulled = false;
    bgScene.add(nebulaQuad);

    // --- Pass 2: the motes ----------------------------------------------
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(46, 1, 0.1, 60);
    const cameraRest = new THREE.Vector3(0, 0, 6.4);
    camera.position.copy(cameraRest);
    camera.lookAt(0, 0, 0);

    const motePalette = MOTE_TOKENS.map((t) => read(t, "#63b3d9"));
    const tintTarget = isLight ? read("--ink-faint", "#8a93a3") : new THREE.Color(1, 1, 1);
    const moteCount =
      host.getBoundingClientRect().width < 640 ? MOTE_COUNT_MOBILE : MOTE_COUNT_DESKTOP;

    const positions = new Float32Array(moteCount * 3);
    const colors = new Float32Array(moteCount * 3);
    const sizes = new Float32Array(moteCount);
    const phases = new Float32Array(moteCount);

    for (let i = 0; i < moteCount; i += 1) {
      const i3 = i * 3;
      positions[i3] = (Math.random() - 0.5) * 15;
      positions[i3 + 1] = (Math.random() - 0.5) * 9;
      // Biased toward the far side so the field has depth to parallax
      // against rather than sitting in one plane.
      positions[i3 + 2] = -5.5 + Math.pow(Math.random(), 0.7) * 8.5;

      // Most motes sit close to the tint target with only a trace of their
      // hue; a minority keep it. An evenly-saturated field reads as confetti,
      // not as a star field, because real point sources desaturate as they
      // dim. The target is white on dark — motes are light sources — and the
      // ink colour on light, where they are specks of pigment instead.
      const hue = motePalette[i % motePalette.length];
      const tint = Math.pow(Math.random(), 2.2);
      colors[i3] = hue.r + (tintTarget.r - hue.r) * (1 - tint);
      colors[i3 + 1] = hue.g + (tintTarget.g - hue.g) * (1 - tint);
      colors[i3 + 2] = hue.b + (tintTarget.b - hue.b) * (1 - tint);

      // A power law, so the field is mostly faint specks with a handful of
      // bright ones — a uniform distribution gives every mote the same
      // visual weight and flattens the depth the sizes are meant to imply.
      sizes[i] = (0.5 + Math.pow(Math.random(), 3.0) * 3.4) * (isLight ? 0.62 : 1);
      phases[i] = Math.random() * Math.PI * 2;
    }

    const moteGeometry = new THREE.BufferGeometry();
    moteGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    moteGeometry.setAttribute("aColor", new THREE.BufferAttribute(colors, 3));
    moteGeometry.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));
    moteGeometry.setAttribute("aPhase", new THREE.BufferAttribute(phases, 1));

    const moteUniforms = {
      uTime: { value: reduced ? STILL_TIME : 0 },
      uPixelRatio: { value: 1 },
      uGlow: { value: isLight ? 1.0 : 1.6 },
      // On dark a mote is a light source and can sit at full strength. On
      // light it is a speck of pigment on paper, and anything near full
      // strength reads as dirt on the page rather than as atmosphere.
      uAlpha: { value: isLight ? 0.3 : 1.0 },
    };
    const moteMaterial = new THREE.ShaderMaterial({
      uniforms: moteUniforms,
      vertexShader: MOTE_VERTEX,
      fragmentShader: MOTE_FRAGMENT,
      transparent: true,
      depthTest: false,
      depthWrite: false,
      // Additive is what makes a mote glow, but it can only ever brighten —
      // on a near-white ground every mote would blow out and vanish. The
      // light theme composites them normally instead, as dark specks.
      blending: isLight ? THREE.NormalBlending : THREE.AdditiveBlending,
    });
    const motes = new THREE.Points(moteGeometry, moteMaterial);
    // The flow field moves motes well outside their authored bounds, which
    // three's culler does not know about — it would decide the whole system
    // had left the frustum and skip drawing it.
    motes.frustumCulled = false;
    scene.add(motes);

    const layout = () => {
      const box = host.getBoundingClientRect();
      const width = Math.max(1, box.width);
      const height = Math.max(1, box.height);
      // Capped harder than the other scenes: this is a per-pixel raymarch-
      // shaped shader, so its cost scales with the square of this number
      // while the gas is soft enough that the extra samples do not show.
      const ratio = Math.min(window.devicePixelRatio || 1, 1.25);
      renderer.setPixelRatio(ratio);
      renderer.setSize(width, height, false);
      nebulaUniforms.uResolution.value.set(width * ratio, height * ratio);
      moteUniforms.uPixelRatio.value = ratio;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };

    renderer.domElement.setAttribute("aria-hidden", "true");
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    renderer.domElement.style.display = "block";
    host.appendChild(renderer.domElement);
    layout();

    // Both passes share one canvas, so the second must not wipe the first.
    renderer.autoClear = false;
    const draw = () => {
      renderer.clear();
      renderer.render(bgScene, bgCamera);
      renderer.render(scene, camera);
    };

    let targetX = 0;
    let targetY = 0;
    let pointerX = 0;
    let pointerY = 0;

    const onPointerMove = (event: PointerEvent) => {
      const box = host.getBoundingClientRect();
      targetX = clamp(((event.clientX - box.left) / box.width - 0.5) * 2, -1, 1);
      targetY = clamp(((event.clientY - box.top) / box.height - 0.5) * 2, -1, 1);
    };

    let frame = 0;
    // Not THREE.Clock — it is deprecated, and a timestamp difference is all
    // this needs. The clamp covers a backgrounded tab or a restored context,
    // where the gap since the last frame can be arbitrarily large and would
    // otherwise jump the whole scene forward in one step.
    let last = performance.now();

    const render = () => {
      const now = performance.now();
      const dt = Math.min((now - last) / 1000, 0.1);
      last = now;
      const lerp = Math.min(1, dt * 2.4);
      pointerX += (targetX - pointerX) * lerp;
      pointerY += (targetY - pointerY) * lerp;

      nebulaUniforms.uPointer.value.set(pointerX, -pointerY);
      camera.position.x = cameraRest.x + pointerX * CAMERA_PARALLAX;
      camera.position.y = cameraRest.y - pointerY * CAMERA_PARALLAX * 0.6;
      camera.lookAt(0, 0, 0);

      nebulaUniforms.uTime.value += dt;
      moteUniforms.uTime.value += dt;

      draw();
      frame = requestAnimationFrame(render);
    };

    if (reduced) {
      // A still frame of the same picture at a developed moment — not the
      // animation paused at zero, which is a comparatively flat field.
      draw();
    } else {
      window.addEventListener("pointermove", onPointerMove, { passive: true });
      frame = requestAnimationFrame(render);
    }

    const onResize = () => {
      layout();
      if (reduced) draw();
    };
    window.addEventListener("resize", onResize);

    // A lost context otherwise leaves a blank canvas and a dead rAF loop.
    const onContextLost = (event: Event) => {
      event.preventDefault();
      cancelAnimationFrame(frame);
    };
    const onContextRestored = () => {
      layout();
      if (reduced) draw();
      else {
        last = performance.now();
        frame = requestAnimationFrame(render);
      }
    };
    renderer.domElement.addEventListener("webglcontextlost", onContextLost);
    renderer.domElement.addEventListener("webglcontextrestored", onContextRestored);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("pointermove", onPointerMove);
      renderer.domElement.removeEventListener("webglcontextlost", onContextLost);
      renderer.domElement.removeEventListener("webglcontextrestored", onContextRestored);
      // GPU memory is not garbage collected — every buffer, program and the
      // renderer itself has to be released by hand, or navigating away leaks
      // the whole scene.
      nebulaGeometry.dispose();
      nebulaMaterial.dispose();
      moteGeometry.dispose();
      moteMaterial.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [reduced]);

  return <div ref={hostRef} aria-hidden className="absolute inset-0 h-full w-full" />;
}
