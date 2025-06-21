#!/usr/bin/env python3
"""
SFB15 ADP Scraper for GoingFor2 Mock Draft Data
Scrapes real SFB15 ADP from actual tournament mock drafts
"""

import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import os
import json

class SFB15ADPScraper:
    """Scrapes SFB15-specific ADP data from GoingFor2"""
    
    def __init__(self, data_dir: str = "data/adp"):
        self.base_url = "https://goingfor2.com/sfb15adp/"
        self.data_dir = data_dir
        self.logger = self._setup_logging()
        
        # Headers to appear as a normal browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for SFB15 ADP scraper"""
        logger = logging.getLogger('SFB15ADPScraper')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def scrape_live_adp(self) -> pd.DataFrame:
        """Scrape current SFB15 ADP data from GoingFor2"""
        try:
            self.logger.info(f"Fetching SFB15 ADP data from {self.base_url}")
            
            # Add delay to be respectful to the server
            time.sleep(1)
            
            response = requests.get(self.base_url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                adp_df = self.parse_adp_table(soup)
                
                if not adp_df.empty:
                    # Validate the scraped data
                    if self.validate_adp_data(adp_df):
                        self.logger.info(f"Successfully scraped {len(adp_df)} players from SFB15 ADP")
                        
                        # Save the data with timestamp
                        self.save_adp_data(adp_df)
                        return adp_df
                    else:
                        self.logger.warning("Scraped data failed validation, attempting fallback")
                        return self.load_cached_adp_data()
                else:
                    self.logger.error("No data extracted from table")
                    return self.load_cached_adp_data()
                    
            else:
                self.logger.error(f"Failed to fetch SFB15 ADP: HTTP {response.status_code}")
                return self.load_cached_adp_data()
                
        except Exception as e:
            self.logger.error(f"Error scraping SFB15 ADP: {str(e)}")
            return self.load_cached_adp_data()
    
    def parse_adp_table(self, soup: BeautifulSoup) -> pd.DataFrame:
        """Parse the ADP table from the webpage"""
        try:
            players_data = []
            
            # Look for the ADP table - it should have headers: Rank, Position, First Name, Last Name, ADP, Number of Mocks
            table = soup.find('table')
            
            if not table:
                self.logger.error("No table found on the page")
                return pd.DataFrame()
            
            # Find all table rows, skip header
            rows = table.find_all('tr')
            
            if len(rows) < 2:
                self.logger.error("No data rows found in table")
                return pd.DataFrame()
            
            # Parse each row
            for row in rows[1:]:  # Skip header row
                cells = row.find_all(['td', 'th'])
                
                if len(cells) >= 6:  # Expect at least 6 columns
                    try:
                        rank = int(cells[0].get_text(strip=True))
                        position = cells[1].get_text(strip=True)
                        first_name = cells[2].get_text(strip=True)
                        last_name = cells[3].get_text(strip=True)
                        adp_text = cells[4].get_text(strip=True)
                        mocks_text = cells[5].get_text(strip=True)
                        
                        # Clean and convert ADP
                        adp = float(adp_text) if adp_text else None
                        
                        # Clean and convert mock count
                        mocks = int(mocks_text) if mocks_text.isdigit() else 0
                        
                        # Combine first and last name
                        full_name = f"{first_name} {last_name}".strip()
                        
                        if full_name and adp is not None:
                            players_data.append({
                                'rank': rank,
                                'name': full_name,
                                'position': position,
                                'consensus_adp': adp,
                                'mock_count': mocks,
                                'adp_source': 'sfb15',
                                'last_updated': datetime.now(),
                                'data_quality': 'high' if mocks >= 10 else 'medium' if mocks >= 5 else 'low'
                            })
                            
                    except (ValueError, IndexError) as e:
                        self.logger.warning(f"Error parsing row: {str(e)}")
                        continue
            
            if players_data:
                df = pd.DataFrame(players_data)
                
                # Add additional calculated fields
                df['overall_rank'] = df['rank']
                df['sources'] = [['sfb15']] * len(df)
                df['sources_count'] = 1
                df['adp_std'] = 0.0  # Single source, no standard deviation
                
                self.logger.info(f"Parsed {len(df)} players from SFB15 ADP table")
                return df
            else:
                self.logger.error("No valid player data extracted")
                return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"Error parsing ADP table: {str(e)}")
            return pd.DataFrame()
    
    def validate_adp_data(self, df: pd.DataFrame) -> bool:
        """Validate scraped ADP data quality"""
        try:
            # Check minimum player count (should have 250+ players)
            if len(df) < 250:
                self.logger.warning(f"Low player count: {len(df)} (expected 250+)")
                return False
            
            # Check for required columns
            required_columns = ['name', 'position', 'consensus_adp', 'rank']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                self.logger.error(f"Missing required columns: {missing_columns}")
                return False
            
            # Check ADP ranges (should be between 1 and 300)
            min_adp = df['consensus_adp'].min()
            max_adp = df['consensus_adp'].max()
            
            if min_adp < 0.5 or max_adp > 350:
                self.logger.warning(f"ADP values out of expected range: {min_adp} - {max_adp}")
                return False
            
            # Check for duplicate names
            duplicate_names = df['name'].duplicated().sum()
            if duplicate_names > 5:  # Allow a few duplicates (different teams)
                self.logger.warning(f"High number of duplicate names: {duplicate_names}")
            
            # Check position distribution
            position_counts = df['position'].value_counts()
            if 'QB' not in position_counts or position_counts.get('QB', 0) < 10:
                self.logger.warning("Insufficient QB count in data")
                return False
            
            self.logger.info("SFB15 ADP data validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating ADP data: {str(e)}")
            return False
    
    def save_adp_data(self, df: pd.DataFrame) -> str:
        """Save SFB15 ADP data with timestamp"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            filename = f"sfb15_adp_{timestamp}.csv"
            filepath = os.path.join(self.data_dir, filename)
            
            # Save the DataFrame
            df.to_csv(filepath, index=False)
            
            # Also save metadata
            metadata = {
                'source': 'goingfor2_sfb15',
                'url': self.base_url,
                'scraped_at': datetime.now().isoformat(),
                'player_count': len(df),
                'min_adp': float(df['consensus_adp'].min()),
                'max_adp': float(df['consensus_adp'].max()),
                'total_mocks': int(df['mock_count'].sum()) if 'mock_count' in df.columns else 0
            }
            
            metadata_file = filepath.replace('.csv', '_metadata.json')
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self.logger.info(f"Saved SFB15 ADP data to {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"Error saving ADP data: {str(e)}")
            return ""
    
    def load_cached_adp_data(self) -> pd.DataFrame:
        """Load the most recent cached SFB15 ADP data"""
        try:
            # Find the most recent SFB15 ADP file
            adp_files = [f for f in os.listdir(self.data_dir) if f.startswith('sfb15_adp_') and f.endswith('.csv')]
            
            if not adp_files:
                self.logger.warning("No cached SFB15 ADP data found")
                return pd.DataFrame()
            
            # Sort by filename (timestamp) and get the latest
            latest_file = sorted(adp_files)[-1]
            filepath = os.path.join(self.data_dir, latest_file)
            
            df = pd.read_csv(filepath)
            
            # Convert datetime columns
            if 'last_updated' in df.columns:
                df['last_updated'] = pd.to_datetime(df['last_updated'])
            
            self.logger.info(f"Loaded cached SFB15 ADP data from {filepath} ({len(df)} players)")
            return df
            
        except Exception as e:
            self.logger.error(f"Error loading cached ADP data: {str(e)}")
            return pd.DataFrame()
    
    def get_adp_age_hours(self) -> float:
        """Get the age of the most recent ADP data in hours"""
        try:
            adp_files = [f for f in os.listdir(self.data_dir) if f.startswith('sfb15_adp_') and f.endswith('.csv')]
            
            if not adp_files:
                return float('inf')
            
            # Extract timestamp from filename
            latest_file = sorted(adp_files)[-1]
            timestamp_str = latest_file.replace('sfb15_adp_', '').replace('.csv', '')
            
            # Parse timestamp (format: YYYYMMDD_HHMM)
            file_datetime = datetime.strptime(timestamp_str, "%Y%m%d_%H%M")
            
            # Calculate age in hours
            age_hours = (datetime.now() - file_datetime).total_seconds() / 3600
            
            return age_hours
            
        except Exception as e:
            self.logger.error(f"Error calculating ADP data age: {str(e)}")
            return float('inf')
    
    def should_update_adp(self, max_age_hours: float = 3.0) -> bool:
        """Check if ADP data should be updated"""
        age_hours = self.get_adp_age_hours()
        
        if age_hours == float('inf'):
            self.logger.info("No cached data found, update needed")
            return True
        
        if age_hours > max_age_hours:
            self.logger.info(f"ADP data is {age_hours:.1f} hours old, update needed")
            return True
        
        self.logger.info(f"ADP data is {age_hours:.1f} hours old, no update needed")
        return False
    
    def get_sfb15_adp(self, force_refresh: bool = False) -> pd.DataFrame:
        """Get SFB15 ADP data, refreshing if needed"""
        try:
            # Check if we need to refresh
            if force_refresh or self.should_update_adp():
                fresh_data = self.scrape_live_adp()
                if not fresh_data.empty:
                    return fresh_data
                else:
                    self.logger.warning("Failed to get fresh data, using cached")
                    return self.load_cached_adp_data()
            else:
                return self.load_cached_adp_data()
                
        except Exception as e:
            self.logger.error(f"Error getting SFB15 ADP data: {str(e)}")
            return pd.DataFrame()
    
    def compare_with_industry_adp(self, sfb15_df: pd.DataFrame, industry_df: pd.DataFrame) -> pd.DataFrame:
        """Compare SFB15 ADP with industry ADP to find value differences"""
        try:
            # Merge the datasets on player name
            comparison = pd.merge(
                sfb15_df[['name', 'position', 'consensus_adp', 'rank']],
                industry_df[['name', 'consensus_adp', 'overall_rank']],
                on='name',
                how='inner',
                suffixes=('_sfb15', '_industry')
            )
            
            if comparison.empty:
                return pd.DataFrame()
            
            # Calculate differences
            comparison['adp_difference'] = comparison['consensus_adp_industry'] - comparison['consensus_adp_sfb15']
            comparison['rank_difference'] = comparison['overall_rank_industry'] - comparison['rank_sfb15']
            
            # Identify value opportunities
            comparison['sfb15_value_type'] = comparison['adp_difference'].apply(
                lambda x: 'SFB15 Value' if x > 10 else 'Industry Value' if x < -10 else 'Similar Value'
            )
            
            # Sort by biggest differences
            comparison = comparison.sort_values('adp_difference', ascending=False)
            
            self.logger.info(f"Compared {len(comparison)} players between SFB15 and industry ADP")
            return comparison
            
        except Exception as e:
            self.logger.error(f"Error comparing ADP sources: {str(e)}")
            return pd.DataFrame() 