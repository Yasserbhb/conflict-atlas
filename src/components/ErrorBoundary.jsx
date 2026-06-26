import { Component } from 'react';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          height: '100%', display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          background: '#070d1a', color: '#94a3b8', gap: 16, padding: 32
        }}>
          <div style={{ fontSize: 32 }}>⚠</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#e2e8f0' }}>Something crashed</div>
          <pre style={{
            fontSize: 11, color: '#475569', maxWidth: 600, whiteSpace: 'pre-wrap',
            background: '#0c1524', padding: '12px 16px', borderRadius: 8,
            border: '1px solid #1e3a5f', overflow: 'auto', maxHeight: 200
          }}>
            {this.state.error.message}
          </pre>
          <button
            onClick={() => this.setState({ error: null })}
            style={{
              background: '#1d4ed8', border: 'none', borderRadius: 6, color: 'white',
              padding: '8px 20px', fontSize: 13, fontWeight: 600, cursor: 'pointer'
            }}
          >
            Try to recover
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
