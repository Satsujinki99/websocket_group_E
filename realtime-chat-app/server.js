// server.js
const express = require('express');
const http = require('http');
const WebSocket = require('ws');
const path = require('path');

// Setup server
const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

// Serve static files
app.use(express.static(path.join(__dirname, 'public')));

// Store connected clients
const clients = new Map();
let userCounter = 0;

// WebSocket connection handler
wss.on('connection', (ws) => {
    const userColor = getRandomColor();
    let userData = { id: null, color: userColor, username: null };
    
    // Store client information
    clients.set(ws, userData);
    
    // Request username from client
    ws.send(JSON.stringify({
        type: 'request_username'
    }));
    
    // Handle username submission before allowing chat
    const handleUsernameSubmission = (message) => {
        try {
            const parsedMessage = JSON.parse(message);
            
            if (parsedMessage.type === 'username_submission') {
                // Sanitize and validate username
                let username = parsedMessage.username.trim();
                if (!username) username = `Guest_${++userCounter}`;
                
                // Update user data
                userData.username = username;
                userData.id = `user_${++userCounter}`;
                
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
                
                // Remove this handler since we've processed the username
                ws.removeListener('message', handleUsernameSubmission);
                
                // Add the regular message handler
                ws.on('message', handleRegularMessage);
            }
        } catch (e) {
            console.error('Invalid username submission format:', e);
        }
    };
    
    // Add temporary message handler for username submission
    ws.on('message', handleUsernameSubmission);
    
    // Regular message handler function
    const handleRegularMessage = (message) => {
        try {
            const parsedMessage = JSON.parse(message);
            const userData = clients.get(ws);
            
            // Check if user has submitted a username
            if (!userData.username) return;
            
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
    };
    
    // Handle disconnection
    ws.on('close', () => {
        const userData = clients.get(ws);
        clients.delete(ws);
        
        // Only broadcast if the user had completed the login process
        if (userData.username) {
            // Broadcast user left message
            broadcastMessage({
                type: 'notification',
                data: { message: `${userData.username} telah keluar` }
            });
        }
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

// Generate random color for user
function getRandomColor() {
    const colors = [
        '#2196F3', '#32c787', '#00BCD4', '#ff5652',
        '#ffc107', '#ff85af', '#FF9800', '#39bbb0'
    ];
    return colors[Math.floor(Math.random() * colors.length)];
}

// Start server
const PORT = process.env.PORT || 3005;
server.listen(PORT, () => {
    console.log(`Server berjalan di http://localhost:${PORT}`);
});