/* ══════════════════════════════════════════════════════════════════
   data.js — every piece of content in the mockup lives here.
   Nothing below is computed; it is all hand-written sample data so
   the UI reads as a real project without a backend.
   ══════════════════════════════════════════════════════════════════ */

var App = window.App || {};

App.PRODUCT = {
  name: 'Styx',
  version: 'Prototype V1.0',
  project: 'Untitled project'
};

/* ── Icon library ───────────────────────────────────────────────
   Each entry is the inner markup of a 24×24 stroke-only SVG.      */
App.ICONS = {
  'new'        : '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/>',
  'open'       : '<path d="M3 6h6l2 2h10v10H3z"/>',
  'save'       : '<path d="M4 4h13l3 3v13H4z"/><path d="M8 4v6h8V4"/><path d="M8 20v-6h8v6"/>',
  'undo'       : '<path d="M5 10h10a4 4 0 010 8h-3"/><path d="M5 10l4-4"/><path d="M5 10l4 4"/>',
  'redo'       : '<path d="M19 10H9a4 4 0 000 8h3"/><path d="M19 10l-4-4"/><path d="M19 10l-4 4"/>',
  'print'      : '<path d="M7 8V3h10v5"/><path d="M5 8h14v8H5z"/><path d="M7 14h10v7H7z"/>',
  'cut'        : '<path d="M6 4l11 13"/><path d="M18 4L7 17"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="19" r="2"/>',
  'copy'       : '<path d="M9 9h11v11H9z"/><path d="M5 15V4h11"/>',
  'paste'      : '<path d="M9 3h6v3H9z"/><path d="M7 5h2v2h6V5h2v16H7z"/>',
  'delete'     : '<path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M6 7l1 14h10l1-14"/>',
  'zoomin'     : '<circle cx="10.5" cy="10.5" r="7"/><path d="M15.5 15.5l5 5"/><path d="M7.5 10.5h6"/><path d="M10.5 7.5v6"/>',
  'zoomout'    : '<circle cx="10.5" cy="10.5" r="7"/><path d="M15.5 15.5l5 5"/><path d="M7.5 10.5h6"/>',
  'zoomfit'    : '<path d="M3 8V3h5"/><path d="M21 8V3h-5"/><path d="M3 16v5h5"/><path d="M21 16v5h-5"/><path d="M8 8h8v8H8z"/>',
  'pan'        : '<path d="M12 3v18M3 12h18"/><path d="M12 3l-2.5 2.5M12 3l2.5 2.5M12 21l-2.5-2.5M12 21l2.5-2.5M3 12l2.5-2.5M3 12l2.5 2.5M21 12l-2.5-2.5M21 12l-2.5 2.5"/>',
  'rotate'     : '<path d="M20 12.5a8 8 0 11-2.6-5.9"/><path d="M20 3.5v5h-5"/>',
  'front'      : '<path d="M4.5 8h12v11H4.5z"/><path d="M4.5 8l3-3h12v11l-3 3"/>',
  'top'        : '<path d="M12 5l9 5-9 5-9-5z"/><path d="M3 10v4l9 5 9-5v-4"/>',
  'side'       : '<path d="M9 5l9 3v11l-9-3z"/><path d="M9 5L6 7v11l3 1"/>',
  'persp'      : '<path d="M3 6l18-3v18L3 18z"/><path d="M3 12h18"/>',
  'ortho'      : '<path d="M6 8h12v12H6z"/><path d="M6 8l3-3h12v12l-3 3"/>',
  'eye'        : '<path d="M2 12s4-6.5 10-6.5S22 12 22 12s-4 6.5-10 6.5S2 12 2 12z"/><circle cx="12" cy="12" r="2.6"/>',
  'grid'       : '<path d="M3 3h18v18H3z"/><path d="M9 3v18M15 3v18M3 9h18M3 15h18"/>',
  'snap'       : '<path d="M5 5h4v7a3 3 0 006 0V5h4v7a7 7 0 01-14 0z"/><path d="M5 9h4M15 9h4"/>',
  'calculate'  : '<path d="M5.5 4l13 8-13 8z"/>',
  'results'    : '<path d="M4 19.5V4.5M4 19.5h16"/><path d="M8 16.5v-5M12 16.5v-9M16 16.5v-3"/>',
  'borehole'   : '<path d="M9 3h6v18H9z"/><path d="M9 8h6M9 13h6M9 18h6"/>',
  'soillayers' : '<path d="M3 5h18v15H3z"/><path d="M3 10h18M3 15h18"/>',
  'materials'  : '<path d="M4 5h7v7H4z"/><path d="M13 5h7v7h-7z"/><path d="M4 14h7v6H4z"/><path d="M13 14h7v6h-7z"/>',
  'select'     : '<path d="M6 3l12 9-5.2 1 3.1 6.1-2.2 1.1-3.1-6.1L6.6 17z"/>',
  'point'      : '<circle cx="12" cy="12" r="2.6"/><path d="M12 3v4M12 17v4M3 12h4M17 12h4"/>',
  'line'       : '<path d="M6.5 17.5L17.5 6.5"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="5" r="2"/>',
  'polygon'    : '<path d="M12 3l9 6-3.4 11H6.4L3 9z"/>',
  'plate'      : '<path d="M2 10l9-4 11 4-9 4z"/><path d="M2 10v3l9 4 11-4v-3"/>',
  'beam'       : '<path d="M6 4h12M6 20h12M12 4v16"/>',
  'embedded'   : '<path d="M12 3v18"/><path d="M8 8h8M8 13h8M8 18h8"/>',
  'anchor'     : '<path d="M12 5v13"/><path d="M6 18l6-3.5 6 3.5"/><path d="M9 9h6"/>',
  'interface'  : '<path d="M8 3v18" stroke-dasharray="3 2"/><path d="M12 3v18" stroke-dasharray="3 2"/><path d="M15 7h5M15 12h5M15 17h5"/>',
  'load'       : '<path d="M6 4v9M6 13l-2-3M6 13l2-3M12 4v9M12 13l-2-3M12 13l2-3M18 4v9M18 13l-2-3M18 13l2-3"/><path d="M3 17h18"/>',
  'prescribed' : '<path d="M12 4v11M12 15l-3-4M12 15l3-4"/><path d="M4 19h16"/>',
  'tunnel'     : '<path d="M4 20V12a8 8 0 0116 0v8z"/><path d="M9 20v-8a3 3 0 016 0v8"/>',
  'refine'     : '<path d="M4 4h16v16H4z"/><path d="M8 4v16M12 4v16M16 4v16M4 8h16M4 12h16M4 16h16"/>',
  'coarsen'    : '<path d="M4 4h16v16H4z"/><path d="M12 4v16M4 12h16"/>',
  'resetmesh'  : '<path d="M20 12a8 8 0 11-2.6-5.9"/><path d="M20 3v5h-5"/><path d="M9 12h6"/>',
  'genmesh'    : '<path d="M3 20L12 4l9 16z"/><path d="M7.5 12h9M12 4v16"/>',
  'viewmesh'   : '<path d="M3 19l4.5-8 4.5 8z"/><path d="M12 19l4.5-8 4.5 8z"/><path d="M7.5 11L12 3l4.5 8"/>',
  'waterlevel' : '<path d="M3 9c3-3 6 3 9 0s6-3 9 0"/><path d="M3 15c3-3 6 3 9 0s6-3 9 0"/>',
  'well'       : '<path d="M9 3h6v16H9z"/><path d="M9 8h6"/><path d="M5 21h14"/>',
  'drain'      : '<path d="M4 6h16"/><path d="M8 6v11M16 6v11"/><path d="M8 17h8"/><path d="M12 9v6M12 15l-2-2M12 15l2-2"/>',
  'flowfn'     : '<path d="M4 18c4 0 4-12 8-12s4 12 8 12"/>',
  'activate'   : '<path d="M5 12.5l5 5L19 7"/>',
  'deactivate' : '<path d="M6 6l12 12M18 6L6 18"/>',
  'selectmulti': '<path d="M3 3h8v8H3z"/><path d="M13 13h8v8h-8z"/><path d="M13 3h8v8h-8z" stroke-dasharray="3 2"/>',
  'folder'     : '<path d="M3 6h6l2 2h10v11H3z"/>',
  'cube'       : '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"/>',
  'surface'    : '<path d="M2 9l8-4 12 5-8 4z"/>',
  'edge'       : '<path d="M5.5 18.5L18.5 5.5"/><circle cx="4" cy="20" r="1.6"/><circle cx="20" cy="4" r="1.6"/>',
  'vertex'     : '<circle cx="12" cy="12" r="3.4"/>',
  'phase'      : '<path d="M4 12h4l2-6 3 12 2-6h5"/>',
  'water'      : '<path d="M12 3s6 6.5 6 10.5A6 6 0 016 13.5C6 9.5 12 3 12 3z"/>',
  'settings'   : '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M22 12h-3M5 12H2M19 5l-2 2M7 17l-2 2M19 19l-2-2M7 7L5 5"/>',
  'help'       : '<circle cx="12" cy="12" r="9"/><path d="M9.6 9.5a2.5 2.5 0 114 2c-.9.7-1.6 1.2-1.6 2.5"/><path d="M12 17.4v.2"/>',
  'structure'  : '<path d="M4 20V8l8-5 8 5v12z"/><path d="M9 20v-7h6v7"/>',
  'info'       : '<circle cx="12" cy="12" r="9"/><path d="M12 11v6"/><path d="M12 7.5v.2"/>',
  'clock'      : '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>'
};

