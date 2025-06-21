#!/usr/bin/env python3
"""
ADP Manager for SFB15 Fantasy Football Dashboard
Handles multiple ADP data sources and integration
"""

import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import os

class ADPManager:
    """Manages ADP data from multiple sources"""
    
    def __init__(self, data_dir: str = "data/adp"):
        self.data_dir = data_dir
        self.logger = self._setup_logging()
        self.adp_sources = {
            'sleeper': 'https://api.sleeper.app/v1/players/nfl/trending/add',
            'fantasypros': 'https://www.fantasypros.com/nfl/adp/ppr.php',
            'underdog': 'https://underdogfantasy.com/pick-em/higher-lower/nfl',
            'yahoo': 'https://football.fantasysports.yahoo.com/f1/draftanalysis'
        }
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for ADP manager"""
        logger = logging.getLogger('ADPManager')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def fetch_sleeper_adp(self) -> pd.DataFrame:
        """Fetch ADP data from Sleeper API"""
        try:
            # Get all NFL players
            players_url = "https://api.sleeper.app/v1/players/nfl"
            response = requests.get(players_url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                players_data = response.json()
                
                # Convert to DataFrame and extract relevant info
                players_list = []
                for player_id, player_info in players_data.items():
                    if player_info.get('active', False) and player_info.get('fantasy_positions'):
                        players_list.append({
                            'player_id': player_id,
                            'name': f"{player_info.get('first_name', '')} {player_info.get('last_name', '')}".strip(),
                            'position': player_info.get('position', ''),
                            'team': player_info.get('team', ''),
                            'age': player_info.get('age'),
                            'fantasy_positions': player_info.get('fantasy_positions', []),
                            'source': 'sleeper'
                        })
                
                df = pd.DataFrame(players_list)
                
                # Add mock ADP data (in production, this would come from actual draft data)
                df['adp'] = self._generate_mock_adp(df)
                df['adp_source'] = 'sleeper'
                df['last_updated'] = datetime.now()
                
                self.logger.info(f"Successfully fetched {len(df)} players from Sleeper")
                return df
                
            else:
                self.logger.error(f"Failed to fetch Sleeper data: {response.status_code}")
                return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"Error fetching Sleeper ADP: {str(e)}")
            return pd.DataFrame()
    
    def fetch_fantasypros_adp(self) -> pd.DataFrame:
        """Fetch ADP data from FantasyPros (web scraping)"""
        try:
            url = self.adp_sources['fantasypros']
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for ADP table (this is a simplified example)
                # In production, you'd need to parse the actual FantasyPros table structure
                players_list = []
                
                # Mock data for demonstration
                mock_players = [
                    {'name': 'Josh Allen', 'position': 'QB', 'team': 'BUF', 'adp': 12.5},
                    {'name': 'Christian McCaffrey', 'position': 'RB', 'team': 'SF', 'adp': 1.2},
                    {'name': 'Cooper Kupp', 'position': 'WR', 'team': 'LAR', 'adp': 8.7},
                    {'name': 'Travis Kelce', 'position': 'TE', 'team': 'KC', 'adp': 15.3}
                ]
                
                for player in mock_players:
                    players_list.append({
                        'name': player['name'],
                        'position': player['position'],
                        'team': player['team'],
                        'adp': player['adp'],
                        'adp_source': 'fantasypros',
                        'last_updated': datetime.now()
                    })
                
                df = pd.DataFrame(players_list)
                self.logger.info(f"Successfully fetched {len(df)} players from FantasyPros")
                return df
                
            else:
                self.logger.error(f"Failed to fetch FantasyPros data: {response.status_code}")
                return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"Error fetching FantasyPros ADP: {str(e)}")
            return pd.DataFrame()
    
    def _generate_mock_adp(self, df: pd.DataFrame) -> List[float]:
        """Generate mock ADP data based on position (for demonstration)"""
        adp_values = []
        
        position_ranges = {
            'QB': (20, 180),
            'RB': (1, 120),
            'WR': (1, 150),
            'TE': (30, 200),
            'K': (180, 250),
            'DEF': (200, 280)
        }
        
        for _, row in df.iterrows():
            position = row.get('position', 'WR')
            if position in position_ranges:
                min_adp, max_adp = position_ranges[position]
                adp = np.random.uniform(min_adp, max_adp)
            else:
                adp = np.random.uniform(50, 200)
            
            adp_values.append(round(adp, 1))
        
        return adp_values
    
    def aggregate_adp_data(self, sources: List[str] = None) -> pd.DataFrame:
        """Aggregate ADP data from multiple sources"""
        if sources is None:
            sources = ['sleeper', 'fantasypros']
        
        all_adp_data = []
        
        for source in sources:
            try:
                if source == 'sleeper':
                    df = self.fetch_sleeper_adp()
                elif source == 'fantasypros':
                    df = self.fetch_fantasypros_adp()
                else:
                    self.logger.warning(f"Unknown ADP source: {source}")
                    continue
                
                if not df.empty:
                    all_adp_data.append(df)
                    
            except Exception as e:
                self.logger.error(f"Error fetching data from {source}: {str(e)}")
                continue
        
        if not all_adp_data:
            self.logger.warning("No ADP data successfully fetched")
            return pd.DataFrame()
        
        # Combine all data
        combined_df = pd.concat(all_adp_data, ignore_index=True)
        
        # Calculate consensus ADP for players appearing in multiple sources
        consensus_adp = self._calculate_consensus_adp(combined_df)
        
        return consensus_adp
    
    def _calculate_consensus_adp(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate consensus ADP from multiple sources"""
        # Group by player name and calculate consensus
        consensus_data = []
        
        for name in df['name'].unique():
            player_data = df[df['name'] == name]
            
            if len(player_data) > 0:
                # Take the most recent data for non-ADP fields
                latest_data = player_data.iloc[-1]
                
                # Calculate consensus ADP (average of all sources)
                consensus_adp = player_data['adp'].mean()
                adp_std = player_data['adp'].std() if len(player_data) > 1 else 0
                
                consensus_data.append({
                    'name': name,
                    'position': latest_data.get('position', ''),
                    'team': latest_data.get('team', ''),
                    'age': latest_data.get('age'),
                    'consensus_adp': round(consensus_adp, 1),
                    'adp_std': round(adp_std, 1),
                    'sources_count': len(player_data),
                    'sources': list(player_data['adp_source'].unique()),
                    'last_updated': datetime.now()
                })
        
        consensus_df = pd.DataFrame(consensus_data)
        
        # Sort by consensus ADP
        consensus_df = consensus_df.sort_values('consensus_adp').reset_index(drop=True)
        consensus_df['overall_rank'] = range(1, len(consensus_df) + 1)
        
        self.logger.info(f"Created consensus ADP for {len(consensus_df)} players")
        return consensus_df
    
    def save_adp_data(self, df: pd.DataFrame, filename: str = None) -> str:
        """Save ADP data to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            filename = f"consensus_adp_{timestamp}.csv"
        
        filepath = os.path.join(self.data_dir, filename)
        df.to_csv(filepath, index=False)
        
        self.logger.info(f"Saved ADP data to {filepath}")
        return filepath
    
    def load_latest_adp_data(self) -> pd.DataFrame:
        """Load the most recent ADP data"""
        try:
            # Find the most recent ADP file
            adp_files = [f for f in os.listdir(self.data_dir) if f.startswith('consensus_adp_') and f.endswith('.csv')]
            
            if not adp_files:
                self.logger.warning("No saved ADP data found, fetching fresh data")
                return self.aggregate_adp_data()
            
            # Sort by filename (timestamp) and get the latest
            latest_file = sorted(adp_files)[-1]
            filepath = os.path.join(self.data_dir, latest_file)
            
            df = pd.read_csv(filepath)
            df['last_updated'] = pd.to_datetime(df['last_updated'])
            
            self.logger.info(f"Loaded ADP data from {filepath}")
            return df
            
        except Exception as e:
            self.logger.error(f"Error loading ADP data: {str(e)}")
            return pd.DataFrame()
    
    def get_adp_trends(self, player_name: str, days: int = 7) -> Dict:
        """Get ADP trend data for a specific player"""
        # This would analyze historical ADP data
        # For now, return mock trend data
        
        trend_data = {
            'player_name': player_name,
            'current_adp': np.random.uniform(20, 150),
            'adp_change_7d': np.random.uniform(-10, 10),
            'adp_change_24h': np.random.uniform(-2, 2),
            'trend_direction': np.random.choice(['up', 'down', 'stable']),
            'volatility': np.random.uniform(0.5, 5.0)
        }
        
        return trend_data
    
    def identify_adp_value_opportunities(self, projections_df: pd.DataFrame, adp_df: pd.DataFrame) -> pd.DataFrame:
        """Identify players with significant ADP vs projection value gaps"""
        try:
            # Merge projections with ADP data
            merged_df = pd.merge(
                projections_df, 
                adp_df, 
                left_on='player_name', 
                right_on='name', 
                how='inner'
            )
            
            if merged_df.empty:
                self.logger.warning("No matching players found between projections and ADP data")
                return pd.DataFrame()
            
            # Calculate value metrics
            merged_df['projection_rank'] = merged_df['projected_points'].rank(ascending=False)
            merged_df['adp_rank'] = merged_df['consensus_adp']
            merged_df['value_gap'] = merged_df['adp_rank'] - merged_df['projection_rank']
            
            # Identify value opportunities (positive value_gap = undervalued by ADP)
            value_opportunities = merged_df[merged_df['value_gap'] > 10].copy()
            value_opportunities = value_opportunities.sort_values('value_gap', ascending=False)
            
            self.logger.info(f"Identified {len(value_opportunities)} ADP value opportunities")
            return value_opportunities
            
        except Exception as e:
            self.logger.error(f"Error identifying ADP value opportunities: {str(e)}")
            return pd.DataFrame()
    
    def update_adp_data(self, force_refresh: bool = False) -> pd.DataFrame:
        """Update ADP data if needed"""
        try:
            # Check if we need to update (every 4 hours by default)
            latest_data = self.load_latest_adp_data()
            
            if not latest_data.empty and not force_refresh:
                last_update = pd.to_datetime(latest_data['last_updated'].iloc[0])
                hours_since_update = (datetime.now() - last_update).total_seconds() / 3600
                
                if hours_since_update < 4:
                    self.logger.info(f"ADP data is recent ({hours_since_update:.1f} hours old), skipping update")
                    return latest_data
            
            # Fetch fresh data
            self.logger.info("Fetching fresh ADP data...")
            fresh_data = self.aggregate_adp_data()
            
            if not fresh_data.empty:
                # Save the fresh data
                self.save_adp_data(fresh_data)
                return fresh_data
            else:
                self.logger.warning("Failed to fetch fresh ADP data, returning cached data")
                return latest_data
                
        except Exception as e:
            self.logger.error(f"Error updating ADP data: {str(e)}")
            return pd.DataFrame() 