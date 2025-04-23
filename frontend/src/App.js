import React, { useState } from 'react';
import Settings from './components/Settings';
import TopicsList from './components/TopicsList';
import TopicDetails from './components/TopicDetails';
import './App.css';

function App() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedTopicIndex, setSelectedTopicIndex] = useState(null);

  const fetchInsights = async (settings) => {
    setLoading(true);
    setError(null);
    setSelectedTopicIndex(null);
    setSummary(null);
    
    try {
      // Build query parameters
      const queryParams = new URLSearchParams({
        period: settings.period,
        ...(settings.sources.length > 0 && { sources: settings.sources.join(',') })
      }).toString();

      console.log(`Fetching from: /insights?${queryParams}`);
      
      // Make the API request with more detailed error handling
      const response = await fetch(`/insights?${queryParams}`, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        }
      });
      
      // Handle non-OK responses
      if (!response.ok) {
        // Try to get error details from response
        let errorMsg = `Server error: ${response.status}`;
        try {
          const errorData = await response.json();
          if (errorData && errorData.error) {
            errorMsg = errorData.error;
          }
        } catch (e) {
          // If we can't parse JSON, use text content if available
          const text = await response.text();
          if (text) errorMsg += ` - ${text}`;
        }
        throw new Error(errorMsg);
      }
      
      // Parse the JSON response
      const data = await response.json();
      console.log('API response:', data);
      setSummary(data);
    } catch (err) {
      console.error('Error fetching insights:', err);
      setError(err.message || 'An error occurred while fetching insights');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectTopic = (index) => {
    setSelectedTopicIndex(index);
  };

  // Get the selected topic if one is selected
  const selectedTopic = summary && 
    summary.topics && 
    selectedTopicIndex !== null ? 
    summary.topics[selectedTopicIndex] : null;

  return (
    <div className="app">
      <header className="app-header">
        <div className="container">
          <h1>News Insights</h1>
          <p>Aggregate, summarize, and gain insights from multiple news sources</p>
        </div>
      </header>
      <main className="container">
        {/* Top section - Settings */}
        <Settings onFetchInsights={fetchInsights} />
        
        {loading && <div className="loading">Loading insights...</div>}
        {error && (
          <div className="error">
            <h3>Error</h3>
            <p>{error}</p>
            <p>Make sure the Flask backend is running on port 5000.</p>
          </div>
        )}
        
        {/* Middle section - Topics list */}
        {!loading && !error && summary && summary.topics && (
          <TopicsList 
            topics={summary.topics} 
            onSelectTopic={handleSelectTopic}
            selectedTopicId={selectedTopicIndex}
          />
        )}
        
        {/* Bottom section - Topic details */}
        {selectedTopic && (
          <TopicDetails topic={selectedTopic} />
        )}
      </main>
    </div>
  );
}

export default App; 