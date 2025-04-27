import React, { useState, useEffect } from 'react';
import './Settings.css';

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

    fetchSources();
  }, []);

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
      const response = await fetch('/subscribe', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
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

  const handleSubmit = (e) => {
    e.preventDefault();
    
    // Combine selected sources from categories with valid custom sources
    const validCustomSources = customSources
      .map(source => source.trim())
      .filter(source => source.length > 0);
    
    const allSources = [...selectedSources, ...validCustomSources];
    
    console.log('Generating summaries with settings:', { period, sources: allSources });
    onFetchSummaries({ period, sources: allSources });
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
      {loading ? (
        <div className="loading-indicator">Loading sources...</div>
      ) : error ? (
        <div className="error-message">
          <p>Error: {error}</p>
          <p>Make sure the Flask backend is running properly.</p>
        </div>
      ) : (
        <form onSubmit={handleSubmit}>
          <div className="source-categories-grid">
            {Object.keys(categories).length === 0 ? (
              <p className="no-sources">No sources available in the database.</p>
            ) : (
              Object.entries(categories).map(([category, sources]) => (
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
              ))
            )}

            {/* Custom Sources section as a category block - email subscription */}
            <div className="source-category-block disabled-feature custom-sources-block">
              <div className="category-header">
                <h3>Custom Sources</h3>
              </div>
              <div className="source-list-container-grid">
                <div className="custom-source-item subscription-message">
                  {subscriptionSubmitted ? (
                    <div className="subscription-success">
                      <span className="success-icon">✓</span>
                      <p>Thank you for subscribing!</p>
                      <p>We'll notify you when custom sources are available.</p>
                    </div>
                  ) : (
                    <>
                      <p>Enter your email to get notified when we add support for custom news sources.</p>
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
    </div>
  );
};

export default Settings; 