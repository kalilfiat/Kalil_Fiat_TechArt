figma.showUI(__html__, {
  width: 360,
  height: 700,
  themeColors: true
});

const DEFAULTS = {
  tileWidth: 32,
  tileHeight: 16,
  depth: 32,
  height: 16,
  prismWidth: 128,
  widthTiles: 1,
  depthTiles: 1,
  heightTiles: 1,
  roomWidthTiles: 4,
  roomDepthTiles: 4,
  roomHeightTiles: 2,
  wallThicknessTiles: 0.25,
  columns: 8,
  rows: 8,
  scale: 1,
  originX: 0,
  originY: 0,
  strokeWidth: 1,
  fillColorTop: "#8fd3ff",
  fillColorLeft: "#5599d6",
  fillColorRight: "#2f6ea8",
  strokeColor: "#1f2937",
  useStroke: true,
  createAsGroup: true,
  snapToPixel: true
};

function clampNumber(value, fallback, min) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(parsed, min);
}

function normalizeSettings(raw) {
  const tileWidth = clampNumber(raw.tileWidth, DEFAULTS.tileWidth, 1);
  const tileHeight = clampNumber(raw.tileHeight, DEFAULTS.tileHeight, 1);
  const widthTiles = clampNumber(raw.widthTiles, DEFAULTS.widthTiles, 0);
  const depthTiles = clampNumber(raw.depthTiles, DEFAULTS.depthTiles, 0);
  const heightTiles = clampNumber(raw.heightTiles, DEFAULTS.heightTiles, 0);
  const roomWidthTiles = clampNumber(raw.roomWidthTiles, DEFAULTS.roomWidthTiles, 0);
  const roomDepthTiles = clampNumber(raw.roomDepthTiles, DEFAULTS.roomDepthTiles, 0);
  const roomHeightTiles = clampNumber(raw.roomHeightTiles, DEFAULTS.roomHeightTiles, 0);
  const wallThicknessTiles = clampNumber(raw.wallThicknessTiles, DEFAULTS.wallThicknessTiles, 0);

  return {
    tileWidth: tileWidth,
    tileHeight: tileHeight,
    widthTiles: widthTiles,
    depthTiles: depthTiles,
    heightTiles: heightTiles,
    roomWidthTiles: roomWidthTiles,
    roomDepthTiles: roomDepthTiles,
    roomHeightTiles: roomHeightTiles,
    wallThicknessTiles: wallThicknessTiles,
    depth: depthTiles * tileWidth,
    height: heightTiles * tileHeight,
    prismWidth: widthTiles * tileWidth,
    columns: Math.floor(clampNumber(raw.columns, DEFAULTS.columns, 1)),
    rows: Math.floor(clampNumber(raw.rows, DEFAULTS.rows, 1)),
    scale: clampNumber(raw.scale, DEFAULTS.scale, 0.01),
    originX: figma.viewport.center.x,
    originY: figma.viewport.center.y,
    strokeWidth: raw.useStroke === false ? 0 : clampNumber(raw.strokeWidth, DEFAULTS.strokeWidth, 0),
    fillColorTop: raw.fillColorTop || DEFAULTS.fillColorTop,
    fillColorLeft: raw.fillColorLeft || DEFAULTS.fillColorLeft,
    fillColorRight: raw.fillColorRight || DEFAULTS.fillColorRight,
    strokeColor: raw.strokeColor || DEFAULTS.strokeColor,
    useStroke: raw.useStroke !== false,
    createAsGroup: raw.createAsGroup !== false,
    snapToPixel: raw.snapToPixel !== false
  };
}

function scaled(settings) {
  const s = settings.scale;
  const result = {};
  Object.keys(settings).forEach(function (key) {
    result[key] = settings[key];
  });
  result.tileWidth = settings.tileWidth * s;
  result.tileHeight = settings.tileHeight * s;
  result.depth = settings.depth * s;
  result.height = settings.height * s;
  result.prismWidth = settings.prismWidth * s;
  result.strokeWidth = settings.strokeWidth * s;
  result.originX = settings.originX;
  result.originY = settings.originY;
  return result;
}

function snap(value, enabled) {
  return enabled ? Math.round(value) : value;
}

function point(x, y, snapToPixel) {
  return {
    x: snap(x, snapToPixel),
    y: snap(y, snapToPixel)
  };
}

function hexToPaint(hex) {
  const clean = String(hex).replace("#", "");
  const bigint = parseInt(clean.length === 3
    ? clean.split("").map(function (char) { return char + char; }).join("")
    : clean, 16);

  if (!Number.isFinite(bigint)) {
    return { type: "SOLID", color: { r: 0, g: 0, b: 0 } };
  }

  return {
    type: "SOLID",
    color: {
      r: ((bigint >> 16) & 255) / 255,
      g: ((bigint >> 8) & 255) / 255,
      b: (bigint & 255) / 255
    }
  };
}

