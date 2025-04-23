import React, { useState, useEffect } from 'react';
import './Settings.css';

// Predefined source lists
const PREDEFINED_SOURCES = {
  'Web3 News': [
    'https://t.me/CoinDeskGlobal',
    'https://t.me/cointelegraph',
    'https://t.me/thedailyape',
    'https://t.me/blockchainnewscentral'
  ],
  'Crypto Markets': [
    'https://t.me/cryptomarketdaily',
    'https://t.me/thecryptomerger',
    'https://t.me/cryptoanalysis'
  ],
  'Energy News': [
    'https://t.me/energynewstoday',
    'https://t.me/energymarkets',
    'https://t.me/climatetech'
  ]
};

const Settings = ({ onFetchInsights }) => {
  const [sourceList, setSourceList] = useState('custom');
  const [customSources, setCustomSources] = useState('');
  const [period, setPeriod] = useState('1d');
  const [isCustom, setIsCustom] = useState(true);
  const [selectedPredefinedSources, setSelectedPredefinedSources] = useState([]);

  useEffect(() => {
    setIsCustom(sourceList === 'custom');
    if (sourceList !== 'custom') {
      setSelectedPredefinedSources(PREDEFINED_SOURCES[sourceList] || []);
    }
  }, [sourceList]);

  const handleSourceListChange = (e) => {
    setSourceList(e.target.value);
  };

  const handleCustomSourcesChange = (e) => {
    setCustomSources(e.target.value);
  };

  const handlePeriodChange = (e) => {
    setPeriod(e.target.value);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    let sources = [];
    if (isCustom) {
      // Parse custom sources (comma-separated)
      sources = customSources
        .split(',')
        .map(source => source.trim())
        .filter(source => source.length > 0);
    } else {
      sources = selectedPredefinedSources;
    }
    
    onFetchInsights({ period, sources });
  };

  return (
    <div className="settings-section">
      <div className="card">
        <h2>News Settings</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <div className="form-control">
              <label htmlFor="sourceList">Source Selection</label>
              <select 
                id="sourceList" 
                value={sourceList} 
                onChange={handleSourceListChange}
              >
                <option value="custom">Custom Sources</option>
                {Object.keys(PREDEFINED_SOURCES).map(category => (
                  <option key={category} value={category}>{category}</option>
                ))}
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

          {isCustom ? (
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
            <div className="selected-sources">
              <p>Selected sources ({selectedPredefinedSources.length}):</p>
              <ul className="source-list">
                {selectedPredefinedSources.map((source, index) => (
                  <li key={index}>{source}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="form-actions">
            <button type="submit" className="btn btn-primary">
              Run Analysis
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Settings; 