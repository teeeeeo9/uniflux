import React, { useState, useRef, useEffect } from 'react';
import Settings from './components/Settings';
import SummariesMosaic from './components/SummariesMosaic';
import TopicDetails from './components/TopicDetails';
import Feedback from './components/Feedback';
import Subscription from './components/Subscription';
import logo from './assets/image.png';
import './App.css';

// Add API_URL from environment variables
const API_URL = process.env.REACT_APP_API_URL || '';

function App() {
  const [summaries, setSummaries] = useState(null);
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedTopicIndex, setSelectedTopicIndex] = useState(null);
  const [loadingStep, setLoadingStep] = useState(null);
  const [showFeedbackTooltip, setShowFeedbackTooltip] = useState(false);
  const topicDetailsRef = useRef(null); // Reference to the TopicDetails component

  // Show feedback tooltip after user has been on the page for 60 seconds
  useEffect(() => {
    const timer = setTimeout(() => {
      setShowFeedbackTooltip(true);
      
      // Hide tooltip after 5 seconds
      const hideTimer = setTimeout(() => {
        setShowFeedbackTooltip(false);
      }, 5000);
      
      return () => clearTimeout(hideTimer);
    }, 60000);
    
    return () => clearTimeout(timer);
  }, []);

  const fetchSummaries = async (settings) => {
    setLoading(true);
    setError(null);
    setSelectedTopicIndex(null);
    setSummaries(null);
    setInsights(null);
    setLoadingStep('summaries');
    
    // Scroll down to show the loading indicator
    setTimeout(() => {
      const loadingElement = document.querySelector('.loading');
      if (loadingElement) {
        window.scrollTo({
          top: loadingElement.getBoundingClientRect().top + window.pageYOffset - 100,
          behavior: 'smooth'
        });
      }
    }, 100);
    
    try {
      // Build query parameters
      const queryParams = new URLSearchParams({
        period: settings.period,
        ...(settings.sources.length > 0 && { sources: settings.sources.join(',') })
      }).toString();

      console.log(`Fetching summaries from: ${API_URL}/summaries?${queryParams}`);
      
      // Fetch summaries
      const summariesResponse = await fetch(`${API_URL}/summaries?${queryParams}`, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true'
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
        setSummaries({ topics: [], noMessagesFound: true });
      } else {
        setSummaries(summariesData);
      }
    } catch (err) {
      console.error('Error fetching summaries:', err);
      setError(err.message || 'An error occurred while processing news data');
      
      // Scroll to error message
      setTimeout(() => {
        const errorElement = document.querySelector('.error');
        if (errorElement) {
          window.scrollTo({
            top: errorElement.getBoundingClientRect().top + window.pageYOffset - 100,
            behavior: 'smooth'
          });
        }
      }, 100);
    } finally {
      setLoading(false);
      setLoadingStep(null);
    }
  };

  const fetchInsights = async () => {
    if (!summaries || !summaries.topics || summaries.topics.length === 0) {
      if (summaries && summaries.noMessagesFound) {
        setError('No messages found in the database for the selected time period and sources. Cannot generate insights.');
      } else {
        setError('No summaries available to generate insights.');
      }
      return null;
    }

    if (selectedTopicIndex === null) {
      setError('No topic selected. Please select a topic to generate insights.');
      return null;
    }

    const selectedTopic = summaries.topics[selectedTopicIndex];
    if (!selectedTopic) {
      setError('Selected topic not found.');
      return null;
    }

    setLoading(true);
    setError(null);
    setLoadingStep('insights');
    
    try {
      console.log(`Fetching insights for topic: ${selectedTopic.topic}`);
      
      // Send the POST request to get insights only for the selected topic
      const insightsResponse = await fetch(`${API_URL}/insights`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true'
        },
        body: JSON.stringify({ topics: [selectedTopic] })
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
      
      let resultData = insightsData;
      
      // Set the insights data - merge with existing topics if we already have some
      if (insights && insights.topics) {
        // Create a map of existing insights by topic
        const topicMap = new Map();
        insights.topics.forEach(topic => {
          topicMap.set(topic.topic, topic);
        });

        // Add the new insight
        if (insightsData.topics && insightsData.topics.length > 0) {
          const newTopic = insightsData.topics[0];
          topicMap.set(newTopic.topic, newTopic);
          
          // Force a re-render by creating a new array
          const updatedTopics = Array.from(topicMap.values());
          resultData = { topics: updatedTopics };
          setInsights(resultData);
        }
      } else {
        // First insight
        setInsights(insightsData);
      }
      
      // Ensure we return a valid result object for the calling component to use
      return resultData;
    } catch (err) {
      console.error('Error fetching insights:', err);
      setError(err.message || 'An error occurred while generating insights');
      return null;
    } finally {
      setLoading(false);
      setLoadingStep(null);
    }
  };

  const handleSelectTopic = (index) => {
    setSelectedTopicIndex(index);
  };

  // Get the selected topic if one is selected
  const selectedTopic = selectedTopicIndex !== null ? (
    // Check if the topic has insights first
    (insights?.topics && 
      insights.topics.find(topic => {
        // Find matching topic by name in insights
        const summaryTopic = summaries?.topics?.[selectedTopicIndex];
        return summaryTopic && topic.topic === summaryTopic.topic;
      })) || 
    // Fall back to the summary topic if no insights
    (summaries?.topics?.[selectedTopicIndex])
  ) : null;

  // Check if the selected topic has insights
  const hasInsights = !!(
    insights?.topics && 
    selectedTopic && 
    insights.topics.some(topic => topic.topic === selectedTopic.topic && topic.insights)
  );

  // Determine if we should enable the generate insights button
  const showGenerateInsightsButton = !!selectedTopic && !hasInsights;

  // Function to scroll to messages section regardless of active tab
  const scrollToMessages = () => {
    if (topicDetailsRef.current) {
      topicDetailsRef.current.scrollToMessages();
    }
  };

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
        {!loading && !error && summaries && summaries.topics && (
          <div className="app-section summaries-section-container">
            <div className="section-header">
              <h2 className="section-title">News Summaries</h2>
            </div>
            
            <SummariesMosaic 
              topics={summaries.topics.map(topic => {
                // If there's a matching topic with insights, add a flag to indicate it has insights
                if (insights?.topics && insights.topics.some(t => t.topic === topic.topic && t.insights)) {
                  return { ...topic, hasGeneratedInsights: true };
                }
                return topic;
              })}
              onSelectTopic={handleSelectTopic}
              selectedTopicId={selectedTopicIndex}
              onScrollToMessages={scrollToMessages}
              noMessagesFound={summaries.noMessagesFound}
            />
          </div>
        )}
        
        {/* Topic Details Section */}
        {selectedTopic && (
          <div className="app-section details-section-container">
            <TopicDetails 
              topic={selectedTopic} 
              hasInsights={hasInsights}
              onGenerateInsights={showGenerateInsightsButton ? fetchInsights : undefined}
              ref={topicDetailsRef}
            />
          </div>
        )}
        
        {/* Show Subscription at the bottom when summaries or details are shown */}
        {(!loading && !error && summaries && summaries.topics && 
          (summaries.topics.length > 0 || !summaries.noMessagesFound)) && (
          <div className="bottom-subscription-container">
            <Subscription />
          </div>
        )}
      </main>
      
      {/* Feedback Component */}
      <Feedback />
      {showFeedbackTooltip && (
        <div className="feedback-tooltip">
          <p>We'd love to hear your thoughts! Click here to provide feedback.</p>
        </div>
      )}
    </div>
  );
}

export default App; 