function localizePoints(points) {
  const xs = points.map(function (p) { return p.x; });
  const ys = points.map(function (p) { return p.y; });
  const minX = Math.min.apply(null, xs);
  const minY = Math.min.apply(null, ys);
  return {
    x: minX,
    y: minY,
    points: points.map(function (p) {
      return { x: p.x - minX, y: p.y - minY };
    })
  };
}

function pathFromPoints(points) {
  const first = points[0];
  const rest = points.slice(1);
  const lines = rest.map(function (p) {
    return "L " + p.x + " " + p.y;
  }).join(" ");
  return "M " + first.x + " " + first.y + " " + lines + " Z";
}

function createPolygon(name, points, fillColor, strokeColor, strokeWidth) {
  const localized = localizePoints(points);
  const vector = figma.createVector();
  vector.name = name;
  vector.x = localized.x;
  vector.y = localized.y;
  vector.vectorPaths = [{
    windingRule: "NONZERO",
    data: pathFromPoints(localized.points)
  }];
  vector.fills = [hexToPaint(fillColor)];
  vector.strokes = strokeWidth > 0 ? [hexToPaint(strokeColor)] : [];
  vector.strokeWeight = strokeWidth;
  vector.strokeJoin = "ROUND";
  return vector;
}

function createIsoDiamondPoints(x, y, w, h, snapToPixel) {
  return [
    point(x + w / 2, y, snapToPixel),
    point(x + w, y + h / 2, snapToPixel),
    point(x + w / 2, y + h, snapToPixel),
    point(x, y + h / 2, snapToPixel)
  ];
}

function createRectPoints(x, y, w, h, snapToPixel) {
  return [
    point(x, y, snapToPixel),
    point(x + w, y, snapToPixel),
    point(x + w, y + h, snapToPixel),
    point(x, y + h, snapToPixel)
  ];
}

function groupOrSelect(nodes, name, createAsGroup) {
  let selection = nodes;
  if (createAsGroup && nodes.length > 1) {
    const group = figma.group(nodes, figma.currentPage);
    group.name = name;
    selection = [group];
  } else if (nodes.length === 1) {
    nodes[0].name = name;
  }

  figma.currentPage.selection = selection;
  figma.viewport.scrollAndZoomIntoView(selection);
  return selection;
}

function createTile(settings) {
  const cfg = scaled(settings);
  const points = createIsoDiamondPoints(
    cfg.originX,
    cfg.originY,
    cfg.tileWidth,
    cfg.tileHeight,
    cfg.snapToPixel
  );
  const tile = createPolygon(
    "ISO_Tile_Face_" + settings.tileWidth + "x" + settings.tileHeight,
    points,
    cfg.fillColorTop,
    cfg.strokeColor,
    cfg.strokeWidth
  );
  return groupOrSelect([tile], "ISO_Tile_" + settings.tileWidth + "x" + settings.tileHeight, cfg.createAsGroup);
}

function createCube(settings) {
  return createBlock(settings, "ISO_Block_" + settings.widthTiles + "x" + settings.depthTiles + "x" + settings.heightTiles);
}

function createBlock(settings, groupName) {
  const cfg = scaled(settings);
  const faces = createBlockFaces(cfg);
  return groupOrSelect(faces, groupName, cfg.createAsGroup);
}

function createBlockFaces(cfg) {
  const x = cfg.originX;
  const y = cfg.originY;
  const widthVector = { x: cfg.prismWidth / 2, y: cfg.widthTiles * cfg.tileHeight / 2 };
  const depthVector = { x: -cfg.depth / 2, y: cfg.depthTiles * cfg.tileHeight / 2 };

  const back = point(x, y, cfg.snapToPixel);
  const right = point(x + widthVector.x, y + widthVector.y, cfg.snapToPixel);
  const front = point(x + widthVector.x + depthVector.x, y + widthVector.y + depthVector.y, cfg.snapToPixel);
  const left = point(x + depthVector.x, y + depthVector.y, cfg.snapToPixel);
  const frontDown = point(front.x, front.y + cfg.height, cfg.snapToPixel);
  const leftDown = point(left.x, left.y + cfg.height, cfg.snapToPixel);
  const rightDown = point(right.x, right.y + cfg.height, cfg.snapToPixel);

  const topFace = createPolygon("Top", [back, right, front, left], cfg.fillColorTop, cfg.strokeColor, cfg.strokeWidth);
  const leftFace = createPolygon("Left", [left, front, frontDown, leftDown], cfg.fillColorLeft, cfg.strokeColor, cfg.strokeWidth);
  const rightFace = createPolygon("Right", [front, right, rightDown, frontDown], cfg.fillColorRight, cfg.strokeColor, cfg.strokeWidth);

  return [leftFace, rightFace, topFace];
}

function createWallGroup(name, cfg) {
  const faces = createBlockFaces(cfg);
  faces.forEach(function (node) {
    node.name = name + "_" + node.name;
  });
  const group = figma.group(faces, figma.currentPage);
  group.name = name;
  return group;
}

