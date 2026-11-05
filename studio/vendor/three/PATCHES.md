# Local patches to three.module.js (three r170, MIT)

Two one-line changes in `WebGLRenderer.renderTransmissionPass`, both for rendering speed in software GL (SwiftShader):

1. the transmission render target is created with `samples: 0` instead of `samples: 4` (the main render is already 2x supersampled);
2. the transmission render target is sized to half the active viewport instead of the full viewport (the frosted shell has
   roughness 0.15 and a 3.6 mm attenuating thickness, so the transmitted image is softened anyway).

Everything else is the unmodified npm `three@0.170.0` build. LICENSE is the upstream MIT licence.
