class WhatsAppClient {
  constructor() {
    this.connected = false;
  }

  connect() {
    this.connected = true;
    return { status: 'connected', service: 'whatsapp-client' };
  }

  disconnect() {
    this.connected = false;
    return { status: 'disconnected', service: 'whatsapp-client' };
  }
}

module.exports = { WhatsAppClient };
