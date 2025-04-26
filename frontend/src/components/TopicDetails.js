import React, { useState } from 'react';
import './TopicDetails.css';

const TopicDetails = ({ topic, hasInsights = false }) => {
  const [activeTab, setActiveTab] = useState('messages');

  if (!topic) {
    return null;
  }

  const handleTabChange = (tab) => {
    setActiveTab(tab);
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
          disabled={!hasInsights || !topic.insights}
        >
          Insights & Analysis
        </button>
        <button 
          className={`tab-button ${activeTab === 'execution' ? 'active' : ''}`}
          onClick={() => handleTabChange('execution')}
          disabled={!hasInsights || !topic.insights}
        >
          Execution
        </button>
      </div>
      
      <div className="topic-content">
        {activeTab === 'messages' && (
          <div className="messages-section">
            <h3 className="content-subtitle">Original Messages</h3>
            {topic.message_ids && topic.message_ids.length > 0 ? (
              <div className="message-list">
                {topic.message_ids.map((messageId, idx) => (
                  <div key={idx} className="message-item">
                    <div className="message-header">
                      <span className="message-id">Message #{messageId}</span>
                      <span className="message-channel">Channel: Unknown</span>
                    </div>
                    <p className="message-text">
                      Message content will be displayed here when available.
                    </p>
                  </div>
                ))}
              </div>
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
                <div className="insight-block">
                  <h4 className="insight-title">General</h4>
                  <p className="insight-text">{topic.insights.general || 'No general insights available.'}</p>
                </div>
                
                <div className="insight-block">
                  <h4 className="insight-title">Long-term Perspective</h4>
                  <p className="insight-text">{topic.insights.long || 'No long-term insights available.'}</p>
                </div>
                
                <div className="insight-block">
                  <h4 className="insight-title">Short-term Perspective</h4>
                  <p className="insight-text">{topic.insights.short || 'No short-term insights available.'}</p>
                </div>
                
                <div className="insight-block">
                  <h4 className="insight-title">Neutral Perspective</h4>
                  <p className="insight-text">{topic.insights.neutral || 'No neutral insights available.'}</p>
                </div>
              </div>
            ) : (
              <p className="no-content">
                {hasInsights 
                  ? 'No insights available for this topic.' 
                  : 'Generate insights first to see analysis for this topic.'}
              </p>
            )}
          </div>
        )}
        
        {activeTab === 'execution' && (
          <div className="execution-section">
            <h3 className="content-subtitle">Execution Options</h3>
            
            {hasInsights && topic.insights && topic.insights.exec_options_long && topic.insights.exec_options_long.length > 0 ? (
              <div className="execution-options">
                {topic.insights.exec_options_long.map((option, idx) => (
                  <div key={idx} className="execution-option">
                    <h4 className="option-title">{option.text}</h4>
                    <p className="option-description">{option.description}</p>
                    <span className="option-type">{option.type}</span>
                    {/* Execution button would go here in the future */}
                  </div>
                ))}
              </div>
            ) : (
              <p className="no-content">
                {hasInsights 
                  ? 'No execution options available for this topic.' 
                  : 'Generate insights first to see execution options.'}
              </p>
            )}
            
            <p className="execution-placeholder">
              This section will allow users to take action based on insights.
              (Feature coming soon)
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

// Helper function to get color based on importance
function getImportanceColor(importance) {
  if (importance >= 8) return '#ef4444'; // High importance - red
  if (importance >= 6) return '#f97316'; // Medium-high importance - orange
  if (importance >= 4) return '#eab308'; // Medium importance - yellow
  return '#22c55e'; // Low importance - green
}

export default TopicDetails; 