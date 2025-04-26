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

  // Get importance-based class
  const getImportanceClass = (importance) => {
    if (importance >= 9) return 'importance-very-highlighted';
    if (importance >= 7) return 'importance-highlighted';
    if (importance >= 5) return 'importance-light';
    return 'importance-neutral';
  };

  // Get initial size based on content, importance and randomness
  const getInitialTileSize = (topic, index, totalTopics) => {
    const summary = topic.summary || '';
    const importance = topic.importance || 5;
    
    // Create multiple pseudorandom values for more randomness
    // These are deterministic but create more varied patterns
    const seed1 = (index * 17 + 13) % 29;
    const seed2 = (index * 23 + 7) % 31;
    const seed3 = (index * 19 + 11) % 37;
    
    const random1 = seed1 / 29; // 0-1 range
    const random2 = seed2 / 31; // 0-1 range
    const random3 = seed3 / 37; // 0-1 range
    
    // Combined random factor (very varied)
    const randomFactor = (random1 + random2 + random3) / 3;
    
    // Give more weight to importance for sizing
    // Scale importance to have stronger effect (0-20 range instead of 0-10)
    const importanceScore = Math.pow(importance / 10, 1.3) * 2;
    
    // Content length still matters but with less weight
    const contentScore = Math.min(1, summary.length / 500);
    
    // Combine factors with randomness having significant weight
    // This makes sizing more random while still respecting importance
    const sizeScore = (importanceScore * 0.5) + (contentScore * 0.2) + (randomFactor * 2.5);
    
    // Map to tile sizes with strong random component
    // Include all allowed sizes with varying probabilities
    
    // Larger tiles (rarer, but more likely for important news)
    if (sizeScore > 3.2 && random1 > 0.7) return { width: 3, height: 3 }; // 3w×3h (rarest)
    if (sizeScore > 2.8 && random2 > 0.6) return { width: 4, height: 2 }; // 4w×2h (rare)
    if (sizeScore > 2.5 && random3 > 0.5) return { width: 3, height: 2 }; // 3w×2h (uncommon)
    
    // Medium tiles (moderate frequency)
    if (sizeScore > 1.8 && random1 > 0.4) return { width: 3, height: 1 }; // 3w×1h
    if (sizeScore > 1.5 && random2 > 0.3) return { width: 2, height: 2 }; // 2w×2h
    if (sizeScore > 1.2 && random3 > 0.3) return { width: 1, height: 3 }; // 1w×3h
    
    // Smaller tiles (common)
    if (sizeScore > 0.8 && random1 > 0.2) return { width: 2, height: 1 }; // 2w×1h
    if (sizeScore > 0.5 && random2 > 0.2) return { width: 1, height: 2 }; // 1w×2h
    
    // Default size (most common)
    return { width: 1, height: 1 }; // 1w×1h
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
    
    // Function to check if an area is free
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
    
    // Function to find the first position where a tile fits (no intersections)
    const findFirstFit = (width, height) => {
      for (let row = 0; row < grid.height; row++) {
        for (let col = 0; col < grid.width; col++) {
          if (isAreaFree(row, col, width, height)) {
            return { row, col, width, height };
          }
        }
      }
      
      // Fallback: If all positions are filled, create a new row at the end
      return { row: grid.height - 1, col: 0, width: 1, height: 1 };
    };
    
    // Place each tile with optimized sizing
    const positionedTiles = [];
    
    // Process tiles in order of importance, then size
    const sortedTopics = [...topics].map((topic, index) => ({ 
      topic, 
      index,
      importance: topic.importance || 5
    }))
    .sort((a, b) => b.importance - a.importance); // Sort by importance descending
    
    // First placement pass - ensure no intersections (absolute priority)
    sortedTopics.forEach(({ topic, index, importance }) => {
      // Get initial ideal size based on topic properties
      const { width, height } = getInitialTileSize(topic, index, topics.length);
      
      // Find first valid position with potentially reduced size
      let finalWidth = width;
      let finalHeight = height;
      
      // Try original size first
      let position = findFirstFit(finalWidth, finalHeight);
      
      // If tile doesn't fit with original size, try smaller sizes
      if (!position) {
        // Try different size variations until one fits
        const sizeVariations = [
          { width: Math.min(finalWidth, MAX_WIDTH), height: finalHeight },
          { width: finalWidth, height: Math.max(1, finalHeight - 1) },
          { width: Math.max(1, finalWidth - 1), height: finalHeight },
          { width: Math.max(1, finalWidth - 1), height: Math.max(1, finalHeight - 1) },
          { width: 2, height: 1 },
          { width: 1, height: 2 },
          { width: 1, height: 1 } // Minimum size as last resort
        ];
        
        for (const size of sizeVariations) {
          position = findFirstFit(size.width, size.height);
          if (position) {
            finalWidth = size.width;
            finalHeight = size.height;
            break;
          }
        }
        
        // If still no fit, use 1x1 at the end
        if (!position) {
          position = findFirstFit(1, 1);
          finalWidth = 1;
          finalHeight = 1;
        }
      }
      
      // Store positioned tile
      const newTile = {
        topic,
        index,
        row: position.row,
        col: position.col,
        width: finalWidth,
        height: finalHeight
      };
      
      positionedTiles.push(newTile);
      
      // Mark cells as occupied
      occupyArea(position.row, position.col, finalWidth, finalHeight, index);
    });
    
    // Find the maximum used row
    let maxRow = 0;
    for (let row = 0; row < grid.height; row++) {
      for (let col = 0; col < grid.width; col++) {
        if (grid.cells[row][col] !== null && row > maxRow) {
          maxRow = row;
        }
      }
    }
    
    // Determine the actual max row (including tile heights)
    let actualMaxRow = maxRow;
    for (const tile of positionedTiles) {
      const tileBottomRow = tile.row + tile.height - 1;
      if (tileBottomRow > actualMaxRow) {
        actualMaxRow = tileBottomRow;
      }
    }
    
    // Second priority: Fill empty spaces
    // Identify and fill gaps
    for (let row = 0; row <= actualMaxRow; row++) {
      for (let col = 0; col < grid.width; col++) {
        if (grid.cells[row][col] === null) {
          // Found a gap
          
          // Try to find the largest possible expansion for this gap
          let maxWidth = 1;
          let maxHeight = 1;
          
          // Check how far to the right we can expand
          while (col + maxWidth < grid.width && grid.cells[row][col + maxWidth] === null) {
            maxWidth++;
          }
          
          // Check how far down we can expand
          let canExpandDown = true;
          let currentHeight = 1;
          
          while (canExpandDown && row + currentHeight <= actualMaxRow) {
            // Check the entire row at this height
            for (let checkCol = col; checkCol < col + maxWidth; checkCol++) {
              if (checkCol >= grid.width || grid.cells[row + currentHeight][checkCol] !== null) {
                canExpandDown = false;
                break;
              }
            }
            
            if (canExpandDown) {
              currentHeight++;
              maxHeight = currentHeight;
            }
          }
          
          // Find the nearest tile that can be expanded
          const adjacentPositions = [
            { direction: 'up', r: row - 1, c: col },
            { direction: 'left', r: row, c: col - 1 },
            { direction: 'right', r: row, c: col + maxWidth },
            { direction: 'down', r: row + maxHeight, c: col }
          ];
          
          let expanded = false;
          
          for (const pos of adjacentPositions) {
            if (pos.r < 0 || pos.c < 0 || pos.r >= grid.height || pos.c >= grid.width) continue;
            
            const adjacentTileIndex = grid.cells[pos.r][pos.c];
            if (adjacentTileIndex === null) continue;
            
            const adjacentTile = positionedTiles.find(t => t.index === adjacentTileIndex);
            if (!adjacentTile) continue;
            
            // Try to expand this tile to fill the gap
            if (pos.direction === 'up' && adjacentTile.col <= col && adjacentTile.col + adjacentTile.width > col) {
              const expansionWidth = Math.min(maxWidth, adjacentTile.width);
              
              // Check if we can expand down without collisions
              let expansionHeight = 1;
              let canExpand = true;
              
              for (let c = adjacentTile.col; c < adjacentTile.col + adjacentTile.width; c++) {
                if (c >= grid.width || (grid.cells[row][c] !== null && grid.cells[row][c] !== adjacentTileIndex)) {
                  canExpand = false;
                  break;
                }
              }
              
              if (canExpand) {
                const originalHeight = adjacentTile.height;
                adjacentTile.height += expansionHeight;
                
                // Mark the new area as occupied
                for (let r = row; r < row + expansionHeight; r++) {
                  for (let c = adjacentTile.col; c < adjacentTile.col + adjacentTile.width; c++) {
                    grid.cells[r][c] = adjacentTileIndex;
                  }
                }
                
                expanded = true;
                break;
              }
            }
            else if (pos.direction === 'left' && adjacentTile.row <= row && adjacentTile.row + adjacentTile.height > row) {
              const expansionHeight = Math.min(maxHeight, adjacentTile.height);
              
              // Check if we can expand right without collisions
              let expansionWidth = 1;
              let canExpand = true;
              
              for (let r = adjacentTile.row; r < adjacentTile.row + adjacentTile.height; r++) {
                if (r >= grid.height || (grid.cells[r][col] !== null && grid.cells[r][col] !== adjacentTileIndex)) {
                  canExpand = false;
              break;
            }
              }
              
              if (canExpand) {
                const originalWidth = adjacentTile.width;
                adjacentTile.width += expansionWidth;
                
                // Mark the new area as occupied
                for (let r = adjacentTile.row; r < adjacentTile.row + adjacentTile.height; r++) {
                  for (let c = col; c < col + expansionWidth; c++) {
                    grid.cells[r][c] = adjacentTileIndex;
                  }
                }
                
                expanded = true;
                break;
              }
            }
          }
          
          // If no expansion was possible, create a new small tile for this gap
          if (!expanded && maxWidth > 0 && maxHeight > 0) {
            // Find a tile we can clone
            let newTileIndex = sortedTopics.length > 0 ? sortedTopics[0].index : 0;
            const cloneSource = positionedTiles.find(t => t.index === newTileIndex);
            
            // Create a new tile filling the gap
            if (cloneSource) {
              const gapTile = {
                topic: cloneSource.topic,
                index: cloneSource.index,
                row: row,
                col: col,
                width: maxWidth,
                height: maxHeight
              };
              
              // Add the new tile to positioned tiles
              positionedTiles.push(gapTile);
              
              // Mark the gap area as occupied
              for (let r = row; r < row + maxHeight; r++) {
                for (let c = col; c < col + maxWidth; c++) {
                  grid.cells[r][c] = gapTile.index;
                }
              }
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
    
    return { tiles, maxRow: actualMaxRow + 1 }; // +1 because grid is 1-indexed
  }, [topics]);

  // Get tile class name based on dimensions
  const getTileClassName = (width, height) => {
    if (width === 3 && height === 3) return 'xl-square';
    if (width === 4 && height === 2) return 'wide-xl-rectangle';
    if (width === 3 && height === 2) return 'large-rectangle';
    if (width === 2 && height === 2) return 'medium-square';
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
    if (area >= 6) return 220; // 3×2
    if (area === 4) return 180; // 2×2
    if (area === 3) return 150; // 3×1, 1×3
    if (area === 2) return 100; // 2×1, 1×2
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
          gridTemplateRows: `repeat(${packedLayout.maxRow}, minmax(98px, auto))`,
          gridTemplateColumns: `repeat(5, 1fr)` // Default 5 columns
        }}
      >
        {packedLayout.tiles.map(({ topic, index, gridColumnStart, gridColumnEnd, gridRowStart, gridRowEnd, width, height }) => {
          const baseColor = getMetatopicColor(topic.metatopic);
          const importanceClass = getImportanceClass(topic.importance || 5);
          const tileClassName = getTileClassName(width, height);
          
          return (
            <div 
              key={index}
              className={`mosaic-tile ${tileClassName} ${importanceClass} ${selectedTopicId === index ? 'selected' : ''}`}
              style={{ 
                backgroundColor: baseColor,
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