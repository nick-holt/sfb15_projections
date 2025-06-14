"""
Projection Manager
Loads and manages enhanced ML model projections for the dashboard
"""

import pandas as pd
import numpy as np
import os
from typing import Dict, List, Optional
from datetime import datetime

class ProjectionManager:
    """Manages loading and processing of enhanced ML projections"""
    
    def __init__(self, projection_path: Optional[str] = None):
        """
        Initialize ProjectionManager
        
        Args:
            projection_path: Path to projection files. If None, uses default enhanced projections.
        """
        self.base_path = projection_path or self._get_default_projection_path()
        self.projections = None
        self.last_updated = None
        
    def _get_default_projection_path(self) -> str:
        """Get the path to the latest enhanced projections"""
        # Look for the most recent enhanced projections
        proj_dir = "projections/2025"
        
        # Priority order: enhanced timestamped > final > regular
        timestamp_files = [f for f in os.listdir(proj_dir) if f.startswith('fantasy_projections_2025_week')]
        if timestamp_files:
            # Get the most recent timestamped file
            latest_file = sorted(timestamp_files, reverse=True)[0]
            return os.path.join(proj_dir, latest_file)
        
        # Fallback to final projections
        final_file = os.path.join(proj_dir, 'fantasy_projections_2025_final.csv')
        if os.path.exists(final_file):
            return final_file
            
        # Last resort - basic projections
        return os.path.join(proj_dir, 'fantasy_projections_2025.csv')
    
    def load_enhanced_projections(self) -> pd.DataFrame:
        """
        Load enhanced projections with all features
        
        Returns:
            DataFrame with enhanced projections including confidence, tiers, etc.
        """
        try:
            print(f"Loading projections from: {self.base_path}")
            
            # Load the projection data
            projections = pd.read_csv(self.base_path)
            
            # Ensure required columns exist
            required_cols = ['player_name', 'position', 'team', 'projected_points']
            missing_cols = [col for col in required_cols if col not in projections.columns]
            if missing_cols:
                raise ValueError(f"Missing required columns: {missing_cols}")
            
            # Clean and standardize data
            projections = self._clean_projection_data(projections)
            
            # Add any missing analytics columns
            projections = self._add_missing_columns(projections)
            
            self.projections = projections
            self.last_updated = datetime.now()
            
            print(f"Successfully loaded {len(projections)} player projections")
            return projections
            
        except Exception as e:
            print(f"Error loading projections: {str(e)}")
            raise
    
    def _clean_projection_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and standardize projection data"""
        df = df.copy()
        
        # Remove any duplicate players (keep highest projection)
        df = df.sort_values('projected_points', ascending=False).drop_duplicates('player_name', keep='first')
        
        # Ensure numeric columns are numeric (excluding confidence which is categorical)
        numeric_cols = ['projected_points', 'age']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Fill missing confidence values
        if 'confidence' not in df.columns:
            df['confidence'] = 'Medium'
        
        # Ensure tier labels exist
        if 'tier_label' not in df.columns:
            df['tier_label'] = 'Unranked'
        
        # Clean position values
        df['position'] = df['position'].str.upper().str.strip()
        
        # Sort by projected points descending
        df = df.sort_values('projected_points', ascending=False).reset_index(drop=True)
        
        return df
    
    def _add_missing_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add any missing analytics columns needed for dashboard"""
        df = df.copy()
        
        # Add overall rank if not present
        if 'overall_rank' not in df.columns:
            df['overall_rank'] = range(1, len(df) + 1)
        
        # Add position rank if not present  
        if 'position_rank' not in df.columns:
            df['position_rank'] = df.groupby('position')['projected_points'].rank(method='min', ascending=False)
        
        # Add draft value placeholder (will be calculated by ValueCalculator)
        if 'draft_value' not in df.columns:
            df['draft_value'] = 0.0
        
        # Add tier if not present
        if 'tier' not in df.columns:
            df['tier'] = 3  # Default to tier 3
            
        return df
    
    def get_player_projection(self, player_name: str) -> Optional[Dict]:
        """
        Get projection for a specific player
        
        Args:
            player_name: Name of the player
            
        Returns:
            Dictionary with player projection data or None if not found
        """
        if self.projections is None:
            self.load_enhanced_projections()
        
        player_data = self.projections[self.projections['player_name'] == player_name]
        if len(player_data) == 0:
            return None
            
        return player_data.iloc[0].to_dict()
    
    def get_players_by_position(self, position: str, limit: Optional[int] = None) -> pd.DataFrame:
        """
        Get players filtered by position
        
        Args:
            position: Position to filter by (QB, RB, WR, TE)
            limit: Maximum number of players to return
            
        Returns:
            DataFrame with filtered players
        """
        if self.projections is None:
            self.load_enhanced_projections()
            
        filtered = self.projections[self.projections['position'] == position.upper()]
        
        if limit:
            filtered = filtered.head(limit)
            
        return filtered
    
    def get_top_players(self, limit: int = 100) -> pd.DataFrame:
        """
        Get top players by projected points
        
        Args:
            limit: Number of top players to return
            
        Returns:
            DataFrame with top players
        """
        if self.projections is None:
            self.load_enhanced_projections()
            
        return self.projections.head(limit)
    
    def search_players(self, search_term: str) -> pd.DataFrame:
        """
        Search for players by name
        
        Args:
            search_term: Search string for player names
            
        Returns:
            DataFrame with matching players
        """
        if self.projections is None:
            self.load_enhanced_projections()
            
        mask = self.projections['player_name'].str.contains(search_term, case=False, na=False)
        return self.projections[mask]
    
    def update_projections(self) -> bool:
        """
        Reload projections from file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.load_enhanced_projections()
            return True
        except Exception as e:
            print(f"Error updating projections: {str(e)}")
            return False 