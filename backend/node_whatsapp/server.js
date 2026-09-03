const express = require('express');
const app = express();
const port = process.env.PORT || 3000;

app.use(express.json());

app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'phoenix-whatsapp-bridge' });
});

app.post('/api/messages/ingest', (req, res) => {
  const payload = req.body || {};
  res.json({
    status: 'accepted',
    message: 'Message ingested into internal evidence workflow.',
    data: {
      source: payload.source || 'unknown',
      case_id: payload.case_id || 'N/A'
    }
  });
});

app.listen(port, () => {
  console.log(`WhatsApp bridge running on port ${port}`);
});
