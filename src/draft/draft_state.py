"""
Live Draft State Management

This module handles the core data structures and state management for tracking
live fantasy football drafts in real-time.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class DraftPick:
    """Represents a single draft pick"""
    pick_number: int
    round: int
    draft_slot: int
    player_id: str
    player_name: str
    position: str
    team: str
    roster_id: int
    picked_by: str  # user_id
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TeamRoster:
    """Represents a team's current roster composition"""
    roster_id: int
    owner_id: str
    owner_name: str
    team_name: Optional[str] = None
    
    # Current roster by position
    qb: List[str] = field(default_factory=list)
    rb: List[str] = field(default_factory=list) 
    wr: List[str] = field(default_factory=list)
    te: List[str] = field(default_factory=list)
    k: List[str] = field(default_factory=list)
    def_: List[str] = field(default_factory=list)
    bench: List[str] = field(default_factory=list)
    
    # Positional needs (calculated)
    needs_qb: int = 0
    needs_rb: int = 0
    needs_wr: int = 0
    needs_te: int = 0
    needs_k: int = 0
    needs_def: int = 0
    needs_flex: int = 0
    needs_bench: int = 0
    
    def add_player(self, player_id: str, position: str):
        """Add a player to the roster"""
        if position == 'QB':
            self.qb.append(player_id)
        elif position == 'RB':
            self.rb.append(player_id)
        elif position == 'WR':
            self.wr.append(player_id)
        elif position == 'TE':
            self.te.append(player_id)
        elif position == 'K':
            self.k.append(player_id)
        elif position == 'DEF':
            self.def_.append(player_id)
        else:
            self.bench.append(player_id)
    
    def get_total_players(self) -> int:
        """Get total number of players on roster"""
        return (len(self.qb) + len(self.rb) + len(self.wr) + 
                len(self.te) + len(self.k) + len(self.def_) + len(self.bench))
    
    def calculate_positional_needs(self, league_settings: Dict[str, Any]):
        """Calculate remaining positional needs based on league settings"""
        settings = league_settings.get('roster_positions', [])
        
        # Count required starters by position
        req_qb = settings.count('QB')
        req_rb = settings.count('RB') 
        req_wr = settings.count('WR')
        req_te = settings.count('TE')
        req_k = settings.count('K')
        req_def = settings.count('DEF')
        req_flex = settings.count('FLEX') + settings.count('WRRB_FLEX') + settings.count('REC_FLEX')
        req_bench = settings.count('BN')
        
        # Calculate remaining needs
        self.needs_qb = max(0, req_qb - len(self.qb))
        self.needs_rb = max(0, req_rb - len(self.rb))
        self.needs_wr = max(0, req_wr - len(self.wr))
        self.needs_te = max(0, req_te - len(self.te))
        self.needs_k = max(0, req_k - len(self.k))
        self.needs_def = max(0, req_def - len(self.def_))
        self.needs_flex = max(0, req_flex - max(0, len(self.rb) + len(self.wr) + len(self.te) - req_rb - req_wr - req_te))
        self.needs_bench = max(0, req_bench - len(self.bench))

@dataclass
class DraftSettings:
    """Draft configuration and settings"""
    league_id: str
    draft_id: str
    league_name: str
    total_teams: int
    total_rounds: int
    pick_timer: int  # seconds
    draft_type: str  # "snake", "linear", etc.
    scoring_type: str  # "ppr", "standard", etc.
    roster_positions: List[str] = field(default_factory=list)
    
    # Draft order mapping
    draft_order: Dict[str, int] = field(default_factory=dict)  # user_id -> draft_slot
    slot_to_roster: Dict[int, int] = field(default_factory=dict)  # draft_slot -> roster_id

