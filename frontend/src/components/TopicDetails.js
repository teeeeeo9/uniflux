import React, { useState, useEffect, useImperativeHandle, forwardRef } from 'react';
import './TopicDetails.css';

// Add API_URL from environment variables
const API_URL = process.env.REACT_APP_API_URL || '';

// Helper function to format message text
const formatMessageText = (text) => {
  if (!text) return '';
  
  // Replace consecutive newlines with a single one
  let formatted = text.replace(/\n{3,}/g, '\n\n');
  
  // Replace special quote characters with standard quotes
  formatted = formatted.replace(/[«»]/g, '"');
  formatted = formatted.replace(/['']/g, "'");
  formatted = formatted.replace(/[""]/g, '"');
  
  // Format links - find URLs and make them proper links
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  formatted = formatted.replace(urlRegex, (url) => {
    // Remove trailing punctuation that might be captured
    let cleanUrl = url;
    if (cleanUrl.endsWith('.') || cleanUrl.endsWith(',') || cleanUrl.endsWith(':') || cleanUrl.endsWith(';') || cleanUrl.endsWith(')')) {
      const lastChar = cleanUrl.slice(-1);
      cleanUrl = cleanUrl.slice(0, -1);
      return `<a href="${cleanUrl}" target="_blank" rel="noopener noreferrer">${cleanUrl}</a>${lastChar}`;
    }
    return `<a href="${cleanUrl}" target="_blank" rel="noopener noreferrer">${cleanUrl}</a>`;
  });
  
  // Replace multiple spaces with a single space
  formatted = formatted.replace(/[ ]{2,}/g, ' ');
  
  return formatted;
};

// Helper function to check if a value is empty (used to hide empty fields)
const isEmpty = (value) => {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string') return value.trim() === '';
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'object') return Object.keys(value).length === 0;
  return false;
};

// Helper function to get stance badge styling
const getStanceBadge = (stance) => {
  if (!stance) return { className: 'stance-badge neutral', label: 'No Stance' };
  
  switch(stance.toLowerCase()) {
    case 'long':
      return { className: 'stance-badge long', label: 'Long' };
    case 'short':
      return { className: 'stance-badge short', label: 'Short' };
    case 'long-neutral':
      return { className: 'stance-badge long-neutral', label: 'Long-Neutral' };
    case 'short-neutral':
      return { className: 'stance-badge short-neutral', label: 'Short-Neutral' };
    case 'neutral':
      return { className: 'stance-badge neutral', label: 'Neutral' };
    case 'no actionable insight':
      return { className: 'stance-badge no-insight', label: 'No Actionable Insight' };
    default:
      return { className: 'stance-badge neutral', label: stance };
  }
};

