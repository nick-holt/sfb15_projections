# Install and load necessary packages
if (!requireNamespace("devtools", quietly = TRUE)) {
        install.packages("devtools")
}
if (!requireNamespace("nflfastR", quietly = TRUE)) {
        devtools::install_github("mrcaseb/nflfastR")
}

library(nflfastR)
library(dplyr)
library(tidyr)

# Define the scoring system
calculate_score <- function(data) {
    data %>%
        mutate(
            # Passing - updated scoring
            passing_yards_points = if_else(!is.na(passing_yards) & player_role == "passer", passing_yards * 0.04, 0), # 25 yards = 1 point
            passing_td_points = if_else(!is.na(pass_touchdown) & player_role == "passer", pass_touchdown * 6, 0),
            passing_2pt_points = if_else(!is.na(pass_2pt_conversion) & player_role == "passer", pass_2pt_conversion * 2, 0),

            # Rushing - updated scoring
            rushing_yards_points = if_else(!is.na(rushing_yards) & player_role == "rusher", rushing_yards * 0.1, 0), # 10 yards = 1 point
            rushing_td_points = if_else(!is.na(rush_touchdown) & player_role == "rusher", rush_touchdown * 6, 0),
            rushing_first_down_points = if_else(!is.na(first_down_rush) & player_role == "rusher", first_down_rush * 1, 0), # +1 point
            rushing_attempt_points = if_else(!is.na(rush_attempt) & player_role == "rusher", rush_attempt * 0.5, 0), # +0.50 points
            rushing_2pt_points = if_else(!is.na(rush_2pt_conversion) & player_role == "rusher", rush_2pt_conversion * 2, 0),

            # Receiving - updated scoring
            receiving_yards_points = if_else(!is.na(receiving_yards) & player_role == "receiver", receiving_yards * 0.1, 0), # 10 yards = 1 point
            receiving_td_points = if_else(!is.na(touchdown) & player_role %in% c("receiver"), touchdown * 6, 0),
            receiving_first_down_points = if_else(!is.na(first_down_pass) & player_role == "receiver", first_down_pass * 1, 0), # +1 point
            receiving_2pt_points = if_else(!is.na(receiving_2pt_conversion) & player_role == "receiver", receiving_2pt_conversion * 2, 0),

            # Reception scoring (position-based)
            receptions_points = case_when(
                position == "QB" & player_role == "receiver" ~ reception * 2.5,
                position == "K" & player_role == "receiver" ~ reception * 2.5,
                position == "RB" & player_role == "receiver" ~ reception * 2.5,
                position == "WR" & player_role == "receiver" ~ reception * 2.5,
                position == "TE" & player_role == "receiver" ~ reception * 2.5, # Updated to +1 for TE below
                TRUE ~ 0
            ),

            # TE Reception Bonus - updated
            te_reception_bonus_points = if_else(position == "TE" & player_role == "receiver" & !is.na(reception), reception * 1, 0), # +1 bonus for TE

            # Special Teams Player scoring
            special_teams_forced_fumble_points = if_else(!is.na(special_teams_forced_fumble) & player_role == "special_teams", special_teams_forced_fumble * 3, 0),
            special_teams_fumble_recovery_points = if_else(!is.na(special_teams_fumble_recovery) & player_role == "special_teams", special_teams_fumble_recovery * 3, 0),
            special_teams_solo_tackle_points = if_else(!is.na(special_teams_solo_tackle) & player_role == "special_teams", special_teams_solo_tackle * 2, 0),

            # Special Teams Defense
            special_teams_defense_td_points = if_else(!is.na(special_teams_defense_td) & player_role == "defense", special_teams_defense_td * 6, 0),

            # Misc
            fumble_recovery_td_points = if_else(!is.na(fumble_recovery_td), fumble_recovery_td * 6, 0),

            # Kicking (if applicable)
            extra_point_points = if_else(!is.na(extra_points_made) & player_role == "kicker", extra_points_made * 3.3, 0),
            field_goal_points = if_else(!is.na(field_goal_made_distance) & player_role == "kicker", field_goal_made_distance * 0.1, 0)
        ) %>%
        mutate(total_points = rowSums(select(., ends_with("_points")), na.rm = TRUE))
}

# Load play-by-play data for the past 10 seasons
pbp_data <- load_pbp(2014:2024)

# Inspect column names
print(colnames(pbp_data))

# Combine relevant player statistics from different columns
pbp_long <- pbp_data %>%
        pivot_longer(
                cols = c(passer_player_id, rusher_player_id, receiver_player_id, kicker_player_id, punt_returner_player_id, kickoff_returner_player_id),
                names_to = "player_role",
                values_to = "player_id",
                values_drop_na = TRUE
        ) %>%
        mutate(
                player_role = case_when(
                        player_role == "passer_player_id" ~ "passer",
                        player_role == "rusher_player_id" ~ "rusher",
                        player_role == "receiver_player_id" ~ "receiver",
                        player_role == "kicker_player_id" ~ "kicker",
                        player_role %in% c("punt_returner_player_id", "kickoff_returner_player_id") ~ "returner",
                        TRUE ~ "unknown"
                )
        )

# Filter for relevant play types and positions
filtered_data <- pbp_long %>%
        filter(week <= 17) %>% # we only care about points scored during the fantasy season
        filter(play_type %in% c("pass", "run", "kickoff", "punt", "field_goal", "extra_point")) %>%
        select(
                season, week, game_id, player_id, player_role, posteam, play_type,
                passing_yards,
                pass_touchdown,
                rushing_yards,
                rush_touchdown,
                first_down_rush,
                rush_attempt,
                receiving_yards,
                first_down_pass,
                extra_point_result,
                kick_distance,
                field_goal_result,
                return_yards,
                yards_gained,
                touchdown
        ) %>%
        mutate(field_goal_made_distance = ifelse(field_goal_result == "made", kick_distance, 0),
               extra_points_made = ifelse(extra_point_result == "made", 1, 0),
               reception = ifelse(receiving_yards > 0 & player_role == "receiver", 1, 0))


# grab player roster data with position info
roster_data <- progressr::with_progress(nflreadr::load_rosters(seasons = 2010:2024)) %>%
        filter(position %in% c("QB", "RB", "TE", "WR", "K")) %>%
        select(player_id = gsis_id, player_name = full_name, position, season) %>%
        distinct()


# Group by game and player, and calculate the aggregated statistics
aggregated_stats <- filtered_data %>%
        left_join(roster_data) %>%
        filter(!is.na(position)) %>%
        group_by(player_name, position, season, week, game_id, player_id, player_role, posteam) %>%
        summarise(across(where(is.numeric), sum, na.rm = TRUE)) %>%
        arrange(player_name)

aggregated_stats_scored <- aggregated_stats %>%
        ungroup() %>%
        calculate_score() %>%
        group_by(player_name, position, season, week, game_id) %>%
        summarise(across(where(is.numeric), sum, na.rm = TRUE))


aggregated_season_stats <- aggregated_stats_scored %>%
        group_by(player_name, position, season) %>%
        summarise(across(where(is.numeric), sum, na.rm = TRUE))


# Save to a CSV file
write.csv(aggregated_stats, "sfb14_historical_player_stats_agg.csv", row.names = FALSE)

write.csv(aggregated_season_stats, "sfb14_historical_season_player_stats_agg.csv", row.names = FALSE)
