import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { LABEL_ART_DATA_URL, LOGO_PREVIEW_DATA_URL } from './assets_bundle.js';

const W = 160;
const H = 144;

export const LCD_PALETTES = {
  dmg: {
    name: 'DMG Olive STN',
    shades: [
      [0x9b / 255, 0xbc / 255, 0x0f / 255],
      [0x7b / 255, 0x9c / 255, 0x12 / 255],
      [0x30 / 255, 0x62 / 255, 0x30 / 255],
      [0x0f / 255, 0x30 / 255, 0x12 / 255],
    ],
    css: ['#9bbc0f', '#7b9c12', '#306230', '#0f3012'],
    backColor: 0x6d7d18,
  },
  paper: {
    name: 'Halftone Paper',
    shades: [
      [0xf3 / 255, 0xef / 255, 0xe5 / 255],
      [0xa9 / 255, 0xa3 / 255, 0x94 / 255],
      [0x5d / 255, 0x59 / 255, 0x4f / 255],
      [0x1a / 255, 0x18 / 255, 0x14 / 255],
    ],
    css: ['#f3efe5', '#a9a394', '#5d594f', '#1a1814'],
    backColor: 0xc8c2b2,
  },
  pocket: {
    name: 'Pocket Crisp',
    shades: [
      [0xe0 / 255, 0xe4 / 255, 0xd8 / 255],
      [0x9d / 255, 0xa3 / 255, 0x94 / 255],
      [0x52 / 255, 0x58 / 255, 0x4e / 255],
      [0x14 / 255, 0x17 / 255, 0x14 / 255],
    ],
    css: ['#e0e4d8', '#9da394', '#52584e', '#141714'],
    backColor: 0xb2b8a8,
  },
};

export const CAMERA_PRESETS = {
  desk_hero: {
    id: 'desk_hero',
    label: '1 · Desk Hero',
    target: [0, -6.5, 2],
    dist: 468,
    rx: -0.07,
    ry: 0.21,
    rz: 0.0,
    exploded: 0,
  },
  uncropped_lcd: {
    id: 'uncropped_lcd',
    label: '2 · Uncropped LCD',
    target: [0, 29.5, 10],
    dist: 215,
    rx: 0.0,
    ry: 0.0,
    rz: 0.0,
    exploded: 0,
  },
  insert_cart: {
    id: 'insert_cart',
    label: '3 · Insert Cart',
    target: [0, 18, -2],
    dist: 390,
    rx: -0.24,
    ry: -0.38,
    rz: 0.0,
    exploded: 0,
  },
  exploded_pcb: {
    id: 'exploded_pcb',
    label: '4 · Exploded PCB X-Ray',
    target: [2, 10, -2],
    dist: 455,
    rx: -0.16,
    ry: 0.42,
    rz: 0.0,
    exploded: 1,
  },
};

function makeRoundedRectShape(w, h, r, ox = 0, oy = 0) {
  const s = new THREE.Shape();
  const hw = w / 2, hh = h / 2;
  const rad = Math.min(r, hw, hh);
  s.moveTo(ox - hw + rad, oy - hh);
  s.lineTo(ox + hw - rad, oy - hh);
  s.quadraticCurveTo(ox + hw, oy - hh, ox + hw, oy - hh + rad);
  s.lineTo(ox + hw, oy + hh - rad);
  s.quadraticCurveTo(ox + hw, oy + hh, ox + hw - rad, oy + hh);
  s.lineTo(ox - hw + rad, oy + hh);
  s.quadraticCurveTo(ox - hw, oy + hh, ox - hw, oy + hh - rad);
  s.lineTo(ox - hw, oy - hh + rad);
  s.quadraticCurveTo(ox - hw, oy - hh, ox - hw + rad, oy - hh);
  return s;
}

function makeDmgBodyShape(w, h, rNorm, rBR) {
  const s = new THREE.Shape();
  const hw = w / 2, hh = h / 2;
  s.moveTo(-hw + rNorm, -hh);
  s.lineTo(hw - rBR, -hh);
  s.quadraticCurveTo(hw, -hh, hw, -hh + rBR);
  s.lineTo(hw, hh - rNorm);
  s.quadraticCurveTo(hw, hh, hw - rNorm, hh);
  s.lineTo(-hw + rNorm, hh);
  s.quadraticCurveTo(-hw, hh, -hw, hh - rNorm);
  s.lineTo(-hw, -hh + rNorm);
  s.quadraticCurveTo(-hw, -hh, -hw + rNorm, -hh);
  return s;
}

function addTriplanarGrain(material, scale = 0.72, bumpStrength = 0.024, roughVar = 0.05) {
  material.customProgramCacheKey = () => `triplanar_${scale}_${bumpStrength}_${roughVar}`;
  material.onBeforeCompile = (shader) => {
    shader.uniforms.uGrainScale = { value: scale };
    shader.uniforms.uGrainStrength = { value: bumpStrength };
    shader.uniforms.uRoughVar = { value: roughVar };
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vLocalPos;\nvarying vec3 vLocalNorm;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvLocalPos = position;\nvLocalNorm = normal;');
    shader.fragmentShader = shader.fragmentShader
      .replace(
        '#include <common>',
        `#include <common>
        varying vec3 vLocalPos;
        varying vec3 vLocalNorm;
        uniform float uGrainScale;
        uniform float uGrainStrength;
        uniform float uRoughVar;
        float hash31(vec3 p) {
          p = fract(p * vec3(443.897, 441.423, 437.195));
          p += dot(p, p.yzx + 19.19);
          return fract((p.x + p.y) * p.z);
        }
        float vnoise3(vec3 p) {
          vec3 i = floor(p);
          vec3 f = fract(p);
          f = f * f * (3.0 - 2.0 * f);
          return mix(
            mix(mix(hash31(i), hash31(i + vec3(1,0,0)), f.x),
                mix(hash31(i + vec3(0,1,0)), hash31(i + vec3(1,1,0)), f.x), f.y),
            mix(mix(hash31(i + vec3(0,0,1)), hash31(i + vec3(1,0,1)), f.x),
                mix(hash31(i + vec3(0,1,1)), hash31(i + vec3(1,1,1)), f.x), f.y),
            f.z);
        }
        float absPebble(vec3 p) {
          vec3 q = p * uGrainScale;
          return 0.65 * vnoise3(q * 3.1) + 0.35 * vnoise3(q * 7.4);
        }`
      )
      .replace(
        '#include <roughnessmap_fragment>',
        `#include <roughnessmap_fragment>
        float gVal = absPebble(vLocalPos);
        roughnessFactor = clamp(roughnessFactor + (gVal - 0.5) * uRoughVar, 0.06, 0.96);`
      )
      .replace(
        '#include <normal_fragment_maps>',
        `#include <normal_fragment_maps>
        float eps = 0.08;
        float h0 = absPebble(vLocalPos);
        vec3 dH = vec3(
          absPebble(vLocalPos + vec3(eps, 0.0, 0.0)) - h0,
          absPebble(vLocalPos + vec3(0.0, eps, 0.0)) - h0,
          absPebble(vLocalPos + vec3(0.0, 0.0, eps)) - h0
        ) / eps;
        normal = normalize(normal - dH * uGrainStrength);`
      );
  };
}

