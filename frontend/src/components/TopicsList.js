import React from 'react';
import './TopicsList.css';

const TopicsList = ({ topics, onSelectTopic, selectedTopicId }) => {
  if (!topics || topics.length === 0) {
    return (
      <div className="topics-empty">
        <p>No topics available. Run an analysis to see insights.</p>
      </div>
    );
  }

  return (
    <div className="topics-list">
      <h2 className="section-title">News Summaries</h2>
      {topics.map((topic, index) => (
        <div 
          key={index}
          className={`topic-card ${selectedTopicId === index ? 'selected' : ''}`}
          onClick={() => onSelectTopic(index)}
        >
          <div className="topic-header">
            <h3 className="topic-title">{topic.topic}</h3>
            <div className="topic-importance">
              <span className="importance-label">Importance:</span>
              <span className="importance-badge" 
                style={{ 
                  backgroundColor: getImportanceColor(topic.importance) 
                }}
              >
                {topic.importance}/10
              </span>
            </div>
          </div>
          <p className="topic-summary">{truncateSummary(topic.summary, 150)}</p>
          <div className="topic-footer">
            <span className="message-count">
              Based on {topic.message_ids?.length || 0} messages
            </span>
            <span className="view-details">View details →</span>
          </div>
        </div>
      ))}
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

// Helper function to truncate summary
function truncateSummary(summary, maxLength) {
  if (!summary) return '';
  if (summary.length <= maxLength) return summary;
  return summary.substring(0, maxLength) + '...';
}

export default TopicsList; 