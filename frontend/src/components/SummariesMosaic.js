import React, { useMemo, useState } from 'react';
import './SummariesMosaic.css';

const SummariesMosaic = ({ topics, onSelectTopic, selectedTopicId, showInsights = false, onScrollToMessages }) => {
  // State to track which tooltips have been disabled by the user
  const [hideImportanceTooltip, setHideImportanceTooltip] = useState(false);
  const [hideMessageCountTooltip, setHideMessageCountTooltip] = useState(false);
  
  // Generate stable random values for each topic that won't change on re-renders
  const topicsWithRandomValues = useMemo(() => {
    return topics.map((topic, index) => ({
      ...topic,
      // These random values will be stable for each topic based on its index
      _randomValue1: (Math.sin(index * 7919) + 1) / 2, // Prime number multiplication for better distribution
      _randomValue2: (Math.cos(index * 7907) + 1) / 2,
      _randomValue3: (Math.sin((index + 1) * 7901) + 1) / 2,
      // Random value for sorting that's stable for the topic
      _sortValue: (Math.sin(index * 7883) + 1) / 2
    }));
  }, [topics]);
  
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

  // Get initial size based on content and stable pseudo-random values
  const getInitialTileSize = (topic) => {
    const summary = topic.summary || '';
    
    // Use the stable random values from the topic
    const random1 = topic._randomValue1;
    const random2 = topic._randomValue2;
    const random3 = topic._randomValue3;
    
    // Combined random factor (very varied)
    const randomFactor = (random1 + random2 + random3) / 3;
    
    // Increase probability of vertical rectangles
    const verticalBias = random3 > 0.5 ? 1.5 : 1.0; // 50% chance of vertical bias
    
    // Content length still matters
    const contentScore = Math.min(1, summary.length / 500);
    
    // Combine factors with pure randomness having the most weight
    const sizeScore = (contentScore * 0.2) + (randomFactor * 3.0);
    
    // Map to tile sizes with strong random component
    // Include all allowed sizes with varying probabilities
    
    // Larger tiles (rarer)
    if (sizeScore > 3.2 && random1 > 0.7) return { width: 3, height: 3 }; // 3w×3h (very rare)
    if (sizeScore > 2.8 && random2 > 0.65) return { width: 4, height: 2 }; // 4w×2h (rare)
    if (sizeScore > 2.5 && random3 > 0.6) return { width: 3, height: 2 }; // 3w×2h (uncommon)
    
    // Medium tiles (moderate frequency)
    if (sizeScore > 1.8 && random1 > 0.45) return { width: 3, height: 1 }; // 3w×1h
    if (sizeScore > 1.5 && random2 > 0.4) return { width: 2, height: 2 }; // 2w×2h
    
    // More vertical tiles 
    if (sizeScore > 1.0 && random3 > 0.4 * verticalBias) return { width: 1, height: 3 }; // 1w×3h (increased probability)
    
    // Smaller tiles
    if (sizeScore > 0.7 && random1 > 0.3) return { width: 2, height: 1 }; // 2w×1h
    if (sizeScore > 0.4 && random2 > 0.3 * verticalBias) return { width: 1, height: 2 }; // 1w×2h (increased probability)
    
    // Default size
    return { width: 1, height: 1 }; // 1w×1h
  };

  // Calculate layout with perfect packing
  const packedLayout = useMemo(() => {
    // Return empty array if no topics
    if (!topicsWithRandomValues || topicsWithRandomValues.length === 0) return { tiles: [], maxRow: 0 };
    
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
    
    // Process tiles in stably randomized order
    const randomizedTopics = [...topicsWithRandomValues]
      .sort((a, b) => a._sortValue - b._sortValue); // Sort by stable random value
    
    // First placement pass - ensure no intersections (absolute priority)
    randomizedTopics.forEach((topic, index) => {
      // Get initial ideal size based on topic properties with stable randomness
      const { width, height } = getInitialTileSize(topic);
      
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
            // Find a tile we can clone - use a deterministic approach
            const gapFillingSeed = (row * 997 + col * 1009) % randomizedTopics.length; // Use prime numbers for good distribution
            const cloneSource = randomizedTopics[gapFillingSeed];
            
            // Create a new tile filling the gap
            if (cloneSource) {
              // Generate a unique index for gap tiles by adding an offset
              // This ensures gap tiles have unique indexes different from regular tiles
              const gapTileIndex = `gap_${row}_${col}`;
              
              const gapTile = {
                topic: cloneSource,
                index: gapTileIndex, // Use the unique gap tile index
                originalIndex: gapFillingSeed, // Store original index for data reference
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
                  grid.cells[r][c] = gapTileIndex;
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
  }, [topicsWithRandomValues]);

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

  // Add a memoized function to get CSS grid styles for positioning tiles
  const renderedLayout = useMemo(() => {
    // If layout isn't calculated yet, return empty
    if (!packedLayout.tiles || packedLayout.tiles.length === 0) {
      return [];
    }

    // Map each tile to include its CSS grid position styles
    return packedLayout.tiles.map(tile => ({
      ...tile,
      style: {
        backgroundColor: getMetatopicColor(tile.topic.metatopic),
        gridColumnStart: tile.gridColumnStart,
        gridColumnEnd: tile.gridColumnEnd,
        gridRowStart: tile.gridRowStart,
        gridRowEnd: tile.gridRowEnd
      },
      className: `mosaic-tile ${getTileClassName(tile.width, tile.height)} ${getImportanceClass(tile.topic.importance || 5)} ${selectedTopicId === (typeof tile.index === 'string' && tile.index.startsWith('gap_') ? tile.topic.originalIndex || 0 : tile.index) ? 'selected' : ''}`
    }));
  }, [packedLayout, selectedTopicId]); // Recalculate only when selectedTopicId or packedLayout changes

  // Handle the scroll to messages section
  const scrollToMessages = (e, index) => {
    // Completely stop event propagation to all parent elements
    e.preventDefault();
    e.stopPropagation();
    
    // First select the topic
    onSelectTopic(index);
    
    // Use the callback to scroll to messages section
    // This will be handled by the parent component
    setTimeout(() => {
      if (onScrollToMessages) {
        onScrollToMessages();
      }
    }, 100); // Small delay to ensure topic selection is processed
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
        {renderedLayout.map(({ topic, index, style, className, width, height }) => {
          // For gap tiles, we need to determine the actual index to use for selection
          const actualIndex = typeof index === 'string' && index.startsWith('gap_') 
            ? topic.originalIndex || parseInt(index.split('_')[2], 10) || 0
            : index;
          
          return (
            <div 
              key={index}
              className={className}
              style={style}
              onClick={() => onSelectTopic(actualIndex)}
            >
              <div className="tile-content">
                <div className="tile-header">
                  <h4 className="tile-title">{topic.topic}</h4>
                  <div className="tile-badges">
                    {topic.metatopic && (
                      <span className="tile-metatopic">{topic.metatopic}</span>
                    )}
                    {topic.hasGeneratedInsights && (
                      <span className="tile-has-insights">Insights Available</span>
                    )}
                  </div>
                </div>
                
                {showInsights && topic.insights ? (
                  <div className="tile-insights-indicator">Has insights</div>
                ) : (
                  <p 
                    className="tile-summary"
                    onClick={(e) => scrollToMessages(e, actualIndex)}  
                  >
                    {topic.summary}
                  </p>
                )}
                
                <div className="tile-footer">
                  <span className="tooltip importance-tooltip">
                    <span className="importance-badge">
                      {topic.importance}/10
                    </span>
                    {!hideImportanceTooltip && (
                      <div className="tooltip-content">
                        <p>Importance rating for this topic based on relevance and impact.</p>
                        <div className="tooltip-actions">
                          <button 
                            className="tooltip-action-btn"
                            onClick={(e) => { 
                              e.stopPropagation(); 
                              setHideImportanceTooltip(true); 
                            }}
                          >
                            Don't show anymore
                          </button>
                        </div>
                      </div>
                    )}
                  </span>
                  <span className="tooltip message-tooltip">
                    <span className="message-count">
                      {topic.message_ids?.length || 0} messages
                    </span>
                    {!hideMessageCountTooltip && (
                      <div className="tooltip-content">
                        <p>Number of messages related to this topic.</p>
                        <div className="tooltip-actions">
                          <button 
                            className="tooltip-action-btn go-to-messages"
                            onClick={(e) => scrollToMessages(e, actualIndex)}
                          >
                            Go to messages
                          </button>
                          <button 
                            className="tooltip-action-btn"
                            onClick={(e) => { 
                              e.stopPropagation(); 
                              setHideMessageCountTooltip(true); 
                            }}
                          >
                            Don't show anymore
                          </button>
                        </div>
                      </div>
                    )}
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
  // No longer needed as we're displaying the full summary with scroll
  return summary || '';
}

export default SummariesMosaic; 