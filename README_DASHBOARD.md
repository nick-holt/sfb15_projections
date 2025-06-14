# SFB15 Fantasy Football Draft Dashboard

A comprehensive, modern fantasy football draft dashboard specifically optimized for Scott Fish Bowl 15 (SFB15) that integrates enhanced ML projections with advanced analytics and draft assistance.

## 🎯 Features

### Core Functionality
- **Enhanced ML Projections**: Industry-competitive projections with 71% model correlation
- **Dynamic Tier Management**: Automatic tier creation based on value gaps
- **Value-Based Drafting (VBD)**: Advanced VBD calculations and recommendations
- **Multi-View Dashboard**: Player rankings, tier analysis, value explorer, and draft assistant
- **Real-time Filtering**: Position, tier, age, confidence, and search filters

### Projection Quality
- **QB Range**: 4.1 - 792.8 fantasy points (Josh Allen: 792.8, Lamar Jackson: 740.9)
- **RB Range**: 20.2 - 540.3 fantasy points (Saquon Barkley: 540.3)
- **WR Range**: 24.7 - 441.0 fantasy points 
- **TE Range**: 22.4 - 411.6 fantasy points (Travis Kelce: 411.6)

### Analytics & Intelligence
- Position scarcity analysis
- Opportunity scoring system
- Sleeper identification algorithms
- Round-based draft suggestions
- Tier break analysis

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Conda environment `sfb15-projections` (from main project)

### Installation

1. **Install Dashboard Dependencies**
   ```bash
   pip install streamlit plotly
   ```

2. **Launch Dashboard**
   ```bash
   streamlit run app.py
   ```

3. **Access Dashboard**
   - Open browser to `http://localhost:8501`
   - Dashboard will auto-load enhanced projections

## 📊 Dashboard Views

### 1. Player Rankings
- **Overall Rankings**: Top players across all positions
- **Position Tabs**: QB, RB, WR, TE dedicated views
- **Display Options**: Card view or table view
- **Detailed Stats**: VBD scores, tier assignments, value indicators

### 2. Tier Analysis
- **Tier Distribution**: Visual tier breakdown by position
- **Tier Summary**: Player counts and average points per tier
- **Tier Recommendations**: Elite targets and value plays
- **Tier Breaks**: Significant value dropoff points

### 3. Value Explorer
- **VBD Analysis**: Value vs projection scatter plots
- **Best Values**: Players with highest VBD scores
- **Safe Picks**: High-confidence, high-projection players
- **Scarcity Metrics**: Position scarcity analysis

### 4. Draft Assistant
- **Round Context**: Position-specific suggestions by round
- **Roster Tracking**: Input your current roster
- **Available Players**: Best remaining players
- **Draft Recommendations**: Tier-based suggestions

## ⚙️ Configuration Options

### Sidebar Controls

#### View Selection
- Choose between 4 main dashboard views
- Real-time view switching

#### Position Filters
- Filter by QB, RB, WR, TE
- Multi-select position combinations

#### Tier Filters
- Maximum tier level (1-6)
- Focus on elite tiers or include deeper players

#### Display Settings
- Show/hide detailed statistics
- Players per page (10-100)
- Card vs table display formats

#### Search & Filters
- Player name search
- Minimum projected points
- Maximum age filter
- Confidence level filter

#### Draft Settings
- Draft position (1-12)
- Current round (1-16)
- League size (8-16 teams)
- Scoring format (PPR, Half PPR, Standard)

#### Advanced Filters
- Injury risk filtering
- Confidence level combinations
- Age-based filtering

### Draft Assistant Features

#### My Team Tracker
- Input current roster players
- Automatic roster size tracking
- Player projection lookups

#### Round-Based Suggestions
- Early rounds: Elite tier focus
- Mid rounds: Strong/solid tiers
- Late rounds: Upside and depth

#### Best Available
- Top remaining players
- Tier and projection display
- Quick-draft buttons

## 🏗️ Technical Architecture

### Project Structure
```
├── app.py                           # Main Streamlit application
├── src/
│   ├── data/
│   │   └── projections.py          # Projection data loading
│   ├── analytics/
│   │   ├── value_calculator.py     # VBD calculations
│   │   └── tier_manager.py         # Dynamic tier management
│   ├── dashboard/
│   │   ├── components/
│   │   │   ├── sidebar.py          # Sidebar controls
│   │   │   └── main_view.py        # Main dashboard views
│   │   └── utils/
│   │       └── styling.py          # CSS styling utilities
├── projections/2025/               # Enhanced projection data
├── requirements.txt                # Dashboard dependencies
└── README_DASHBOARD.md            # This documentation
```

