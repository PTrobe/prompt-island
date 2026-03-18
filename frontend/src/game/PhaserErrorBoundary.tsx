/**
 * PhaserErrorBoundary.tsx — Catches Phaser crashes so the stream never shows
 * a white screen. Renders a dark fallback with an error message instead.
 */

'use client';

import React from 'react';

interface Props {
  children: React.ReactNode;
}

interface State {
  error: Error | null;
}

export class PhaserErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    console.error('[PhaserErrorBoundary] Phaser crash:', error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            width: '100%',
            height: '100%',
            background: '#0a0a0a',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#888',
            fontFamily: 'monospace',
            fontSize: '12px',
            gap: '8px',
          }}
        >
          <div style={{ color: '#cc4444', fontSize: '14px' }}>⚠ Game engine error</div>
          <div>{this.state.error.message}</div>
          <button
            onClick={() => this.setState({ error: null })}
            style={{
              marginTop: '12px',
              padding: '6px 16px',
              background: '#222',
              border: '1px solid #555',
              color: '#ccc',
              cursor: 'pointer',
              fontFamily: 'monospace',
            }}
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