@dataclass 
class DraftState:
    """Complete state of a live draft"""
    settings: DraftSettings
    status: str  # "pre_draft", "drafting", "complete"
    current_pick: int = 1
    current_round: int = 1
    current_draft_slot: int = 1
    
    # All completed picks
    picks: List[DraftPick] = field(default_factory=list)
    
    # Team rosters
    rosters: Dict[int, TeamRoster] = field(default_factory=dict)  # roster_id -> TeamRoster
    
    # Available players (player_id -> player_info)
    available_players: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Draft timing
    last_pick_time: Optional[datetime] = None
    pick_deadline: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize rosters if not provided"""
        if not self.rosters:
            for slot, roster_id in self.settings.slot_to_roster.items():
                # We'll need to populate owner info from API calls
                self.rosters[roster_id] = TeamRoster(
                    roster_id=roster_id,
                    owner_id="",  # Will be populated from API
                    owner_name=""  # Will be populated from API
                )
    
    def add_pick(self, pick: DraftPick):
        """Add a new draft pick and update state"""
        self.picks.append(pick)
        
        # Update roster
        if pick.roster_id in self.rosters:
            self.rosters[pick.roster_id].add_player(pick.player_id, pick.position)
            self.rosters[pick.roster_id].calculate_positional_needs(
                {'roster_positions': self.settings.roster_positions}
            )
        
        # Remove from available players
        if pick.player_id in self.available_players:
            del self.available_players[pick.player_id]
        
        # Update current pick info
        self.current_pick += 1
        self.last_pick_time = pick.timestamp or datetime.now()
        
        # Calculate next pick position for snake draft
        if self.settings.draft_type == "snake":
            if self.current_round % 2 == 1:  # Odd rounds go 1->N
                self.current_draft_slot = ((self.current_pick - 1) % self.settings.total_teams) + 1
            else:  # Even rounds go N->1
                self.current_draft_slot = self.settings.total_teams - ((self.current_pick - 1) % self.settings.total_teams)
        else:  # Linear draft
            self.current_draft_slot = ((self.current_pick - 1) % self.settings.total_teams) + 1
        
        # Update round
        self.current_round = ((self.current_pick - 1) // self.settings.total_teams) + 1
        
        logger.info(f"Added pick {self.current_pick - 1}: {pick.player_name} to roster {pick.roster_id}")
    
    def get_current_team(self) -> Optional[TeamRoster]:
        """Get the team that's currently on the clock"""
        if self.current_draft_slot in self.settings.slot_to_roster:
            roster_id = self.settings.slot_to_roster[self.current_draft_slot]
            return self.rosters.get(roster_id)
        return None
    
    def get_next_picks(self, count: int = 5) -> List[int]:
        """Get the next N draft slots that will pick"""
        next_slots = []
        for i in range(count):
            pick_num = self.current_pick + i
            if pick_num > self.settings.total_teams * self.settings.total_rounds:
                break
                
            round_num = ((pick_num - 1) // self.settings.total_teams) + 1
            
            if self.settings.draft_type == "snake":
                if round_num % 2 == 1:  # Odd rounds go 1->N
                    slot = ((pick_num - 1) % self.settings.total_teams) + 1
                else:  # Even rounds go N->1
                    slot = self.settings.total_teams - ((pick_num - 1) % self.settings.total_teams)
            else:  # Linear draft
                slot = ((pick_num - 1) % self.settings.total_teams) + 1
            
            next_slots.append(slot)
        
        return next_slots
    
    def is_draft_complete(self) -> bool:
        """Check if the draft is finished"""
        total_picks = self.settings.total_teams * self.settings.total_rounds
        return len(self.picks) >= total_picks
    
    def get_picks_by_round(self, round_num: int) -> List[DraftPick]:
        """Get all picks from a specific round"""
        return [pick for pick in self.picks if pick.round == round_num]
    
    def get_picks_by_team(self, roster_id: int) -> List[DraftPick]:
        """Get all picks made by a specific team"""
        return [pick for pick in self.picks if pick.roster_id == roster_id]
    
    def get_available_by_position(self, position: str) -> List[Dict[str, Any]]:
        """Get all available players at a specific position"""
        return [
            player for player in self.available_players.values()
            if player.get('position') == position
        ]
    
    def export_state(self) -> Dict[str, Any]:
        """Export current state to dictionary for serialization"""
        return {
            'settings': {
                'league_id': self.settings.league_id,
                'draft_id': self.settings.draft_id,
                'league_name': self.settings.league_name,
                'total_teams': self.settings.total_teams,
                'total_rounds': self.settings.total_rounds,
                'pick_timer': self.settings.pick_timer,
                'draft_type': self.settings.draft_type,
                'scoring_type': self.settings.scoring_type,
                'roster_positions': self.settings.roster_positions,
                'draft_order': self.settings.draft_order,
                'slot_to_roster': self.settings.slot_to_roster
            },
            'status': self.status,
            'current_pick': self.current_pick,
            'current_round': self.current_round,
            'current_draft_slot': self.current_draft_slot,
            'picks': [
                {
                    'pick_number': pick.pick_number,
                    'round': pick.round,
                    'draft_slot': pick.draft_slot,
                    'player_id': pick.player_id,
                    'player_name': pick.player_name,
                    'position': pick.position,
                    'team': pick.team,
                    'roster_id': pick.roster_id,
                    'picked_by': pick.picked_by,
                    'timestamp': pick.timestamp.isoformat() if pick.timestamp else None
                }
                for pick in self.picks
            ],
            'last_pick_time': self.last_pick_time.isoformat() if self.last_pick_time else None
        } 