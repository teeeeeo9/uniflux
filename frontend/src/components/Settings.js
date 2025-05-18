import React, { useState, useEffect, useRef } from 'react';
import './Settings.css';

// Add API_URL from environment variables
const API_URL = process.env.REACT_APP_API_URL || '';

const Settings = ({ onFetchSummaries }) => {
  // State for time period
  const [period, setPeriod] = useState('1d');
  
  // State for API data
  const [categories, setCategories] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // State for selected sources
  const [selectedSources, setSelectedSources] = useState([]);
  
  // State for category checkboxes
  const [selectedCategories, setSelectedCategories] = useState({});
  
  // State for custom sources
  const [customSources, setCustomSources] = useState(['']);
  
  // State for subscription
  const [email, setEmail] = useState('');
  const [subscriptionSubmitted, setSubscriptionSubmitted] = useState(false);
  const [subscriptionError, setSubscriptionError] = useState('');

  // State for active tab
  const [activeTab, setActiveTab] = useState('telegram-export');

  // State for Telegram export
  const [telegramFile, setTelegramFile] = useState(null);
  const [fileError, setFileError] = useState('');
  const [channels, setChannels] = useState([]);
  const [channelTopics, setChannelTopics] = useState([]);
  const [selectedChannels, setSelectedChannels] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [clustering, setClustering] = useState(false);
  
  // State for drag and drop
  const [isDragging, setIsDragging] = useState(false);
  
  // State for progress tracking
  const [progress, setProgress] = useState({
    clusteringComplete: false,
    processedChannels: 0,
    totalChannels: 0,
    currentChannel: null
  });
  
  // Create a ref for the file input
  const fileInputRef = useRef(null);

  // Fetch sources from API on component mount
  useEffect(() => {
    if (activeTab === 'default-sources') {
      fetchSources();
    }
  }, [activeTab]);

    const fetchSources = async () => {
      setLoading(true);
      try {
        console.log('Fetching sources from /sources endpoint');
        const response = await fetch(`${API_URL}/sources`, {
          method: 'GET',
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'ngrok-skip-browser-warning': 'true'
          }
        });
        
        if (!response.ok) {
          // Try to get detailed error message
          let errorMsg = `Server error: ${response.status}`;
          try {
            const errorData = await response.json();
            if (errorData && errorData.error) {
              errorMsg = errorData.error;
            }
          } catch (e) {
            const text = await response.text();
            if (text) errorMsg += ` - ${text}`;
          }
          throw new Error(errorMsg);
        }
        
        const data = await response.json();
        console.log('Sources response:', data);
        setCategories(data.sources || {});
        
        // Initialize selected categories state
        const initialSelectedCategories = {};
        Object.keys(data.sources || {}).forEach(category => {
          initialSelectedCategories[category] = false;
        });
        setSelectedCategories(initialSelectedCategories);
      } catch (err) {
        console.error('Error fetching sources:', err);
        setError(err.message || 'Failed to fetch sources');
      } finally {
        setLoading(false);
      }
    };

  const handlePeriodChange = (e) => {
    setPeriod(e.target.value);
  };

  const handleSourceToggle = (url) => {
    setSelectedSources(prev => {
      if (prev.includes(url)) {
        return prev.filter(source => source !== url);
      } else {
        return [...prev, url];
      }
    });
  };
  
  const handleCategoryToggle = (category) => {
    const updatedSelectedCategories = {
      ...selectedCategories,
      [category]: !selectedCategories[category]
    };
    setSelectedCategories(updatedSelectedCategories);
    
    // Update selected sources based on category selection
    const categoryUrls = categories[category].map(source => source.url);
    
    if (updatedSelectedCategories[category]) {
      // Add all sources in this category if they're not already selected
      setSelectedSources(prev => {
        const newSources = [...prev];
        categoryUrls.forEach(url => {
          if (!newSources.includes(url)) {
            newSources.push(url);
          }
        });
        return newSources;
      });
    } else {
      // Remove all sources in this category
      setSelectedSources(prev => prev.filter(url => !categoryUrls.includes(url)));
    }
  };

  // Toggle all sources selection
  const toggleAllSources = () => {
    if (selectedSources.length === 0) {
      // Select all sources
      const allUrls = [];
      Object.values(categories).forEach(sourcesList => {
        sourcesList.forEach(source => {
          if (!allUrls.includes(source.url)) {
            allUrls.push(source.url);
          }
        });
      });
      setSelectedSources(allUrls);
    } else {
      // Remove all selections
      setSelectedSources([]);
    }
  };
  
  // Toggle all channels selection
  const toggleAllChannels = () => {
    if (selectedChannels.length === 0) {
      // Select all channels
      const allChannelIds = [];
      channelTopics.forEach(topic => {
        topic.channels.forEach(channel => {
          allChannelIds.push(channel.id);
        });
      });
      setSelectedChannels(allChannelIds);
    } else {
      // Remove all selections
      setSelectedChannels([]);
    }
  };

  // Check if all sources in a category are selected
  const isCategorySelected = (category) => {
    const categoryUrls = categories[category].map(source => source.url);
    return categoryUrls.every(url => selectedSources.includes(url));
  };

  // Check if some (but not all) sources in a category are selected
  const isCategoryPartiallySelected = (category) => {
    const categoryUrls = categories[category].map(source => source.url);
    const isPartial = categoryUrls.some(url => selectedSources.includes(url)) && 
                     !categoryUrls.every(url => selectedSources.includes(url));
    return isPartial;
  };

  // Update selected categories state based on source selections
  useEffect(() => {
    const newSelectedCategories = {};
    
    Object.keys(categories).forEach(category => {
      newSelectedCategories[category] = isCategorySelected(category);
    });
    
    setSelectedCategories(newSelectedCategories);
  }, [selectedSources, categories]);
  
  // Handle custom source input change
  const handleCustomSourceChange = (index, value) => {
    const newCustomSources = [...customSources];
    newCustomSources[index] = value;
    setCustomSources(newCustomSources);
  };
  
  // Handle key press in custom source input
  const handleCustomSourceKeyPress = (e, index) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      
      // If there's text in the current field, add a new empty field
      if (customSources[index].trim() !== '') {
        setCustomSources([...customSources, '']);
      }
    }
  };
  
  // Remove a custom source
  const removeCustomSource = (index) => {
    const newCustomSources = customSources.filter((_, i) => i !== index);
    if (newCustomSources.length === 0) {
      newCustomSources.push('');
    }
    setCustomSources(newCustomSources);
  };

  // Handle email subscription
  const handleEmailChange = (e) => {
    setEmail(e.target.value);
    if (subscriptionError) setSubscriptionError('');
  };

  const validateEmail = (email) => {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
  };

  const handleSubscribe = async () => {
    // Reset previous error and success states
    setSubscriptionError('');
    
    // Validate email
    if (!email.trim()) {
      setSubscriptionError('Please enter an email address');
      return;
    }
    
    if (!validateEmail(email)) {
      setSubscriptionError('Please enter a valid email address');
      return;
    }
    
    try {
      // Send subscription to backend
      const response = await fetch(`${API_URL}/subscribe`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'ngrok-skip-browser-warning': 'true'
        },
        body: JSON.stringify({
          email: email,
          source: 'custom-sources'
        })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to subscribe');
      }
      
      console.log(`Email ${email} subscribed for custom sources notifications`);
      
      // Show success message
      setSubscriptionSubmitted(true);
      setEmail('');
      
      // Reset success message after 3 seconds
      setTimeout(() => {
        setSubscriptionSubmitted(false);
      }, 3000);
    } catch (err) {
      console.error('Error saving subscription:', err);
      setSubscriptionError(err.message || 'Failed to subscribe. Please try again.');
    }
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
  };

  // Drag and drop handlers
  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isDragging) setIsDragging(true);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      handleFiles(files[0]);
    }
  };

  const handleFileInputChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      handleFiles(file);
    }
  };

  const handleFiles = (file) => {
    // Check file type
    if (file.type !== 'application/json') {
      setFileError('Please upload a JSON file');
      return;
    }
    
    setTelegramFile(file);
    setFileError('');
  };

  const handleClickUploadArea = () => {
    // Trigger the hidden file input when the upload area is clicked
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleChannelToggle = (channelId) => {
    setSelectedChannels(prev => {
      if (prev.includes(channelId)) {
        return prev.filter(id => id !== channelId);
      } else {
        return [...prev, channelId];
      }
    });
  };

  const handleTopicToggle = (topic) => {
    // Find all channel IDs in this topic
    const channelIds = topic.channels.map(channel => channel.id);
    
    // Check if all channels in this topic are already selected
    const allSelected = channelIds.every(id => selectedChannels.includes(id));
    
    if (allSelected) {
      // Remove all channels in this topic
      setSelectedChannels(prev => prev.filter(id => !channelIds.includes(id)));
    } else {
      // Add all channels in this topic that aren't already selected
      setSelectedChannels(prev => {
        const newSelected = [...prev];
        channelIds.forEach(id => {
          if (!newSelected.includes(id)) {
            newSelected.push(id);
          }
        });
        return newSelected;
      });
    }
  };

  // Check if all channels in a topic are selected
  const isTopicSelected = (topic) => {
    const topicChannelIds = topic.channels.map(channel => channel.id);
    return topicChannelIds.every(id => selectedChannels.includes(id));
  };

  // Check if some (but not all) channels in a topic are selected
  const isTopicPartiallySelected = (topic) => {
    const topicChannelIds = topic.channels.map(channel => channel.id);
    return topicChannelIds.some(id => selectedChannels.includes(id)) && 
           !topicChannelIds.every(id => selectedChannels.includes(id));
  };

  // Check if we should show language tags (only when multiple languages)
  const shouldShowLanguages = () => {
    if (!channelTopics || channelTopics.length === 0) return false;
    
    const uniqueLanguages = new Set();
    channelTopics.forEach(topic => {
      if (topic.language) {
        uniqueLanguages.add(topic.language);
      }
    });
    
    return uniqueLanguages.size > 1;
  };

  const uploadTelegramExport = async () => {
    if (!telegramFile) {
      setFileError('Please select a file to upload');
      return;
    }
    
    setUploading(true);
    setFileError('');
    
    // Reset progress tracking
    setProgress({
      clusteringComplete: false,
      processedChannels: 0,
      totalChannels: 0,
      currentChannel: null
    });
    
    try {
      // Create FormData and append file
      const formData = new FormData();
      formData.append('file', telegramFile);
      
      // Generate a request ID for tracking progress
      const requestId = Date.now().toString();
      
      // Upload the file to backend
      const response = await fetch(`${API_URL}/upload-telegram-export`, {
        method: 'POST',
        body: formData
      });
      
      // Check content type before trying to parse as JSON
      const contentType = response.headers.get('content-type');
      if (!response.ok) {
        if (contentType && contentType.includes('application/json')) {
          const errorData = await response.json();
          throw new Error(errorData.error || `Server error: ${response.status}`);
        } else {
          // If it's not JSON, get the text instead
          const errorText = await response.text();
          console.error('Server returned non-JSON response:', errorText.substring(0, 200) + '...');
          throw new Error(`Server error: ${response.status}. The server did not return a valid JSON response.`);
        }
      }
      
      // Verify we have JSON before parsing
      if (!contentType || !contentType.includes('application/json')) {
        const responseText = await response.text();
        console.error('Server returned non-JSON response:', responseText.substring(0, 200) + '...');
        throw new Error('The server returned an invalid response format.');
      }
      
      const data = await response.json();
      
      if (!data.success) {
        throw new Error(data.error || 'Failed to process the file');
      }
      
      setChannels(data.channels);
      
      // Update progress tracking
      setProgress(prev => ({
        ...prev,
        totalChannels: data.channels.length
      }));
      
      // Set up event source for clustering progress
      const clusterEventSource = new EventSource(`${API_URL}/channel-progress?requestId=${requestId}`);
      
      clusterEventSource.onmessage = (event) => {
        const progressData = JSON.parse(event.data);
        setProgress(prev => ({
          ...prev,
          processedChannels: progressData.processedChannels,
          totalChannels: progressData.totalChannels,
          currentChannel: progressData.currentChannel
        }));
        
        // Close the event source when clustering is complete
        if (progressData.currentChannel === "Clustering complete!") {
          clusterEventSource.close();
          setProgress(prev => ({
            ...prev,
            clusteringComplete: true,
            processedChannels: channelTopics.length,
            totalChannels: channelTopics.length,
            currentChannel: "Analysis complete"
          }));
        }
      };
      
      clusterEventSource.onerror = () => {
        console.error('EventSource error');
        clusterEventSource.close();
      };
      
      // Cluster the channels
      await clusterChannels(data.channels, requestId);
      
      // Close the event source
      clusterEventSource.close();
      
    } catch (err) {
      console.error('Error uploading Telegram export:', err);
      setFileError(err.message || 'Failed to upload file');
    } finally {
      setUploading(false);
    }
  };

  const clusterChannels = async (channelsData, requestId) => {
    setClustering(true);
    
    try {
      // Update progress for clustering start
      setProgress(prev => ({
        ...prev,
        clusteringComplete: false,
        processedChannels: 0,
        totalChannels: channelsData.length
      }));
      
      // Send channels to clustering endpoint
      const response = await fetch(`${API_URL}/cluster-channels`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'ngrok-skip-browser-warning': 'true',
          'X-Request-ID': requestId || Date.now().toString()
        },
        body: JSON.stringify({ 
          channels: channelsData,
          simplified_fetching: true // Tell backend to skip link parsing for initial clustering
        })
      });
      
      // Check content type before trying to parse as JSON
      const contentType = response.headers.get('content-type');
      if (!response.ok) {
        if (contentType && contentType.includes('application/json')) {
          const errorData = await response.json();
          throw new Error(errorData.error || `Server error: ${response.status}`);
        } else {
          // If it's not JSON, get the text instead
          const errorText = await response.text();
          console.error('Server returned non-JSON response:', errorText.substring(0, 200) + '...');
          throw new Error(`Server error: ${response.status}. The server did not return a valid JSON response.`);
        }
      }
      
      // Verify we have JSON before parsing
      if (!contentType || !contentType.includes('application/json')) {
        const responseText = await response.text();
        console.error('Server returned non-JSON response:', responseText.substring(0, 200) + '...');
        throw new Error('The server returned an invalid response format.');
      }
      
      const data = await response.json();
      
      if (!data.success) {
        throw new Error(data.error || 'Failed to cluster channels');
      }
      
      setChannelTopics(data.topics);
      
      // Update progress for completed clustering
      setProgress(prev => ({
        ...prev,
        clusteringComplete: true,
        processedChannels: channelTopics.length,
        totalChannels: channelTopics.length,
        currentChannel: "Analysis complete"
      }));
      
      // Select only the first 2 channels in each topic
      const initialSelectedChannels = [];
      data.topics.forEach(topic => {
        // Get up to the first 2 channels from each topic
        const topChannels = topic.channels.slice(0, 2);
        
        // Add their IDs to the selected channels
        topChannels.forEach(channel => {
          initialSelectedChannels.push(channel.id);
        });
      });
      
      // Set initial selected channels
      setSelectedChannels(initialSelectedChannels);
      
    } catch (err) {
      console.error('Error clustering channels:', err);
      setFileError(err.message || 'Failed to analyze channels');
    } finally {
      setClustering(false);
    }
  };

  const handleDefaultSubmit = (e) => {
    e.preventDefault();
    
    // Combine selected sources from categories with valid custom sources
    const validCustomSources = customSources
      .map(source => source.trim())
      .filter(source => source.length > 0);
    
    const allSources = [...selectedSources, ...validCustomSources];
    
    console.log('Generating summaries with settings:', { period, sources: allSources });
    onFetchSummaries({ period, sources: allSources });
  };

  const handleTelegramSubmit = async (e) => {
    e.preventDefault();
    
    if (selectedChannels.length === 0) {
      setFileError('Please select at least one channel');
      return;
    }
    
    // Find the selected channel data
    const selectedChannelData = [];
    channelTopics.forEach(topic => {
      topic.channels.forEach(channel => {
        if (selectedChannels.includes(channel.id)) {
          selectedChannelData.push(channel);
        }
      });
    });

    // Show loading state
    setUploading(true);
    setFileError('');
    
    // Reset progress tracking for channel processing
    setProgress(prev => ({
      ...prev,
      processedChannels: 0,
      totalChannels: selectedChannelData.length,
      currentChannel: null
    }));
    
    try {
      // First save channels to database and fetch messages
      console.log('Saving selected channels to database:', selectedChannelData);
      
      const saveResponse = await fetch(`${API_URL}/save-telegram-channels`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'ngrok-skip-browser-warning': 'true'
        },
        body: JSON.stringify({
          channels: selectedChannelData,
          period: period
        })
      });
      
      // Set up event source for progress updates
      const eventSource = new EventSource(`${API_URL}/channel-progress?requestId=${Date.now()}`);
      
      eventSource.onmessage = (event) => {
        const progressData = JSON.parse(event.data);
        setProgress(prev => ({
          ...prev,
          processedChannels: progressData.processedChannels,
          totalChannels: progressData.totalChannels,
          currentChannel: progressData.currentChannel
        }));
        
        // Close the event source when all channels are processed
        if (progressData.processedChannels >= progressData.totalChannels) {
          eventSource.close();
        }
      };
      
      eventSource.onerror = () => {
        console.error('EventSource error');
        eventSource.close();
      };
      
      if (!saveResponse.ok) {
        const errorData = await saveResponse.json();
        throw new Error(errorData.error || `Server error: ${saveResponse.status}`);
      }
      
      const saveResult = await saveResponse.json();
      console.log('Save result:', saveResult);
      
      // Convert Telegram channel IDs to t.me URLs for the summary generation
      const channelUrls = selectedChannelData.map(channel => 
        channel.url || `https://t.me/${channel.id}`
      );
      
      console.log('Generating summaries for Telegram channels:', { period, sources: channelUrls });
      onFetchSummaries({ period, sources: channelUrls });
      
      // Close the event source after fetch is complete
      eventSource.close();
      
    } catch (err) {
      console.error('Error processing Telegram channels:', err);
      setFileError(err.message || 'Failed to process channels');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="settings-section">
      <div className="header-container">
        <h2>News Settings</h2>
        <div className="time-period-container">
          <label htmlFor="period" className="time-period-label">Time Period:</label>
          <select 
            id="period" 
            value={period} 
            onChange={handlePeriodChange}
            className="time-period-select"
          >
            <option value="1d">Last 24 hours</option>
            <option value="2d">Last 2 days</option>
            {/* <option value="1w">Last week</option> */}
          </select>
        </div>
      </div>
      
      {/* Tab Navigation */}
      <div className="settings-tabs">
        <button 
          className={`tab-button ${activeTab === 'telegram-export' ? 'active' : ''}`}
          onClick={() => handleTabChange('telegram-export')}
        >
          Telegram Export
        </button>
        <button 
          className={`tab-button ${activeTab === 'default-sources' ? 'active' : ''}`}
          onClick={() => handleTabChange('default-sources')}
        >
          Default Sources
        </button>
      </div>
      
      {/* Telegram Export Tab */}
      {activeTab === 'telegram-export' && (
        <div className="telegram-export-section">
          <div className="telegram-export-instructions">
            <h3>How to Export Data from Telegram</h3>
            <ol>
              <li>Open the Telegram app and click on <strong>Settings</strong> (⚙️)</li>
              <li>Go to <strong>Privacy and Security</strong> → <strong>Export Telegram Data</strong></li>
              <li>Select <strong>Export chats and channels list</strong> (you don't need chat history)</li>
              <li>Format: <strong>JSON</strong></li>
              <li>Click <strong>Export</strong> and download the file</li>
              <li>Upload the JSON file below</li>
            </ol>
          </div>
          
          <div className="file-upload-section">
            <div 
              className={`file-upload-dropzone ${isDragging ? 'dragging' : ''} ${telegramFile ? 'has-file' : ''}`}
              onDragEnter={handleDragEnter}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={handleClickUploadArea}
            >
              <div className="dropzone-content">
                <span className="upload-icon">📁</span>
                <span className="upload-text">
                  {isDragging ? 'Drop Here' : 
                   telegramFile ? `Selected: ${telegramFile.name}` : 
                   'Drag & Drop Telegram Export File or Click to Browse'}
                </span>
                <input 
                  type="file" 
                  ref={fileInputRef}
                  accept=".json" 
                  onChange={handleFileInputChange}
                  className="file-input hidden"
                />
              </div>
            </div>
            
            {telegramFile && (
              <div className="selected-file">
                <button 
                  className="upload-file-btn" 
                  onClick={uploadTelegramExport}
                  disabled={uploading || clustering}
                >
                  {uploading ? 'Uploading...' : clustering ? 'Analyzing...' : 'Upload & Analyze'}
                </button>
              </div>
            )}
            {fileError && <p className="error-message">{fileError}</p>}
          </div>
          
          {/* Progress indicators for clustering and channel processing */}
          {(clustering || uploading || progress.processedChannels > 0) && (
            <div className="progress-section">
              {clustering && (
                <div className="progress-item">
                  <h4>Analyzing Channels...</h4>
                  <div className="progress-bar">
                    <div className="progress-bar-inner indeterminate"></div>
                  </div>
                </div>
              )}
              
              {progress.clusteringComplete && progress.totalChannels > 0 && (
                <div className="progress-item">
                  <h4>
                    Processing Channels: {progress.processedChannels} of {progress.totalChannels}
                  </h4>
                  {progress.currentChannel && (
                    <div className="current-channel">
                      <span className="channel-indicator">Current Channel:</span> 
                      <span className="channel-name">{progress.currentChannel}</span>
                    </div>
                  )}
                  <div className="progress-bar">
                    <div 
                      className="progress-bar-inner" 
                      style={{width: `${(progress.processedChannels / progress.totalChannels) * 100}%`}}
                    ></div>
                  </div>
                </div>
              )}
            </div>
          )}
          
          {channelTopics.length > 0 && (
            <form onSubmit={handleTelegramSubmit}>
              <div className="channel-topics-section">
                <h3>Telegram Channels by Topic</h3>
                <div className="selection-controls">
                  <p className="select-channels-prompt">Select channels to include in the summaries:</p>
                  <button 
                    type="button" 
                    className="toggle-selection-btn"
                    onClick={toggleAllChannels}
                  >
                    {selectedChannels.length === 0 ? 'Select All' : 'Remove All Selection'}
                  </button>
                </div>
                
                <div className="channel-topics-grid">
                  {channelTopics.map((topic, index) => (
                    <div key={index} className="channel-topic-block">
                      <div className="topic-header">
                        <label className="topic-checkbox-label">
                          <input
                            type="checkbox"
                            checked={isTopicSelected(topic)}
                            onChange={() => handleTopicToggle(topic)}
                            className="topic-checkbox"
                            ref={el => {
                              if (el) {
                                el.indeterminate = isTopicPartiallySelected(topic);
                              }
                            }}
                          />
                          <h4>{topic.topic} ({topic.channels.length})</h4>
                          {shouldShowLanguages() && topic.language && (
                            <span className="language-tag">{topic.language.toUpperCase()}</span>
                          )}
                        </label>
                      </div>
                      <div className="channel-list-container">
                        {topic.channels.map(channel => (
                          <div key={channel.id} className="channel-item">
                            <label className="channel-checkbox-label">
                              <input
                                type="checkbox"
                                checked={selectedChannels.includes(channel.id)}
                                onChange={() => handleChannelToggle(channel.id)}
                              />
                              <span className="channel-name" title={channel.name}>
                                {channel.name}
                                {channel.left && <span className="left-indicator"> (left)</span>}
                                {channel.last_message_date && (
                                  <span className="last-message-date" title={`Last message: ${channel.last_message_date}`}>
                                    {' '}{new Date(channel.last_message_date).toLocaleDateString()}
                                  </span>
                                )}
                              </span>
                            </label>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="selected-count">
                  Selected channels: {selectedChannels.length}
                </div>
              </div>
              
              <div className="form-actions">
                <button 
                  type="submit" 
                  className="btn btn-primary"
                  disabled={selectedChannels.length === 0 || uploading}
                >
                  {uploading ? 'Processing Channels...' : 'Generate Summaries from Telegram'}
                </button>
                {uploading && <p className="processing-note">Fetching messages from channels. This may take a moment...</p>}
              </div>
            </form>
          )}
        </div>
      )}
      
      {/* Default Sources Tab */}
      {activeTab === 'default-sources' && (
        <>
      {loading ? (
        <div className="loading-indicator">Loading sources...</div>
      ) : error ? (
        <div className="error-message">
          <p>Error: {error}</p>
          <p>Make sure the Flask backend is running properly.</p>
        </div>
      ) : (
            <form onSubmit={handleDefaultSubmit}>
          <div className="source-categories-grid">
            {Object.keys(categories).length === 0 ? (
              <p className="no-sources">No sources available in the database.</p>
            ) : (
              <>
                <div className="selection-controls">
                  <button 
                    type="button" 
                    className="toggle-selection-btn"
                    onClick={toggleAllSources}
                  >
                    {selectedSources.length === 0 ? 'Select All' : 'Remove All Selection'}
                  </button>
                </div>
                {Object.entries(categories).map(([category, sources]) => (
                  <div key={category} className="source-category-block">
                    <div className="category-header">
                      <label className="category-checkbox-label">
                        <input
                          type="checkbox"
                          checked={isCategorySelected(category)}
                          onChange={() => handleCategoryToggle(category)}
                          className="category-checkbox"
                          ref={el => {
                            if (el) {
                              el.indeterminate = isCategoryPartiallySelected(category);
                            }
                          }}
                        />
                        <h3>{category}</h3>
                      </label>
                    </div>
                    <div className="source-list-container-grid">
                      {sources.map(source => (
                        <div key={source.id} className="source-item">
                          <label className="checkbox-label">
                            <input
                              type="checkbox"
                              checked={selectedSources.includes(source.url)}
                              onChange={() => handleSourceToggle(source.url)}
                            />
                            <span className="source-name" title={source.url}>
                              {source.name}
                            </span>
                          </label>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}

                {/* Custom Sources section as a category block - email subscription */}
                <div className="source-category-block disabled-feature custom-sources-block">
                  <div className="category-header">
                    <h3>Custom Sources</h3>
                  </div>
                  <div className="source-list-container-grid blurred-content">
                    <div className="custom-source-item subscription-message">
                      {subscriptionSubmitted ? (
                        <div className="subscription-success">
                          <span className="success-icon">✓</span>
                          <p>Thank you for subscribing!</p>
                          <p>We'll notify you when custom sources are available.</p>
                        </div>
                      ) : (
                        <>
                          <p>Enter your email to get access to custom news sources feature.</p>
                          <div className="email-subscription-form">
                            <input 
                              type="email" 
                              className={`email-input ${subscriptionError ? 'input-error' : ''}`}
                              placeholder="Your email address"
                              aria-label="Email address for subscription"
                              value={email}
                              onChange={handleEmailChange}
                            />
                            <button 
                              className="subscribe-button" 
                              type="button"
                              onClick={handleSubscribe}
                            >
                              Subscribe
                            </button>
                          </div>
                          {subscriptionError && (
                            <p className="error-message">{subscriptionError}</p>
                          )}
                        </>
                      )}
                    </div>
                    {/* Custom source inputs remain hidden */}
                  </div>
                </div>
              </>
            )}
          </div>
          <div className="selected-count">
            Selected sources: {selectedSources.length}
          </div>

          <div className="form-actions">
            <button 
              type="submit" 
              className="btn btn-primary"
              disabled={selectedSources.length === 0}
            >
              Generate Summaries
            </button>
          </div>
        </form>
          )}
        </>
      )}
    </div>
  );
};

export default Settings; 