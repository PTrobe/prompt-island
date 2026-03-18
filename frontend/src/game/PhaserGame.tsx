/**
 * PhaserGame.tsx — React wrapper that mounts/unmounts the Phaser game instance.
 *
 * Loaded with next/dynamic { ssr: false } — Phaser uses window/document APIs
 * that do not exist during server-side rendering.
 *
 * Props:
 *   onSceneReady(scene) — fired once IslandScene is live, so the parent
 *                          can call scene.agentSpeak(), scene.focusCamera(), etc.
 */

'use client';

import { useEffect, useRef } from 'react';
import Phaser from 'phaser';
import { IslandScene } from './scenes/IslandScene';
import { PhaserErrorBoundary } from './PhaserErrorBoundary';

interface PhaserGameProps {
  onSceneReady?: (scene: IslandScene) => void;
}

function PhaserCanvas({ onSceneReady }: PhaserGameProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const gameRef      = useRef<Phaser.Game | null>(null);

  useEffect(() => {
    if (!containerRef.current || gameRef.current) return;

    const scene = new IslandScene();

    const config: Phaser.Types.Core.GameConfig = {
      type: Phaser.AUTO,
      width:  1280,
      height: 960,
      backgroundColor: '#1a3a5c',
      pixelArt: true,
      antialias: false,
      roundPixels: true,
      parent: containerRef.current,
      scene,
      scale: {
        mode: Phaser.Scale.FIT,
        autoCenter: Phaser.Scale.CENTER_BOTH,
      },
    };

    gameRef.current = new Phaser.Game(config);

    // Wait for scene to be fully created before exposing it
    gameRef.current.events.once('ready', () => {
      const islandScene = gameRef.current!.scene.getScene('IslandScene') as IslandScene;
      if (islandScene && onSceneReady) {
        // Scenes are created async — wait for the create() to finish
        if (islandScene.scene.isActive()) {
          onSceneReady(islandScene);
        } else {
          islandScene.events.once('create', () => onSceneReady(islandScene));
        }
      }
    });

    return () => {
      gameRef.current?.destroy(true);
      gameRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: '100%', imageRendering: 'pixelated' }}
    />
  );
}

export default function PhaserGame(props: PhaserGameProps) {
  return (
    <PhaserErrorBoundary>
      <PhaserCanvas {...props} />
    </PhaserErrorBoundary>
  );
}
