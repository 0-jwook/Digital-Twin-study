# myCobot 280 Pi URDF Assets

Source: https://github.com/peisuke/mycobot_280_urdf (meshes originally by Elephant Robotics)
License: BSD 2-Clause (see `LICENSE` in this folder)

Files used: `mycobot_280_jn.urdf` (no gripper) + its referenced Collada meshes/textures
(`G_base.dae`, `joint1_jet.dae`, `joint2..7.dae`, `joint2..7.png`).

Loaded via `urdf-loader`, which routes `.dae` meshes through three.js's own
`ColladaLoader` internally (no custom mesh loader needed on our side).

## Local modification: `joint5.dae`

The upstream `joint5.dae` encodes its faces with COLLADA `<polygons>` elements,
which three.js's `ColladaLoader` does not implement (it logs "Unsupported
primitive type: polygons" and silently produces zero geometry -- this made
joint 5 invisible while every other link rendered fine). All 8 `<polygons>`
blocks in this file were losslessly restructured into `<polylist>` (same
vertex/index data, just grouped with an explicit `<vcount>` per face instead
of one `<p>` per face) using a one-off Node script, which `ColladaLoader` does
support. No geometry, position, or texture data was altered -- confirmed by
parsing both the original and converted file headlessly and comparing mesh
count / vertex count / bounding box before and after.
