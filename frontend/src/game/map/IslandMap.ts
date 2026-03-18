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
  // Beach — loose line on the sand strip at the north shore (rows 13-16)
  beach: {
    id: 'beach',
    label: 'Beach',
    cx: 1312,
    cy: 448,
    spots: [
      { x: 1312, y: 416 },
      { x: 1440, y: 416 },
      { x: 1248, y: 448 },
      { x: 1376, y: 416 },
      { x: 1184, y: 480 },
      { x: 1248, y: 480 },
    ],
  },
  // Jungle — west interior, compact dark-grass zone (cols 21-25, rows 23-28)
  jungle: {
    id: 'jungle',
    label: 'Jungle',
    cx: 736,
    cy: 800,
    spots: [
      { x: 672, y: 736 },
      { x: 800, y: 736 },
      { x: 672, y: 832 },
      { x: 800, y: 832 },
      { x: 704, y: 896 },
      { x: 768, y: 864 },
    ],
  },
  // Tribal fire — arc/semicircle around fire (rows 42-46, cols 37-43)
  tribal_fire: {
    id: 'tribal_fire',
    label: 'Tribal Fire',
    cx: 1280,
    cy: 1408,
    spots: [
      { x: 1184, y: 1344 },
      { x: 1280, y: 1344 },
      { x: 1376, y: 1344 },
      { x: 1184, y: 1440 },
      { x: 1280, y: 1440 },
      { x: 1408, y: 1440 },
    ],
  },
  // Confessional hut — east interior, safely within island (cols 55-62, rows 20-27)
  confessional_hut: {
    id: 'confessional_hut',
    label: 'Confessional',
    cx: 1792,
    cy: 704,
    spots: [
      { x: 1760, y: 640 },
      { x: 1696, y: 704 },
      { x: 1824, y: 704 },
      { x: 1760, y: 768 },
      { x: 1888, y: 736 },
      { x: 1696, y: 800 },
    ],
  },
  // Shelter — south-west interior, all safely on grass (rows 38-41, cols 26-31)
  shelter: {
    id: 'shelter',
    label: 'Shelter',
    cx: 896,
    cy: 1248,
    spots: [
      { x: 832,  y: 1216 },
      { x: 960,  y: 1216 },
      { x: 864,  y: 1280 },
      { x: 992,  y: 1248 },
      { x: 896,  y: 1312 },
      { x: 960,  y: 1280 },
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
