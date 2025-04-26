import React, { useState } from 'react';
import Settings from './components/Settings';
import SummariesMosaic from './components/SummariesMosaic';
import TopicDetails from './components/TopicDetails';
import logo from './assets/image.png';
import './App.css';

function App() {
  const [summaries, setSummaries] = useState(null);
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedTopicIndex, setSelectedTopicIndex] = useState(null);
  const [loadingStep, setLoadingStep] = useState(null);

  const fetchSummaries = async (settings) => {
    setLoading(true);
    setError(null);
    setSelectedTopicIndex(null);
    setSummaries(null);
    setInsights(null);
    setLoadingStep('summaries');
    
    // Scroll down to show the loading indicator
    setTimeout(() => {
      window.scrollTo({
        top: document.querySelector('.loading').getBoundingClientRect().top + window.pageYOffset - 100,
        behavior: 'smooth'
      });
    }, 100);
    
    try {
      // Build query parameters
      const queryParams = new URLSearchParams({
        period: settings.period,
        ...(settings.sources.length > 0 && { sources: settings.sources.join(',') })
      }).toString();

      console.log(`Fetching summaries from: /summaries?${queryParams}`);
      
      // Fetch summaries
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
        setSummaries({ topics: [] });
      } else {
        setSummaries(summariesData);
      }
    } catch (err) {
      console.error('Error fetching summaries:', err);
      setError(err.message || 'An error occurred while processing news data');
    } finally {
      setLoading(false);
      setLoadingStep(null);
    }
  };

  const fetchInsights = async () => {
    if (!summaries || !summaries.topics || summaries.topics.length === 0) {
      setError('No summaries available to generate insights.');
      return;
    }

    setLoading(true);
    setError(null);
    setLoadingStep('insights');
    
    try {
      console.log('Fetching insights for summaries');
      
      // Send the POST request to get insights
      const insightsResponse = await fetch('/insights', {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(summaries)
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
      
      // Set the insights data
      setInsights(insightsData);
    } catch (err) {
      console.error('Error fetching insights:', err);
      setError(err.message || 'An error occurred while generating insights');
    } finally {
      setLoading(false);
      setLoadingStep(null);
    }
  };

  const handleSelectTopic = (index) => {
    setSelectedTopicIndex(index);
  };

  // Get the selected topic if one is selected
  const selectedTopic = insights && 
    insights.topics && 
    selectedTopicIndex !== null ? 
    insights.topics[selectedTopicIndex] : 
    summaries && 
    summaries.topics && 
    selectedTopicIndex !== null ? 
    summaries.topics[selectedTopicIndex] : null;

  // Determine if we have topics to display (either from summaries or insights)
  const displayTopics = insights?.topics || summaries?.topics || [];

  return (
    <div className="app">
      <header className="app-header">
        <div className="container">
          <div className="header-content">
            <div className="logo-container">
              <img src={logo} alt="Uniflux Logo" className="app-logo" />
            </div>
            <h1>Uniflux</h1>
          </div>
          <p>Aggregate, summarize, and gain insights from multiple news sources</p>
        </div>
      </header>
      <main className="container">
        {/* Settings Section */}
        <div className="app-section settings-section-container">
          <Settings onFetchSummaries={fetchSummaries} />
        </div>
        
        {/* Loading and Error States */}
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
        
        {/* Summaries Section */}
        {!loading && !error && summaries && summaries.topics && summaries.topics.length > 0 && (
          <div className="app-section summaries-section-container">
            <div className="section-header">
              <h2 className="section-title">News Summaries</h2>
            </div>
            
            <SummariesMosaic 
              topics={summaries.topics} 
              onSelectTopic={handleSelectTopic}
              selectedTopicId={selectedTopicIndex}
            />
          </div>
        )}
        
        {/* Insights Section */}
        {!loading && !error && insights && insights.topics && insights.topics.length > 0 && (
          <div className="app-section insights-section-container">
            <div className="section-header">
              <h2 className="section-title">Generated Insights</h2>
            </div>
            
            <SummariesMosaic 
              topics={insights.topics} 
              onSelectTopic={handleSelectTopic}
              selectedTopicId={selectedTopicIndex}
              showInsights={true}
            />
          </div>
        )}
        
        {/* Topic Details Section */}
        {selectedTopic && (
          <div className="app-section details-section-container">
            <TopicDetails 
              topic={selectedTopic} 
              hasInsights={!!insights} 
              onGenerateInsights={!insights ? fetchInsights : undefined}
            />
          </div>
        )}
      </main>
    </div>
  );
}

export default App; 