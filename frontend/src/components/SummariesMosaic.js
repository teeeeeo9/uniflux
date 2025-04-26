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

  // Get initial size based on content and importance
  // This function determines which of our allowed sizes to use
  const getInitialTileSize = (topic, index) => {
    const summary = topic.summary || '';
    const importance = topic.importance || 5;
    const textLength = summary.length;
    
    // Create pseudorandom but deterministic variation
    const pseudoRandom = ((index * 13) % 17) / 17;
    
    // Combine factors to create a size score
    const sizeScore = (textLength / 200) + (importance / 10) * 2 + pseudoRandom * 2;
    
    // Map to one of our allowed sizes
    // Larger boxes - less frequent
    if (sizeScore > 5) return { width: 3, height: 3 }; // 3w×3h - largest
    if (sizeScore > 4.5) return { width: 4, height: 2 }; // 4w×2h
    if (sizeScore > 4) return { width: 3, height: 2 }; // 3w×2h
    
    // Smaller boxes - more frequent
    if (sizeScore > 3) return { width: 3, height: 1 }; // 3w×1h
    if (sizeScore > 2) return { width: 2, height: 1 }; // 2w×1h
    if (sizeScore > 1.5) return { width: 1, height: 3 }; // 1w×3h
    if (sizeScore > 1) return { width: 1, height: 2 }; // 1w×2h
    
    return { width: 1, height: 1 }; // 1w×1h - smallest
  };

  // Calculate layout with perfect packing
  const packedLayout = useMemo(() => {
    // Return empty array if no topics
    if (!topics || topics.length === 0) return { tiles: [], maxRow: 0 };
    
    // Maximum width for the grid (5 units per row)
    const MAX_WIDTH = 5;
    
    // Initialize the grid
    const grid = {
      width: MAX_WIDTH,
      height: 100, // Allow plenty of rows
      cells: [] // Will be a 2D array: grid.cells[row][col]
    };
    
    // Initialize empty grid
    for (let row = 0; row < grid.height; row++) {
      grid.cells[row] = [];
      for (let col = 0; col < grid.width; col++) {
        grid.cells[row][col] = null; // null means cell is empty
      }
    }
    
    // Function to check if a position is available
    const isAreaFree = (startRow, startCol, width, height) => {
      // Check boundaries
      if (startCol + width > grid.width || startRow + height > grid.height) {
        return false;
      }
      
      // Check if all cells are free
      for (let row = startRow; row < startRow + height; row++) {
        for (let col = startCol; col < startCol + width; col++) {
          if (grid.cells[row][col] !== null) {
            return false;
          }
        }
      }
      
      return true;
    };
    
    // Function to mark cells as occupied
    const occupyArea = (startRow, startCol, width, height, tileIndex) => {
      for (let row = startRow; row < startRow + height; row++) {
        for (let col = startCol; col < startCol + width; col++) {
          grid.cells[row][col] = tileIndex;
        }
      }
    };
    
    // Function to find the next available position
    const findNextPosition = (width, height) => {
      for (let row = 0; row < grid.height; row++) {
        for (let col = 0; col < grid.width; col++) {
          if (isAreaFree(row, col, width, height)) {
            return { row, col };
          }
        }
      }
      
      // Fallback (shouldn't happen with a large grid)
      return { row: 0, col: 0 };
    };
    
    // Place each tile and track positions
    const positionedTiles = [];
    
    topics.forEach((topic, index) => {
      // Get initial ideal size
      const { width, height } = getInitialTileSize(topic, index);
      
      // Find position
      const { row, col } = findNextPosition(width, height);
      
      // Store positioned tile
      positionedTiles.push({
        topic,
        index,
        row,
        col,
        width,
        height
      });
      
      // Mark cells as occupied
      occupyArea(row, col, width, height, index);
    });
    
    // Find highest used row
    let maxRow = 0;
    for (let row = 0; row < grid.height; row++) {
      for (let col = 0; col < grid.width; col++) {
        if (grid.cells[row][col] !== null && row > maxRow) {
          maxRow = row;
        }
      }
    }
    
    // Maximum row + the height of the tallest tile in that row
    let actualMaxRow = maxRow;
    for (const tile of positionedTiles) {
      if (tile.row <= maxRow && tile.row + tile.height > actualMaxRow) {
        actualMaxRow = tile.row + tile.height;
      }
    }
    
    // Fill any gaps by extending neighboring tiles
    for (let row = 0; row <= maxRow; row++) {
      for (let col = 0; col < grid.width; col++) {
        // If cell is empty, try to extend a neighboring tile
        if (grid.cells[row][col] === null) {
          // Try extending a tile from the left
          if (col > 0 && grid.cells[row][col - 1] !== null) {
            const tileIndex = grid.cells[row][col - 1];
            const tile = positionedTiles.find(t => t.index === tileIndex);
            
            // Check if we can extend this tile
            let canExtend = true;
            for (let r = tile.row; r < tile.row + tile.height; r++) {
              if (r >= grid.height || grid.cells[r][col] !== null) {
                canExtend = false;
                break;
              }
            }
            
            // Extend if possible
            if (canExtend) {
              tile.width += 1;
              occupyArea(tile.row, tile.col, tile.width, tile.height, tile.index);
            }
          }
          // Or try extending a tile from above
          else if (row > 0 && grid.cells[row - 1][col] !== null) {
            const tileIndex = grid.cells[row - 1][col];
            const tile = positionedTiles.find(t => t.index === tileIndex);
            
            // Check if we can extend this tile
            let canExtend = true;
            for (let c = tile.col; c < tile.col + tile.width; c++) {
              if (c >= grid.width || grid.cells[row][c] !== null) {
                canExtend = false;
                break;
              }
            }
            
            // Extend if possible
            if (canExtend) {
              tile.height += 1;
              occupyArea(tile.row, tile.col, tile.width, tile.height, tile.index);
            }
          }
        }
      }
    }
    
    // Convert positioned tiles to the format expected by the renderer
    const tiles = positionedTiles.map(tile => ({
      topic: tile.topic,
      index: tile.index,
      gridColumnStart: tile.col + 1, // Grid is 1-indexed
      gridColumnEnd: tile.col + tile.width + 1,
      gridRowStart: tile.row + 1,
      gridRowEnd: tile.row + tile.height + 1,
      width: tile.width,
      height: tile.height
    }));
    
    return { tiles, maxRow: actualMaxRow };
  }, [topics]);

  // Get tile class name based on dimensions
  const getTileClassName = (width, height) => {
    if (width === 3 && height === 3) return 'xl-square';
    if (width === 4 && height === 2) return 'wide-xl-rectangle';
    if (width === 3 && height === 2) return 'large-rectangle';
    if (width === 3 && height === 1) return 'wide-rectangle';
    if (width === 2 && height === 1) return 'medium-rectangle';
    if (width === 1 && height === 3) return 'tall-xl-rectangle';
    if (width === 1 && height === 2) return 'tall-rectangle';
    return 'small-square';
  };

  // Get appropriate summary length based on tile size
  const getSummaryLength = (width, height) => {
    const area = width * height;
    if (area >= 9) return 300; // 3×3
    if (area >= 8) return 250; // 4×2
    if (area >= 6) return 200; // 3×2
    if (area >= 3) return 150; // 3×1, 1×3
    if (area >= 2) return 100; // 2×1, 1×2
    return 70; // 1×1
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
          gridTemplateRows: `repeat(${packedLayout.maxRow}, minmax(70px, auto))`,
          gridTemplateColumns: `repeat(5, 1fr)`
        }}
      >
        {packedLayout.tiles.map(({ topic, index, gridColumnStart, gridColumnEnd, gridRowStart, gridRowEnd, width, height }) => {
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