function roomVector(cfg, widthTiles, depthTiles) {
  return {
    x: (widthTiles * cfg.tileWidth - depthTiles * cfg.tileWidth) / 2,
    y: (widthTiles * cfg.tileHeight + depthTiles * cfg.tileHeight) / 2
  };
}

function blockCfgFromUnits(settings, x, y, widthTiles, depthTiles, heightTiles) {
  const cfg = scaled(settings);
  cfg.originX = x;
  cfg.originY = y;
  cfg.widthTiles = widthTiles;
  cfg.depthTiles = depthTiles;
  cfg.heightTiles = heightTiles;
  cfg.prismWidth = widthTiles * settings.tileWidth * settings.scale;
  cfg.depth = depthTiles * settings.tileWidth * settings.scale;
  cfg.height = heightTiles * settings.tileHeight * settings.scale;
  return cfg;
}

function createRoom(settings) {
  const cfg = scaled(settings);
  const x = cfg.originX;
  const y = cfg.originY;
  const roomWidth = settings.roomWidthTiles;
  const roomDepth = settings.roomDepthTiles;
  const roomHeight = settings.roomHeightTiles;
  const thickness = settings.wallThicknessTiles;
  const walls = [];
  const frontOffset = roomVector(cfg, 0, Math.max(roomDepth - thickness, 0));
  const rightOffset = roomVector(cfg, Math.max(roomWidth - thickness, 0), 0);

  const backWall = blockCfgFromUnits(settings, x, y, roomWidth, thickness, roomHeight);
  const frontWall = blockCfgFromUnits(settings, x + frontOffset.x, y + frontOffset.y, roomWidth, thickness, roomHeight);
  const leftWall = blockCfgFromUnits(settings, x, y, thickness, roomDepth, roomHeight);
  const rightWall = blockCfgFromUnits(settings, x + rightOffset.x, y + rightOffset.y, thickness, roomDepth, roomHeight);

  walls.push(createWallGroup("Room_Back_Wall", backWall));
  walls.push(createWallGroup("Room_Left_Wall", leftWall));
  walls.push(createWallGroup("Room_Right_Wall", rightWall));
  walls.push(createWallGroup("Room_Front_Wall", frontWall));

  return groupOrSelect(walls, "ISO_Room_" + roomWidth + "x" + roomDepth + "x" + roomHeight, true);
}

function createFlatWall(settings, orientation) {
  const cfg = scaled(settings);
  const width = Math.max(cfg.prismWidth, 1);
  const height = Math.max(cfg.height, 1);
  const fillColor = orientation === "horizontal" ? cfg.fillColorLeft : cfg.fillColorRight;
  const suffix = orientation === "horizontal" ? "H" : "V";
  const points = createRectPoints(cfg.originX, cfg.originY, width, height, cfg.snapToPixel);
  const wall = createPolygon(
    "Wall_" + suffix,
    points,
    fillColor,
    cfg.strokeColor,
    cfg.strokeWidth
  );
  return groupOrSelect([wall], "ISO_Flat_Wall_" + suffix + "_" + settings.widthTiles + "x" + settings.heightTiles, cfg.createAsGroup);
}

function createPlane(settings) {
  const cfg = scaled(settings);
  const nodes = [];

  for (let row = 0; row < cfg.rows; row += 1) {
    for (let col = 0; col < cfg.columns; col += 1) {
      const x = cfg.originX + (col - row) * (cfg.tileWidth / 2);
      const y = cfg.originY + (col + row) * (cfg.tileHeight / 2);
      const points = createIsoDiamondPoints(x, y, cfg.tileWidth, cfg.tileHeight, cfg.snapToPixel);
      nodes.push(createPolygon(
        "Tile_" + (col + 1) + "_" + (row + 1),
        points,
        cfg.fillColorTop,
        cfg.strokeColor,
        cfg.strokeWidth
      ));
    }
  }

  return groupOrSelect(nodes, "ISO_Plane_" + settings.columns + "x" + settings.rows, cfg.createAsGroup);
}

figma.ui.postMessage({ type: "defaults", settings: DEFAULTS });

figma.ui.onmessage = function (message) {
  try {
    if (message.type === "resize-ui") {
      figma.ui.resize(
        clampNumber(message.width, 360, 320),
        clampNumber(message.height, 700, 420)
      );
      return;
    }

    const settings = normalizeSettings(message.settings || {});

    if (message.type === "create-tile") createTile(settings);
    if (message.type === "create-cube") createCube(settings);
    if (message.type === "create-wall-horizontal") createFlatWall(settings, "horizontal");
    if (message.type === "create-wall-vertical") createFlatWall(settings, "vertical");
    if (message.type === "create-plane") createPlane(settings);
    if (message.type === "create-room") createRoom(settings);

    figma.ui.postMessage({ type: "status", message: "Created" });
  } catch (error) {
    figma.notify("Iso Shape Builder error: " + error.message);
    figma.ui.postMessage({ type: "status", message: error.message });
  }
};