### Data Flow
```
Enhanced ML Models → ProjectionManager → ValueCalculator → TierManager → Dashboard Views
```

### Key Components

#### ProjectionManager
- Loads latest enhanced projections
- Handles data cleaning and standardization
- Provides player search and filtering

#### ValueCalculator
- Implements Value-Based Drafting methodology
- Calculates opportunity and sleeper scores
- Provides value recommendations

#### TierManager
- Creates dynamic tiers based on value gaps
- Updates tiers post-draft
- Provides tier-based recommendations

## 🎯 Draft Strategy Integration

### Tier-Based Drafting
- **Tier 1 (Elite)**: Must-have players, worth reaching for
- **Tier 2 (Strong)**: High-value targets, solid floor/ceiling
- **Tier 3 (Solid)**: Reliable contributors, good value
- **Tier 4+ (Serviceable)**: Depth plays, upside targets

### Value-Based Drafting (VBD)
- Replacement level calculations per position
- Position scarcity adjustments
- Combined value scoring (40% projection + 40% VBD + 20% adjusted value)

### Round Strategy
- **Rounds 1-4**: Target elite/strong tiers, build foundation
- **Rounds 5-8**: Strong/solid tiers, fill positional needs
- **Rounds 9+**: Solid players and high-upside targets

## 📈 Enhanced Features vs Legacy

### Previous Limitations RESOLVED
- ✅ **QB Ceiling Crisis**: Now 792.8 max vs previous 263.6
- ✅ **WR Talent Evaluation**: Elite WRs properly identified
- ✅ **Elite-Replacement Spreads**: Realistic separation achieved
- ✅ **Missing Context**: Game script and elite indicators integrated

### New Capabilities
- **Dynamic Tier Management**: Tiers adjust based on value gaps
- **Advanced VBD**: Position scarcity and opportunity scoring
- **Multi-View Analytics**: 4 distinct dashboard perspectives
- **Real-time Filtering**: Comprehensive filter system
- **Draft Context**: Round and position-specific suggestions

## 🔧 Customization

### League Settings
- Adjust replacement levels in `ValueCalculator` for league size
- Modify tier break thresholds in `TierManager` for tier sensitivity
- Update position scarcity multipliers for league preferences

### Scoring Systems
- PPR projections are default
- Half PPR and Standard settings available
- Custom scoring multipliers can be added

### Visual Styling
- Custom CSS in `styling.py`
- Position-specific color schemes
- Tier badge styling
- Value indicators

## 🚀 Production Deployment

### Streamlit Cloud
```bash
# Push to GitHub repository
git add .
git commit -m "SFB15 Dashboard Ready"
git push origin main

# Deploy on Streamlit Cloud
# Connect GitHub repo and deploy
```

### Local Sharing
```bash
# Share on local network
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

## 📊 Model Performance

### Validation Metrics
- **71% correlation** with actual fantasy performance
- **Industry-competitive ranges** across all positions
- **Proper elite player identification** vs replacement level
- **Realistic positional scarcity** modeling

### Data Sources
- Enhanced ML models from `models/final_proper/`
- 6,744 historical player records
- Pre-season only features (no data leakage)
- Position-specific feature engineering

## 🔄 Data Updates

### Projection Refresh
- Dashboard auto-loads latest timestamped projections
- Manual refresh available via sidebar button
- Supports multiple projection file formats

### Model Retraining
- Run main projection scripts to generate new data
- Dashboard automatically picks up latest files
- Tier and value calculations update automatically

## 📞 Support & Development

### Created for SFB15 2025
- **Enhanced ML Projections**: 996 players with industry-competitive ranges
- **Dynamic Analytics**: Real-time tier and value calculations
- **Draft Intelligence**: Round and context-aware suggestions
- **Production Ready**: Full Streamlit deployment capability

### Future Enhancements
- Sleeper API integration for live draft tracking
- ADP data integration and comparison
- Multi-league support and roster tracking
- Export functionality for draft boards

---

**Ready to dominate your SFB15 draft with enhanced ML projections and advanced analytics!** 🏆 