/* ── Menu bar ───────────────────────────────────────────────────
   { label, items: [ {label, icon, key, checked, disabled, action}
                   | '-'  (separator)
                   | {title:'…'} (section caption) ] }             */
App.MENUS = [
  { label: 'File', items: [
    { label: 'New project…',      icon: 'new',  key: 'Ctrl+N' },
    { label: 'Open project…',     icon: 'open', key: 'Ctrl+O' },
    { label: 'Recent projects',   icon: 'clock', sub: true },
    '-',
    { label: 'Save',              icon: 'save', key: 'Ctrl+S' },
    { label: 'Save as…',                        key: 'Ctrl+Shift+S' },
    { label: 'Pack project…' },
    '-',
    { label: 'Print…',            icon: 'print', key: 'Ctrl+P' },
    { label: 'Export model…' },
    '-',
    { label: 'Exit',                            key: 'Alt+F4' }
  ]},
  { label: 'Edit', items: [
    { label: 'Undo',   icon: 'undo', key: 'Ctrl+Z' },
    { label: 'Redo',   icon: 'redo', key: 'Ctrl+Y', disabled: true },
    '-',
    { label: 'Cut',    icon: 'cut',    key: 'Ctrl+X', disabled: true },
    { label: 'Copy',   icon: 'copy',   key: 'Ctrl+C', disabled: true },
    { label: 'Paste',  icon: 'paste',  key: 'Ctrl+V', disabled: true },
    { label: 'Delete', icon: 'delete', key: 'Del',    disabled: true },
    '-',
    { label: 'Select all',        key: 'Ctrl+A' },
    { label: 'Deselect all',      key: 'Esc' }
  ]},
  { label: 'View', items: [
    { label: 'Zoom in',        icon: 'zoomin',  key: 'Ctrl++',  action: 'zoomIn' },
    { label: 'Zoom out',       icon: 'zoomout', key: 'Ctrl+-',  action: 'zoomOut' },
    { label: 'Zoom to fit',    icon: 'zoomfit', key: 'F5',      action: 'zoomFit' },
    '-',
    { title: 'Standard views' },
    { label: 'Front view',     icon: 'front', action: 'viewFront' },
    { label: 'Top view',       icon: 'top',   action: 'viewTop' },
    { label: 'Side view',      icon: 'side',  action: 'viewSide' },
    { label: 'Isometric view', icon: 'cube',  action: 'viewIso' },
    '-',
    { label: 'Perspective projection', icon: 'persp', checked: true, action: 'toggleProjection' },
    { label: 'Show grid',      icon: 'grid', checked: true, action: 'toggleGrid' },
    { label: 'Show axes triad', checked: true, action: 'toggleTriad' },
    { label: 'Show command panel', checked: true, action: 'toggleCmd' }
  ]},
  { label: 'Soil', items: [
    { label: 'Create borehole',    icon: 'borehole', action: 'createBorehole' },
    { label: 'Modify soil layers…', icon: 'soillayers', action: 'soilLayers' },
    '-',
    { label: 'Show material sets…', icon: 'materials', action: 'materials' },
    { label: 'Import soil layers…', action: 'importSoilLayers' }
  ]},
  { label: 'Structures', items: [
    { label: 'Create point',   icon: 'point' },
    { label: 'Create line',    icon: 'line' },
    { label: 'Create surface', icon: 'polygon' },
    '-',
    { label: 'Create plate',          icon: 'plate' },
    { label: 'Create beam',           icon: 'beam' },
    { label: 'Create embedded beam',  icon: 'embedded' },
    { label: 'Create anchor',         icon: 'anchor' },
    { label: 'Create interface',      icon: 'interface' },
    '-',
    { label: 'Create load',                 icon: 'load', sub: true },
    { label: 'Create prescribed displacement', icon: 'prescribed', sub: true },
    '-',
    { label: 'Tunnel designer…', icon: 'tunnel' }
  ]},
  { label: 'Mesh', items: [
    { label: 'Refine mesh',    icon: 'refine' },
    { label: 'Coarsen mesh',   icon: 'coarsen' },
    { label: 'Reset local refinement', icon: 'resetmesh' },
    '-',
    { label: 'Generate mesh…', icon: 'genmesh', key: 'F9', action: 'generateMesh' },
    { label: 'View mesh',      icon: 'viewmesh' }
  ]},
  { label: 'Flow conditions', items: [
    { label: 'Create water level', icon: 'waterlevel' },
    { label: 'Create well',        icon: 'well' },
    { label: 'Create drain',       icon: 'drain' },
    '-',
    { label: 'Flow functions…',    icon: 'flowfn' },
    { label: 'Global water level', checked: true }
  ]},
  { label: 'Phases', items: [
    { label: 'Edit phases…',   icon: 'phase' },
    { label: 'Add phase' },
    { label: 'Insert phase' },
    { label: 'Delete phase',   disabled: true },
    '-',
    { label: 'Calculate',      icon: 'calculate', key: 'F9', action: 'calculate' },
    { label: 'View calculation results', icon: 'results', action: 'results' }
  ]},
  { label: 'Expert', items: [
    { label: 'Command line', checked: true, action: 'toggleCmd' },
    { label: 'Examine commands…' },
    { label: 'Macro library…' },
    '-',
    { label: 'Configure remote scripting server…' },
    { label: 'Python interpreter…' }
  ]},
  { label: 'Help', items: [
    { label: 'Reference manual',   icon: 'help', key: 'F1' },
    { label: 'Command reference',  action: 'cmdref' },
    { label: 'Tutorial manual' },
    '-',
    { label: 'About…', icon: 'info', action: 'about' }
  ]}
];