function createBezelOverlayTexture(anisotropy = 8) {
  // Renders the authentic DMG-01 Screen Lens Bezel graphics onto a transparent overlay plane
  // Bezel dimensions: 77mm wide x 57mm tall (centered at y = 31.8)
  // Screen opening: 49mm wide x 44.5mm tall (centered at x = 0, y = 31.8 -> local y = 0)
  const cw = 1540, ch = 1140; // 20 px per mm
  const c = document.createElement('canvas');
  c.width = cw;
  c.height = ch;
  const ctx = c.getContext('2d');
  ctx.clearRect(0, 0, cw, ch);

  const mm = 20;
  const cx = cw / 2;
  const cy = ch / 2;

  // Screen cutout in local bezel coords: [-24.5, +24.5] x [-22.25, +22.25] mm
  // Top border region is y from -28.5mm to -22.25mm (in canvas Y, top is 0)
  // Wait: in canvas coords, y=0 is TOP (+28.5mm in 3D), y=ch is BOTTOM (-28.5mm in 3D)
  const toX = (xMm) => cx + xMm * mm;
  const toY = (yMm) => cy - yMm * mm;

  // Outer frame stripes wrapping around top header & sides of bezel
  // Top header stripes at yMm = +25.8mm (magenta) and +24.6mm (navy)
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  // Left and Right segment of top stripes (leaving gap for "DOT MATRIX WITH STEREO SOUND" from x = -11mm to +33mm)
  const drawStripe = (yMm, color, lineWidthMm) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidthMm * mm;
    // Left top bar
    ctx.beginPath();
    ctx.moveTo(toX(-34.5), toY(yMm));
    ctx.lineTo(toX(-11.5), toY(yMm));
    ctx.stroke();
    // Right top bar
    ctx.beginPath();
    ctx.moveTo(toX(31.2), toY(yMm));
    ctx.lineTo(toX(34.5), toY(yMm));
    ctx.stroke();
  };

  drawStripe(25.9, '#9f224a', 0.65); // Authentic DMG Crimson-Magenta stripe
  drawStripe(24.5, '#27367d', 0.65); // Authentic DMG Navy-Blue stripe

  // "DOT MATRIX WITH STEREO SOUND" text in top header
  ctx.fillStyle = '#c8ccd4';
  ctx.font = `700 ${Math.round(1.62 * mm)}px "Inter", "Helvetica Neue", Arial, sans-serif`;
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'left';
  ctx.fillText('DOT MATRIX WITH STEREO SOUND', toX(-10.4), toY(25.2));

  // Left bezel column: "BATTERY" label + small battery icon below the red LED at (-31, +1.5mm local)
  ctx.fillStyle = '#c4c8d0';
  ctx.font = `700 ${Math.round(1.42 * mm)}px "Inter", "Helvetica Neue", Arial, sans-serif`;
  ctx.textAlign = 'center';
  ctx.fillText('BATTERY', toX(-31.0), toY(-4.8));

  // Subtle decorative dual lines left of LED
  ctx.strokeStyle = '#9f224a';
  ctx.lineWidth = 0.45 * mm;
  ctx.beginPath();
  ctx.moveTo(toX(-35.2), toY(8.5));
  ctx.lineTo(toX(-27.2), toY(8.5));
  ctx.stroke();
  ctx.strokeStyle = '#27367d';
  ctx.beginPath();
  ctx.moveTo(toX(-35.2), toY(7.4));
  ctx.lineTo(toX(-27.2), toY(7.4));
  ctx.stroke();

  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = anisotropy;
  tex.needsUpdate = true;
  return tex;
}

function createFrontSilkscreenTexture(anisotropy = 8) {
  // Covers front body below and above bezel: 86mm wide x 144mm tall (centered at 0,0)
  const mm = 18;
  const cw = 86 * mm;
  const ch = 144 * mm;
  const c = document.createElement('canvas');
  c.width = cw;
  c.height = ch;
  const ctx = c.getContext('2d');
  ctx.clearRect(0, 0, cw, ch);

  const cx = cw / 2;
  const cy = ch / 2;
  const toX = (xMm) => cx + xMm * mm;
  const toY = (yMm) => cy - yMm * mm;

  const navy = '#1d2861';
  const molded = 'rgba(72, 68, 60, 0.58)';

  // 1. Top "◀ OFF•ON ▶" molded engraving inside top-left pill (x = -27, y = 66.2)
  ctx.fillStyle = molded;
  ctx.font = `800 ${Math.round(1.65 * mm)}px "Inter", Arial, sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText('◀ OFF•ON ▶', toX(-25.5), toY(66.2));

  // 2. Classic Navy Badge directly below bezel left corner (x = -38.5, y = -0.3)
  ctx.save();
  ctx.fillStyle = navy;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'alphabetic';
  ctx.font = `900 ${Math.round(2.75 * mm)}px "Georgia", serif`;
  ctx.fillText('DMG-01', toX(-38.2), toY(-0.5));
  ctx.font = `italic 800 ${Math.round(3.55 * mm)}px "Inter", "Helvetica Neue", Arial, sans-serif`;
  ctx.fillText('GAME BOY', toX(-20.2), toY(-0.4));
  ctx.font = `700 ${Math.round(1.45 * mm)}px "JetBrains Mono", monospace`;
  ctx.fillStyle = 'rgba(29, 40, 97, 0.78)';
  ctx.fillText('TM · SM83 64K STUDIO', toX(6.5), toY(-0.5));
  ctx.restore();

  // 3. Angled "B" and "A" labels below the magenta buttons
  // B is at (16.2, -26.5), A is at (30.2, -19.8), button tilt is -25 deg
  const drawAngledLabel = (xMm, yMm, text, sizeMm = 3.2, angleDeg = -25) => {
    ctx.save();
    ctx.translate(toX(xMm), toY(yMm));
    ctx.rotate((angleDeg * Math.PI) / 180);
    ctx.fillStyle = navy;
    ctx.font = `800 ${Math.round(sizeMm * mm)}px "Inter", "Helvetica Neue", Arial, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, 0, 0);
    ctx.restore();
  };

  drawAngledLabel(20.0, -34.2, 'B', 3.4, -25);
  drawAngledLabel(34.0, -27.5, 'A', 3.4, -25);

  // 4. Angled "SELECT" and "START" labels below the silicone pills
  // SELECT is at (-10.8, -48.5), START is at (3.2, -48.5)
  drawAngledLabel(-9.0, -53.2, 'SELECT', 2.05, -25);
  drawAngledLabel(5.0, -53.2, 'START', 2.05, -25);

  // 5. Subtle D-Pad directional triangles around (-23.5, -23.0)
  ctx.fillStyle = molded;
  const dpx = -23.5, dpy = -23.0;
  const tri = (tx, ty, rot) => {
    ctx.save();
    ctx.translate(toX(tx), toY(ty));
    ctx.rotate(rot);
    ctx.beginPath();
    ctx.moveTo(0, -1.1 * mm);
    ctx.lineTo(0.95 * mm, 0.8 * mm);
    ctx.lineTo(-0.95 * mm, 0.8 * mm);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  };
  tri(dpx, dpy + 15.2, 0);
  tri(dpx, dpy - 15.2, Math.PI);
  tri(dpx - 15.2, dpy, -Math.PI / 2);
  tri(dpx + 15.2, dpy, Math.PI / 2);

  // 6. Bottom "PHONES 🎧" molded engraving at (0, -67.2)
  ctx.fillStyle = molded;
  ctx.font = `800 ${Math.round(1.55 * mm)}px "Inter", Arial, sans-serif`;
  ctx.textAlign = 'center';
  ctx.fillText('(( PHONES ))', toX(0), toY(-67.2));

  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = anisotropy;
  tex.needsUpdate = true;
  return tex;
}

