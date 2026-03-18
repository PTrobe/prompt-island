/**
 * IslandMap.ts — Location definitions and formation spots for all 6 agents.
 *
 * World: 80×60 tiles × 32px = 2560×1920px
 * Canvas: 1280×960 — initial zoom=2 shows a comfortable close-up
 *
 * Formation spots are deliberately irregular (not a grid) so agents look like
 * people standing naturally rather than a military parade.
 * Minimum gap between spots: ~96px (3× character width).
 */

export type LocationId =
  | 'camp'
  | 'beach'
  | 'jungle'
  | 'tribal_fire'
  | 'confessional_hut'
  | 'shelter';

export interface Location {
  id: LocationId;
  label: string;
  /** Centre pixel coord for camera focus */
  cx: number;
  cy: number;
  /** 6 formation spots (pixel coords) where agents stand */
  spots: Array<{ x: number; y: number }>;
}

export const LOCATIONS: Record<LocationId, Location> = {
  // Camp — loose arc, 3 front + 3 behind, staggered x offsets
  camp: {
    id: 'camp',
    label: 'Camp',
    cx: 896,
    cy: 960,
    spots: [
      { x: 800, y: 992 },
      { x: 896, y: 1008 },
      { x: 992, y: 992 },
      { x: 752, y: 896 },
      { x: 880, y: 880 },
      { x: 1008, y: 904 },
    ],
  },
  // Beach — loose horizontal line along the water, slightly staggered depth
  beach: {
    id: 'beach',
    label: 'Beach',
    cx: 1280,
    cy: 352,
    spots: [
      { x: 1072, y: 368 },
      { x: 1168, y: 352 },
      { x: 1264, y: 384 },
      { x: 1360, y: 352 },
      { x: 1456, y: 368 },
      { x: 1168, y: 448 },
    ],
  },
  // Jungle — scattered irregularly among trees
  jungle: {
    id: 'jungle',
    label: 'Jungle',
    cx: 512,
    cy: 768,
    spots: [
      { x: 432, y: 720 },
      { x: 560, y: 736 },
      { x: 464, y: 832 },
      { x: 592, y: 848 },
      { x: 384, y: 816 },
      { x: 528, y: 912 },
    ],
  },
  // Tribal fire — arc/semicircle around fire (fire is at ~1280, 1472)
  tribal_fire: {
    id: 'tribal_fire',
    label: 'Tribal Fire',
    cx: 1280,
    cy: 1488,
    spots: [
      { x: 1152, y: 1440 },
      { x: 1280, y: 1408 },
      { x: 1408, y: 1440 },
      { x: 1120, y: 1536 },
      { x: 1280, y: 1568 },
      { x: 1440, y: 1536 },
    ],
  },
  // Confessional hut — 1 agent enters, rest wait outside in a loose cluster
  confessional_hut: {
    id: 'confessional_hut',
    label: 'Confessional',
    cx: 2048,
    cy: 800,
    spots: [
      { x: 2048, y: 720 },
      { x: 1936, y: 784 },
      { x: 2048, y: 832 },
      { x: 2160, y: 784 },
      { x: 1952, y: 896 },
      { x: 2144, y: 896 },
    ],
  },
  // Shelter — two rows with natural stagger, people lounging around
  shelter: {
    id: 'shelter',
    label: 'Shelter',
    cx: 832,
    cy: 1312,
    spots: [
      { x: 720,  y: 1280 },
      { x: 848,  y: 1264 },
      { x: 960,  y: 1280 },
      { x: 672,  y: 1376 },
      { x: 816,  y: 1392 },
      { x: 944,  y: 1360 },
    ],
  },
};

/** Map Phaser phase names → location id */
export function phaseToLocation(phase: string): LocationId {
  if (phase.includes('confessional')) return 'confessional_hut';
  if (phase.includes('tribal') || phase.includes('vote')) return 'tribal_fire';
  if (phase.includes('beach')) return 'beach';
  if (phase.includes('jungle')) return 'jungle';
  if (phase.includes('shelter')) return 'shelter';
  return 'camp';
}
