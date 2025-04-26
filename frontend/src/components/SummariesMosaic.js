import React, { useMemo } from 'react';
import './SummariesMosaic.css';

const SummariesMosaic = ({ topics, onSelectTopic, selectedTopicId, showInsights = false }) => {
  // Map metatopics to predefined colors
  const getMetatopicColor = (metatopic) => {
    const metatopicLower = (metatopic || '').toLowerCase();
    
    if (metatopicLower.includes('crypto')) return 'var(--color-crypto)';
    if (metatopicLower.includes('financ') || metatopicLower.includes('econom')) return 'var(--color-finance)';
    if (metatopicLower.includes('tech')) return 'var(--color-technology)';
    if (metatopicLower.includes('politic')) return 'var(--color-politics)';
    if (metatopicLower.includes('commodit') || metatopicLower.includes('energy')) return 'var(--color-commodities)';
    if (metatopicLower.includes('general')) return 'var(--color-general)';
    
    return 'var(--color-other)';
  };

  // Calculate color opacity based on importance
  const getImportanceOpacity = (importance) => {
    return Math.max(0.5, Math.min(1.0, importance / 10));
  };

  // Function to determine tile sizes based on content and importance
  const getTileSize = (topic, index, totalTopics) => {
    const summary = topic.summary || '';
    const importance = topic.importance || 5;
    const textLength = summary.length;
    
    // Create pseudorandom but deterministic variation based on index
    const pseudoRandom = ((index * 13) % 17) / 17;
    
    // Consider text length, importance, and deterministic randomness
    const sizeScore = (textLength / 200) + (importance / 10) * 2 + pseudoRandom * 2;
    
    // Need more small tiles than large ones for better packing
    if (sizeScore > 4.5) return { width: 3, height: 2 }; // large rectangle: 3x2
    if (sizeScore > 3.5) return { width: 2, height: 2 }; // medium square: 2x2
    if (sizeScore > 2.5) return { width: 2, height: 1 }; // wide rectangle: 2x1
    if (sizeScore > 1.5) return { width: 1, height: 2 }; // tall rectangle: 1x2
    return { width: 1, height: 1 };                      // small square: 1x1
  };

  // Apply bin packing algorithm to positions - moved before the conditional return
  const packedTiles = useMemo(() => {
    // Return empty array if no topics to avoid processing
    if (!topics || topics.length === 0) return [];
    
    // Create a grid (default 12 columns for desktop)
    const grid = {
      columns: 12,
      cells: [] // Will track which cells are filled
    };
    
    // Initialize grid cells as all empty (false)
    for (let i = 0; i < grid.columns * 36; i++) { // Allow up to 36 rows
      grid.cells.push(false);
    }
    
    // Function to check if a position is available
    const isPositionAvailable = (col, row, width, height) => {
      // Check if outside the grid boundaries
      if (col + width > grid.columns || row < 0) return false;
      
      // Check each cell that would be occupied
      for (let c = 0; c < width; c++) {
        for (let r = 0; r < height; r++) {
          const cellIndex = (row + r) * grid.columns + (col + c);
          // If cell is already occupied or outside bounds, position is not available
          if (cellIndex >= grid.cells.length || grid.cells[cellIndex]) {
            return false;
          }
        }
      }
      
      return true;
    };
    
    // Function to mark cells as occupied
    const occupyPosition = (col, row, width, height) => {
      for (let c = 0; c < width; c++) {
        for (let r = 0; r < height; r++) {
          const cellIndex = (row + r) * grid.columns + (col + c);
          grid.cells[cellIndex] = true;
        }
      }
    };
    
    // Function to find the next available position for a tile
    const findPosition = (width, height) => {
      // Scan the grid from top to bottom, left to right
      for (let row = 0; row < 36; row++) { // Limit to 36 rows max
        for (let col = 0; col < grid.columns; col++) {
          if (isPositionAvailable(col, row, width, height)) {
            return { col, row };
          }
        }
      }
      
      // If no position is found (shouldn't happen with 36 rows, but just in case)
      return { col: 0, row: 0 };
    };
    
    // Place each tile using the bin packing algorithm
    return topics.map((topic, index) => {
      // Determine tile size
      const { width, height } = getTileSize(topic, index, topics.length);
      
      // Find next available position
      const { col, row } = findPosition(width, height);
      
      // Mark cells as occupied
      occupyPosition(col, row, width, height);
      
      // Return topic with positioned tile information
      return {
        topic,
        index,
        gridColumnStart: col + 1, // Grid columns/rows are 1-based
        gridColumnEnd: col + width + 1,
        gridRowStart: row + 1,
        gridRowEnd: row + height + 1,
        width,
        height
      };
    });
  }, [topics]);

  const getMaxRow = () => {
    if (packedTiles.length === 0) return 0;
    
    let maxRow = 0;
    packedTiles.forEach(tile => {
      maxRow = Math.max(maxRow, tile.gridRowEnd - 1);
    });
    return maxRow;
  };

  // Get class name based on tile dimensions
  const getTileClassName = (width, height) => {
    if (width === 3 && height === 2) return 'large-rectangle';
    if (width === 2 && height === 2) return 'medium-square';
    if (width === 2 && height === 1) return 'wide-rectangle';
    if (width === 1 && height === 2) return 'tall-rectangle';
    return 'small-square';
  };

  // Get appropriate summary length based on tile size
  const getSummaryLength = (width, height) => {
    const area = width * height;
    if (area >= 6) return 250; // Large tiles
    if (area >= 4) return 200; // Medium tiles
    if (area >= 2) return 120; // Small-medium tiles
    return 80; // Smallest tiles
  };

  // Now add the conditional return after all hooks are defined
  if (!topics || topics.length === 0) {
    return (
      <div className="mosaic-empty">
        <p>No topics available. Run an analysis to see insights.</p>
      </div>
    );
  }

  return (
    <div className="summaries-mosaic">
      <div 
        className="mosaic-container" 
        style={{ 
          gridTemplateRows: `repeat(${getMaxRow()}, 70px)`,
          gridTemplateColumns: 'repeat(12, 1fr)'
        }}
      >
        {packedTiles.map(({ topic, index, gridColumnStart, gridColumnEnd, gridRowStart, gridRowEnd, width, height }) => {
          const baseColor = getMetatopicColor(topic.metatopic);
          const opacity = getImportanceOpacity(topic.importance || 5);
          const tileClassName = getTileClassName(width, height);
          
          return (
            <div 
              key={index}
              className={`mosaic-tile ${tileClassName} ${selectedTopicId === index ? 'selected' : ''}`}
              style={{ 
                backgroundColor: baseColor,
                opacity: opacity,
                gridColumnStart,
                gridColumnEnd,
                gridRowStart,
                gridRowEnd
              }}
              onClick={() => onSelectTopic(index)}
            >
              <div className="tile-content">
                <div className="tile-header">
                  <h4 className="tile-title">{topic.topic}</h4>
                  {topic.metatopic && (
                    <span className="tile-metatopic">{topic.metatopic}</span>
                  )}
                </div>
                
                {showInsights && topic.insights ? (
                  <div className="tile-insights-indicator">Has insights</div>
                ) : (
                  <p className="tile-summary">{truncateSummary(topic.summary, getSummaryLength(width, height))}</p>
                )}
                
                <div className="tile-footer">
                  <span className="importance-badge">
                    {topic.importance}/10
                  </span>
                  <span className="message-count">
                    {topic.message_ids?.length || 0} messages
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// Helper function to truncate summary
function truncateSummary(summary, maxLength) {
  if (!summary) return '';
  if (summary.length <= maxLength) return summary;
  return summary.substring(0, maxLength) + '...';
}

export default SummariesMosaic; 