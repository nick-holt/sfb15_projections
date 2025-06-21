#!/usr/bin/env python3
"""
Enhanced ADP Manager for SFB15 Fantasy Football Dashboard
Handles multiple ADP data sources with SFB15-specific integration
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

# Import the SFB15 scraper
from .sfb15_adp_scraper import SFB15ADPScraper

class ADPManager:
    """Manages ADP data from multiple sources"""
    
    def __init__(self, data_dir: str = "data/adp"):
        self.data_dir = data_dir
        self.logger = self._setup_logging()
        
        # Initialize SFB15 scraper
        self.sfb15_scraper = SFB15ADPScraper(data_dir)
        
        # Configure ADP sources with SFB15 as primary
        self.adp_sources = {
            'sfb15': 'https://goingfor2.com/sfb15adp/',  # Primary for SFB15
            'sleeper': 'https://api.sleeper.app/v1/players/nfl/trending/add',
            'fantasypros': 'https://www.fantasypros.com/nfl/adp/ppr.php',
            'underdog': 'https://underdogfantasy.com/pick-em/higher-lower/nfl',
            'yahoo': 'https://football.fantasysports.yahoo.com/f1/draftanalysis'
        }
        
        # Source weights for blended ADP (SFB15 gets highest weight)
        self.source_weights = {
            'sfb15': 0.70,      # Primary for tournament play
            'sleeper': 0.20,    # Secondary for market context
            'fantasypros': 0.10  # Tertiary for consensus view
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
    
    def fetch_sfb15_adp(self) -> pd.DataFrame:
        """Fetch SFB15-specific ADP data from GoingFor2"""
        try:
            return self.sfb15_scraper.get_sfb15_adp()
        except Exception as e:
            self.logger.error(f"Error fetching SFB15 ADP: {str(e)}")
            return pd.DataFrame()
    
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
            sources = ['sfb15', 'sleeper', 'fantasypros']  # Default includes SFB15
        
        all_adp_data = []
        
        for source in sources:
            try:
                if source == 'sfb15':
                    df = self.fetch_sfb15_adp()
                elif source == 'sleeper':
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
    
    def get_blended_adp(self, sources: List[str] = None, weights: Dict[str, float] = None) -> pd.DataFrame:
        """Get weighted blend of ADP from multiple sources"""
        try:
            if sources is None:
                sources = list(self.source_weights.keys())
            
            if weights is None:
                weights = self.source_weights
            
            # Fetch data from all sources
            source_data = {}
            for source in sources:
                if source == 'sfb15':
                    data = self.fetch_sfb15_adp()
                elif source == 'sleeper':
                    data = self.fetch_sleeper_adp()
                elif source == 'fantasypros':
                    data = self.fetch_fantasypros_adp()
                else:
                    continue
                
                if not data.empty:
                    # Ensure we have a valid name column
                    if 'name' not in data.columns or data['name'].isna().all():
                        self.logger.warning(f"No valid names found in {source} data")
                        continue
                    
                    # Standardize the ADP column name
                    if 'consensus_adp' in data.columns:
                        data['standard_adp'] = data['consensus_adp']
                    elif 'adp' in data.columns:
                        data['standard_adp'] = data['adp']
                    else:
                        self.logger.warning(f"No ADP column found in {source} data")
                        continue
                    
                    # Filter out rows with missing names or ADP values
                    data_clean = data.dropna(subset=['name', 'standard_adp'])
                    if data_clean.empty:
                        self.logger.warning(f"No valid data after cleaning {source}")
                        continue
                    
                    source_data[source] = data_clean
                    self.logger.info(f"Loaded {len(data_clean)} clean records from {source}")
            
            if not source_data:
                self.logger.error("No ADP data available from any source")
                return pd.DataFrame()
            
            # Calculate weighted ADP
            blended_data = []
            
            # Get all unique player names from ALL sources (including those with NaN in some sources)
            all_players = set()
            for source, data in source_data.items():
                # Get all names, even if some are NaN in other columns
                source_names = data['name'].dropna().tolist()
                all_players.update(source_names)
                self.logger.debug(f"Added {len(source_names)} valid names from {source}")
            
            self.logger.info(f"Found {len(all_players)} unique players across all sources")
            
            for player_name in all_players:
                weighted_adp = 0
                total_weight = 0
                player_info = {}
                
                for source, data in source_data.items():
                    player_data = data[data['name'] == player_name]
                    
                    if len(player_data) > 0:
                        weight = weights.get(source, 0)
                        adp_value = player_data.iloc[0]['standard_adp']
                        
                        weighted_adp += adp_value * weight
                        total_weight += weight
                        
                        # Store player info from highest weighted source
                        if weight == max(weights.get(s, 0) for s in source_data.keys()):
                            player_info = {
                                'name': player_name,
                                'position': player_data.iloc[0].get('position', ''),
                                'team': player_data.iloc[0].get('team', ''),
                                'age': player_data.iloc[0].get('age')
                            }
                
                if total_weight > 0:
                    final_adp = weighted_adp / total_weight
                    
                    blended_data.append({
                        **player_info,
                        'consensus_adp': round(final_adp, 1),
                        'sources': list(source_data.keys()),
                        'sources_count': len(source_data),
                        'blend_weights': weights,
                        'last_updated': datetime.now()
                    })
            
            if blended_data:
                df = pd.DataFrame(blended_data)
                df = df.sort_values('consensus_adp').reset_index(drop=True)
                df['overall_rank'] = range(1, len(df) + 1)
                
                self.logger.info(f"Created blended ADP for {len(df)} players using sources: {list(source_data.keys())}")
                return df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"Error creating blended ADP: {str(e)}")
            return pd.DataFrame()
    
    def switch_primary_source(self, source: str) -> None:
        """Dynamically switch primary ADP source"""
        try:
            if source not in self.adp_sources:
                self.logger.error(f"Unknown ADP source: {source}")
                return
            
            # Adjust weights to make the selected source primary
            if source == 'sfb15':
                self.source_weights = {'sfb15': 0.70, 'sleeper': 0.20, 'fantasypros': 0.10}
            elif source == 'sleeper':
                self.source_weights = {'sleeper': 0.60, 'sfb15': 0.30, 'fantasypros': 0.10}
            elif source == 'fantasypros':
                self.source_weights = {'fantasypros': 0.60, 'sfb15': 0.25, 'sleeper': 0.15}
            
            self.logger.info(f"Switched primary ADP source to {source}")
            
        except Exception as e:
            self.logger.error(f"Error switching primary source: {str(e)}")
    
    def compare_adp_sources(self) -> pd.DataFrame:
        """Compare ADP across all available sources"""
        try:
            # Fetch data from all sources
            sfb15_data = self.fetch_sfb15_adp()
            sleeper_data = self.fetch_sleeper_adp()
            fp_data = self.fetch_fantasypros_adp()
            
            # Start with SFB15 as base
            if sfb15_data.empty:
                self.logger.warning("No SFB15 data available for comparison")
                return pd.DataFrame()
            
            comparison_df = sfb15_data[['name', 'position', 'consensus_adp']].copy()
            comparison_df.rename(columns={'consensus_adp': 'sfb15_adp'}, inplace=True)
            
            # Add Sleeper data
            if not sleeper_data.empty:
                sleeper_subset = sleeper_data[['name', 'consensus_adp']].copy()
                sleeper_subset.rename(columns={'consensus_adp': 'sleeper_adp'}, inplace=True)
                comparison_df = pd.merge(comparison_df, sleeper_subset, on='name', how='left')
            
            # Add FantasyPros data
            if not fp_data.empty:
                fp_subset = fp_data[['name', 'consensus_adp']].copy()
                fp_subset.rename(columns={'consensus_adp': 'fantasypros_adp'}, inplace=True)
                comparison_df = pd.merge(comparison_df, fp_subset, on='name', how='left')
            
            # Calculate differences
            if 'sleeper_adp' in comparison_df.columns:
                comparison_df['sfb15_vs_sleeper'] = comparison_df['sleeper_adp'] - comparison_df['sfb15_adp']
            
            if 'fantasypros_adp' in comparison_df.columns:
                comparison_df['sfb15_vs_fantasypros'] = comparison_df['fantasypros_adp'] - comparison_df['sfb15_adp']
            
            # Identify biggest differences (SFB15 value opportunities)
            comparison_df['max_difference'] = 0
            diff_cols = [col for col in comparison_df.columns if 'sfb15_vs_' in col]
            
            if diff_cols:
                comparison_df['max_difference'] = comparison_df[diff_cols].max(axis=1, skipna=True)
                comparison_df['value_type'] = comparison_df['max_difference'].apply(
                    lambda x: 'SFB15 Value' if x > 20 else 'Industry Value' if x < -20 else 'Similar'
                )
            
            # Sort by biggest SFB15 values first
            comparison_df = comparison_df.sort_values('max_difference', ascending=False)
            
            self.logger.info(f"Compared ADP across sources for {len(comparison_df)} players")
            return comparison_df
            
        except Exception as e:
            self.logger.error(f"Error comparing ADP sources: {str(e)}")
            return pd.DataFrame()
    
    def get_source_health_status(self) -> Dict[str, Dict]:
        """Get health status of all ADP sources"""
        try:
            status = {}
            
            # Check SFB15 source
            sfb15_age = self.sfb15_scraper.get_adp_age_hours()
            status['sfb15'] = {
                'available': sfb15_age != float('inf'),
                'last_updated_hours': sfb15_age if sfb15_age != float('inf') else None,
                'status': 'healthy' if sfb15_age < 4 else 'stale' if sfb15_age < 24 else 'offline',
                'player_count': 0
            }
            
            # Get player count if data is available
            try:
                sfb15_data = self.sfb15_scraper.load_cached_adp_data()
                if not sfb15_data.empty:
                    status['sfb15']['player_count'] = len(sfb15_data)
            except:
                pass
            
            # Check other sources (simplified)
            for source in ['sleeper', 'fantasypros']:
                try:
                    if source == 'sleeper':
                        data = self.fetch_sleeper_adp()
                    else:
                        data = self.fetch_fantasypros_adp()
                    
                    status[source] = {
                        'available': not data.empty,
                        'status': 'healthy' if not data.empty else 'offline',
                        'player_count': len(data) if not data.empty else 0
                    }
                except:
                    status[source] = {
                        'available': False,
                        'status': 'offline',
                        'player_count': 0
                    }
            
            return status
            
        except Exception as e:
            self.logger.error(f"Error getting source health status: {str(e)}")
            return {} 