/* ── Main toolbar ──────────────────────────────────────────────── */
App.TOOLBAR = [
  { icon: 'new',  tip: 'New project (Ctrl+N)' },
  { icon: 'open', tip: 'Open project (Ctrl+O)' },
  { icon: 'save', tip: 'Save project (Ctrl+S)' },
  '|',
  { icon: 'undo', tip: 'Undo (Ctrl+Z)' },
  { icon: 'redo', tip: 'Redo (Ctrl+Y)', disabled: true },
  '|',
  { icon: 'zoomin',  tip: 'Zoom in',     action: 'zoomIn' },
  { icon: 'zoomout', tip: 'Zoom out',    action: 'zoomOut' },
  { icon: 'zoomfit', tip: 'Zoom to fit (F5)', action: 'zoomFit' },
  { icon: 'pan',     tip: 'Pan — middle-drag in the viewport', toggle: 'pan' },
  { icon: 'rotate',  tip: 'Rotate — left-drag in the viewport', toggle: 'rotate', on: true },
  '|',
  { icon: 'front', tip: 'Front view', action: 'viewFront' },
  { icon: 'top',   tip: 'Top view',   action: 'viewTop' },
  { icon: 'side',  tip: 'Side view',  action: 'viewSide' },
  { icon: 'cube',  tip: 'Isometric view', action: 'viewIso' },
  { icon: 'persp', tip: 'Toggle perspective / orthographic', action: 'toggleProjection', on: true },
  '|',
  { icon: 'eye',  tip: 'Visibility settings', action: 'visibility' },
  { icon: 'grid', tip: 'Show grid', action: 'toggleGrid', on: true },
  { icon: 'snap', tip: 'Object snapping', action: 'toggleSnap', on: true },
  '|',
  { icon: 'calculate', tip: 'Calculate (F9)', wide: 'Calculate', cta: true, action: 'calculate' },
  { icon: 'results',   tip: 'View calculation results', action: 'results' }
];

/* ── Modes and their tool rails ────────────────────────────────── */
App.MODES = [
  { id: 'soil',       label: 'Soil',       group: 1,
    hint: 'Soil mode — create boreholes and define the soil stratigraphy.' },
  { id: 'structures', label: 'Structures', group: 1,
    hint: 'Structures mode — draw geometry and assign structural elements.' },
  { id: 'mesh',       label: 'Mesh',       group: 2,
    hint: 'Mesh mode — set element distribution and generate the finite element mesh.' },
  { id: 'flow',       label: 'Flow conditions', group: 2,
    hint: 'Flow conditions mode — define water levels and groundwater flow boundaries.' },
  { id: 'staged',     label: 'Staged construction', group: 2,
    hint: 'Staged construction mode — activate and deactivate objects per calculation phase.' }
];

App.RAILS = {
  soil: [
    { icon: 'select',     tip: 'Select', toggle: true, on: true },
    '-',
    { icon: 'borehole',   tip: 'Create borehole', action: 'createBorehole' },
    { icon: 'soillayers', tip: 'Modify soil layers…', action: 'soilLayers' },
    '-',
    { icon: 'materials',  tip: 'Show material sets…', action: 'materials' }
  ],
  structures: [
    { icon: 'select',      tip: 'Select', toggle: true, on: true },
    { icon: 'selectmulti', tip: 'Select multiple objects', flyout: [
      { icon: 'selectmulti', label: 'Select rectangle' },
      { icon: 'polygon',     label: 'Select polygon' },
      { icon: 'cube',        label: 'Select volumes' } ] },
    '-',
    { icon: 'point',   tip: 'Create point' },
    { icon: 'line',    tip: 'Create line' },
    { icon: 'polygon', tip: 'Create surface' },
    '-',
    { icon: 'plate',    tip: 'Create plate', flyout: [
      { icon: 'plate',     label: 'Create plate' },
      { icon: 'polygon',   label: 'Create surface, then plate' },
      { icon: 'interface', label: 'Create plate with interfaces' } ] },
    { icon: 'beam',     tip: 'Create beam' },
    { icon: 'embedded', tip: 'Create embedded beam row' },
    { icon: 'anchor',   tip: 'Create node-to-node anchor', flyout: [
      { icon: 'anchor', label: 'Node-to-node anchor' },
      { icon: 'anchor', label: 'Fixed-end anchor' } ] },
    { icon: 'interface', tip: 'Create interface' },
    '-',
    { icon: 'load', tip: 'Create load', flyout: [
      { icon: 'load',   label: 'Point load' },
      { icon: 'line',   label: 'Line load' },
      { icon: 'surface',label: 'Surface load' } ] },
    { icon: 'prescribed', tip: 'Create prescribed displacement', flyout: [
      { icon: 'prescribed', label: 'Point prescribed displacement' },
      { icon: 'prescribed', label: 'Line prescribed displacement' },
      { icon: 'prescribed', label: 'Surface prescribed displacement' } ] },
    '-',
    { icon: 'tunnel', tip: 'Tunnel designer…' }
  ],
  mesh: [
    { icon: 'select',    tip: 'Select', toggle: true, on: true },
    '-',
    { icon: 'refine',    tip: 'Refine mesh' },
    { icon: 'coarsen',   tip: 'Coarsen mesh' },
    { icon: 'resetmesh', tip: 'Reset local refinement' },
    '-',
    { icon: 'genmesh',   tip: 'Generate mesh (F9)', action: 'generateMesh' },
    { icon: 'viewmesh',  tip: 'View mesh', action: 'viewMesh' }
  ],
  flow: [
    { icon: 'select',     tip: 'Select', toggle: true, on: true },
    '-',
    { icon: 'waterlevel', tip: 'Create water level' },
    { icon: 'well',       tip: 'Create well' },
    { icon: 'drain',      tip: 'Create drain' },
    '-',
    { icon: 'flowfn',     tip: 'Flow functions…' }
  ],
  staged: [
    { icon: 'select',      tip: 'Select', toggle: true, on: true },
    { icon: 'selectmulti', tip: 'Select multiple objects' },
    '-',
    { icon: 'activate',    tip: 'Activate selection' },
    { icon: 'deactivate',  tip: 'Deactivate selection' },
    '-',
    { icon: 'eye',         tip: 'Preview phase' },
    { icon: 'calculate',   tip: 'Calculate (F9)', action: 'calculate' }
  ]
};

