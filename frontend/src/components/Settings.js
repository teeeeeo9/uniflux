import React, { useState, useEffect } from 'react';
import './Settings.css';

const Settings = ({ onFetchInsights }) => {
  // State for different view modes
  const [viewMode, setViewMode] = useState('categories'); // 'categories' or 'custom'
  const [customSources, setCustomSources] = useState('');
  const [period, setPeriod] = useState('1d');
  
  // State for API data
  const [categories, setCategories] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // State for selected sources
  const [selectedSources, setSelectedSources] = useState([]);

  // Fetch sources from API on component mount
  useEffect(() => {
    const fetchSources = async () => {
      setLoading(true);
      try {
        console.log('Fetching sources from /sources endpoint');
        const response = await fetch('/sources', {
          method: 'GET',
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
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
      } catch (err) {
        console.error('Error fetching sources:', err);
        setError(err.message || 'Failed to fetch sources');
      } finally {
        setLoading(false);
      }
    };

    fetchSources();
  }, []);

  const handleViewModeChange = (e) => {
    setViewMode(e.target.value);
  };

  const handleCustomSourcesChange = (e) => {
    setCustomSources(e.target.value);
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

  const handleSubmit = (e) => {
    e.preventDefault();
    
    let sources = [];
    if (viewMode === 'custom') {
      // Parse custom sources (comma-separated)
      sources = customSources
        .split(',')
        .map(source => source.trim())
        .filter(source => source.length > 0);
    } else {
      sources = selectedSources;
    }
    
    console.log('Submitting analysis with settings:', { period, sources });
    onFetchInsights({ period, sources });
  };

  return (
    <div className="settings-section">
      <div className="card">
        <h2>News Settings</h2>
        {loading ? (
          <div className="loading-indicator">Loading sources...</div>
        ) : error ? (
          <div className="error-message">
            <p>Error: {error}</p>
            <p>Make sure the Flask backend is running properly.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <div className="form-control">
                <label htmlFor="viewMode">Source Selection</label>
                <select 
                  id="viewMode" 
                  value={viewMode} 
                  onChange={handleViewModeChange}
                >
                  <option value="categories">Select from categories</option>
                  <option value="custom">Enter custom sources</option>
                </select>
              </div>

              <div className="form-control">
                <label htmlFor="period">Time Period</label>
                <select 
                  id="period" 
                  value={period} 
                  onChange={handlePeriodChange}
                >
                  <option value="1d">Last 24 hours</option>
                  <option value="2d">Last 2 days</option>
                  <option value="1w">Last week</option>
                </select>
              </div>
            </div>

            {viewMode === 'custom' ? (
              <div className="form-control">
                <label htmlFor="customSources">
                  Enter Telegram channels (comma-separated)
                </label>
                <input
                  type="text"
                  id="customSources"
                  value={customSources}
                  onChange={handleCustomSourcesChange}
                  placeholder="e.g., https://t.me/channel1, https://t.me/channel2"
                />
              </div>
            ) : (
              <div className="source-categories">
                {Object.keys(categories).length === 0 ? (
                  <p className="no-sources">No sources available in the database.</p>
                ) : (
                  Object.entries(categories).map(([category, sources]) => (
                    <div key={category} className="source-category">
                      <h3>{category}</h3>
                      <div className="source-list-container">
                        {sources.map(source => (
                          <div key={source.id} className="source-item">
                            <label className="checkbox-label">
                              <input
                                type="checkbox"
                                checked={selectedSources.includes(source.url)}
                                onChange={() => handleSourceToggle(source.url)}
                              />
                              <span className="source-url">{source.url}</span>
                            </label>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))
                )}
                <div className="selected-count">
                  Selected sources: {selectedSources.length}
                </div>
              </div>
            )}

            <div className="form-actions">
              <button 
                type="submit" 
                className="btn btn-primary"
                disabled={viewMode === 'categories' && selectedSources.length === 0}
              >
                Generate Insights
              </button>
              <div className="process-steps">
                <div className="step">
                  <span className="step-number">1</span>
                  <span className="step-name">Generate Summaries</span>
                </div>
                <div className="step-arrow">→</div>
                <div className="step">
                  <span className="step-number">2</span>
                  <span className="step-name">Generate Insights</span>
                </div>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

export default Settings; 