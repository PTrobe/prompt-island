/**
 * IslandMap.ts — Location definitions and formation spots for all 6 agents.
 *
 * World: 40×30 tiles × 32px = 1280×960px
 * Camera zoom=1 → full island visible in 1280×960 canvas
 *
 * Each location has 6 formation spots (pixel coords) so agents never overlap.
 * Spots are arranged around the focal point of each area.
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
    cx: 448,
    cy: 480,
    spots: [
      { x: 416, y: 448 },
      { x: 448, y: 448 },
      { x: 480, y: 448 },
      { x: 416, y: 480 },
      { x: 448, y: 480 },
      { x: 480, y: 480 },
    ],
  },
  beach: {
    id: 'beach',
    label: 'Beach',
    cx: 640,
    cy: 160,
    spots: [
      { x: 576, y: 144 },
      { x: 608, y: 144 },
      { x: 640, y: 144 },
      { x: 672, y: 144 },
      { x: 608, y: 176 },
      { x: 640, y: 176 },
    ],
  },
  jungle: {
    id: 'jungle',
    label: 'Jungle',
    cx: 256,
    cy: 384,
    spots: [
      { x: 224, y: 352 },
      { x: 256, y: 352 },
      { x: 288, y: 352 },
      { x: 224, y: 384 },
      { x: 256, y: 384 },
      { x: 288, y: 384 },
    ],
  },
  tribal_fire: {
    id: 'tribal_fire',
    label: 'Tribal Fire',
    cx: 640,
    cy: 736,
    spots: [
      { x: 592, y: 704 },
      { x: 624, y: 704 },
      { x: 656, y: 704 },
      { x: 688, y: 704 },
      { x: 608, y: 736 },
      { x: 672, y: 736 },
    ],
  },
  confessional_hut: {
    id: 'confessional_hut',
    label: 'Confessional',
    cx: 1024,
    cy: 384,
    spots: [
      { x: 992, y: 352 },
      { x: 1024, y: 352 },
      { x: 1056, y: 352 },
      { x: 992, y: 384 },
      { x: 1024, y: 384 },
      { x: 1056, y: 384 },
    ],
  },
  shelter: {
    id: 'shelter',
    label: 'Shelter',
    cx: 416,
    cy: 640,
    spots: [
      { x: 384, y: 608 },
      { x: 416, y: 608 },
      { x: 448, y: 608 },
      { x: 384, y: 640 },
      { x: 416, y: 640 },
      { x: 448, y: 640 },
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