/* ── Materials ─────────────────────────────────────────────────── */
/* The value sets the material editor's dropdowns offer. These mirror the
   Literal unions on the server's Material schema (server/app/schemas.py:85-86,
   :94) — an entry that is not in the server's list is rejected with a 422, so
   the two lists must stay in step. */
App.MATERIAL_MODELS = ['Mohr-Coulomb', 'Hardening Soil', 'Soft Soil', 'Linear Elastic'];
App.MATERIAL_TYPES  = ['Drained', 'Undrained (A)', 'Undrained (B)', 'Non-porous'];
App.INTERFACE_PERM  = ['Neutral', 'Drain', 'Impermeable'];

App.MATERIALS = [
  { id:'m1', name:'Fill',          model:'Mohr-Coulomb',  type:'Drained',   color:'#d8c48a',
    gUnsat:17.0, gSat:20.0, E:15000,  nu:0.30, c:1.0,  phi:30.0, k:1.0,
    rInter:0.70, interfacePerm:'Neutral' },
  { id:'m2', name:'Sand, loose',   model:'Hardening Soil',type:'Drained',   color:'#c4a86a',
    gUnsat:18.0, gSat:20.5, E:25000,  nu:0.28, c:0.5,  phi:32.0, k:1.5,
    rInter:0.70, interfacePerm:'Neutral' },
  { id:'m3', name:'Clay, soft',    model:'Soft Soil',     type:'Undrained (A)', color:'#8fa86b',
    gUnsat:15.0, gSat:16.0, E:4000,   nu:0.35, c:5.0,  phi:22.0, k:0.0001,
    rInter:0.50, interfacePerm:'Impermeable' },
  { id:'m4', name:'Clay, stiff',   model:'Mohr-Coulomb',  type:'Undrained (A)', color:'#6f8fa8',
    gUnsat:17.5, gSat:18.5, E:12000,  nu:0.33, c:15.0, phi:25.0, k:0.0005,
    rInter:0.55, interfacePerm:'Impermeable' },
  { id:'m5', name:'Sand, dense',   model:'Hardening Soil',type:'Drained',   color:'#b08a6a',
    gUnsat:19.0, gSat:21.0, E:45000,  nu:0.25, c:0.0,  phi:36.0, k:5.0,
    rInter:0.75, interfacePerm:'Neutral' },
  { id:'m6', name:'Bedrock',       model:'Linear Elastic',type:'Non-porous',color:'#8d8d99',
    gUnsat:24.0, gSat:24.0, E:2.0e6,  nu:0.20, c:null, phi:null, k:0.0,
    rInter:1.00, interfacePerm:'Impermeable' }
];

/**
 * Looks a material up by id, falling back to the first material.
 * Used by the tree, the 3D scene and the Modify soil layers dialog.
 * @param {string} id
 * @return {!Object} The matching material, or the first one when none matches.
 */
App.matById = function (id) {
  return App.MATERIALS.filter(function (m) { return m.id === id; })[0] || App.MATERIALS[0];
};

App.STRUCT_MATERIALS = [
  { id:'p1', name:'Diaphragm wall',   kind:'Plate',  detail:'d = 0.80 m · EA = 2.4E7 kN/m · EI = 1.28E6 kNm²/m' },
  { id:'b1', name:'Strut HEB 400',    kind:'Beam',   detail:'A = 0.0198 m² · E = 2.1E8 kN/m²' },
  { id:'a1', name:'Ground anchor',    kind:'Anchor', detail:'EA = 6.5E5 kN · Lspacing = 2.5 m' },
  { id:'e1', name:'Bored pile Ø0.6',  kind:'Embedded beam', detail:'E = 3.0E7 kN/m² · Lspacing = 3.0 m' }
];

/* ── Boreholes and soil layers ─────────────────────────────────── */
App.BOREHOLES = [
  { id:'bh1', name:'BH-1', x: 0.0,  y: 0.0,  head: 0.00, water: -1.50 },
  { id:'bh2', name:'BH-2', x: 28.0, y: 4.0,  head:-0.40, water: -1.80 },
  { id:'bh3', name:'BH-3', x: 12.0, y: 30.0, head: 0.20, water: -1.20 }
];

/* Layer tops/bottoms are per borehole; the dialog edits this array.
   Deliberately kept to two layers so the mockup stays easy to read. */
App.LAYERS = [
  { id:'L1', name:'Soil_1', mat:'m2', tops:{ bh1: 0.00, bh2: -0.40, bh3:  0.20 },
                                      bots:{ bh1:-8.00, bh2: -9.20, bh3: -7.20 } },
  { id:'L2', name:'Soil_2', mat:'m4', tops:{ bh1:-8.00, bh2: -9.20, bh3: -7.20 },
                                      bots:{ bh1:-25.00, bh2:-25.00, bh3:-25.00 } }
];

// Counter behind the unique ids handed out by App.addBorehole.
App._boreholeSeq = App.BOREHOLES.length;
/**
 * Adds a borehole, copying each layer's top/bottom from the last borehole so
 * the stratigraphy stays well-formed.
 * Shared by the "Modify soil layers" dialog, the Soil-mode "Create borehole"
 * tool/menu item and the command-line `borehole` command.
 * Does not refresh the tree/3D scene: callers must also call
 * App.refreshSoilData() and App.Viewport.rebuildSoil().
 * @param {number=} x Plan x in metres; defaults to 10 m past the last borehole.
 * @param {number=} y Plan y in metres; defaults to the last borehole's y.
 * @return {!Object} The new borehole.
 */
