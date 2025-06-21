"""
Sleeper API Client

This module handles all interactions with the Sleeper Fantasy Football API
for retrieving live draft data, league information, and player data.
"""

import requests
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class SleeperAPIError(Exception):
    """Custom exception for Sleeper API errors"""
    pass

class SleeperClient:
    """Client for interacting with the Sleeper API"""
    
    BASE_URL = "https://api.sleeper.app/v1"
    
    def __init__(self, rate_limit_delay: float = 0.1):
        """
        Initialize Sleeper API client
        
        Args:
            rate_limit_delay: Delay between API calls to respect rate limits
        """
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
        self.session = requests.Session()
        
        # Set user agent
        self.session.headers.update({
            'User-Agent': 'Fantasy-Projection-Dashboard/1.0'
        })
    
    def _make_request(self, endpoint: str) -> Dict[str, Any]:
        """
        Make a rate-limited request to the Sleeper API
        
        Args:
            endpoint: API endpoint path
            
        Returns:
            JSON response data
            
        Raises:
            SleeperAPIError: If the API request fails
        """
        # Rate limiting
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        
        try:
            logger.debug(f"Making request to: {url}")
            response = self.session.get(url, timeout=10)
            self.last_request_time = time.time()
            
            if response.status_code == 429:
                logger.warning("Rate limited by Sleeper API, waiting 60 seconds")
                time.sleep(60)
                return self._make_request(endpoint)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to {url}: {e}")
            raise SleeperAPIError(f"Failed to fetch data from Sleeper API: {e}")
    
    def get_user(self, username_or_id: str) -> Dict[str, Any]:
        """
        Get user information by username or user_id
        
        Args:
            username_or_id: Sleeper username or user_id
            
        Returns:
            User information dictionary
        """
        endpoint = f"user/{username_or_id}"
        return self._make_request(endpoint)
    
    def get_user_leagues(self, user_id: str, sport: str = "nfl", season: str = "2025") -> List[Dict[str, Any]]:
        """
        Get all leagues for a user
        
        Args:
            user_id: Sleeper user_id
            sport: Sport (default: "nfl")
            season: Season year (default: "2025")
            
        Returns:
            List of league dictionaries
        """
        endpoint = f"user/{user_id}/leagues/{sport}/{season}"
        return self._make_request(endpoint)
    
    def get_league(self, league_id: str) -> Dict[str, Any]:
        """
        Get specific league information
        
        Args:
            league_id: Sleeper league_id
            
        Returns:
            League information dictionary
        """
        endpoint = f"league/{league_id}"
        return self._make_request(endpoint)
    
    def get_league_rosters(self, league_id: str) -> List[Dict[str, Any]]:
        """
        Get all rosters in a league
        
        Args:
            league_id: Sleeper league_id
            
        Returns:
            List of roster dictionaries
        """
        endpoint = f"league/{league_id}/rosters"
        return self._make_request(endpoint)
    
    def get_league_users(self, league_id: str) -> List[Dict[str, Any]]:
        """
        Get all users in a league
        
        Args:
            league_id: Sleeper league_id
            
        Returns:
            List of user dictionaries
        """
        endpoint = f"league/{league_id}/users"
        return self._make_request(endpoint)
    
    def get_league_drafts(self, league_id: str) -> List[Dict[str, Any]]:
        """
        Get all drafts for a league
        
        Args:
            league_id: Sleeper league_id
            
        Returns:
            List of draft dictionaries
        """
        endpoint = f"league/{league_id}/drafts"
        return self._make_request(endpoint)
    
    def get_draft(self, draft_id: str) -> Dict[str, Any]:
        """
        Get specific draft information
        
        Args:
            draft_id: Sleeper draft_id
            
        Returns:
            Draft information dictionary
        """
        endpoint = f"draft/{draft_id}"
        return self._make_request(endpoint)
    
    def get_draft_picks(self, draft_id: str) -> List[Dict[str, Any]]:
        """
        Get all picks in a draft
        
        Args:
            draft_id: Sleeper draft_id
            
        Returns:
            List of pick dictionaries
        """
        endpoint = f"draft/{draft_id}/picks"
        return self._make_request(endpoint)
    
    def get_nfl_players(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all NFL players (use sparingly - 5MB response)
        
        Returns:
            Dictionary mapping player_id to player info
        """
        endpoint = "players/nfl"
        return self._make_request(endpoint)
    
    def get_nfl_state(self) -> Dict[str, Any]:
        """
        Get current NFL season state
        
        Returns:
            NFL state information
        """
        endpoint = "state/nfl"
        return self._make_request(endpoint)

class SleeperDraftMonitor:
    """Monitor a specific Sleeper draft for live updates"""
    
    def __init__(self, draft_id: str, client: Optional[SleeperClient] = None):
        """
        Initialize draft monitor
        
        Args:
            draft_id: Sleeper draft_id to monitor
            client: SleeperClient instance (creates new one if None)
        """
        self.draft_id = draft_id
        self.client = client or SleeperClient()
        self._last_pick_count = 0
        self._cached_picks = []
        self._cached_draft_info = None
        
    def get_draft_info(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get draft information (cached)
        
        Args:
            force_refresh: Force refresh from API
            
        Returns:
            Draft information dictionary
        """
        if self._cached_draft_info is None or force_refresh:
            self._cached_draft_info = self.client.get_draft(self.draft_id)
            logger.info(f"Refreshed draft info for {self.draft_id}")
        
        return self._cached_draft_info
    
    def get_new_picks(self) -> List[Dict[str, Any]]:
        """
        Get any new picks since last check
        
        Returns:
            List of new pick dictionaries
        """
        current_picks = self.client.get_draft_picks(self.draft_id)
        
        # Check if there are new picks
        if len(current_picks) > self._last_pick_count:
            new_picks = current_picks[self._last_pick_count:]
            self._last_pick_count = len(current_picks)
            self._cached_picks = current_picks
            
            logger.info(f"Found {len(new_picks)} new picks in draft {self.draft_id}")
            return new_picks
        
        return []
    
    def get_all_picks(self) -> List[Dict[str, Any]]:
        """
        Get all picks in the draft
        
        Returns:
            List of all pick dictionaries
        """
        if not self._cached_picks:
            self._cached_picks = self.client.get_draft_picks(self.draft_id)
            self._last_pick_count = len(self._cached_picks)
        
        return self._cached_picks
    
    def is_draft_active(self) -> bool:
        """
        Check if draft is currently active
        
        Returns:
            True if draft is in progress
        """
        draft_info = self.get_draft_info()
        return draft_info.get('status') == 'drafting'
    
    def reset_cache(self):
        """Reset all cached data"""
        self._last_pick_count = 0
        self._cached_picks = []
        self._cached_draft_info = None

class SleeperPlayerCache:
    """Cache for Sleeper player data to avoid repeated large API calls"""
    
    def __init__(self, client: Optional[SleeperClient] = None, cache_duration_hours: int = 24):
        """
        Initialize player cache
        
        Args:
            client: SleeperClient instance
            cache_duration_hours: How long to cache player data
        """
        self.client = client or SleeperClient()
        self.cache_duration_hours = cache_duration_hours
        self._players_cache = {}
        self._cache_timestamp = None
    
    def get_players(self, force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Get player data (cached)
        
        Args:
            force_refresh: Force refresh from API
            
        Returns:
            Dictionary mapping player_id to player info
        """
        now = datetime.now()
        
        # Check if cache is stale or doesn't exist
        if (self._cache_timestamp is None or 
            force_refresh or
            (now - self._cache_timestamp).total_seconds() > self.cache_duration_hours * 3600):
            
            logger.info("Refreshing Sleeper player cache...")
            self._players_cache = self.client.get_nfl_players()
            self._cache_timestamp = now
            logger.info(f"Cached {len(self._players_cache)} players")
        
        return self._players_cache
    
    def get_player(self, player_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific player by ID
        
        Args:
            player_id: Sleeper player_id
            
        Returns:
            Player information or None if not found
        """
        players = self.get_players()
        return players.get(player_id)
    
    def search_players(self, name: str, position: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for players by name and optionally position
        
        Args:
            name: Player name to search for
            position: Optional position filter
            
        Returns:
            List of matching players
        """
        players = self.get_players()
        name_lower = name.lower()
        
        matches = []
        for player_id, player_data in players.items():
            # Check name match
            full_name = f"{player_data.get('first_name', '')} {player_data.get('last_name', '')}".lower()
            if name_lower in full_name:
                # Check position filter
                if position is None or player_data.get('position') == position:
                    player_data['player_id'] = player_id
                    matches.append(player_data)
        
        return matches 