/**
 * IslandMap.ts — Location definitions and formation spots for all 6 agents.
 *
 * World: 40×30 tiles × 64px = 2560×1920px
 * Canvas: 1280×960 — zoom=0.5 shows full island, zoom=1 shows a close quadrant
 *
 * Each location has 6 formation spots (pixel coords) so agents never overlap.
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
  camp: {
    id: 'camp',
    label: 'Camp',
    cx: 896,
    cy: 960,
    spots: [
      { x: 832, y: 896 },
      { x: 896, y: 896 },
      { x: 960, y: 896 },
      { x: 832, y: 960 },
      { x: 896, y: 960 },
      { x: 960, y: 960 },
    ],
  },
  beach: {
    id: 'beach',
    label: 'Beach',
    cx: 1280,
    cy: 320,
    spots: [
      { x: 1152, y: 288 },
      { x: 1216, y: 288 },
      { x: 1280, y: 288 },
      { x: 1344, y: 288 },
      { x: 1216, y: 352 },
      { x: 1280, y: 352 },
    ],
  },
  jungle: {
    id: 'jungle',
    label: 'Jungle',
    cx: 512,
    cy: 768,
    spots: [
      { x: 448, y: 704 },
      { x: 512, y: 704 },
      { x: 576, y: 704 },
      { x: 448, y: 768 },
      { x: 512, y: 768 },
      { x: 576, y: 768 },
    ],
  },
  tribal_fire: {
    id: 'tribal_fire',
    label: 'Tribal Fire',
    cx: 1280,
    cy: 1472,
    spots: [
      { x: 1184, y: 1408 },
      { x: 1248, y: 1408 },
      { x: 1312, y: 1408 },
      { x: 1376, y: 1408 },
      { x: 1216, y: 1472 },
      { x: 1344, y: 1472 },
    ],
  },
  confessional_hut: {
    id: 'confessional_hut',
    label: 'Confessional',
    cx: 2048,
    cy: 768,
    spots: [
      { x: 1984, y: 704 },
      { x: 2048, y: 704 },
      { x: 2112, y: 704 },
      { x: 1984, y: 768 },
      { x: 2048, y: 768 },
      { x: 2112, y: 768 },
    ],
  },
  shelter: {
    id: 'shelter',
    label: 'Shelter',
    cx: 832,
    cy: 1280,
    spots: [
      { x: 768, y: 1216 },
      { x: 832, y: 1216 },
      { x: 896, y: 1216 },
      { x: 768, y: 1280 },
      { x: 832, y: 1280 },
      { x: 896, y: 1280 },
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