App.addBorehole = function (x, y) {
  var last = App.BOREHOLES[App.BOREHOLES.length - 1];
  App._boreholeSeq += 1;
  var id = 'bhx' + App._boreholeSeq;
  var nb = { id: id, name: 'BH-' + (App.BOREHOLES.length + 1),
             x: x === undefined ? last.x + 10 : x,
             y: y === undefined ? last.y : y,
             head: last.head, water: last.water };
  App.LAYERS.forEach(function (L) {
    L.tops[id] = L.tops[last.id];
    L.bots[id] = L.bots[last.id];
  });
  App.BOREHOLES.push(nb);
  return nb;
};

/* ── Material set editing ───────────────────────────────────────
   Shared by the Material sets dialog in both apps. Ids must be unique and
   1-64 chars to satisfy the server's Ident type, and a material may only be
   removed once no layer references it — the server's Project validator
   rejects a layer pointing at a missing material outright. */

App._materialSeq = 0;

/**
 * Builds a new material with a fresh unique id.
 * Defaults satisfy every bound the server enforces, so it saves as-is.
 * @return {!Object}
 */
App.newMaterialDefaults = function () {
  App._materialSeq += 1;
  return {
    id: 'mx' + App._materialSeq,
    name: 'Material_' + (App.MATERIALS.length + 1),
    model: 'Mohr-Coulomb', type: 'Drained', color: '#9aa7b4',
    gUnsat: 17.0, gSat: 20.0, E: 10000, nu: 0.30, c: 0.0, phi: 30.0, k: 1.0,
    rInter: 0.70, interfacePerm: 'Neutral'
  };
};

/**
 * Appends a default material to App.MATERIALS.
 * @return {!Object} The new material.
 */
App.addMaterial = function () {
  var m = App.newMaterialDefaults();
  App.MATERIALS.push(m);
  return m;
};

/**
 * Inserts a deep copy of a material, with a new id, right after the source.
 * @param {!Object} src Material to copy; must be in App.MATERIALS.
 * @return {!Object} The copy.
 */
App.duplicateMaterial = function (src) {
  var m = JSON.parse(JSON.stringify(src));
  App._materialSeq += 1;
  m.id = 'mx' + App._materialSeq;
  m.name = src.name + ' (copy)';
  App.MATERIALS.splice(App.MATERIALS.indexOf(src) + 1, 0, m);
  return m;
};

/**
 * Returns the layers standing in the way of deleting a material.
 * @param {string} id Material id.
 * @return {!Array<string>} Names of the layers that reference it.
 */
App.layersUsingMaterial = function (id) {
  return App.LAYERS.filter(function (l) { return l.mat === id; })
                   .map(function (l) { return l.name; });
};

/* ── Layer editing ─────────────────────────────────────────────────
   Shared by the "Modify soil layers" dialog, the Model-explorer context
   menu and the Selection-explorer property grid. Every mutator keeps the
   two invariants the server enforces (server/app/schemas.py:110-135): a
   layer never inverts, and the stack never gains a gap. They return an
   error string to refuse an edit, or null when it was applied. */

/**
 * Looks a layer up by id.
 * @param {string} id
 * @return {?Object} The layer, or null when none matches.
 */
App.layerById = function (id) {
  return App.LAYERS.filter(function (l) { return l.id === id; })[0] || null;
};

/**
 * Removes a layer and closes the gap it leaves: the layer above takes over
 * its bottom, or, when the topmost one goes, the layer below takes over its
 * top. Refuses to remove the only layer.
 * @param {string} id
 * @return {?string} An error message, or null when the layer was removed.
 */
App.deleteLayerById = function (id) {
  if (App.LAYERS.length <= 1) return 'A model needs at least one soil layer.';
  var i = -1;
  App.LAYERS.forEach(function (l, n) { if (l.id === id) i = n; });
  if (i < 0) return 'That layer no longer exists.';

  var L = App.LAYERS[i];
  App.BOREHOLES.forEach(function (b) {
    if (i > 0) App.LAYERS[i - 1].bots[b.id] = L.bots[b.id];
    else if (App.LAYERS[1]) App.LAYERS[1].tops[b.id] = L.tops[b.id];
  });
  App.LAYERS.splice(i, 1);
  return null;
};

/**
 * Notes on the command line when a sloping layer boundary was flattened.
 * Says so rather than quietly discarding the slope; editing individual
 * boreholes in "Modify soil layers" keeps it.
 * @param {string} edge Which boundary changed: 'top' or 'bottom'.
 * @param {string} layerName
 * @param {!Array<number>} previous Boundary levels per borehole before the edit.
 */
function noteIfFlattened(edge, layerName, previous) {
  var varied = previous.some(function (z) { return Math.abs(z - previous[0]) > 1e-9; });
  if (varied && App.Command && App.Command.note) {
    App.Command.note('The ' + edge + ' of ' + layerName + ' sloped between boreholes; ' +
                     'it is now one level at every borehole.');
  }
}

/**
 * Puts a layer's top at one level across every borehole, carrying the
 * boundary with the layer above. Flattens a sloping boundary by design.
 * @param {string} id Layer id.
 * @param {number} z New top level in metres.
 * @return {?string} An error message, or null when the edit was applied.
 */
App.setLayerTopLevel = function (id, z) {
  var i = -1;
  App.LAYERS.forEach(function (l, n) { if (l.id === id) i = n; });
  if (i < 0) return 'That layer no longer exists.';
  var L = App.LAYERS[i], above = i > 0 ? App.LAYERS[i - 1] : null;

  var bad = null;
  App.BOREHOLES.forEach(function (b) {
    if (z < L.bots[b.id]) bad = 'z max must stay at or above this layer\'s bottom.';
    else if (above && z > above.tops[b.id]) bad = 'z max cannot rise above the top of the layer above.';
  });
  if (bad) return bad;

  var levelled = App.BOREHOLES.map(function (b) { return L.tops[b.id]; });
  App.BOREHOLES.forEach(function (b) {
    L.tops[b.id] = z;
    if (above) above.bots[b.id] = z;
  });
  noteIfFlattened('top', L.name, levelled);
  return null;
};

/**
 * Puts a layer's bottom at one level across every borehole, carrying the
 * boundary with the layer below. Flattens a sloping boundary by design.
 * @param {string} id Layer id.
 * @param {number} z New bottom level in metres.
 * @return {?string} An error message, or null when the edit was applied.
 */
