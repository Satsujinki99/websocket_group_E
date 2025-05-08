// server.js
const express = require('express');
const https = require('https');
const http = require('http');
const WebSocket = require('ws');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const cookieParser = require('cookie-parser');
const session = require('express-session');

// Setup server
const app = express();
const PORT = process.env.PORT || 3005;
const SESSION_SECRET = process.env.SESSION_SECRET || 'chat-app-secure-secret-key';

// SSL/TLS configuration for HTTPS and WSS
const sslOptions = {
  key: fs.readFileSync(path.join(__dirname, 'ssl/private-key.pem')),
  cert: fs.readFileSync(path.join(__dirname, 'ssl/certificate.pem'))
};

// Create HTTPS server
const server = https.createServer(sslOptions, app);

// Session middleware
const sessionParser = session({
  secret: SESSION_SECRET,
  resave: false,
  saveUninitialized: false,
  cookie: { 
    secure: true, // for HTTPS
    httpOnly: true,
    maxAge: 24 * 60 * 60 * 1000 // 24 hours
  }
});

// Use middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());
app.use(sessionParser);
app.use(express.static(path.join(__dirname, 'public')));

// Authentication middleware
const users = new Map(); // In-memory user database (replace with actual DB in production)

// WebSocket Server with authentication
const wss = new WebSocket.Server({ 
  server,
  verifyClient: (info, callback) => {
    // Parse the cookies from the upgrade request
    const cookies = {};
    if (info.req.headers.cookie) {
      info.req.headers.cookie.split(';').forEach(cookie => {
        const parts = cookie.trim().split('=');
        cookies[parts[0]] = parts[1];
      });
    }

    // Verify session
    sessionParser(info.req, {}, () => {
      const session = info.req.session;
      const isAuthenticated = session && session.userId;
      
      if (!isAuthenticated) {
        callback(false, 401, 'Unauthorized');
        return;
      }
      
      // Limit connections to 3 per user
      const userId = session.userId;
      const connections = [...wss.clients].filter(client => {
        return client.userId === userId;
      }).length;
      
      if (connections >= 3) {
        callback(false, 429, 'Too many connections. Maximum 3 allowed per user.');
        return;
      }
      
      // Pass user data to WebSocket object for future use
      info.req.userId = userId;
      info.req.username = session.username;
      
      callback(true);
    });
  }
});

  // Store connected clients and track connections per user
const clients = new Map();
const userConnections = new Map(); // Track number of connections per user
let userCounter = 0;

// Routes for authentication
app.get('/login', (req, res) => {
  res.sendFile(path.join(__dirname, 'public/login.html'));
});