const TopicDetails = forwardRef(({ topic, hasInsights = false, onGenerateInsights }, ref) => {
  const [activeTab, setActiveTab] = useState('messages');
  const [messageContents, setMessageContents] = useState({});
  const [loadingMessages, setLoadingMessages] = useState(false);

  // Expose functions to parent components via ref
  useImperativeHandle(ref, () => ({
    // Function that can be called from parent to scroll to messages section
    scrollToMessages: () => {
      // First switch to messages tab if it's not active
      if (activeTab !== 'messages') {
        setActiveTab('messages');
        // Allow time for the tab switch to take effect
        setTimeout(() => {
          const messagesSection = document.querySelector('.messages-section');
          if (messagesSection) {
            messagesSection.scrollIntoView({ behavior: 'smooth' });
          }
        }, 50);
      } else {
        // Messages tab is already active, just scroll
        const messagesSection = document.querySelector('.messages-section');
        if (messagesSection) {
          messagesSection.scrollIntoView({ behavior: 'smooth' });
        }
      }
    }
  }));

  // Fetch message contents when topic changes or when messages tab is activated
  useEffect(() => {
    if (topic && topic.message_ids && topic.message_ids.length > 0 && activeTab === 'messages') {
      fetchMessageContents();
    }
  }, [topic, activeTab]);
  
  // Switch to insights tab when insights become available
  useEffect(() => {
    if (hasInsights && topic && topic.insights) {
      setActiveTab('insights');
    }
  }, [hasInsights, topic]);

  // Function to fetch message contents from the backend
  const fetchMessageContents = async () => {
    if (!topic || !topic.message_ids || topic.message_ids.length === 0) return;

    setLoadingMessages(true);
    
    try {
      // Fetch each message content
      const contents = {};
      
      // Create promises for all message fetch operations
      const fetchPromises = topic.message_ids.map(async (messageId) => {
        try {
          const response = await fetch(`${API_URL}/message/${messageId}`);
          if (response.ok) {
            const data = await response.json();
            contents[messageId] = data;
          } else {
            contents[messageId] = { error: 'Failed to fetch message' };
          }
        } catch (error) {
          console.error(`Error fetching message ${messageId}:`, error);
          contents[messageId] = { error: 'Error fetching message' };
        }
      });
      
      // Wait for all fetches to complete
      await Promise.all(fetchPromises);
      
      setMessageContents(contents);
    } catch (error) {
      console.error('Error fetching message contents:', error);
    } finally {
      setLoadingMessages(false);
    }
  };

  if (!topic) {
    return null;
  }

  const handleTabChange = (tab) => {
    setActiveTab(tab);
  };

  // Function to handle generating insights
  const handleGenerateInsights = async (e) => {
    // Ensure the event doesn't bubble up or trigger other actions
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    
    if (onGenerateInsights) {
      try {
        // Add a visual feedback class to indicate the button is active
        const button = e?.target?.closest('.generate-insights-button');
        if (button) {
          button.classList.add('button-processing');
          button.disabled = true;
        }
        
        // Call the generate insights function
        const result = await onGenerateInsights();
        
        // If successful, switch to the insights tab
        if (result && result.topics && result.topics.length > 0) {
          setActiveTab('insights');
        }
      } catch (error) {
        console.error('Error generating insights:', error);
      } finally {
        // Remove the visual feedback
        const button = e?.target?.closest('.generate-insights-button');
        if (button) {
          button.classList.remove('button-processing');
          button.disabled = false;
        }
      }
    }
  };

  return (
    <div className="topic-details">
      <div className="topic-details-header">
        <h2 className="topic-details-title">{topic.topic}</h2>
        <div className="topic-meta">
          {topic.metatopic && (
            <span className="topic-metatopic">{topic.metatopic}</span>
          )}
          <div className="importance-indicator">
            <span className="importance-text">Importance:</span>
            <span 
              className="importance-value"
              style={{ 
                backgroundColor: getImportanceColor(topic.importance) 
              }}
            >
              {topic.importance}/10
            </span>
          </div>
        </div>
      </div>
      
      <div className="topic-tabs">
        <button 
          className={`tab-button ${activeTab === 'messages' ? 'active' : ''}`}
          onClick={() => handleTabChange('messages')}
        >
          Original Messages
        </button>
        <button 
          className={`tab-button ${activeTab === 'insights' ? 'active' : ''}`}
          onClick={() => handleTabChange('insights')}
          disabled={!hasInsights && !onGenerateInsights}
        >
          Insights & Analysis
        </button>
        <button 
          className="tab-button coming-soon"
          title="Coming soon!"
          disabled={true}
        >
          Execution
        </button>
      </div>
      
      <div className="topic-content">
        {activeTab === 'messages' && (
          <div className="messages-section">
            <h3 className="content-subtitle">Original Messages</h3>
            {topic.message_ids && topic.message_ids.length > 0 ? (
              <>
                {loadingMessages ? (
                  <div className="messages-loading">Loading message contents...</div>
                ) : (
                  <div className="message-list">
                    {topic.message_ids.map((messageId, idx) => {
                      const messageContent = messageContents[messageId];
                      
                      return (
                        <div key={idx} className="message-item">
                          <div className="message-header">
                            <span className="message-source">
                              Source: {messageContent?.source || 'Unknown'}
                            </span>
                            {messageContent?.date && (
                              <span className="message-date">
                                {new Date(messageContent.date).toLocaleString()}
                              </span>
                            )}
                          </div>
                          <div className="message-text"
                            dangerouslySetInnerHTML={{
                              __html: messageContent?.content 
                                ? formatMessageText(messageContent.content)
                                : (messageContent?.error
                                  ? `Error: ${messageContent.error}`
                                  : 'Fetching message content...')
                            }}
                          />
                        </div>
                      );
                    })}
                  </div>
                )}
                
                {onGenerateInsights && (
                  <div className="insight-action-container">
                    <button className="generate-insights-button" onClick={handleGenerateInsights}>
                      <span className="button-icon">✨</span>
                      Discover actionable insights
                    </button>
                  </div>
                )}
              </>
            ) : (
              <p className="no-content">No original messages available for this topic.</p>
            )}
          </div>
        )}
        
        {activeTab === 'insights' && (
          <div className="insights-section">
            <h3 className="content-subtitle">Insights & Analysis</h3>
            {hasInsights && topic.insights ? (
              <div className="insights-content">
                {/* Analysis Summary and Stance */}
                {!isEmpty(topic.insights.analysis_summary) && (
                  <div className="insight-block insight-summary">
                    <h4 className="insight-title">Analysis Summary</h4>
                    <p className="insight-text">{topic.insights.analysis_summary}</p>
                    
                    {!isEmpty(topic.insights.stance) && (
                      <div className="stance-container">
                        <span className="stance-label">Stance:</span>
                        <span className={getStanceBadge(topic.insights.stance).className}>
                          {getStanceBadge(topic.insights.stance).label}
                        </span>
                      </div>
                    )}
                  </div>
                )}
                
                {/* Rationales - only show non-empty sections */}
                <div className="rationales-container">
                  {!isEmpty(topic.insights.rationale_long) && (
                    <div className="insight-block rationale-block rationale-long">
                      <h4 className="insight-title">Long Thesis</h4>
                      <p className="insight-text">{topic.insights.rationale_long}</p>
                    </div>
                  )}
                  
                  {!isEmpty(topic.insights.rationale_short) && (
                    <div className="insight-block rationale-block rationale-short">
                      <h4 className="insight-title">Short Thesis</h4>
                      <p className="insight-text">{topic.insights.rationale_short}</p>
                    </div>
                  )}
                  
                  {!isEmpty(topic.insights.rationale_neutral) && (
                    <div className="insight-block rationale-block rationale-neutral">
                      <h4 className="insight-title">Neutral Assessment</h4>
                      <p className="insight-text">{topic.insights.rationale_neutral}</p>
                    </div>
                  )}
                </div>
                
                {/* Risks and Watchouts */}
                {!isEmpty(topic.insights.risks_and_watchouts) && (
                  <div className="insight-block risks-block">
                    <h4 className="insight-title">Risks & Watchouts</h4>
                    <ul className="risks-list">
                      {topic.insights.risks_and_watchouts.map((risk, idx) => (
                        <li key={idx} className="risk-item">{risk}</li>
                      ))}
                    </ul>
                  </div>
                )}
                
                {/* Key Questions */}
                {!isEmpty(topic.insights.key_questions_for_user) && (
                  <div className="insight-block questions-block">
                    <h4 className="insight-title">Key Questions for Research</h4>
                    <ul className="questions-list">
                      {topic.insights.key_questions_for_user.map((question, idx) => (
                        <li key={idx} className="question-item">{question}</li>
                      ))}
                    </ul>
                  </div>
                )}
                
                {/* Suggested Instruments - Long */}
                {!isEmpty(topic.insights.suggested_instruments_long) && (
                  <div className="insight-block instruments-block long-instruments">
                    <h4 className="insight-title">Long Execution Options</h4>
                    <div className="instruments-grid">
                      {topic.insights.suggested_instruments_long.map((instrument, idx) => (
                        <div key={idx} className="instrument-card">
                          <h5 className="instrument-name">{instrument.instrument}</h5>
                          <p className="instrument-rationale">{instrument.rationale}</p>
                          <span className="instrument-type">{instrument.type}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Suggested Instruments - Short */}
                {!isEmpty(topic.insights.suggested_instruments_short) && (
                  <div className="insight-block instruments-block short-instruments">
                    <h4 className="insight-title">Short Execution Options</h4>
                    <div className="instruments-grid">
                      {topic.insights.suggested_instruments_short.map((instrument, idx) => (
                        <div key={idx} className="instrument-card">
                          <h5 className="instrument-name">{instrument.instrument}</h5>
                          <p className="instrument-rationale">{instrument.rationale}</p>
                          <span className="instrument-type">{instrument.type}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Useful Resources */}
                {!isEmpty(topic.insights.useful_resources) && (
                  <div className="insight-block resources-block">
                    <h4 className="insight-title">Useful Resources</h4>
                    <div className="resources-list">
                      {topic.insights.useful_resources.map((resource, idx) => (
                        <div key={idx} className="resource-item">
                          <a href={resource.url} target="_blank" rel="noopener noreferrer" className="resource-link">
                            {resource.url.replace(/^https?:\/\/(www\.)?/, '').split('/')[0]}
                          </a>
                          <p className="resource-description">{resource.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <p className="no-content">No insights available for this topic yet.</p>
            )}
            
            {/* Duplicate the "Discover actionable insights" button on the Insights tab */}
            {onGenerateInsights && !hasInsights && (
              <div className="insight-action-container">
                <button className="generate-insights-button" onClick={handleGenerateInsights}>
                  <span className="button-icon">✨</span>
                  Discover actionable insights
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
});

// Helper function to get color based on importance
function getImportanceColor(importance) {
  if (importance >= 8) return '#ef4444'; // High importance - red
  if (importance >= 6) return '#f97316'; // Medium-high importance - orange
  if (importance >= 4) return '#eab308'; // Medium importance - yellow
  return '#22c55e'; // Low importance - green
}

export default TopicDetails; 