App.setLayerBottomLevel = function (id, z) {
  var i = -1;
  App.LAYERS.forEach(function (l, n) { if (l.id === id) i = n; });
  if (i < 0) return 'That layer no longer exists.';
  var L = App.LAYERS[i], below = App.LAYERS[i + 1] || null;

  var bad = null;
  App.BOREHOLES.forEach(function (b) {
    if (z > L.tops[b.id]) bad = 'z min must stay at or below this layer\'s top.';
    else if (below && z < below.bots[b.id]) bad = 'z min cannot drop below the bottom of the layer below.';
  });
  if (bad) return bad;

  var levelled = App.BOREHOLES.map(function (b) { return L.bots[b.id]; });
  App.BOREHOLES.forEach(function (b) {
    L.bots[b.id] = z;
    if (below) below.tops[b.id] = z;
  });
  noteIfFlattened('bottom', L.name, levelled);
  return null;
};

/* Editor descriptors for the Selection-explorer property grid. A row that
   carries one renders a real control instead of static text
   (js/explorer.js propRow). */
App.LayerEditors = {
  /**
   * Builds a dropdown editor for a layer's material.
   * @param {!Object} layer
   * @return {!Object} Editor descriptor.
   */
  material: function (layer) {
    return {
      kind: 'select',
      options: function () {
        return App.MATERIALS.map(function (m) { return { value: m.id, text: m.name }; });
      },
      get: function () { return layer.mat; },
      set: function (v) { layer.mat = v; return null; }
    };
  },
  /**
   * Builds a number editor for a layer's highest top level, in metres.
   * @param {!Object} layer
   * @return {!Object} Editor descriptor.
   */
  topLevel: function (layer) {
    return {
      kind: 'number', decimals: 3, unit: 'm',
      get: function () {
        return Math.max.apply(null, App.BOREHOLES.map(function (b) { return layer.tops[b.id]; }));
      },
      set: function (v) { return App.setLayerTopLevel(layer.id, v); }
    };
  },
  /**
   * Builds a number editor for a layer's lowest bottom level, in metres.
   * @param {!Object} layer
   * @return {!Object} Editor descriptor.
   */
  bottomLevel: function (layer) {
    return {
      kind: 'number', decimals: 3, unit: 'm',
      get: function () {
        return Math.min.apply(null, App.BOREHOLES.map(function (b) { return layer.bots[b.id]; }));
      },
      set: function (v) { return App.setLayerBottomLevel(layer.id, v); }
    };
  }
};

/* ── Calculation phases ────────────────────────────────────────── */
App.PHASES = [
  { id:'ph0', name:'Initial phase',                 kind:'K0 procedure',  state:'initial', depth:0 },
  { id:'ph1', name:'Phase_1 — Wall installation',   kind:'Plastic',       state:'done',    depth:1 },
  { id:'ph2', name:'Phase_2 — Dewatering to -4.0 m',kind:'Flow only',     state:'done',    depth:2 },
  { id:'ph3', name:'Phase_3 — Excavation to -4.5 m',kind:'Plastic',       state:'done',    depth:3 },
  { id:'ph4', name:'Phase_4 — Strut installation',  kind:'Plastic',       state:'pending', depth:4 },
  { id:'ph5', name:'Phase_5 — Excavation to -9.0 m',kind:'Plastic',       state:'pending', depth:5 },
  { id:'ph6', name:'Phase_6 — Consolidation 90 d',  kind:'Consolidation', state:'pending', depth:6 }
];

App.PHASE_PROPS = {
  'General': [
    ['Name',                'Phase_4'],
    ['Start from phase',    'Phase_3 — Excavation to -4.5 m'],
    ['Calculation type',    'Plastic'],
    ['Loading type',        'Staged construction'],
    ['Pore pressure calc.', 'Phreatic'],
    ['Time interval',       '0.000', 'day']
  ],
  'Deformation control': [
    ['Ignore undrained behaviour', false],
    ['Reset displacements to zero', false],
    ['Reset small strain',          false],
    ['Updated mesh',                false]
  ],
  'Numerical control': [
    ['Max steps',            '250'],
    ['Tolerated error',      '0.010'],
    ['Max unloading steps',  '5'],
    ['Max iterations',       '60'],
    ['Arc-length control',   true]
  ]
};

/* ── Selection-explorer property sets, keyed by viewport object ── */
App.OBJECT_PROPS = {
  wall: {
    title: 'Plate_1 (Diaphragm wall)', icon: 'plate',
    groups: {
      'General':   [['Material','Diaphragm wall'], ['Active',true], ['Visible',true]],
      'Geometry':  [['Length','26.000','m'], ['Height','14.600','m'], ['Thickness','0.800','m'],
                    ['Local axis 1','(1.000, 0.000, 0.000)','',true],
                    ['Local axis 2','(0.000, 0.000, 1.000)','',true]],
      'Structural':[['EA₁','2.400E7','kN/m'], ['EI','1.280E6','kNm²/m'],
                    ['w','5.000','kN/m/m'], ['ν','0.150']],
      'Interfaces':[['Positive interface',true], ['Negative interface',true], ['Rinter','0.670']]
    }
  },
  struts: {
    title: 'Beam_1 (Strut HEB 400)', icon: 'beam',
    groups: {
      'General':   [['Material','Strut HEB 400'], ['Active',true]],
      'Geometry':  [['Length','21.600','m'], ['z','-3.000','m'], ['Spacing','6.000','m']],
      'Structural':[['A','1.980E-2','m²'], ['E','2.100E8','kN/m²'], ['I₂','5.770E-4','m⁴']]
    }
  },
  anchors: {
    title: 'NodeToNodeAnchor_1', icon: 'anchor',
    groups: {
      'General':   [['Material','Ground anchor'], ['Active',true]],
      'Geometry':  [['Length','12.000','m'], ['Inclination','35.0','°'], ['Spacing','6.000','m']],
      'Structural':[['EA','6.500E5','kN'], ['|Fmax,comp|','1.000E15','kN',true]]
    }
  },
  load: {
    title: 'SurfaceLoad_1', icon: 'load',
    groups: {
      'General':   [['Distribution','Uniform'], ['Active',true]],
      'Components':[['σz','-20.00','kN/m²'], ['σx','0.00','kN/m²'], ['σy','0.00','kN/m²']],
      'Geometry':  [['Area','60.000','m²']]
    }
  },
  water: {
    title: 'WaterLevel_1 (Global)', icon: 'waterlevel',
    groups: {
      'General':   [['Type','Borehole water level'], ['Active',true]],
      'Geometry':  [['z at BH-1','-1.500','m'], ['z at BH-2','-1.800','m'], ['z at BH-3','-1.200','m']],
      'Conditions':[['Time dependency','Constant'], ['Head function','—','',true]]
    }
  },
  mesh: {
    title: 'Mesh', icon: 'genmesh',
    groups: {
      'Statistics':[['Element type','10-node tetrahedral','',true],
                    ['Elements','24 118','',true], ['Nodes','38 942','',true],
                    ['Average element size','1.842','m',true]],
      'Settings':  [['Element distribution','Medium'], ['Relative element size','1.000'],
                    ['Enhanced mesh refinements',true]]
    }
  },
  excavation: {
    title: 'SoilVolume_pit (deactivated)', icon: 'cube',
    groups: {
      'General':   [['Material','Sand, loose'], ['Active',false]],
      'Geometry':  [['Depth','-7.000','m'], ['Plan area','520.000','m²']],
      'Phase':     [['Deactivated in','Phase_3','',true]]
    }
  }
};

