import React, { useState } from 'react';
import Settings from './components/Settings';
import './App.css';

function App() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchInsights = async (settings) => {
    setLoading(true);
    setError(null);
    try {
      const queryParams = new URLSearchParams({
        period: settings.period,
        ...(settings.sources.length > 0 && { sources: settings.sources.join(',') })
      }).toString();

      const response = await fetch(`/insights?${queryParams}`);
      if (!response.ok) {
        throw new Error('Failed to fetch insights');
      }
      const data = await response.json();
      setSummary(data);
    } catch (err) {
      console.error('Error fetching insights:', err);
      setError(err.message || 'An error occurred while fetching insights');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="container">
          <h1>News Insights</h1>
          <p>Aggregate, summarize, and gain insights from multiple news sources</p>
        </div>
      </header>
      <main className="container">
        <Settings onFetchInsights={fetchInsights} />
        
        {/* Middle section (to be implemented) */}
        
        {/* Bottom section (to be implemented) */}
        
        {loading && <div className="loading">Loading insights...</div>}
        {error && <div className="error">Error: {error}</div>}
      </main>
    </div>
  );
}

export default App; 