library(shiny)
library(DT)
library(dplyr)

# Load your draft data (replace with the correct path to your CSV file)
draft_data <- read.csv("draft_strategy_output_tiered.csv")

# Define the UI
ui <- fluidPage(
        titlePanel("Fantasy Football Draft Helper"),
        
        tabsetPanel(
                tabPanel("Draft Board",
                         sidebarLayout(
                                 sidebarPanel(
                                         h4("Player Selection"),
                                         selectInput("metric", "Select Metric", choices = c("VORP", "VBD", "Draft_Value", "projected_points", "current_adp_round")),
                                         actionButton("reset", "Reset Drafted Players"),
                                         br(),
                                         br(),
                                         h4("Best Available Players by Position"),
                                         tableOutput("bestAvailableTable")
                                 ),
                                 
                                 mainPanel(
                                         h4("Player List"),
                                         DTOutput("draftTable")
                                 )
                         )
                ),
                
                tabPanel("Drafted Players",
                         h4("Drafted Players List"),
                         DTOutput("draftedTable"),
                         br(),
                         actionButton("restore", "Restore Selected Player")
                )
        )
)

# Define the server logic
server <- function(input, output, session) {
        # Reactive data frames to handle available and drafted players
        reactiveDraftData <- reactiveVal(draft_data)
        reactiveDraftedData <- reactiveVal(data.frame())
        
        # Render the data table for available players
        output$draftTable <- renderDT({
                datatable(
                        reactiveDraftData(), 
                        selection = "single", 
                        options = list(pageLength = 15)
                )
        })
        
        # Render the data table for drafted players
        output$draftedTable <- renderDT({
                datatable(
                        reactiveDraftedData(), 
                        selection = "single", 
                        options = list(pageLength = 15)
                )
        })
        
        # Observe the selected player and "cross out" when selected
        observeEvent(input$draftTable_rows_selected, {
                if (!is.null(input$draftTable_rows_selected)) {
                        selected_row <- input$draftTable_rows_selected
                        updated_data <- reactiveDraftData()
                        drafted_player <- updated_data[selected_row, ]
                        
                        # Remove from available players and add to drafted players
                        updated_data <- updated_data[-selected_row, ]
                        reactiveDraftData(updated_data)
                        reactiveDraftedData(rbind(reactiveDraftedData(), drafted_player))
                }
        })
        
        # Restore a player from drafted back to available
        observeEvent(input$restore, {
                if (!is.null(input$draftedTable_rows_selected)) {
                        selected_row <- input$draftedTable_rows_selected
                        updated_drafted <- reactiveDraftedData()
                        restored_player <- updated_drafted[selected_row, ]
                        
                        # Remove from drafted players and add back to available players
                        updated_drafted <- updated_drafted[-selected_row, ]
                        reactiveDraftedData(updated_drafted)
                        reactiveDraftData(rbind(reactiveDraftData(), restored_player))
                }
        })
        
        # Reset the drafted players
        observeEvent(input$reset, {
                reactiveDraftData(draft_data)
                reactiveDraftedData(data.frame())
        })
        
        # Show best available players by position
        output$bestAvailableTable <- renderTable({
                metric <- input$metric
                best_players <- reactiveDraftData() %>%
                        group_by(position) %>%
                        arrange(desc(!!sym(metric))) %>%
                        slice(1) %>%
                        select(player_name, position, !!sym(metric)) %>% 
                        arrange(desc(!!sym(metric))) # Arrange by the chosen metric in descending order
                        
                
                best_players
        })
}

# Run the application 
shinyApp(ui = ui, server = server)


