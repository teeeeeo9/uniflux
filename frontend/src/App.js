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
  const [loadingStep, setLoadingStep] = useState(null); // Track which step is loading

  const fetchInsights = async (settings) => {
    setLoading(true);
    setError(null);
    setSelectedTopicIndex(null);
    setSummary(null);
    setLoadingStep('summaries');
    
    try {
      // Build query parameters
      const queryParams = new URLSearchParams({
        period: settings.period,
        ...(settings.sources.length > 0 && { sources: settings.sources.join(',') })
      }).toString();

      console.log(`Fetching summaries from: /summaries?${queryParams}`);
      
      // Step 1: Fetch summaries
      const summariesResponse = await fetch(`/summaries?${queryParams}`, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        }
      });
      
      // Handle non-OK summaries response
      if (!summariesResponse.ok) {
        let errorMsg = `Server error fetching summaries: ${summariesResponse.status}`;
        try {
          const errorData = await summariesResponse.json();
          if (errorData && errorData.error) {
            errorMsg = errorData.error;
          }
        } catch (e) {
          const text = await summariesResponse.text();
          if (text) errorMsg += ` - ${text}`;
        }
        throw new Error(errorMsg);
      }
      
      // Parse the summaries response
      const summariesData = await summariesResponse.json();
      console.log('Summaries response:', summariesData);
      
      // Check if we have valid summaries
      if (!summariesData.topics || summariesData.topics.length === 0) {
        console.log('No topics found in summaries');
        setSummary({ topics: [] });
        setLoading(false);
        return;
      }
      
      // Step 2: Get insights for the summaries
      setLoadingStep('insights');
      console.log('Fetching insights for summaries');
      
      const insightsResponse = await fetch('/insights', {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(summariesData)
      });
      
      // Handle non-OK insights response
      if (!insightsResponse.ok) {
        let errorMsg = `Server error fetching insights: ${insightsResponse.status}`;
        try {
          const errorData = await insightsResponse.json();
          if (errorData && errorData.error) {
            errorMsg = errorData.error;
          }
        } catch (e) {
          const text = await insightsResponse.text();
          if (text) errorMsg += ` - ${text}`;
        }
        throw new Error(errorMsg);
      }
      
      // Parse the insights response
      const insightsData = await insightsResponse.json();
      console.log('Insights response:', insightsData);
      
      // Set the final data with insights
      setSummary(insightsData);
    } catch (err) {
      console.error('Error in pipeline:', err);
      setError(err.message || 'An error occurred while processing news data');
    } finally {
      setLoading(false);
      setLoadingStep(null);
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
        
        {loading && (
          <div className="loading">
            {loadingStep === 'summaries' ? 'Generating summaries...' : 'Generating insights...'}
          </div>
        )}
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