/* Per-layer and per-borehole Selection-explorer properties, matching the
   per-layer/per-borehole keys used by the tree and viewport. Rebuilt by
   App.refreshSoilData() below whenever App.LAYERS/App.BOREHOLES change. */

/* ── Model explorer trees, per mode ────────────────────────────── */
(function () {
  /**
   * Builds a tree leaf for a material.
   * @param {!Object} m Material.
   * @return {!Object} Tree node.
   */
  function mat(m) { return { label: m.name, icon: null, swatch: m.color, leaf: true }; }

  /**
   * Builds an empty "Soil materials" tree node, one per Attributes library.
   * Its children are filled by App.refreshSoilData() so a material renamed or
   * recoloured in the material editor updates here too.
   * @return {!Object} Tree node.
   */
  function soilMaterialsNode() {
    return { label: 'Soil materials', icon: 'materials', count: 0, children: [] };
  }
  var soilMaterialLists = [soilMaterialsNode(), soilMaterialsNode()];

  var attributesSoil = {
    label: 'Attributes library', icon: 'folder', children: [
      soilMaterialLists[0],
      { label: 'Water levels', icon: 'waterlevel', count: 2, children: [
        { label: 'BoreholeWaterLevel_1', icon: 'water', leaf: true, obj: 'water' },
        { label: 'UserWaterLevel_1',     icon: 'water', leaf: true, obj: 'water' } ] }
    ]
  };

  var attributesStruct = {
    label: 'Attributes library', icon: 'folder', children: [
      soilMaterialLists[1],
      { label: 'Structural materials', icon: 'structure', count: App.STRUCT_MATERIALS.length,
        children: App.STRUCT_MATERIALS.map(function (s) {
          return { label: s.name + '  (' + s.kind + ')', icon: 'structure', leaf: true }; }) },
      { label: 'Loads', icon: 'load', count: 3, children: [
        { label: 'PointLoad_1',   icon: 'load', leaf: true, obj: 'load' },
        { label: 'LineLoad_1',    icon: 'load', leaf: true, obj: 'load' },
        { label: 'SurfaceLoad_1', icon: 'load', leaf: true, obj: 'load' } ] },
      { label: 'Water levels', icon: 'waterlevel', count: 2, children: [
        { label: 'BoreholeWaterLevel_1', icon: 'water', leaf: true, obj: 'water' },
        { label: 'UserWaterLevel_1',     icon: 'water', leaf: true, obj: 'water' } ] }
    ]
  };

  var soilVolumes = {
    label: 'Soil', icon: 'cube', count: 0, eye: true, obj: 'soil', children: []
  };

  var boreholeNodes = {
    label: 'Boreholes', icon: 'borehole', count: 0, eye: true, obj: 'boreholes', children: []
  };

  var geometry = {
    label: 'Geometry', icon: 'cube', children: [
      { label: 'Points',   icon: 'vertex',  count: 46, leaf: true },
      { label: 'Lines',    icon: 'edge',    count: 68, leaf: true },
      { label: 'Surfaces', icon: 'surface', count: 22, leaf: true },
      { label: 'Volumes',  icon: 'cube',    count:  7, leaf: true }
    ]
  };

  var structures = {
    label: 'Structures', icon: 'structure', children: [
      { label: 'Plates', icon: 'plate', count: 4, eye: true, obj: 'wall', children: [
        { label: 'Plate_1  (north wall)', icon:'plate', leaf:true, eye:true, obj:'wall' },
        { label: 'Plate_2  (east wall)',  icon:'plate', leaf:true, eye:true, obj:'wall' },
        { label: 'Plate_3  (south wall)', icon:'plate', leaf:true, eye:true, obj:'wall' },
        { label: 'Plate_4  (west wall)',  icon:'plate', leaf:true, eye:true, obj:'wall' } ] },
      { label: 'Beams', icon: 'beam', count: 3, eye: true, obj: 'struts', children: [
        { label: 'Beam_1  (strut)', icon:'beam', leaf:true, eye:true, obj:'struts' },
        { label: 'Beam_2  (strut)', icon:'beam', leaf:true, eye:true, obj:'struts' },
        { label: 'Beam_3  (strut)', icon:'beam', leaf:true, eye:true, obj:'struts' } ] },
      { label: 'Node-to-node anchors', icon: 'anchor', count: 6, eye: true, obj: 'anchors', leaf: true },
      { label: 'Embedded beam rows',   icon: 'embedded', count: 12, eye: true, obj: 'piles', leaf: true },
      { label: 'Interfaces',           icon: 'interface', count: 8, leaf: true }
    ]
  };

  var modelConditions = {
    label: 'Model conditions', icon: 'settings', children: [
      { label: 'Domain',        icon: 'cube',   leaf: true },
      { label: 'Water',         icon: 'water',  leaf: true, eye: true, obj: 'water' },
      { label: 'GroundwaterFlow', icon:'flowfn',leaf: true },
      { label: 'Climate',       icon: 'flowfn', leaf: true },
      { label: 'Initial condition', icon:'settings', leaf: true },
      { label: 'Pseudo-static', icon: 'settings', leaf: true }
    ]
  };

  var meshNode = {
    label: 'Mesh', icon: 'genmesh', eye: true, obj: 'mesh', children: [
      { label: 'Element distribution: Medium', icon: 'settings', leaf: true },
      { label: 'Elements: 24 118', icon: 'genmesh',  leaf: true, obj: 'mesh' },
      { label: 'Nodes: 38 942',    icon: 'vertex',   leaf: true, obj: 'mesh' },
      { label: 'Local refinements (3)', icon: 'refine', leaf: true }
    ]
  };

  var flowNode = {
    label: 'Flow conditions', icon: 'waterlevel', eye: true, obj: 'water', children: [
      { label: 'BoreholeWaterLevel_1', icon: 'water', leaf: true, eye: true, obj: 'water' },
      { label: 'UserWaterLevel_1',     icon: 'water', leaf: true, eye: true, obj: 'water' },
      { label: 'Well_1  (extraction)', icon: 'well',  leaf: true, eye: true, obj: 'wells' },
      { label: 'Well_2  (extraction)', icon: 'well',  leaf: true, eye: true, obj: 'wells' },
      { label: 'Drain_1',              icon: 'drain', leaf: true }
    ]
  };

  App.TREES = {
    soil:       [attributesSoil, soilVolumes, boreholeNodes, modelConditions],
    structures: [attributesStruct, geometry, structures, soilVolumes, modelConditions],
    mesh:       [meshNode, geometry, structures, soilVolumes, modelConditions],
    flow:       [flowNode, attributesSoil, soilVolumes, structures, modelConditions],
    staged:     [structures, soilVolumes, flowNode, modelConditions]
  };

  /**
   * Rebuilds everything derived from App.LAYERS / App.BOREHOLES in place.
   * Updates the material, Soil and Boreholes tree nodes and the per-layer and
   * per-borehole entries of App.OBJECT_PROPS, so the Model explorer and
   * property grid stay in sync after soil data changes.
   */
  App.refreshSoilData = function () {
    soilMaterialLists.forEach(function (node) {
      node.count = App.MATERIALS.length;
      node.children = App.MATERIALS.map(mat);
    });

    soilVolumes.count = App.LAYERS.length;
    soilVolumes.children = App.LAYERS.map(function (l) {
      var m = App.matById(l.mat);
      return { label: l.name + '  ·  ' + m.name, swatch: m.color, leaf: true, eye: true, obj: 'soil_' + l.id };
    });

    boreholeNodes.count = App.BOREHOLES.length;
    boreholeNodes.children = App.BOREHOLES.map(function (b) {
      return { label: b.name, icon: 'borehole', leaf: true, eye: true, obj: 'bh_' + b.id };
    });

    Object.keys(App.OBJECT_PROPS).forEach(function (k) {
      if (k.indexOf('soil_') === 0 || k.indexOf('bh_') === 0) delete App.OBJECT_PROPS[k];
    });

    App.LAYERS.forEach(function (l, i) {
      var m = App.matById(l.mat);
      var tops = App.BOREHOLES.map(function (bh) { return l.tops[bh.id]; });
      var bots = App.BOREHOLES.map(function (bh) { return l.bots[bh.id]; });
      var zMax = Math.max.apply(null, tops), zMin = Math.min.apply(null, bots);
      App.OBJECT_PROPS['soil_' + l.id] = {
        title: 'BoreholeVolume_' + (i + 1) + ' (' + l.name + ')', icon: 'cube',
        groups: {
          'General':   [['Material', m.name, '', false, App.LayerEditors.material(l)],
                        ['Volume', '48 000.0', 'm³', true], ['Active', true]],
          // x/y are the model's plan extents, which this build bakes into
          // js/viewport.js — nothing here could act on an edit, so they are
          // shown read-only rather than styled as if they were editable.
          'Geometry':  [['x min','0.000','m', true], ['x max','50.000','m', true],
                        ['y min','0.000','m', true], ['y max','40.000','m', true],
                        ['z min', zMin.toFixed(3), 'm', false, App.LayerEditors.bottomLevel(l)],
                        ['z max', zMax.toFixed(3), 'm', false, App.LayerEditors.topLevel(l)]],
          'Mesh':      [['Coarseness factor','1.000'], ['Element count','—', '', true]]
        }
      };
    });

    App.BOREHOLES.forEach(function (b) {
      var bots = App.LAYERS.map(function (l) { return l.bots[b.id]; });
      var zBot = Math.min.apply(null, bots);
      App.OBJECT_PROPS['bh_' + b.id] = {
        title: b.name, icon: 'borehole',
        groups: {
          'General':  [['x', b.x.toFixed(3), 'm'], ['y', b.y.toFixed(3), 'm'],
                       ['Ground level', b.head.toFixed(3), 'm'],
                       ['Water level', b.water.toFixed(3), 'm']],
          'Layers':   [['Number of layers', String(App.LAYERS.length), '', true],
                       ['Bottom level', zBot.toFixed(3), 'm', true]]
        }
      };
    });
  };

  App.refreshSoilData();
})();

