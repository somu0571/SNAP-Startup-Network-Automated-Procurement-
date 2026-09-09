require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const session = require('express-session');
const { MongoStore } = require('connect-mongo');
const path = require('path');
const { spawn } = require('child_process');

const app = express();
const PORT = process.env.PORT || 5000;

const mongoUri = process.env.MONGODB_URI || process.env.MONGO_URI || 'mongodb://localhost:27017/snap_prototype';

// Pre-register all Mongoose models so populate() works everywhere
require('./models/User');
require('./models/Department');
require('./models/Startup');
require('./models/Challenge');
require('./models/Application');
require('./models/Evaluation');
require('./models/Pilot');
require('./models/KPI');
require('./models/Validation');
require('./models/Recommendation');

// Connect to MongoDB
mongoose.connect(mongoUri)
  .then(() => console.log('✅ MongoDB Connected'))
  .catch(err => console.error('MongoDB Connection Error:', err));

// Middleware
app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// EJS Setup
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Session setup
app.use(session({
  secret: process.env.SESSION_SECRET || 'secret',
  resave: false,
  saveUninitialized: false,
  store: MongoStore.create({ mongoUrl: mongoUri }),
  cookie: { maxAge: 1000 * 60 * 60 * 24 } // 1 day
}));

// Global variables for views
app.use((req, res, next) => {
  res.locals.user = req.session.user || null;
  res.locals.error = req.session.error || null;
  res.locals.success = req.session.success || null;
  delete req.session.error;
  delete req.session.success;
  next();
});

// Routes
const authRoutes = require('./routes/authRoutes');
const challengeRoutes = require('./routes/challengeRoutes');
const marketplaceRoutes = require('./routes/marketplaceRoutes');
const startupRoutes = require('./routes/startupRoutes');
const applicationRoutes = require('./routes/applicationRoutes');
const evaluationRoutes = require('./routes/evaluationRoutes');
const pilotRoutes = require('./routes/pilotRoutes');
const dashboardRoutes = require('./routes/dashboardRoutes');

app.use('/auth', authRoutes);
app.use('/', challengeRoutes);
app.use('/', marketplaceRoutes);
app.use('/', startupRoutes);
app.use('/', applicationRoutes);
app.use('/', evaluationRoutes);
app.use('/', pilotRoutes);
app.use('/', dashboardRoutes);

app.get('/', (req, res) => {
  res.render('layouts/main', { body: 'partials/home' });
});

// ── Health Check ─────────────────────────────────────────
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'SNAP GovTech Platform', version: '1.0.0' });
});

// ── RAG Engine Integration ───────────────────────────────
// Serve standalone RAG Engine frontend
app.get('/rag', (req, res) => {
  const ragFrontend = path.join(__dirname, 'rag-engine', 'frontend', 'index.html');
  const fs = require('fs');
  if (fs.existsSync(ragFrontend)) {
    res.sendFile(ragFrontend);
  } else {
    res.json({ message: 'RAG Engine frontend not found. API available at /rag/health' });
  }
});

// Proxy RAG API requests to internal FastAPI microservice (port 8000)
const ragBaseUrl = process.env.RAG_ENGINE_URL || 'http://127.0.0.1:8000';

app.all(/^\/(problem|startup\/upload|shortlist|search|problems)/, async (req, res) => {
  try {
    const targetUrl = `${ragBaseUrl}${req.originalUrl}`;
    const headers = { ...req.headers };
    delete headers.host;

    const fetchOptions = {
      method: req.method,
      headers: headers,
      signal: AbortSignal.timeout(180000) // 3 min timeout for scoring
    };

    if (req.method !== 'GET' && req.method !== 'HEAD') {
      fetchOptions.body = req;
      fetchOptions.duplex = 'half';
    }

    const response = await fetch(targetUrl, fetchOptions);
    res.status(response.status);
    response.headers.forEach((v, k) => {
      if (k.toLowerCase() !== 'transfer-encoding') {
        res.setHeader(k, v);
      }
    });
    const data = await response.arrayBuffer();
    res.send(Buffer.from(data));
  } catch (err) {
    console.error('[RAG Proxy] Error:', err.message);
    res.status(502).json({
      error: 'RAG Engine unavailable',
      detail: err.message,
      hint: 'Ensure the RAG Engine is running: cd rag-engine && python -m uvicorn main:app --port 8000'
    });
  }
});

// ── Auto-start RAG Engine ────────────────────────────────
const ragService = require('./services/ragService');

function ensureRagEngine() {
  ragService.isAvailable().then(isOnline => {
    if (isOnline) {
      console.log('⚡ RAG Engine is active on', ragBaseUrl);
    } else {
      console.log('🚀 Auto-starting RAG Engine (port 8000)...');
      const ragDir = path.join(__dirname, 'rag-engine');

      // Try python executable from env, then common paths
      const pythonExe = process.env.PYTHON_PATH || 'python';

      const pyProc = spawn(pythonExe, ['-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000'], {
        cwd: ragDir,
        stdio: 'inherit',
        shell: false
      });

      pyProc.on('error', (err) => {
        console.warn('⚠️  RAG Engine auto-start failed:', err.message);
        console.warn('   To start manually: cd rag-engine && pip install -r requirements.txt && python -m uvicorn main:app --port 8000');
      });

      process.on('exit', () => { try { pyProc.kill(); } catch (_) {} });
    }
  }).catch(() => {
    console.warn('⚠️  Could not check RAG Engine status. Start it manually if needed.');
  });
}

// ── Start Server ─────────────────────────────────────────
app.listen(PORT, () => {
  console.log('====================================================');
  console.log(` SNAP GovTech Platform running on http://localhost:${PORT}`);
  console.log(` AI RAG Engine expected on ${ragBaseUrl}`);
  console.log('====================================================');
  ensureRagEngine();
});
