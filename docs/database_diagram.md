# Proglem - Database Architecture

This document outlines the relational structure of the Proglem platform database.

## Entity Relationship Diagram (ERD)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#a855f7', 'primaryTextColor': '#fff', 'primaryBorderColor': '#a855f7', 'lineColor': '#991b1b', 'secondaryColor': '#09060d', 'tertiaryColor': '#120c1a' }}}%%
erDiagram
    USERS ||--o{ CV_CATALOG : creates
    USERS ||--o{ GODOT_GAMES : uploads
    USERS ||--o{ GAME_LIKES : likes
    USERS ||--o{ GAME_COMMENTS : writes
    USERS ||--o{ CHAT_MESSAGES : sends
    
    GAME_JAMS ||--o{ GODOT_GAMES : contains
    GAME_JAMS ||--o{ CHAT_ROOMS : has_chat
    
    GODOT_GAMES ||--o{ GAME_LIKES : received
    GODOT_GAMES ||--o{ GAME_COMMENTS : commented_on
    
    CHAT_ROOMS ||--o{ CHAT_MESSAGES : holds

    USERS {
        int id PK
        string username
        string email
        string password_hash
        boolean is_admin
        datetime created_at
        json preferences
    }

    CV_CATALOG {
        int id PK
        int user_id FK
        string title
        string location
        string summary
        json cv_data
        text custom_htmx
        string photo_url
        string github_url
        datetime created_at
    }

    GAME_JAMS {
        int id PK
        string title
        string theme
        datetime start_time
        datetime end_time
        string youtube_url
        string image_url
    }

    GODOT_GAMES {
        int id PK
        int user_id FK
        int jam_id FK
        string title
        string description
        string game_url
        string icon_url
        string github_url
        string validation_status
        int views
        datetime created_at
    }

    CHAT_ROOMS {
        int id PK
        string name
        int jam_id FK
        boolean is_enabled
        datetime created_at
    }

    CHAT_MESSAGES {
        int id PK
        int user_id FK
        int room_id FK
        string content
        string image_url
        datetime created_at
    }

    ANALYTICS_LOGS {
        int id PK
        string method
        string path
        string visitor_id
        boolean is_htmx
        int status_code
        int duration_ms
        datetime created_at
    }

    AI_SYSTEM_LOGS {
        int id PK
        string event_type
        string status
        string message
        datetime created_at
    }

    SYSTEM_TASKS {
        string id PK
        string user_id
        string task_type
        json payload
        string status
        text result
        datetime created_at
    }
```

## Visual Representations

### 1. Detailed Entity Relationship Diagram
This is a high-fidelity rendering of the actual database schema, following the project's **60-30-10** design system.

![Detailed Database ERD](assets/database_erd.png)

*   **60% (Base)**: Deep Blackcurrant (`#09060d`) - Background
*   **30% (Primary)**: Vibrant Purple (`#a855f7`) - Table Headers & Accents
*   **10% (Contrast)**: Crimson Red (`#991b1b`) - Relationship Connectors

### 2. Conceptual Architecture
A high-level visualization of the platform's module interconnectedness.

![Conceptual Database Architecture](assets/database_architecture.png)

> [!NOTE]
> The Mermaid ERD at the top of this document is the live-synced reference for development. The images above provide a professional visual overview for documentation and presentation purposes.