function createCartridgeLabelTexture(anisotropy = 8, artImage = null, logoImage = null) {
  const cw = 920, ch = 760;
  const c = document.createElement('canvas');
  c.width = cw;
  c.height = ch;
  const ctx = c.getContext('2d');

  // Warm archival paper card base
  ctx.fillStyle = '#ece6d8';
  ctx.fillRect(0, 0, cw, ch);

  // Outer lithographic ink border
  ctx.strokeStyle = '#1b1916';
  ctx.lineWidth = 10;
  ctx.strokeRect(18, 18, cw - 36, ch - 36);

  // Left metallic magenta/navy Game Boy Pak sidebar
  ctx.fillStyle = '#232d66';
  ctx.fillRect(24, 24, 108, ch - 48);
  ctx.fillStyle = '#9b224b';
  ctx.fillRect(132, 24, 16, ch - 48);

  // Vertical sidebar text
  ctx.save();
  ctx.translate(78, ch / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillStyle = '#f3efe5';
  ctx.font = '800 34px "Inter", Arial, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText('DMG-01 GAME PAK · 64 KiB', 0, 0);
  ctx.restore();

  // Top header banner
  ctx.fillStyle = '#1a1814';
  ctx.fillRect(164, 38, cw - 202, 74);
  ctx.fillStyle = '#f3efe5';
  ctx.font = '800 30px "JetBrains Mono", monospace';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillText('ORIGINAL SM83 ROM · MBC5 + SRAM', 186, 75);

  // Main Title "HALFTONE"
  ctx.fillStyle = '#181613';
  ctx.font = '900 96px "Inter", "Helvetica Neue", Arial, sans-serif';
  ctx.fillText('HALFTONE', 176, 212);

  // Subtitle
  ctx.fillStyle = '#5d594f';
  ctx.font = '700 28px "JetBrains Mono", monospace';
  ctx.fillText('8 PLATES · B-BUTTON INK POLARITY · 59.73 HZ', 180, 266);

  // Draw halftone dot gradient / art band in the middle
  ctx.fillStyle = '#1a1814';
  ctx.fillRect(176, 300, cw - 216, 290);

  if (artImage) {
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(artImage, 186, 310, 400, 270);
  } else {
    // Procedural halftone bridge scene
    for (let y = 0; y < 18; y++) {
      for (let x = 0; x < 42; x++) {
        const r = ((x + y) % 3 === 0) ? 5 : 2.5;
        ctx.fillStyle = x < 21 ? '#9bbc0f' : '#f3efe5';
        ctx.beginPath();
        ctx.arc(200 + x * 15, 326 + y * 15, r, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  // Right badge inside art box
  ctx.fillStyle = '#f3efe5';
  ctx.fillRect(606, 324, 250, 242);
  ctx.fillStyle = '#1a1814';
  ctx.font = '800 24px "JetBrains Mono", monospace';
  ctx.fillText('SHA-256 VERIFIED', 624, 362);
  ctx.font = '700 22px "JetBrains Mono", monospace';
  ctx.fillStyle = '#9b224b';
  ctx.fillText('HDR CHK: 0xE4 OK', 624, 400);
  ctx.fillStyle = '#232d66';
  ctx.fillText('GLB CHK: 0x9062', 624, 434);
  ctx.fillStyle = '#1a1814';
  ctx.fillText('4 × 16K BANKS', 624, 472);
  ctx.fillText('8K BATTERY SAV', 624, 506);
  ctx.fillText('0 LAG / 8060 FR', 624, 540);

  // Footer
  ctx.fillStyle = '#1a1814';
  ctx.font = '800 28px "JetBrains Mono", monospace';
  ctx.fillText('MODEL NO. DMG-HT-USA', 178, 668);
  ctx.textAlign = 'right';
  ctx.fillText('MADE IN CODE · 2026', cw - 44, 668);

  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = anisotropy;
  tex.needsUpdate = true;
  return tex;
}

function createMotherboardPcbTexture(anisotropy = 8) {
  // High-detail DMG-CPU-06 emerald solder-mask PCB with gold traces & silkscreen
  const cw = 1024, ch = 1680;
  const c = document.createElement('canvas');
  c.width = cw;
  c.height = ch;
  const ctx = c.getContext('2d');

  // Deep emerald solder mask
  const grad = ctx.createLinearGradient(0, 0, cw, ch);
  grad.addColorStop(0, '#0c4f2c');
  grad.addColorStop(0.5, '#093f22');
  grad.addColorStop(1, '#07331b');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, cw, ch);

  // Copper/gold ground plane regions
  ctx.fillStyle = 'rgba(28, 120, 68, 0.38)';
  ctx.fillRect(48, 48, cw - 96, ch - 96);

  // Gold-plated button contact pads (D-Pad on left, A/B on right, Start/Select below)
  const drawCarbonContactPad = (x, y, r) => {
    ctx.fillStyle = '#d8a938';
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
    // Interlocking comb fingers
    ctx.strokeStyle = '#141816';
    ctx.lineWidth = 4;
    for (let dy = -r * 0.65; dy <= r * 0.65; dy += 8) {
      ctx.beginPath();
      ctx.moveTo(x - r * 0.7, y + dy);
      ctx.lineTo(x + r * 0.7, y + dy);
      ctx.stroke();
    }
  };

  // D-Pad contacts around (245, 1110)
  drawCarbonContactPad(245, 1020, 38);
  drawCarbonContactPad(245, 1200, 38);
  drawCarbonContactPad(155, 1110, 38);
  drawCarbonContactPad(335, 1110, 38);

  // B and A contacts
  drawCarbonContactPad(705, 1150, 44);
  drawCarbonContactPad(865, 1070, 44);

  // Copper bus traces across the board
  ctx.strokeStyle = '#389e63';
  ctx.lineWidth = 3;
  for (let i = 0; i < 36; i++) {
    const x0 = 140 + i * 21;
    ctx.beginPath();
    ctx.moveTo(x0, 140);
    ctx.lineTo(x0, 460 + (i % 5) * 35);
    ctx.lineTo(x0 + ((i % 2 === 0) ? 45 : -45), 620 + (i % 7) * 40);
    ctx.lineTo(x0, 960);
    ctx.stroke();
  }

  // Gold via holes
  ctx.fillStyle = '#deb146';
  for (let y = 120; y < ch - 120; y += 64) {
    for (let x = 90; x < cw - 90; x += 64) {
      if ((x + y) % 128 === 0) {
        ctx.beginPath();
        ctx.arc(x, y, 5.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#072212';
        ctx.beginPath();
        ctx.arc(x, y, 2.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#deb146';
      }
    }
  }

  // White PCB silkscreen markings
  ctx.strokeStyle = 'rgba(240, 244, 236, 0.85)';
  ctx.fillStyle = 'rgba(240, 244, 236, 0.9)';
  ctx.lineWidth = 3;
  ctx.font = '700 24px "JetBrains Mono", monospace';
  ctx.fillText('DMG-CPU-06 · SHARP SM83 MOTHERBOARD', 84, 96);
  ctx.fillText('U1: LR35902 CPU', 380, 520);
  ctx.fillText('U2: 8K VRAM', 140, 560);
  ctx.fillText('U3: 8K WRAM', 680, 560);
  ctx.fillText('X1: 4.194304 MHz', 140, 820);
  ctx.fillText('CN1: 32-PIN PAK BUS', 350, 210);

  // Corner mounting holes with gold rings
  for (const [mx, my] of [[76, 76], [cw - 76, 76], [76, ch - 76], [cw - 76, ch - 76]]) {
    ctx.fillStyle = '#d8a938';
    ctx.beginPath();
    ctx.arc(mx, my, 28, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#121519';
    ctx.beginPath();
    ctx.arc(mx, my, 14, 0, Math.PI * 2);
    ctx.fill();
  }

  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = anisotropy;
  tex.needsUpdate = true;
  return tex;
}

export class DmgHandheld3D {
  constructor(container) {
    this.container = container;
    this.width = container.clientWidth || 960;
    this.height = container.clientHeight || 720;

    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      powerPreference: 'high-performance',
      preserveDrawingBuffer: true,
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(this.width, this.height);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.08;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(this.renderer.domElement);

    this.maxAniso = Math.min(8, this.renderer.capabilities.getMaxAnisotropy());

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x11141a);

    this.camera = new THREE.PerspectiveCamera(27, this.width / this.height, 10, 2400);

    // Environment lighting (synchronous RoomEnvironment + studio softboxes)
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    const roomEnv = new RoomEnvironment();
    this.scene.environment = pmrem.fromScene(roomEnv, 0.04).texture;
    roomEnv.dispose();
    pmrem.dispose();

    // State
    this.paletteKey = 'dmg';
    this.ghostingEnabled = true;
    this.cartInserted = true;
    this.cartInsertProgress = 1.0; // 0 = floated out above slot, 1 = seated & latched
    this.cartTargetProgress = 1.0;
    this.explodedProgress = 0.0;
    this.explodedTarget = 0.0;

    // Camera rig state (smoothly damped)
    const p0 = CAMERA_PRESETS.desk_hero;
    this.camState = {
      target: new THREE.Vector3(...p0.target),
      goalTarget: new THREE.Vector3(...p0.target),
      dist: p0.dist,
      goalDist: p0.dist,
      rx: p0.rx,
      goalRx: p0.rx,
      ry: p0.ry,
      goalRy: p0.ry,
      rz: p0.rz,
      goalRz: p0.rz,
      presetId: p0.id,
    };

    // Button press state (0..1 animated)
    this.btnAnim = {
      right: 0, left: 0, up: 0, down: 0,
      A: 0, B: 0, select: 0, start: 0,
    };
    this.joyMask = 0;

    // LCD buffers (160x144 shade indices 0..3)
    this.lcdCurBuf = new Uint8Array(W * H);
    this.lcdPrevBuf = new Uint8Array(W * H);
    this.lcdCurTex = new THREE.DataTexture(this.lcdCurBuf, W, H, THREE.RedFormat, THREE.UnsignedByteType);
    this.lcdPrevTex = new THREE.DataTexture(this.lcdPrevBuf, W, H, THREE.RedFormat, THREE.UnsignedByteType);
    for (const t of [this.lcdCurTex, this.lcdPrevTex]) {
      t.magFilter = THREE.NearestFilter;
      t.minFilter = THREE.NearestFilter;
      t.flipY = true;
      t.needsUpdate = true;
    }

    this.interactiveButtons = [];
    this.calloutAnchors = {};

    this._buildLightsAndWorkbench();
    this._buildHandheldAndCartridge();
    this._setupPointerControls();
    this.updateCamera(1.0);
  }

  _buildLightsAndWorkbench() {
    // Studio lighting rig: warm key light (shadow-casting), cool right fill light, warm rim light, hemisphere ambient
    const dirLight = new THREE.DirectionalLight(0xfff5e4, 2.5);
    dirLight.position.set(-140, 230, 240);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.set(1024, 1024);
    dirLight.shadow.camera.near = 60;
    dirLight.shadow.camera.far = 680;
    const d = 145;
    dirLight.shadow.camera.left = -d;
    dirLight.shadow.camera.right = d;
    dirLight.shadow.camera.top = d;
    dirLight.shadow.camera.bottom = -d;
    dirLight.shadow.bias = -0.0004;
    this.scene.add(dirLight);

    const fillLight = new THREE.DirectionalLight(0xdce8ff, 1.35);
    fillLight.position.set(220, 90, 180);
    this.scene.add(fillLight);

    const rimLight = new THREE.DirectionalLight(0xffeacc, 1.65);
    rimLight.position.set(30, 240, -210);
    this.scene.add(rimLight);

    const bottomFill = new THREE.DirectionalLight(0xc8d4e8, 0.65);
    bottomFill.position.set(0, -200, 160);
    this.scene.add(bottomFill);

    const hemi = new THREE.HemisphereLight(0xf6f4ee, 0x1a1e28, 0.75);
    this.scene.add(hemi);

    // Precision architectural cutting mat / workbench backdrop behind the floating handheld
    const matCanvas = document.createElement('canvas');
    matCanvas.width = 1024;
    matCanvas.height = 1024;
    const mctx = matCanvas.getContext('2d');
    const bgGrad = mctx.createRadialGradient(512, 512, 60, 512, 512, 620);
    bgGrad.addColorStop(0, '#1a1f29');
    bgGrad.addColorStop(0.65, '#13171f');
    bgGrad.addColorStop(1, '#0d1016');
    mctx.fillStyle = bgGrad;
    mctx.fillRect(0, 0, 1024, 1024);

    // Subtle engineering grid lines
    mctx.strokeStyle = 'rgba(148, 163, 184, 0.055)';
    mctx.lineWidth = 1;
    for (let i = 0; i <= 1024; i += 32) {
      mctx.beginPath(); mctx.moveTo(i, 0); mctx.lineTo(i, 1024); mctx.stroke();
      mctx.beginPath(); mctx.moveTo(0, i); mctx.lineTo(1024, i); mctx.stroke();
    }
    mctx.strokeStyle = 'rgba(155, 188, 15, 0.08)';
    for (let i = 0; i <= 1024; i += 128) {
      mctx.beginPath(); mctx.moveTo(i, 0); mctx.lineTo(i, 1024); mctx.stroke();
      mctx.beginPath(); mctx.moveTo(0, i); mctx.lineTo(1024, i); mctx.stroke();
    }

    const deskTex = new THREE.CanvasTexture(matCanvas);
    deskTex.colorSpace = THREE.SRGBColorSpace;
    const deskPlane = new THREE.Mesh(
      new THREE.PlaneGeometry(1400, 1100),
      new THREE.MeshStandardMaterial({
        map: deskTex,
        roughness: 0.9,
        metalness: 0.05,
      })
    );
    deskPlane.position.set(0, 0, -95);
    deskPlane.receiveShadow = true;
    this.scene.add(deskPlane);
  }

  _buildHandheldAndCartridge() {
    this.rig = new THREE.Group();
    this.scene.add(this.rig);

    this.frontShellGroup = new THREE.Group();
    this.lcdModuleGroup = new THREE.Group();
    this.pcbGroup = new THREE.Group();
    this.backShellGroup = new THREE.Group();
    this.rig.add(this.frontShellGroup, this.lcdModuleGroup, this.pcbGroup, this.backShellGroup);

    // Shared PBR materials
    const matBody = new THREE.MeshPhysicalMaterial({
      color: 0xd5d0c4, // Classic 1989 DMG-01 warm putty grey
      roughness: 0.54,
      metalness: 0.0,
      clearcoat: 0.08,
      clearcoatRoughness: 0.55,
      envMapIntensity: 0.72,
    });
    addTriplanarGrain(matBody, 0.75, 0.025, 0.05);

    const matGroove = new THREE.MeshStandardMaterial({
      color: 0x7b776d,
      roughness: 0.85,
    });

    const matBezel = new THREE.MeshPhysicalMaterial({
      color: 0x454852, // Authentic DMG anthracite bezel
      roughness: 0.42,
      metalness: 0.04,
      clearcoat: 0.25,
      clearcoatRoughness: 0.35,
      envMapIntensity: 0.75,
    });
    addTriplanarGrain(matBezel, 1.2, 0.01, 0.03);

    const matDpad = new THREE.MeshPhysicalMaterial({
      color: 0x181a1e,
      roughness: 0.44,
      metalness: 0.03,
      clearcoat: 0.14,
      clearcoatRoughness: 0.4,
    });
    addTriplanarGrain(matDpad, 1.3, 0.015, 0.03);

    const matMagentaBtn = new THREE.MeshPhysicalMaterial({
      color: 0x8e1b44, // Iconic DMG concave crimson-magenta
      roughness: 0.16,
      metalness: 0.02,
      clearcoat: 0.88,
      clearcoatRoughness: 0.09,
      envMapIntensity: 1.05,
    });

    const matSiliconePill = new THREE.MeshStandardMaterial({
      color: 0x5c5f68,
      roughness: 0.76,
      metalness: 0.0,
    });

    // =========================================================================
    // 1. FRONT SHELL + SILKSCREEN + BEZEL + CONTROLS
    // =========================================================================
    const frontBodyShape = makeDmgBodyShape(86, 144, 4.5, 17.5);
    frontBodyShape.holes.push(makeRoundedRectShape(54.2, 49.6, 2.0, 0, 31.8));
    const frontGeo = new THREE.ExtrudeGeometry(frontBodyShape, {
      depth: 10.2,
      bevelEnabled: true,
      bevelThickness: 2.0,
      bevelSize: 2.0,
      bevelSegments: 8,
      curveSegments: 24,
    });
    const frontMesh = new THREE.Mesh(frontGeo, matBody);
    frontMesh.castShadow = true;
    frontMesh.receiveShadow = true;
    this.frontShellGroup.add(frontMesh);

    // Front silkscreen overlay (Navy "DMG-01 GAME BOY", "A", "B", "SELECT", "START", "OFF•ON", "PHONES")
    const frontSilkTex = createFrontSilkscreenTexture(this.maxAniso);
    const frontSilkPlane = new THREE.Mesh(
      new THREE.PlaneGeometry(86, 144),
      new THREE.MeshBasicMaterial({
        map: frontSilkTex,
        transparent: true,
        depthWrite: false,
      })
    );
    frontSilkPlane.position.set(0, 0, 12.24);
    this.frontShellGroup.add(frontSilkPlane);

    // Molded top & vertical groove rules on front shell
    const topGroove = new THREE.Mesh(new THREE.BoxGeometry(90.1, 0.65, 10.5), matGroove);
    topGroove.position.set(0, 60.5, 6.2);
    this.frontShellGroup.add(topGroove);
    for (const sx of [-35.5, 35.5]) {
      const vg = new THREE.Mesh(new THREE.BoxGeometry(0.65, 13.5, 5.0), matGroove);
      vg.position.set(sx, 67.2, 9.8);
      this.frontShellGroup.add(vg);
    }

    // Speaker grille slots (6 deep-cut angled slots at bottom-right corner with acoustic mesh inside)
    const slotPivot = new THREE.Group();
    slotPivot.position.set(27.5, -54.5, 11.4);
    slotPivot.rotation.z = (-29 * Math.PI) / 180;
    this.frontShellGroup.add(slotPivot);
    const slotMat = new THREE.MeshStandardMaterial({ color: 0x121316, roughness: 0.95 });
    for (let i = 0; i < 6; i++) {
      const slot = new THREE.Mesh(new RoundedBoxGeometry(1.55, 13.2, 2.2, 3, 0.65), slotMat);
      slot.position.set((i - 2.5) * 3.7, 0, 0);
      slotPivot.add(slot);
    }

    // Screen Lens Bezel (dark anthracite frame with cutout for 160x144 LCD)
    const bezelShape = makeDmgBodyShape(77, 57, 3.2, 11.5);
    bezelShape.holes.push(makeRoundedRectShape(49.2, 44.6, 1.2));
    const bezelGeo = new THREE.ExtrudeGeometry(bezelShape, {
      depth: 1.0,
      bevelEnabled: true,
      bevelThickness: 0.35,
      bevelSize: 0.35,
      bevelSegments: 4,
      curveSegments: 18,
    });
    const bezelMesh = new THREE.Mesh(bezelGeo, matBezel);
    bezelMesh.position.set(0, 31.8, 10.95);
    this.frontShellGroup.add(bezelMesh);

    // Bezel Silkscreen Overlay ("DOT MATRIX WITH STEREO SOUND", magenta/navy stripes, "BATTERY")
    const bezelSilkTex = createBezelOverlayTexture(this.maxAniso);
    const bezelSilkShape = makeDmgBodyShape(77, 57, 3.2, 11.5);
    bezelSilkShape.holes.push(makeRoundedRectShape(49.4, 44.8, 1.2));
    const bezelSilkGeo = new THREE.ShapeGeometry(bezelSilkShape, 18);
    // Normalize UVs of ShapeGeometry from [-38.5..38.5] x [-28.5..28.5] to [0..1] x [0..1]
    const bPos = bezelSilkGeo.attributes.position;
    const bUv = bezelSilkGeo.attributes.uv;
    for (let i = 0; i < bPos.count; i++) {
      bUv.setXY(i, (bPos.getX(i) + 38.5) / 77.0, (bPos.getY(i) + 28.5) / 57.0);
    }
    const bezelSilkMesh = new THREE.Mesh(
      bezelSilkGeo,
      new THREE.MeshBasicMaterial({
        map: bezelSilkTex,
        transparent: true,
        depthWrite: false,
      })
    );
    bezelSilkMesh.position.set(0, 31.8, 12.33);
    this.frontShellGroup.add(bezelSilkMesh);

    // Recessed inner LCD shadow well wall (flush with bezel hole so 0 pixels are ever grazed at any angle)
    const wellShape = makeRoundedRectShape(50.8, 46.2, 1.3);
    wellShape.holes.push(makeRoundedRectShape(49.2, 44.6, 1.1));
    const wellGeo = new THREE.ExtrudeGeometry(wellShape, { depth: 1.4, bevelEnabled: false });
    const wellMesh = new THREE.Mesh(
      wellGeo,
      new THREE.MeshStandardMaterial({ color: 0x262922, roughness: 0.85 })
    );
    wellMesh.position.set(0, 31.8, 10.65);
    this.frontShellGroup.add(wellMesh);

    // Protective specular acrylic glass over LCD opening
    const glassMesh = new THREE.Mesh(
      new THREE.PlaneGeometry(49.2, 44.6),
      new THREE.MeshPhysicalMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.09,
        roughness: 0.08,
        metalness: 0.0,
        clearcoat: 1.0,
        clearcoatRoughness: 0.05,
        envMapIntensity: 1.4,
        depthWrite: false,
      })
    );
    glassMesh.position.set(0, 31.8, 12.28);
    this.frontShellGroup.add(glassMesh);

    // Ruby-Red "BATTERY" LED with emissive dome + point light
    const ledWell = new THREE.Mesh(
      new THREE.CylinderGeometry(2.1, 2.1, 0.7, 24),
      new THREE.MeshStandardMaterial({ color: 0x1a1a1e, roughness: 0.7 })
    );
    ledWell.rotation.x = Math.PI / 2;
    ledWell.position.set(-31.0, 33.4, 12.05);
    this.frontShellGroup.add(ledWell);

    this.ledMat = new THREE.MeshPhysicalMaterial({
      color: 0xff261b,
      emissive: 0xff1e10,
      emissiveIntensity: 3.2,
      roughness: 0.18,
      transmission: 0.35,
      thickness: 1.5,
    });
    const ledDome = new THREE.Mesh(
      new THREE.SphereGeometry(1.65, 24, 16, 0, Math.PI * 2, 0, Math.PI * 0.65),
      this.ledMat
    );
    ledDome.rotation.x = Math.PI / 2;
    ledDome.position.set(-31.0, 33.4, 12.15);
    this.frontShellGroup.add(ledDome);

    this.ledLight = new THREE.PointLight(0xff2a18, 8.5, 22, 1.8);
    this.ledLight.position.set(-31.0, 33.4, 14.5);
    this.frontShellGroup.add(this.ledLight);

    // Tactile Matte-Black Cross D-Pad (-23.5, -23.0)
    const dpadWell = new THREE.Mesh(
      new THREE.CylinderGeometry(13.8, 13.8, 0.8, 36),
      new THREE.MeshStandardMaterial({ color: 0xbcb7aa, roughness: 0.68 })
    );
    dpadWell.rotation.x = Math.PI / 2;
    dpadWell.position.set(-23.5, -23.0, 11.88);
    this.frontShellGroup.add(dpadWell);

    this.dpadPivot = new THREE.Group();
    this.dpadPivot.position.set(-23.5, -23.0, 12.2);
    this.frontShellGroup.add(this.dpadPivot);

    const armH = new THREE.Mesh(new RoundedBoxGeometry(23.6, 7.8, 3.8, 4, 0.75), matDpad);
    const armV = new THREE.Mesh(new RoundedBoxGeometry(7.8, 23.6, 3.8, 4, 0.75), matDpad);
    armH.castShadow = true;
    armV.castShadow = true;
    this.dpadPivot.add(armH, armV);

    // D-pad grip ridges & center pivot dish
    const centerDish = new THREE.Mesh(new THREE.CylinderGeometry(2.6, 2.6, 0.6, 24), matDpad);
    centerDish.rotation.x = Math.PI / 2;
    centerDish.position.z = 1.75;
    this.dpadPivot.add(centerDish);

    const ribGeoH = new RoundedBoxGeometry(4.4, 0.85, 0.65, 2, 0.25);
    const ribGeoV = new RoundedBoxGeometry(0.85, 4.4, 0.65, 2, 0.25);
    for (const s of [-1, 1]) {
      for (const r of [5.8, 7.9, 10.0]) {
        const rh = new THREE.Mesh(ribGeoH, matDpad);
        rh.position.set(0, s * r, 1.9);
        const rv = new THREE.Mesh(ribGeoV, matDpad);
        rv.position.set(s * r, 0, 1.9);
        this.dpadPivot.add(rh, rv);
      }
    }

    // Invisible hit targets on D-Pad directions for 3D raycast clicking
    const hitMat = new THREE.MeshBasicMaterial({ visible: false });
    const addHitBox = (name, x, y, w, h, parent) => {
      const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, 6), hitMat);
      m.position.set(x, y, 2);
      m.userData.gbButton = name;
      parent.add(m);
      this.interactiveButtons.push(m);
    };
    addHitBox('up', 0, 8, 8, 8, this.dpadPivot);
    addHitBox('down', 0, -8, 8, 8, this.dpadPivot);
    addHitBox('left', -8, 0, 8, 8, this.dpadPivot);
    addHitBox('right', 8, 0, 8, 8, this.dpadPivot);

    // Glossy Concave Crimson-Magenta B & A Buttons
    const makeConcaveActionButton = (name) => {
      const pts = [];
      const R = 5.45;
      pts.push(new THREE.Vector2(0, -2.5));
      pts.push(new THREE.Vector2(R, -2.5));
      pts.push(new THREE.Vector2(R, 0.9));
      for (let i = 0; i <= 14; i++) {
        const t = i / 14;
        const r = R - t * 1.15;
        const y = 0.9 + Math.sin(t * Math.PI * 0.5) * 0.85;
        pts.push(new THREE.Vector2(r, y));
      }
      for (let i = 1; i <= 12; i++) {
        const u = 1 - i / 12;
        const r = (R - 1.15) * u;
        const y = 1.75 - (1 - u * u) * 0.42; // Concave thumb dish
        pts.push(new THREE.Vector2(r, y));
      }
      const geo = new THREE.LatheGeometry(pts, 36);
      geo.rotateX(Math.PI / 2);
      const mesh = new THREE.Mesh(geo, matMagentaBtn);
      mesh.castShadow = true;
      mesh.userData.gbButton = name;
      this.interactiveButtons.push(mesh);
      return mesh;
    };

    this.btnB = makeConcaveActionButton('B');
    this.btnB.position.set(16.2, -26.5, 12.3);
    this.btnA = makeConcaveActionButton('A');
    this.btnA.position.set(30.2, -19.8, 12.3);
    this.frontShellGroup.add(this.btnB, this.btnA);

    // Select & Start angled silicone pill buttons
    const makeSiliconePill = (name, x, y) => {
      const g = new THREE.Group();
      g.position.set(x, y, 12.15);
      g.rotation.z = (-25 * Math.PI) / 180;
      const geo = new THREE.CapsuleGeometry(1.5, 6.2, 10, 20);
      geo.rotateZ(Math.PI / 2);
      const mesh = new THREE.Mesh(geo, matSiliconePill);
      mesh.scale.set(1, 1, 0.68);
      mesh.castShadow = true;
      mesh.userData.gbButton = name;
      this.interactiveButtons.push(mesh);
      g.add(mesh);
      this.frontShellGroup.add(g);
      return g;
    };
    this.btnSelect = makeSiliconePill('select', -10.8, -48.5);
    this.btnStart = makeSiliconePill('start', 3.2, -48.5);

    // =========================================================================
    // 2. LIVE 160x144 STN DOT-MATRIX LCD MODULE (NEVER CROPPED!)
    // =========================================================================
    const pal0 = LCD_PALETTES[this.paletteKey];

    // Metallic olive-gold reflective STN backing plate behind the liquid crystal layer
    this.lcdBackMat = new THREE.MeshStandardMaterial({
      color: pal0.backColor,
      roughness: 0.36,
      metalness: 0.12,
    });
    const lcdBackMesh = new THREE.Mesh(new THREE.PlaneGeometry(49.6, 45.0), this.lcdBackMat);
    lcdBackMesh.position.set(0, 31.8, 10.95);
    this.lcdModuleGroup.add(lcdBackMesh);

    // Custom ShaderMaterial for the 160x144 pixel matrix + unprinted STN border + sub-pixel grid + STN response ghosting
    this.lcdUniforms = {
      uCurTex: { value: this.lcdCurTex },
      uPrevTex: { value: this.lcdPrevTex },
      uGhostMix: { value: 0.28 },
      uCol0: { value: new THREE.Vector3(...pal0.shades[0]) },
      uCol1: { value: new THREE.Vector3(...pal0.shades[1]) },
      uCol2: { value: new THREE.Vector3(...pal0.shades[2]) },
      uCol3: { value: new THREE.Vector3(...pal0.shades[3]) },
    };

    this.lcdShaderMat = new THREE.ShaderMaterial({
      uniforms: this.lcdUniforms,
      vertexShader: `
        varying vec2 vUv;
        void main() {
          vUv = uv;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        uniform sampler2D uCurTex;
        uniform sampler2D uPrevTex;
        uniform float uGhostMix;
        uniform vec3 uCol0;
        uniform vec3 uCol1;
        uniform vec3 uCol2;
        uniform vec3 uCol3;
        varying vec2 vUv;

        vec3 shadeColor(float s) {
          if (s < 0.5) return uCol0;
          if (s < 1.5) return uCol1;
          if (s < 2.5) return uCol2;
          return uCol3;
        }

        void main() {
          // 160x144 active matrix framed inside an authentic 5px unprinted STN liquid-crystal glass margin (170x154 total)
          vec2 totalRes = vec2(170.0, 154.0);
          vec2 pad = vec2(5.0, 5.0);
          vec2 res = vec2(160.0, 144.0);
          vec2 gridCoord = vUv * totalRes - pad;

          vec3 col = uCol0;
          float dotMask = 1.0;

          if (gridCoord.x >= 0.0 && gridCoord.x < res.x && gridCoord.y >= 0.0 && gridCoord.y < res.y) {
            vec2 cell = fract(gridCoord);
            vec2 pUv = (floor(gridCoord) + 0.5) / res;

            float sCur = floor(texture2D(uCurTex, pUv).r * 255.0 + 0.5);
            float sPrev = floor(texture2D(uPrevTex, pUv).r * 255.0 + 0.5);
            vec3 cCur = shadeColor(sCur);
            vec3 cPrev = shadeColor(sPrev);
            col = mix(cCur, cPrev, uGhostMix);

            // Authentic STN dot-matrix inter-pixel grid gap
            float gx = smoothstep(0.0, 0.09, cell.x) * (1.0 - smoothstep(0.90, 1.0, cell.x));
            float gy = smoothstep(0.0, 0.09, cell.y) * (1.0 - smoothstep(0.90, 1.0, cell.y));
            dotMask = mix(0.86, 1.0, gx * gy);
          }

          // Subtle shadow from recessed bezel edge onto top/left of LCD glass
          float topShadow = smoothstep(0.0, 0.035, 1.0 - vUv.y);
          float leftShadow = smoothstep(0.0, 0.03, vUv.x);
          float bezelShadow = mix(0.88, 1.0, topShadow * leftShadow);

          gl_FragColor = vec4(col * dotMask * bezelShadow, 1.0);
        }
      `,
    });

    this.lcdScreenMesh = new THREE.Mesh(new THREE.PlaneGeometry(49.2, 44.6), this.lcdShaderMat);
    this.lcdScreenMesh.position.set(0, 31.8, 11.65);
    this.lcdModuleGroup.add(this.lcdScreenMesh);

    // Copper flex ribbon connecting LCD module to PCB (visible in Exploded X-Ray mode)
    const ribbonMesh = new THREE.Mesh(
      new THREE.BoxGeometry(28, 18, 0.4),
      new THREE.MeshStandardMaterial({ color: 0xc87d28, roughness: 0.45, metalness: 0.5 })
    );
    ribbonMesh.position.set(0, 8, 9.2);
    this.lcdModuleGroup.add(ribbonMesh);

    // =========================================================================
    // 3. EMERALD DMG-CPU-06 MOTHERBOARD PCB (FOR EXPLODED X-RAY VIEW)
    // =========================================================================
    const pcbTex = createMotherboardPcbTexture(this.maxAniso);
    const pcbBoard = new THREE.Mesh(
      new RoundedBoxGeometry(82, 138, 1.8, 3, 2.0),
      new THREE.MeshStandardMaterial({
        map: pcbTex,
        roughness: 0.42,
        metalness: 0.18,
      })
    );
    pcbBoard.position.set(0, 0, 0);
    this.pcbGroup.add(pcbBoard);

    const icMat = new THREE.MeshStandardMaterial({ color: 0x16181c, roughness: 0.38, metalness: 0.08 });
    const pinMat = new THREE.MeshStandardMaterial({ color: 0xd0d5dd, roughness: 0.25, metalness: 0.85 });

    const makeICChip = (w, h, d, x, y, labelKey) => {
      const g = new THREE.Group();
      g.position.set(x, y, 1.6);
      const body = new THREE.Mesh(new RoundedBoxGeometry(w, h, d, 2, 0.3), icMat);
      g.add(body);
      // Gull-wing pins along sides
      const pinCount = Math.floor(h / 1.4);
      for (let i = 0; i < pinCount; i++) {
        const py = -h / 2 + 1.0 + i * 1.4;
        const pL = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.55, 0.4), pinMat);
        pL.position.set(-w / 2 - 0.6, py, -0.3);
        const pR = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.55, 0.4), pinMat);
        pR.position.set(w / 2 + 0.6, py, -0.3);
        g.add(pL, pR);
      }
      this.pcbGroup.add(g);
      if (labelKey) {
        this.calloutAnchors[labelKey] = g;
      }
      return g;
    };

    // U1: Sharp LR35902 (SM83 CPU) 80-pin QFP in center of PCB
    makeICChip(18, 18, 2.2, 0, 8, 'sm83_cpu');
    // U2: 8 KiB VRAM
    makeICChip(10, 15, 1.9, -22, 6, 'vram_chip');
    // U3: 8 KiB WRAM
    makeICChip(10, 15, 1.9, 22, 6, 'wram_chip');
    // U4: Audio Amp
    makeICChip(9, 11, 1.8, 18, -28, null);

    // 4.194304 MHz Quartz Crystal Oscillator Can
    const xtalCan = new THREE.Mesh(
      new THREE.CylinderGeometry(2.8, 2.8, 8.5, 20),
      pinMat
    );
    xtalCan.position.set(-22, -16, 2.2);
    this.pcbGroup.add(xtalCan);

    // 32-Pin Cartridge Edge Connector Slot on PCB top
    const cartSlotBlock = new THREE.Mesh(
      new THREE.BoxGeometry(54, 5.5, 4.2),
      new THREE.MeshStandardMaterial({ color: 0x1e2026, roughness: 0.5 })
    );
    cartSlotBlock.position.set(0, 32, 2.0);
    this.pcbGroup.add(cartSlotBlock);

    // Mylar Speaker Driver at bottom right of PCB
    const speakerRing = new THREE.Mesh(
      new THREE.CylinderGeometry(11.5, 11.5, 2.4, 32),
      new THREE.MeshStandardMaterial({ color: 0x22252a, roughness: 0.4, metalness: 0.5 })
    );
    speakerRing.rotation.x = Math.PI / 2;
    speakerRing.position.set(24, -52, 2.0);
    this.pcbGroup.add(speakerRing);

    // =========================================================================
    // 4. BACK SHELL + CARTRIDGE WELL + SIDE WHEELS + POWER SWITCH
    // =========================================================================
    const backGeo = new THREE.ExtrudeGeometry(makeDmgBodyShape(86, 144, 4.5, 17.5), {
      depth: 15.8,
      bevelEnabled: true,
      bevelThickness: 2.0,
      bevelSize: 2.0,
      bevelSegments: 8,
      curveSegments: 24,
    });
    const backMesh = new THREE.Mesh(backGeo, matBody);
    backMesh.position.z = -16.0;
    backMesh.castShadow = true;
    backMesh.receiveShadow = true;
    this.backShellGroup.add(backMesh);

    // Perimeter seam band
    const seamGeo = new THREE.ExtrudeGeometry(makeDmgBodyShape(89.1, 147.1, 5.8, 19.0), {
      depth: 1.5,
      bevelEnabled: false,
      curveSegments: 24,
    });
    const seamMesh = new THREE.Mesh(seamGeo, matGroove);
    seamMesh.position.z = -0.75;
    this.backShellGroup.add(seamMesh);

    // Recessed Cartridge Slot Well on rear top
    const cartWell = new THREE.Mesh(
      new RoundedBoxGeometry(60.6, 46.5, 9.5, 3, 1.2),
      new THREE.MeshStandardMaterial({ color: 0xaba69a, roughness: 0.72 })
    );
    cartWell.position.set(0, 50.8, -14.2);
    this.backShellGroup.add(cartWell);

    // Top Sliding Power Switch ("OFF•ON")
    this.powerSwitch = new THREE.Mesh(
      new RoundedBoxGeometry(5.6, 3.8, 5.2, 3, 0.7),
      matDpad
    );
    this.powerSwitch.position.set(-25.5, 73.6, -2.5);
    this.powerSwitch.userData.gbButton = 'power';
    this.interactiveButtons.push(this.powerSwitch);
    this.backShellGroup.add(this.powerSwitch);

    // Knurled Side Rotary Thumbwheels (Contrast on Left, Volume on Right)
    const makeKnurledWheel = (x, y) => {
      const wg = new THREE.Group();
      wg.position.set(x, y, -2.2);
      const disk = new THREE.Mesh(new THREE.CylinderGeometry(7.2, 7.2, 2.2, 32), matDpad);
      wg.add(disk);
      for (let i = 0; i < 24; i++) {
        const a = (i / 24) * Math.PI * 2;
        const tooth = new THREE.Mesh(new THREE.BoxGeometry(0.65, 2.3, 0.9), matDpad);
        tooth.position.set(Math.cos(a) * 7.2, 0, Math.sin(a) * 7.2);
        tooth.rotation.y = -a;
        wg.add(tooth);
      }
      this.backShellGroup.add(wg);
      return wg;
    };
    makeKnurledWheel(-41.2, 24.0); // Contrast dial
    makeKnurledWheel(41.2, 32.0);  // Volume dial

    // Molded AA Battery Compartment Door on Back
    const battDoor = new THREE.Mesh(
      new RoundedBoxGeometry(56, 62, 1.2, 3, 2.0),
      matBody
    );
    battDoor.position.set(0, -24, -18.0);
    this.backShellGroup.add(battDoor);

    // =========================================================================
    // 5. TRANSLUCENT SMOKED 3D GAME PAK CARTRIDGE (WITH INTERNAL ROM/MBC5/SRAM PCB!)
    // =========================================================================
    this.cartGroup = new THREE.Group();
    // Seated position: y = 48.0, z = -13.2
    this.cartGroup.position.set(0, 48.0, -13.2);
    this.rig.add(this.cartGroup);

    // Translucent smoked polycarbonate Game Pak shell so internal PCB + CR2025 battery are visible!
    const matCartShell = new THREE.MeshPhysicalMaterial({
      color: 0x3b404c,
      roughness: 0.24,
      metalness: 0.05,
      transmission: 0.52,
      thickness: 3.5,
      ior: 1.49,
      clearcoat: 0.65,
      clearcoatRoughness: 0.15,
      envMapIntensity: 1.15,
    });

    const cartShell = new THREE.Mesh(
      new RoundedBoxGeometry(58.2, 64.5, 7.6, 4, 1.4),
      matCartShell
    );
    cartShell.castShadow = true;
    cartShell.receiveShadow = true;
    this.cartGroup.add(cartShell);

    // Top grip header block with horizontal ribs
    const cartTopHeader = new THREE.Mesh(
      new RoundedBoxGeometry(55.4, 12.2, 8.2, 3, 1.1),
      matCartShell
    );
    cartTopHeader.position.set(0, 25.0, 0);
    this.cartGroup.add(cartTopHeader);

    const ribMat = new THREE.MeshStandardMaterial({ color: 0x282c36, roughness: 0.4 });
    for (let i = 0; i < 5; i++) {
      const rib = new THREE.Mesh(new RoundedBoxGeometry(56.0, 0.9, 8.5, 2, 0.3), ribMat);
      rib.position.set(0, 12.5 + i * 2.2, 0);
      this.cartGroup.add(rib);
    }

    // Internal Cartridge PCB visible inside the translucent shell!
    const cartPcb = new THREE.Mesh(
      new RoundedBoxGeometry(52.0, 56.0, 1.4, 2, 1.0),
      new THREE.MeshStandardMaterial({ color: 0x115e34, roughness: 0.4, metalness: 0.2 })
    );
    cartPcb.position.set(0, -2.0, 0);
    this.cartGroup.add(cartPcb);

    // 16 Gold Edge-Connector Fingers at the bottom of the cartridge PCB
    const goldMat = new THREE.MeshStandardMaterial({ color: 0xebbd42, roughness: 0.2, metalness: 0.92 });
    for (let i = 0; i < 16; i++) {
      const fx = -22.5 + i * 3.0;
      const fingerF = new THREE.Mesh(new THREE.BoxGeometry(1.9, 7.5, 1.65), goldMat);
      fingerF.position.set(fx, -26.2, 0);
      this.cartGroup.add(fingerF);
    }

    // Internal Cartridge Chips: 64 KiB ROM, MBC5 Controller, 8 KiB SRAM, and CR2025 Battery!
    const romChip = new THREE.Mesh(new RoundedBoxGeometry(18, 12, 2.8, 2, 0.3), icMat);
    romChip.position.set(-11, -6, 0.8);
    this.cartGroup.add(romChip);
    this.calloutAnchors['rom_mbc5'] = romChip;

    const mbc5Chip = new THREE.Mesh(new RoundedBoxGeometry(11, 11, 2.8, 2, 0.3), icMat);
    mbc5Chip.position.set(13, 6, 0.8);
    this.cartGroup.add(mbc5Chip);

    const sramChip = new THREE.Mesh(new RoundedBoxGeometry(12, 9, 2.8, 2, 0.3), icMat);
    sramChip.position.set(-12, 10, 0.8);
    this.cartGroup.add(sramChip);

    // CR2025 Coin-Cell Battery with yellow perimeter insulator ring (for 8 KiB battery-backed SRAM!)
    const battGroup = new THREE.Group();
    battGroup.position.set(12, -10, 1.1);
    const coinCell = new THREE.Mesh(
      new THREE.CylinderGeometry(8.2, 8.2, 2.2, 32),
      pinMat
    );
    coinCell.rotation.x = Math.PI / 2;
    const yellowRing = new THREE.Mesh(
      new THREE.TorusGeometry(8.2, 0.65, 12, 32),
      new THREE.MeshStandardMaterial({ color: 0xfacc15, roughness: 0.4 })
    );
    battGroup.add(coinCell, yellowRing);
    this.cartGroup.add(battGroup);
    this.calloutAnchors['sram_battery'] = battGroup;

    // Cartridge Sticker Label on both front (+z) and rear (-z) of the Game Pak
    this.cartLabelTex = createCartridgeLabelTexture(this.maxAniso, null, null);
    const labelMat = new THREE.MeshPhysicalMaterial({
      map: this.cartLabelTex,
      roughness: 0.28,
      clearcoat: 0.45,
      clearcoatRoughness: 0.2,
    });
    const labelFront = new THREE.Mesh(new THREE.PlaneGeometry(46.5, 38.0), labelMat);
    labelFront.position.set(0, -4.5, 3.86);
    const labelBack = new THREE.Mesh(new THREE.PlaneGeometry(46.5, 38.0), labelMat);
    labelBack.rotation.y = Math.PI;
    labelBack.position.set(0, -4.5, -3.86);
    this.cartGroup.add(labelFront, labelBack);

    // Load embedded art Image asynchronously to enrich cartridge sticker texture
    const artImg = new Image();
    artImg.onload = () => {
      this.cartLabelTex = createCartridgeLabelTexture(this.maxAniso, artImg, null);
      labelMat.map = this.cartLabelTex;
      labelMat.needsUpdate = true;
    };
    artImg.src = LABEL_ART_DATA_URL;
  }

  _setupPointerControls() {
    const dom = this.renderer.domElement;
    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    let dragging = false;
    let lastX = 0, lastY = 0;
    let activeGbButton = null;

    dom.addEventListener('pointerdown', (e) => {
      const rect = dom.getBoundingClientRect();
      this.pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      this.pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      this.raycaster.setFromCamera(this.pointer, this.camera);
      const hits = this.raycaster.intersectObjects(this.interactiveButtons, true);
      if (hits.length > 0) {
        let obj = hits[0].object;
        while (obj && !obj.userData.gbButton) obj = obj.parent;
        const btn = obj?.userData?.gbButton;
        if (btn === 'power') {
          if (this.onToggleCartridge) this.onToggleCartridge();
          return;
        }
        if (btn && this.onButtonPress) {
          activeGbButton = btn;
          this.onButtonPress(btn, true);
          dom.setPointerCapture(e.pointerId);
          return;
        }
      }
      dragging = true;
      lastX = e.clientX;
      lastY = e.clientY;
      dom.setPointerCapture(e.pointerId);
    });

    dom.addEventListener('pointermove', (e) => {
      if (!dragging) return;
      const dx = e.clientX - lastX;
      const dy = e.clientY - lastY;
      lastX = e.clientX;
      lastY = e.clientY;
      this.camState.goalRy += dx * 0.0065;
      this.camState.goalRx = Math.max(-0.85, Math.min(0.65, this.camState.goalRx - dy * 0.0055));
    });

    const endInteraction = () => {
      if (activeGbButton && this.onButtonPress) {
        this.onButtonPress(activeGbButton, false);
        activeGbButton = null;
      }
      dragging = false;
    };
    dom.addEventListener('pointerup', endInteraction);
    dom.addEventListener('pointercancel', endInteraction);

    dom.addEventListener(
      'wheel',
      (e) => {
        e.preventDefault();
        this.camState.goalDist = Math.max(185, Math.min(620, this.camState.goalDist + e.deltaY * 0.22));
      },
      { passive: false }
    );
  }

  setPalette(paletteKey) {
    if (!LCD_PALETTES[paletteKey]) return;
    this.paletteKey = paletteKey;
    const pal = LCD_PALETTES[paletteKey];
    this.lcdUniforms.uCol0.value.set(...pal.shades[0]);
    this.lcdUniforms.uCol1.value.set(...pal.shades[1]);
    this.lcdUniforms.uCol2.value.set(...pal.shades[2]);
    this.lcdUniforms.uCol3.value.set(...pal.shades[3]);
    this.lcdBackMat.color.setHex(pal.backColor);
  }

  setCameraPreset(presetId, immediate = false) {
    const p = CAMERA_PRESETS[presetId];
    if (!p) return;
    this.camState.presetId = presetId;
    this.camState.goalTarget.set(...p.target);
    this.camState.goalDist = p.dist;
    this.camState.goalRx = p.rx;
    this.camState.goalRy = p.ry;
    this.camState.goalRz = p.rz;
    this.explodedTarget = p.exploded || 0;

    if (immediate) {
      this.camState.target.copy(this.camState.goalTarget);
      this.camState.dist = this.camState.goalDist;
      this.camState.rx = this.camState.goalRx;
      this.camState.ry = this.camState.goalRy;
      this.camState.rz = this.camState.goalRz;
      this.explodedProgress = this.explodedTarget;
      this.updateCamera(1.0);
    }
  }

  triggerCartridgeInsertAnimation() {
    this.cartInsertProgress = 0.0;
    this.cartTargetProgress = 1.0;
    this.cartInserted = true;
  }

  toggleCartridgeEject() {
    this.cartInserted = !this.cartInserted;
    this.cartTargetProgress = this.cartInserted ? 1.0 : 0.0;
    return this.cartInserted;
  }

  updateLcdFromRgbaFrame(rgbaBytes) {
    // Convert binjgb 160x144 RGBA frame into 0..3 shade index buffer
    this.lcdPrevBuf.set(this.lcdCurBuf);
    for (let i = 0, p = 0; i < W * H; i++, p += 4) {
      const luma = rgbaBytes[p]; // binjgb monochrome palette R channel
      let shade = 0;
      if (luma < 45) shade = 3;
      else if (luma < 128) shade = 2;
      else if (luma < 210) shade = 1;
      else shade = 0;
      this.lcdCurBuf[i] = shade;
    }
    this.lcdPrevTex.needsUpdate = true;
    this.lcdCurTex.needsUpdate = true;
  }

  setJoypadMask(mask) {
    this.joyMask = mask;
  }

  updateCamera(alpha = 0.14) {
    const cs = this.camState;
    cs.target.lerp(cs.goalTarget, alpha);
    cs.dist += (cs.goalDist - cs.dist) * alpha;
    cs.rx += (cs.goalRx - cs.rx) * alpha;
    cs.ry += (cs.goalRy - cs.ry) * alpha;
    cs.rz += (cs.goalRz - cs.rz) * alpha;

    const euler = new THREE.Euler(cs.rx, cs.ry, cs.rz, 'YXZ');
    const offset = new THREE.Vector3(0, 0, cs.dist).applyEuler(euler);
    this.camera.position.copy(cs.target).add(offset);
    this.camera.up.set(0, 1, 0).applyAxisAngle(new THREE.Vector3(0, 0, 1), cs.rz);
    this.camera.lookAt(cs.target);
  }

  stepState(dt = 1 / 60) {
    const alpha = Math.min(1.0, dt * 8.5);
    this.updateCamera(alpha);

    // 1. Cartridge insertion / latch interpolation
    const prevCart = this.cartInsertProgress;
    this.cartInsertProgress += (this.cartTargetProgress - this.cartInsertProgress) * Math.min(1.0, dt * 6.5);
    if (prevCart < 0.94 && this.cartInsertProgress >= 0.94 && this.onCartridgeLatched) {
      this.onCartridgeLatched();
    }

    // 2. Exploded PCB X-Ray interpolation (Front Shell + Live LCD on left, Full SM83 Motherboard PCB + Cart + Back Shell fanned to the right)
    this.explodedProgress += (this.explodedTarget - this.explodedProgress) * Math.min(1.0, dt * 6.0);
    const ex = this.explodedProgress;

    this.frontShellGroup.position.set(-ex * 36.0, 0, ex * 26.0);
    this.lcdModuleGroup.position.set(-ex * 36.0, 0, ex * 25.8);
    this.pcbGroup.position.set(ex * 28.0, 0, -ex * 4.0);
    this.backShellGroup.position.set(ex * 54.0, 0, -ex * 34.0);

    // Cartridge position combines insertion slide (28mm vertical travel) + exploded offset
    const slideOffset = (1.0 - this.cartInsertProgress) * 30.0;
    this.cartGroup.position.set(ex * 28.0, 48.0 + slideOffset + ex * 22.0, -13.2 - ex * 10.0);

    // Power switch slides right when cartridge is seated
    const swMix = Math.max(0, Math.min(1, (this.cartInsertProgress - 0.75) * 4.0));
    this.powerSwitch.position.x = -29.0 + swMix * 3.6;

    // Battery LED illumination
    const ledOn = swMix;
    this.ledMat.emissiveIntensity = 0.15 + ledOn * 3.1;
    this.ledLight.intensity = ledOn * 8.5;

    // 3. Physical 3D Button & D-Pad Animation from joypad bitmask
    // Bits: right=1, left=2, up=4, down=8, A=16, B=32, select=64, start=128
    const bRate = Math.min(1.0, dt * 22.0);
    const targets = {
      right: (this.joyMask & 1) ? 1 : 0,
      left: (this.joyMask & 2) ? 1 : 0,
      up: (this.joyMask & 4) ? 1 : 0,
      down: (this.joyMask & 8) ? 1 : 0,
      A: (this.joyMask & 16) ? 1 : 0,
      B: (this.joyMask & 32) ? 1 : 0,
      select: (this.joyMask & 64) ? 1 : 0,
      start: (this.joyMask & 128) ? 1 : 0,
    };
    for (const k of Object.keys(targets)) {
      this.btnAnim[k] += (targets[k] - this.btnAnim[k]) * bRate;
    }

    const tilt = (3.8 * Math.PI) / 180;
    this.dpadPivot.rotation.x = (this.btnAnim.down - this.btnAnim.up) * tilt;
    this.dpadPivot.rotation.y = (this.btnAnim.right - this.btnAnim.left) * tilt;
    this.dpadPivot.position.z =
      12.2 - Math.max(this.btnAnim.up, this.btnAnim.down, this.btnAnim.left, this.btnAnim.right) * 0.45;

    this.btnA.position.z = 12.3 - this.btnAnim.A * 1.45;
    this.btnB.position.z = 12.3 - this.btnAnim.B * 1.45;
    this.btnSelect.position.z = 12.15 - this.btnAnim.select * 0.95;
    this.btnStart.position.z = 12.15 - this.btnAnim.start * 0.95;

    this.lcdUniforms.uGhostMix.value = this.ghostingEnabled ? 0.25 : 0.0;
  }

  renderFrame() {
    this.renderer.render(this.scene, this.camera);
  }

  stepAndRender(dt = 1 / 60) {
    this.stepState(dt);
    this.renderFrame();
  }

  getCalloutScreenPositions() {
    // Projects 3D hardware callout anchors into 2D container pixel coordinates for the Exploded PCB X-Ray HUD
    const out = {};
    const v = new THREE.Vector3();
    for (const [key, obj] of Object.entries(this.calloutAnchors)) {
      obj.getWorldPosition(v);
      v.project(this.camera);
      out[key] = {
        x: (v.x * 0.5 + 0.5) * this.width,
        y: (-v.y * 0.5 + 0.5) * this.height,
        visible: this.explodedProgress > 0.35 && v.z < 1.0,
      };
    }
    return out;
  }

  resize() {
    this.width = this.container.clientWidth || 960;
    this.height = this.container.clientHeight || 720;
    this.camera.aspect = this.width / this.height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(this.width, this.height);
  }
}
