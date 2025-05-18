import React, { useState, useEffect } from 'react';
import { Box, LinearProgress, Typography, Alert } from '@mui/material';

// Add API_URL from environment variables
const API_URL = process.env.REACT_APP_API_URL || '';

const generateRequestId = () => {
  return Date.now().toString() + '-' + Math.random().toString(36).substr(2, 9);
};

const ChannelProgress = ({ requestId }) => {
  const [progress, setProgress] = useState({
    processedChannels: 0,
    totalChannels: 0,
    currentChannel: 'Starting analysis...'
  });
  const [error, setError] = useState(null);
  const [complete, setComplete] = useState(false);
  const [connected, setConnected] = useState(false);
  const [statusHistory, setStatusHistory] = useState([]);
  const [phase, setPhase] = useState('initializing'); // initializing, fetching, clustering, finalizing, complete
  const [lastEventTime, setLastEventTime] = useState(Date.now());
  const [messageCount, setMessageCount] = useState(0); // Add a counter for received messages

  // Add debugging log for requestId changes
  console.log(`[DEBUG-ChannelProgress] Component rendered with requestId: ${requestId}`);

  useEffect(() => {
    console.log(`[DEBUG-ChannelProgress] useEffect triggered with requestId: ${requestId}`);
    
    if (!requestId) {
      console.error('[DEBUG-ChannelProgress] No requestId provided to ChannelProgress component');
      return;
    }

    console.log(`[DEBUG-ChannelProgress] Tracking progress for requestId: ${requestId}, creating EventSource...`);
    let eventSource = null;
    let checkConnectionInterval = null;
    
    try {
      console.log(`[DEBUG-ChannelProgress] Connecting to SSE for requestId: ${requestId}`);
      const url = `${API_URL}/channel-progress?requestId=${encodeURIComponent(requestId)}`;
      console.log(`[DEBUG-ChannelProgress] SSE URL: ${url}`);
      
      // Create the EventSource
      eventSource = new EventSource(url);
      console.log(`[DEBUG-ChannelProgress] EventSource created:`, eventSource);
      
      // Set up connection health check
      checkConnectionInterval = setInterval(() => {
        const now = Date.now();
        const timeSinceLastEvent = now - lastEventTime;
        console.log(`[DEBUG-ChannelProgress] Time since last event: ${timeSinceLastEvent}ms, messageCount: ${messageCount}`);
        
        // If no events for 10 seconds, consider connection stale
        if (connected && timeSinceLastEvent > 10000 && !complete) {
          console.warn('[DEBUG-ChannelProgress] Connection appears stale, attempting to reconnect...');
          if (eventSource) {
            console.log(`[DEBUG-ChannelProgress] Closing stale connection...`);
            eventSource.close();
            console.log(`[DEBUG-ChannelProgress] Creating new connection...`);
            eventSource = new EventSource(url);
            setLastEventTime(Date.now());
            
            // Add a status message about reconnecting
            setStatusHistory(prev => {
              const newHistory = [...prev, "Reconnecting to server..."];
              return newHistory.slice(-5);
            });
          }
        }
      }, 5000);
      
      eventSource.onopen = () => {
        console.log('[DEBUG-ChannelProgress] SSE connection opened');
        setConnected(true);
        setLastEventTime(Date.now());
      };
      
      eventSource.onmessage = (event) => {
        try {
          setLastEventTime(Date.now());
          setMessageCount(prev => prev + 1);
          
          console.log(`[DEBUG-ChannelProgress] Message received (#${messageCount + 1}):`, event.data);
          
          const data = JSON.parse(event.data);
          console.log('[DEBUG-ChannelProgress] Parsed message data:', data);
          
          // Determine the current phase based on message content
          if (data.currentChannel) {
            console.log(`[DEBUG-ChannelProgress] Current channel status: ${data.currentChannel}`);
            const currentStatus = data.currentChannel.toLowerCase();
            
            if (currentStatus.includes('finalizing')) {
              setPhase('finalizing');
              console.log('[DEBUG-ChannelProgress] Set phase to: finalizing');
            } else if (currentStatus.includes('processing ai') || 
                      currentStatus.includes('clustering') || 
                      currentStatus.includes('analyzing')) {
              setPhase('clustering');
              console.log('[DEBUG-ChannelProgress] Set phase to: clustering');
            } else if (currentStatus.includes('fetching') || 
                      currentStatus.includes('processing message') ||
                      currentStatus.includes('processing link')) {
              setPhase('fetching');
              console.log('[DEBUG-ChannelProgress] Set phase to: fetching');
            } else if (currentStatus.includes('complete')) {
              setPhase('complete');
              console.log('[DEBUG-ChannelProgress] Set phase to: complete');
            } else if (currentStatus.includes('initializing')) {
              setPhase('initializing');
              console.log('[DEBUG-ChannelProgress] Set phase to: initializing');
            }
            
            // Add to status history (avoid duplicates)
            if (data.currentChannel && 
               (!statusHistory.length || 
                statusHistory[statusHistory.length-1] !== data.currentChannel)) {
              console.log(`[DEBUG-ChannelProgress] Adding to status history: ${data.currentChannel}`);
              setStatusHistory(prev => {
                // Only keep the latest 5 statuses for cleaner display
                const newHistory = [...prev, data.currentChannel];
                return newHistory.slice(-5);
              });
            }
          }
          
          setProgress(data);
          console.log('[DEBUG-ChannelProgress] Updated progress state:', data);
          
          // Mark as complete when all channels are processed and seeing complete message
          if (data.processedChannels >= data.totalChannels && 
              data.totalChannels > 0 && 
              data.currentChannel && 
              (data.currentChannel.toLowerCase().includes('complete') || 
               data.currentChannel.toLowerCase().includes('finalizing'))) {
            console.log('[DEBUG-ChannelProgress] Marking as complete');
            setComplete(true);
          }
          
          // Check for error
          if (data.error) {
            console.error(`[DEBUG-ChannelProgress] Error from server: ${data.error}`);
            setError(data.error);
            if (eventSource) eventSource.close();
          }
        } catch (e) {
          console.error('[DEBUG-ChannelProgress] Error parsing SSE data:', e);
        }
      };
      
      // Handle specific event types
      eventSource.addEventListener('connected', (event) => {
        console.log('[DEBUG-ChannelProgress] Connected event received:', event.data);
      });
      
      eventSource.addEventListener('error', (event) => {
        try {
          console.error('[DEBUG-ChannelProgress] SSE error event:', event);
          setLastEventTime(Date.now());
          if (event.data) {
            const data = JSON.parse(event.data);
            console.error('[DEBUG-ChannelProgress] Error data:', data);
            setError(data.error || 'Connection error');
          } else {
            console.error('[DEBUG-ChannelProgress] No error data available');
            setError('Connection error occurred');
          }
          setConnected(false);
          if (eventSource) eventSource.close();
        } catch (e) {
          console.error('[DEBUG-ChannelProgress] Error parsing SSE error event:', e);
          setError('Connection error');
        }
      });
      
      eventSource.addEventListener('complete', (event) => {
        try {
          console.log('[DEBUG-ChannelProgress] SSE complete event received:', event.data);
          setLastEventTime(Date.now());
          setComplete(true);
          setPhase('complete');
          if (eventSource) eventSource.close();
        } catch (e) {
          console.error('[DEBUG-ChannelProgress] Error handling complete event:', e);
        }
      });
      
      eventSource.onerror = (e) => {
        console.error('[DEBUG-ChannelProgress] SSE connection error:', e);
        setConnected(false);
        setLastEventTime(Date.now());
        
        // Try to reconnect after a brief delay
        setTimeout(() => {
          if (eventSource) {
            if (eventSource.readyState === EventSource.CLOSED) {
              console.log('[DEBUG-ChannelProgress] Attempting to reconnect...');
              eventSource = new EventSource(url);
            }
          }
        }, 3000);
      };
    } catch (e) {
      console.error('[DEBUG-ChannelProgress] Error setting up SSE connection:', e);
      setError(`Connection error: ${e.message}`);
    }
    
    return () => {
      console.log('[DEBUG-ChannelProgress] Cleanup function running, closing connections');
      if (eventSource) {
        console.log('[DEBUG-ChannelProgress] Closing SSE connection');
        eventSource.close();
      }
      if (checkConnectionInterval) {
        console.log('[DEBUG-ChannelProgress] Clearing check interval');
        clearInterval(checkConnectionInterval);
      }
    };
  }, [requestId, lastEventTime, connected, complete, statusHistory.length, messageCount]);

  // Display error if present
  if (error) {
    return (
      <Alert severity="error" sx={{ mt: 2, mb: 2 }}>
        Error: {error}
      </Alert>
    );
  }

  // Calculate percentage
  const percentage = progress.totalChannels > 0 
    ? Math.round((progress.processedChannels / progress.totalChannels) * 100) 
    : 0;
  
  // Get phase-specific color
  const getPhaseColor = () => {
    switch(phase) {
      case 'clustering': return '#e3f2fd'; // light blue
      case 'fetching': return '#e8f5e9';   // light green
      case 'finalizing': return '#fff8e1'; // light amber
      case 'complete': return '#e8f5e9';   // light green
      default: return '#f5f5f5';           // light grey
    }
  };
  
  // Get connection status message
  const getConnectionStatus = () => {
    if (!connected && !complete && !error) {
      return "Connecting to server...";
    }
    if (connected && Date.now() - lastEventTime > 5000 && !complete) {
      return "Connection may be slow...";
    }
    return null;
  };
    
  return (
    <Box sx={{ width: '100%', mb: 2 }}>
      {/* Debug info section */}
      <Box sx={{ mb: 2, p: 1, bgcolor: '#f0f0f0', fontSize: '0.8rem', borderRadius: 1 }}>
        <Typography variant="caption" sx={{ fontFamily: 'monospace', display: 'block' }}>
          Debug Info:
        </Typography>
        <Typography variant="caption" sx={{ fontFamily: 'monospace', display: 'block' }}>
          Request ID: {requestId || 'none'}
        </Typography>
        <Typography variant="caption" sx={{ fontFamily: 'monospace', display: 'block' }}>
          Connection: {connected ? 'ACTIVE' : 'INACTIVE'}
        </Typography>
        <Typography variant="caption" sx={{ fontFamily: 'monospace', display: 'block' }}>
          Events Received: {messageCount}
        </Typography>
        <Typography variant="caption" sx={{ fontFamily: 'monospace', display: 'block' }}>
          Last Event: {new Date(lastEventTime).toLocaleTimeString()}
        </Typography>
        <Typography variant="caption" sx={{ fontFamily: 'monospace', display: 'block' }}>
          Phase: {phase}
        </Typography>
      </Box>
      
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
        <Box sx={{ flexGrow: 1 }}>
          <LinearProgress 
            variant={connected ? "determinate" : "indeterminate"}
            value={percentage} 
            sx={{ 
              height: 10, 
              borderRadius: 5,
              '& .MuiLinearProgress-bar': {
                backgroundColor: phase === 'fetching' ? '#4caf50' : 
                                 phase === 'clustering' ? '#2196f3' : 
                                 phase === 'finalizing' ? '#ff9800' : 
                                 phase === 'complete' ? '#4caf50' : '#9e9e9e'
              }
            }}
          />
        </Box>
        <Box sx={{ ml: 2 }}>
          <Typography variant="body2" color="text.secondary">
            {percentage}%
          </Typography>
        </Box>
      </Box>
      
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 'bold' }}>
          {progress.processedChannels} of {progress.totalChannels} channels processed
        </Typography>
        {getConnectionStatus() && (
          <Typography variant="body2" color="warning.main">
            {getConnectionStatus()}
          </Typography>
        )}
      </Box>
      
      <Box sx={{ 
        p: 2, 
        border: '1px solid #eee', 
        borderRadius: 2, 
        bgcolor: getPhaseColor(),
        transition: 'background-color 0.5s ease'
      }}>
        <Typography variant="body1" color="text.primary" sx={{ fontWeight: 'bold', mb: 1 }}>
          Current Status: {progress.currentChannel || 'Waiting...'}
        </Typography>
        
        {statusHistory.length > 1 && (
          <>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1, fontWeight: 'bold' }}>
              Recent Progress:
            </Typography>
            <Box component="ul" sx={{ mt: 0.5, pl: 2 }}>
              {statusHistory.slice(0, -1).map((status, i) => (
                <Typography component="li" variant="body2" color="text.secondary" key={i}>
                  {status}
                </Typography>
              ))}
            </Box>
          </>
        )}
      </Box>
      
      {complete && (
        <Alert severity="success" sx={{ mt: 2 }}>
          Processing complete! {progress.totalChannels} channels processed successfully.
        </Alert>
      )}
    </Box>
  );
};

export { ChannelProgress, generateRequestId }; 