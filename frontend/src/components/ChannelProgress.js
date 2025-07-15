import React, { useState, useEffect, useRef } from 'react';
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
  const [phase, setPhase] = useState('initializing');
  const [lastEventTime, setLastEventTime] = useState(Date.now());
  const [messageCount, setMessageCount] = useState(0);
  const [prevChannelName, setPrevChannelName] = useState('');
  
  // Use a ref to track connection state and prevent multiple connections
  const eventSourceRef = useRef(null);
  const activeRequestIdRef = useRef(null);

  useEffect(() => {
    if (!requestId) {
      console.error('[ChannelProgress] No requestId provided to ChannelProgress component');
      return;
    }

    // If we already have an active connection for this requestId, don't create another one
    if (eventSourceRef.current && activeRequestIdRef.current === requestId) {
      console.log(`[ChannelProgress] Already connected to requestId: ${requestId}, skipping duplicate connection`);
      return;
    }

    // Close any existing connection before creating a new one
    if (eventSourceRef.current) {
      console.log(`[ChannelProgress] Closing previous connection before creating new one`);
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    let checkConnectionInterval = null;
    
    try {
      const url = `${API_URL}/channel-progress?requestId=${encodeURIComponent(requestId)}`;
      console.log(`[ChannelProgress] SSE URL: ${url}`);
      
      // Create the EventSource
      const eventSource = new EventSource(url);
      eventSourceRef.current = eventSource;
      activeRequestIdRef.current = requestId;
      
      // Set up connection health check
      checkConnectionInterval = setInterval(() => {
        const now = Date.now();
        const timeSinceLastEvent = now - lastEventTime;
        
        // If no events for 10 seconds, consider connection stale
        if (connected && timeSinceLastEvent > 10000 && !complete) {
          console.warn('[ChannelProgress] Connection appears stale, attempting to reconnect...');
          if (eventSourceRef.current) {
            eventSourceRef.current.close();
            eventSourceRef.current = new EventSource(url);
            setLastEventTime(Date.now());
          }
        }
      }, 5000);
      
      eventSource.onopen = () => {
        console.log('[ChannelProgress] SSE connection opened');
        setConnected(true);
        setLastEventTime(Date.now());
      };
      
      eventSource.onmessage = (event) => {
        try {
          setLastEventTime(Date.now());
          
          const data = JSON.parse(event.data);
          
          // Only update the message count if we have a meaningful change
          // Check if channel has changed or progress count has changed
          const channelName = getChannelNameFromStatus(data.currentChannel || '');
          const hasNewChannel = channelName && channelName !== prevChannelName && channelName !== '';
          const hasProgressChange = data.processedChannels !== progress.processedChannels;
          
          if (hasNewChannel || hasProgressChange) {
            setMessageCount(prev => prev + 1);
            setPrevChannelName(channelName);
          }
          
          // Determine the current phase based on message content
          if (data.currentChannel) {
            const currentStatus = data.currentChannel.toLowerCase();
            
            if (currentStatus.includes('finalizing')) {
              setPhase('finalizing');
            } else if (currentStatus.includes('processing ai') || 
                      currentStatus.includes('clustering') || 
                      currentStatus.includes('analyzing')) {
              setPhase('clustering');
            } else if (currentStatus.includes('fetching') || 
                      currentStatus.includes('processing message') ||
                      currentStatus.includes('processing link')) {
              setPhase('fetching');
            } else if (currentStatus.includes('complete')) {
              setPhase('complete');
            } else if (currentStatus.includes('initializing')) {
              setPhase('initializing');
            }
          }
          
          setProgress(data);
          
          // Mark as complete when all channels are processed and seeing complete message
          if (data.processedChannels >= data.totalChannels && 
              data.totalChannels > 0 && 
              data.currentChannel && 
              (data.currentChannel.toLowerCase().includes('complete') || 
               data.currentChannel.toLowerCase().includes('finalizing'))) {
            setComplete(true);
          }
          
          // Check for error
          if (data.error) {
            console.error(`[ChannelProgress] Error from server: ${data.error}`);
            setError(data.error);
            if (eventSourceRef.current) eventSourceRef.current.close();
          }
        } catch (e) {
          console.error('[ChannelProgress] Error parsing SSE data:', e);
        }
      };
      
      // Handle specific event types
      eventSource.addEventListener('connected', (event) => {
        console.log('[ChannelProgress] Connected event received:', event.data);
      });
      
      eventSource.addEventListener('error', (event) => {
        try {
          console.error('[ChannelProgress] SSE error event:', event);
          setLastEventTime(Date.now());
          if (event.data) {
            const data = JSON.parse(event.data);
            setError(data.error || 'Connection error');
          } else {
            setError('Connection error occurred');
          }
          setConnected(false);
          if (eventSourceRef.current) eventSourceRef.current.close();
        } catch (e) {
          console.error('[ChannelProgress] Error parsing SSE error event:', e);
          setError('Connection error');
        }
      });
      
      eventSource.addEventListener('complete', (event) => {
        try {
          console.log('[ChannelProgress] SSE complete event received:', event.data);
          setLastEventTime(Date.now());
          setComplete(true);
          setPhase('complete');
          if (eventSourceRef.current) eventSourceRef.current.close();
        } catch (e) {
          console.error('[ChannelProgress] Error handling complete event:', e);
        }
      });
      
      eventSource.onerror = (e) => {
        console.error('[ChannelProgress] SSE connection error:', e);
        setConnected(false);
        setLastEventTime(Date.now());
        
        // Try to reconnect after a brief delay
        setTimeout(() => {
          if (eventSourceRef.current && eventSourceRef.current.readyState === EventSource.CLOSED) {
            console.log('[ChannelProgress] Attempting to reconnect...');
            eventSourceRef.current = new EventSource(url);
          }
        }, 3000);
      };
    } catch (e) {
      console.error('[ChannelProgress] Error setting up SSE connection:', e);
      setError(`Connection error: ${e.message}`);
    }
    
    return () => {
      if (eventSourceRef.current) {
        console.log(`[ChannelProgress] Cleanup: closing connection for requestId: ${requestId}`);
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (checkConnectionInterval) {
        clearInterval(checkConnectionInterval);
      }
    };
  }, [requestId]);

  // Extract just the channel name from status message
  const getChannelNameFromStatus = (statusText) => {
    if (!statusText) return '';
    
    // Extract channel name from patterns like "Processing 1/10: Channel Name" or "Fetching messages from: Channel Name"
    let match = statusText.match(/Processing \d+\/\d+: (.+)/) || 
                statusText.match(/Fetching messages from: (.+)/);
    
    if (match && match[1]) {
      return match[1].trim();
    }
    return '';
  };

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
      case 'clustering': return '#2196f3'; // blue
      case 'fetching': return '#4caf50';   // green
      case 'finalizing': return '#ff9800'; // amber
      case 'complete': return '#4caf50';   // green
      default: return '#9e9e9e';           // grey
    }
  };
  
  // Get phase-specific gradient for a more visually interesting look
  const getPhaseGradient = () => {
    switch(phase) {
      case 'clustering': 
        return 'linear-gradient(90deg, rgba(33,150,243,1) 0%, rgba(33,150,243,0.7) 100%)';
      case 'fetching': 
        return 'linear-gradient(90deg, rgba(76,175,80,1) 0%, rgba(76,175,80,0.7) 100%)';
      case 'finalizing': 
        return 'linear-gradient(90deg, rgba(255,152,0,1) 0%, rgba(255,152,0,0.7) 100%)';
      case 'complete': 
        return 'linear-gradient(90deg, rgba(76,175,80,1) 0%, rgba(76,175,80,0.7) 100%)';
      default: 
        return 'linear-gradient(90deg, rgba(158,158,158,1) 0%, rgba(158,158,158,0.7) 100%)';
    }
  };
  
  // Format channel name
  const getFormattedChannelName = () => {
    // If channel name includes "analyzing" or generic text, simplify
    const channel = progress.currentChannel || '';
    
    // Skip uninformative text like "Analyzing channels" or "Starting analysis"
    if (channel.includes('Analyzing channels') || 
        channel.includes('Starting analysis') ||
        channel.includes('Initializing') ||
        channel.includes('Clustering channels')) {
      return '';
    }
    
    // Extract just channel name if present
    if (channel.includes('Processing')) {
      const parts = channel.split(':');
      if (parts.length > 1) {
        return parts[1].trim();
      }
    }
    
    // Extract channel name if fetching messages
    if (channel.includes('Fetching messages from:')) {
      const parts = channel.split('Fetching messages from:');
      if (parts.length > 1) {
        return parts[1].trim();
      }
    }
    
    // Return original if no simplification needed
    return channel;
  };
  
  const channelName = getFormattedChannelName();
  
  return (
    <Box sx={{ width: '100%', mb: 2 }}>
      <Box sx={{ 
        p: 2, 
        borderRadius: 3, 
        bgcolor: '#f8f9fa',
        boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        transition: 'all 0.3s ease'
      }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1, alignItems: 'center' }}>
          <Typography variant="body2" sx={{ 
            fontWeight: 'bold', 
            color: '#333',
            fontSize: '0.9rem'
          }}>
            {progress.processedChannels} / {progress.totalChannels}
          </Typography>
          <Typography variant="body2" sx={{ 
            color: '#555',
            fontWeight: 'bold',
            fontSize: '0.9rem',
            bgcolor: 'rgba(0,0,0,0.04)',
            px: 1.5,
            py: 0.3,
            borderRadius: 10
          }}>
            {percentage}%
          </Typography>
        </Box>
        
        <Box sx={{ position: 'relative', mb: 2 }}>
          {/* Background track */}
          <Box sx={{ 
            height: 10, 
            borderRadius: 5,
            bgcolor: 'rgba(0,0,0,0.04)',
            position: 'relative',
            overflow: 'hidden'
          }} />
          
          {/* Progress indicator */}
          <Box sx={{ 
            position: 'absolute',
            top: 0,
            left: 0,
            height: 10,
            width: `${percentage}%`,
            borderRadius: 5,
            background: getPhaseGradient(),
            transition: 'width 0.4s cubic-bezier(0.65, 0, 0.35, 1), background 0.5s ease',
            boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end'
          }}>
            {percentage > 10 && (
              <Box sx={{ 
                width: 6, 
                height: 6, 
                borderRadius: '50%', 
                bgcolor: '#fff', 
                mr: 0.5, 
                boxShadow: '0 0 4px rgba(255,255,255,0.8)',
                animation: 'pulse 1.5s infinite'
              }} />
            )}
          </Box>
          
          {/* CSS for pulsing animation */}
          <style>{`
            @keyframes pulse {
              0% { opacity: 0.6; transform: scale(0.8); }
              50% { opacity: 1; transform: scale(1.1); }
              100% { opacity: 0.6; transform: scale(0.8); }
            }
          `}</style>
        </Box>
        
        {channelName && (
          <Typography variant="body2" sx={{ 
            fontWeight: 'medium', 
            color: '#444',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            animation: 'fadeIn 0.3s',
            pl: 0.5
          }}>
            {channelName}
          </Typography>
        )}
      </Box>
      
      {complete && (
        <Alert 
          severity="success" 
          sx={{ 
            mt: 2, 
            borderRadius: 2,
            animation: 'fadeIn 0.5s'
          }}
        >
          Processing complete! {progress.totalChannels} channels processed.
        </Alert>
      )}
      
      {/* CSS for fade-in animation */}
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(5px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </Box>
  );
};

export { ChannelProgress, generateRequestId }; 