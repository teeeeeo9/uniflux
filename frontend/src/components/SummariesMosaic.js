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
    
    // Function to clear an area (mark as unoccupied)
    const clearArea = (startRow, startCol, width, height) => {
      for (let row = startRow; row < startRow + height; row++) {
        for (let col = startCol; col < startCol + width; col++) {
          grid.cells[row][col] = null;
        }
      }
    };
    
    // Function to find the next available position using dynamic sizing
    const findBestPosition = (preferredWidth, preferredHeight, tileIndex) => {
      // First try with the preferred size
      for (let row = 0; row < grid.height; row++) {
        for (let col = 0; col < grid.width; col++) {
          if (isAreaFree(row, col, preferredWidth, preferredHeight)) {
            return {
              row,
              col,
              width: preferredWidth,
              height: preferredHeight,
              resized: false
            };
          }
        }
      }
      
      // If preferred size doesn't fit, try smaller variations
      const sizeVariations = [
        // Try reducing width first (for wide tiles)
        { width: Math.max(1, preferredWidth - 1), height: preferredHeight },
        // Try reducing height (for tall tiles)
        { width: preferredWidth, height: Math.max(1, preferredHeight - 1) },
        // Try reducing both 
        { width: Math.max(1, preferredWidth - 1), height: Math.max(1, preferredHeight - 1) },
        // Last resort: use smallest possible size
        { width: 1, height: 1 }
      ];
      
      // Try each size variation until one fits
      for (const variation of sizeVariations) {
        for (let row = 0; row < grid.height; row++) {
          for (let col = 0; col < grid.width; col++) {
            if (isAreaFree(row, col, variation.width, variation.height)) {
              return {
                row,
                col,
                width: variation.width,
                height: variation.height,
                resized: true
              };
            }
          }
        }
      }
      
      // Should not reach here with our grid size, but provide fallback
      return { row: 0, col: 0, width: 1, height: 1, resized: true };
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
    
    sortedTopics.forEach(({ topic, index, importance }) => {
      // Get initial ideal size based on topic properties
      const { width, height } = getInitialTileSize(topic, index, topics.length);
      
      // Find best position and possibly resize if needed
      const { row, col, width: finalWidth, height: finalHeight } = findBestPosition(width, height, index);
      
      // Store positioned tile
      const newTile = {
        topic,
        index,
        row,
        col,
        width: finalWidth,
        height: finalHeight
      };
      
      positionedTiles.push(newTile);
      
      // Mark cells as occupied
      occupyArea(row, col, finalWidth, finalHeight, index);
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
      if (tile.row <= maxRow && tile.row + tile.height > actualMaxRow) {
        actualMaxRow = tile.row + tile.height;
      }
    }
    
    // Fill any gaps by adjusting tiles (growing or shrinking)
    // First, scan for gaps
    const gaps = [];
    for (let row = 0; row <= actualMaxRow; row++) {
      for (let col = 0; col < grid.width; col++) {
        if (grid.cells[row][col] === null) {
          gaps.push({ row, col });
        }
      }
    }
    
    // Process each gap
    gaps.forEach(gap => {
      const { row, col } = gap;
      
      // Skip if this gap was already filled by a previous operation
      if (grid.cells[row][col] !== null) {
        return;
      }
      
      // Try strategies to fill the gap
      const strategies = [
        // 1. Extend a tile from above
        () => {
          if (row > 0 && grid.cells[row - 1][col] !== null) {
            const tileIndex = grid.cells[row - 1][col];
            const tile = positionedTiles.find(t => t.index === tileIndex);
            
            // Check if all cells in the row for this tile width are free
            let canExtend = true;
            for (let c = tile.col; c < tile.col + tile.width; c++) {
              if (c >= grid.width || (grid.cells[row][c] !== null && grid.cells[row][c] !== tileIndex)) {
                canExtend = false;
                break;
              }
            }
            
            if (canExtend) {
              // Clear the tile's current area
              clearArea(tile.row, tile.col, tile.width, tile.height);
              
              // Update the tile dimensions
              tile.height += 1;
              
              // Occupy the new area
              occupyArea(tile.row, tile.col, tile.width, tile.height, tile.index);
              return true;
            }
          }
          return false;
        },
        
        // 2. Extend a tile from the left
        () => {
          if (col > 0 && grid.cells[row][col - 1] !== null) {
            const tileIndex = grid.cells[row][col - 1];
            const tile = positionedTiles.find(t => t.index === tileIndex);
            
            // Don't make extremely wide tiles (max 4)
            if (tile.width >= 4) return false;
            
            // Check if all cells in the column for this tile height are free
            let canExtend = true;
            for (let r = tile.row; r < tile.row + tile.height; r++) {
              if (r >= grid.height || (grid.cells[r][col] !== null && grid.cells[r][col] !== tileIndex)) {
                canExtend = false;
                break;
              }
            }
            
            if (canExtend) {
              // Clear the tile's current area
              clearArea(tile.row, tile.col, tile.width, tile.height);
              
              // Update the tile dimensions
              tile.width += 1;
              
              // Occupy the new area
              occupyArea(tile.row, tile.col, tile.width, tile.height, tile.index);
              return true;
            }
          }
          return false;
        },
        
        // 3. Create a new 1x1 tile by shrinking an adjacent tile
        () => {
          // Look for an adjacent tile that can be shrunk
          const adjacentPositions = [
            { r: row - 1, c: col }, // Above
            { r: row, c: col - 1 }, // Left
            { r: row + 1, c: col }, // Below
            { r: row, c: col + 1 }  // Right
          ];
          
          for (const pos of adjacentPositions) {
            if (pos.r < 0 || pos.c < 0 || pos.r >= grid.height || pos.c >= grid.width) continue;
            
            const adjTileIndex = grid.cells[pos.r][pos.c];
            if (adjTileIndex === null) continue;
            
            const adjTile = positionedTiles.find(t => t.index === adjTileIndex);
            
            // Only consider shrinking tiles that are at least 2 in width or height
            if (adjTile.width > 1 || adjTile.height > 1) {
              // Try to carve out a 1x1 space for the gap
              let canShrink = false;
              let newWidth = adjTile.width;
              let newHeight = adjTile.height;
              
              // If the gap is within the tile's boundaries
              if (row >= adjTile.row && row < adjTile.row + adjTile.height &&
                  col >= adjTile.col && col < adjTile.col + adjTile.width) {
                
                // Determine if we should split horizontally or vertically
                if (adjTile.width > 1 && col === adjTile.col + adjTile.width - 1) {
                  // Shrink width
                  newWidth--;
                  canShrink = true;
                } 
                else if (adjTile.height > 1 && row === adjTile.row + adjTile.height - 1) {
                  // Shrink height
                  newHeight--;
                  canShrink = true;
                }
                
                if (canShrink) {
                  // Clear the tile's current area
                  clearArea(adjTile.row, adjTile.col, adjTile.width, adjTile.height);
                  
                  // Update dimensions
                  adjTile.width = newWidth;
                  adjTile.height = newHeight;
                  
                  // Reoccupy the new area
                  occupyArea(adjTile.row, adjTile.col, adjTile.width, adjTile.height, adjTile.index);
                  
                  return true;
                }
              }
            }
          }
          return false;
        },
        
        // 4. Search for a nearby small tile that can be moved here
        () => {
          // Scan for small 1x1 tiles that could be relocated
          const movableTiles = positionedTiles.filter(t => t.width === 1 && t.height === 1);
          
          for (const movableTile of movableTiles) {
            // Skip tiles too far away (arbitrary limit to improve performance)
            const distance = Math.abs(movableTile.row - row) + Math.abs(movableTile.col - col);
            if (distance > 5) continue; // Only consider nearby tiles
            
            // Check if the original position will be fillable after moving
            const originalRow = movableTile.row;
            const originalCol = movableTile.col;
            
            // Temporarily clear the tile
            clearArea(originalRow, originalCol, 1, 1);
            
            // Check if an adjacent tile can expand to fill the original position
            let originalFillable = false;
            
            // Check adjacent positions to the original position
            const originalAdjacent = [
              { r: originalRow - 1, c: originalCol }, // Above
              { r: originalRow, c: originalCol - 1 }, // Left
              { r: originalRow + 1, c: originalCol }, // Below
              { r: originalRow, c: originalCol + 1 }  // Right
            ];
            
            for (const adjPos of originalAdjacent) {
              if (adjPos.r < 0 || adjPos.c < 0 || adjPos.r >= grid.height || adjPos.c >= grid.width) continue;
              
              const adjTileIndex = grid.cells[adjPos.r][adjPos.c];
              if (adjTileIndex === null) continue;
              
              // If an adjacent tile exists, we can potentially fill the original position
              originalFillable = true;
              break;
            }
            
            if (originalFillable) {
              // Now move the tile to the gap
              movableTile.row = row;
              movableTile.col = col;
              
              // Mark the new position as occupied
              occupyArea(row, col, 1, 1, movableTile.index);
              
              return true;
            } else {
              // If not fillable, restore the original occupation
              occupyArea(originalRow, originalCol, 1, 1, movableTile.index);
            }
          }
          return false;
        }
      ];
      
      // Try each strategy until one works
      for (const strategy of strategies) {
        if (strategy()) {
          break; // Stop if a strategy succeeded
        }
      }
    });
    
    // Final check for remaining gaps - emergency fill
    for (let row = 0; row <= actualMaxRow; row++) {
      for (let col = 0; col < grid.width; col++) {
        if (grid.cells[row][col] === null) {
          // Emergency measure: extend any adjacent tile
          const adjacentPositions = [
            { r: row - 1, c: col }, // Above
            { r: row, c: col - 1 }, // Left
            { r: row + 1, c: col }, // Below
            { r: row, c: col + 1 }  // Right
          ];
          
          for (const pos of adjacentPositions) {
            if (pos.r < 0 || pos.c < 0 || pos.r >= grid.height || pos.c >= grid.width) continue;
            
            const adjTileIndex = grid.cells[pos.r][pos.c];
            if (adjTileIndex === null) continue;
            
            const adjTile = positionedTiles.find(t => t.index === adjTileIndex);
            
            // Always extend horizontally or vertically depending on position
            if (pos.r === row - 1) { // Tile is above
              clearArea(adjTile.row, adjTile.col, adjTile.width, adjTile.height);
              adjTile.height += 1;
              occupyArea(adjTile.row, adjTile.col, adjTile.width, adjTile.height, adjTile.index);
              break;
            } 
            else if (pos.c === col - 1) { // Tile is to the left
              clearArea(adjTile.row, adjTile.col, adjTile.width, adjTile.height);
              adjTile.width += 1;
              occupyArea(adjTile.row, adjTile.col, adjTile.width, adjTile.height, adjTile.index);
              break;
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
          gridTemplateRows: `repeat(${packedLayout.maxRow}, minmax(70px, auto))`,
          gridTemplateColumns: `repeat(5, 1fr)` // Default 5 columns
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