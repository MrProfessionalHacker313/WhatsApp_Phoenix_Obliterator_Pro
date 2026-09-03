class MultiDeviceManager {
  constructor() {
    this.sessions = new Map();
  }

  register(sessionId, metadata = {}) {
    this.sessions.set(sessionId, metadata);
    return { sessionId, ok: true };
  }

  list() {
    return Array.from(this.sessions.entries()).map(([sessionId, metadata]) => ({ sessionId, metadata }));
  }
}

module.exports = { MultiDeviceManager };