/* ── Command line ──────────────────────────────────────────────── */
App.CMD_WELCOME = [
  ['note', '# ' + App.PRODUCT.name + ' — ' + App.PRODUCT.version],
  ['note', '# UI mockup: the command line accepts a small set of demo commands.'],
  ['note', '# Try:  borehole 0 0  ·  gotostructures  ·  mesh  ·  soillayers  ·  help'],
  ['ok',   'Project "' + App.PRODUCT.project + '" opened.'],
  ['ok',   'Model geometry: 50.0 × 40.0 × 25.0 m — 3 boreholes, 2 soil layers.']
];

App.CMD_HISTORY = [
  ['echo', '_borehole 0 0'],
  ['ok',   'BH-1'],
  ['echo', '_soillayer 2'],
  ['ok',   'Soil_1 Soil_2'],
  ['echo', '_setmaterial Soil_1 "Sand, loose"'],
  ['ok',   'OK'],
  ['echo', '_surface (0 0 0) (30 0 0) (30 24 0) (0 24 0)'],
  ['ok',   'Surface_1'],
  ['echo', '_plate Surface_1'],
  ['ok',   'Plate_1'],
  ['echo', '_mesh 0.06'],
  ['ok',   'Mesh generated: 24118 elements, 38942 nodes'],
  ['echo', '_phase InitialPhase'],
  ['ok',   'Phase_1']
];

/* Canned responses. Key = first word of the typed command. */
App.CMD_RESPONSES = {
  'help': [['note','Available demo commands:'],
           ['note','  borehole <x> <y>      add a borehole marker'],
           ['note','  soillayers            open the Modify soil layers window'],
           ['note','  materials             open the material sets window'],
           ['note','  mesh                  generate the finite element mesh'],
           ['note','  gotosoil | gotostructures | gotomesh | gotoflow | gotostaged'],
           ['note','  view iso|top|front|side       zoomfit       clear']],
  'soillayer':  [['ok','Soil_1 Soil_2']],
  'plate':      [['ok','Plate_5']],
  'beam':       [['ok','Beam_4']],
  'anchor':     [['ok','NodeToNodeAnchor_7']],
  'surface':    [['ok','Surface_23']],
  'line':       [['ok','Line_69']],
  'point':      [['ok','Point_47']],
  'calculate':  [['note','Calculation is not available in this UI mockup — no solver is attached.']]
};