app.post('/api/register', (req, res) => {
  const { username, password } = req.body;
  
  if (!username || !password) {
    return res.status(400).json({ success: false, message: 'Username and password are required' });
  }
  
  // Check if user already exists
  if (Array.from(users.values()).some(user => user.username === username)) {
    return res.status(409).json({ success: false, message: 'Username already exists' });
  }
  
  // Generate userId and salt
  const userId = `user_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  const salt = crypto.randomBytes(16).toString('hex');
  
  // Hash the password
  const hash = crypto.pbkdf2Sync(password, salt, 1000, 64, 'sha512').toString('hex');
  
  // Store user data
  users.set(userId, {
    userId,
    username,
    salt,
    hash,
    color: getRandomColor()
  });
  
  // Create session
  req.session.userId = userId;
  req.session.username = username;
  
  res.json({ success: true, message: 'Registration successful' });
});

app.post('/api/login', (req, res) => {
  const { username, password } = req.body;
  
  if (!username || !password) {
    return res.status(400).json({ success: false, message: 'Username and password are required' });
  }
  
  // Find user
  const user = Array.from(users.entries()).find(([_, u]) => u.username === username);
  
  if (!user) {
    return res.status(401).json({ success: false, message: 'Invalid username or password' });
  }
  
  const [userId, userData] = user;
  
  // Verify password
  const hash = crypto.pbkdf2Sync(password, userData.salt, 1000, 64, 'sha512').toString('hex');
  
  if (hash !== userData.hash) {
    return res.status(401).json({ success: false, message: 'Invalid username or password' });
  }
  
  // Create session
  req.session.userId = userId;
  req.session.username = username;
  
  res.json({ success: true, message: 'Login successful' });
});

app.get('/api/logout', (req, res) => {
  // Destroy session
  if (req.session) {
    req.session.destroy(err => {
      if (err) {
        return res.status(500).json({ success: false, message: 'Failed to logout' });
      }
      res.clearCookie('connect.sid');
      res.json({ success: true, message: 'Logout successful' });
    });
  } else {
    res.json({ success: true, message: 'Already logged out' });
  }
});

app.get('/api/session', (req, res) => {
  // Check if user is authenticated
  if (req.session && req.session.userId) {
    const user = users.get(req.session.userId);
    if (user) {
      return res.json({
        authenticated: true,
        username: user.username
      });
    }
  }
  
  res.json({ authenticated: false });
});

// WebSocket connection handler
wss.on('connection', (ws, req) => {
  const userId = req.userId;
  const username = req.username;
  const user = users.get(userId);
  
  if (!user) {
    ws.close(1008, 'User not found');
    return;
  }
  
  // Attach user info to websocket connection
  ws.userId = userId;
  ws.username = username;
  
  // Store client information
  const userData = {
    id: userId,
    username: username,
    color: user.color
  };
  
  clients.set(ws, userData);
  
  // Track user connections
  if (!userConnections.has(userId)) {
    userConnections.set(userId, 0);
  }
  userConnections.set(userId, userConnections.get(userId) + 1);
  
  // Send updated connection count to this user's connections
  const connectionCount = userConnections.get(userId);
  sendConnectionCountToUser(userId, connectionCount);
  
  // Send confirmation to the user
  ws.send(JSON.stringify({
    type: 'connect',
    data: { 
      id: userData.id, 
      color: userData.color, 
      username: userData.username,
      message: 'Selamat datang di chat!' 
    }
  }));
  
  // Broadcast user joined message
  broadcastMessage({
    type: 'notification',
    data: { message: `${userData.username} telah bergabung` }
  }, ws);
  
  // Message handler
  ws.on('message', (message) => {
    try {
      const parsedMessage = JSON.parse(message);
      
      // Broadcast the message to all clients
      broadcastMessage({
        type: 'message',
        data: {
          id: userData.id,
          username: userData.username,
          color: userData.color,
          text: parsedMessage.text,
          timestamp: new Date().toLocaleTimeString()
        }
      });
    } catch (e) {
      console.error('Invalid message format:', e);
    }
  });
  
  // Handle disconnection
  ws.on('close', () => {
    const userData = clients.get(ws);
    if (!userData) return;
    
    const userId = userData.id;
    clients.delete(ws);
    
    // Update user connection count
    if (userConnections.has(userId)) {
      const newCount = Math.max(0, userConnections.get(userId) - 1);
      if (newCount === 0) {
        userConnections.delete(userId);
      } else {
        userConnections.set(userId, newCount);
        // Send updated connection count
        sendConnectionCountToUser(userId, newCount);
      }
    }
    
    // Broadcast user left message
    broadcastMessage({
      type: 'notification',
      data: { message: `${userData.username} telah keluar` }
    });
  });
});

// Broadcast message to all clients
function broadcastMessage(message, sender = null) {
  const messageStr = JSON.stringify(message);
  wss.clients.forEach((client) => {
    // Don't send message back to sender if specified
    if (sender && client === sender) return;
    
    // Send only to connected clients
    if (client.readyState === WebSocket.OPEN) {
      client.send(messageStr);
    }
  });
}

// Send connection count to a specific user's connections
function sendConnectionCountToUser(userId, count) {
  const message = JSON.stringify({
    type: 'connection_count',
    data: { count }
  });
  
  wss.clients.forEach((client) => {
    if (client.readyState === WebSocket.OPEN && client.userId === userId) {
      client.send(message);
    }
  });
}

// Generate random color for user
function getRandomColor() {
  const colors = [
    '#2196F3', '#32c787', '#00BCD4', '#ff5652',
    '#ffc107', '#ff85af', '#FF9800', '#39bbb0'
  ];
  return colors[Math.floor(Math.random() * colors.length)];
}

// For development: HTTP redirect to HTTPS
const httpServer = http.createServer((req, res) => {
  res.writeHead(301, { Location: `https://${req.headers.host}${req.url}` });
  res.end();
});

// Start server
httpServer.listen(80, () => {
  console.log('HTTP server redirecting to HTTPS');
});

server.listen(PORT, () => {
  console.log(`Server berjalan di https://localhost:${PORT}`);
});