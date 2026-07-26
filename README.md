# AI Diet Chart & Nutrition Calculator

A full-featured desktop application for personalized diet planning, nutrition tracking, 
and health management — built with Python and powered by Google's Gemini AI for 
intelligent, personalized recommendations.

## Overview

AI Diet Chart & Nutrition Calculator is a desktop health companion that combines 
traditional calculators (BMI, calorie needs, water intake) with AI-driven insights 
for meal planning, nutrition lookup, and health tips. It supports full user 
authentication (including face login), an admin management panel, and progress 
tracking with visual charts — all in a clean, healthcare-themed interface.

## Features

### Core Health Tools
- **BMI Calculator** — instant BMI computation with health category feedback
- **Calorie Calculator** — auto-calculates daily calorie needs based on user stats, 
  updates live as inputs change
- **Water Intake Calculator** — tracks daily water consumption with rolling 24-hour totals
- **Nutrition Calculator** — AI-powered nutrition lookup for foods and meals

### AI-Powered Features (Google Gemini)
- **Diet Planner** — generates personalized diet plans based on user goals and profile
- **Meal Planner** — suggests meals aligned with nutrition targets
- **AI Health Tips** — contextual health and wellness advice

### Tracking & Insights
- **Progress Tracker** — visual charts (via Matplotlib) tracking weight, calorie, 
  and nutrition trends over time
- **Dashboard** — live overview of BMI, calorie goals, water intake, streaks, 
  and recent meals
- **Exercise Recommendations** — rule-based exercise suggestions using MET formulas

### Authentication & Security
- Standard email/password login with **bcrypt** password hashing
- **Face ID login** as an alternative authentication method
- Forgot password / account recovery flow
- Session management across the app

### Admin Panel
- Full CRUD admin dashboard — manage admin accounts (add, edit, delete, search)
- Access-gated with session validation on every navigation
- Protected default admin account (cannot be deleted)

### Other
- User profile management with profile pictures
- App settings and preferences (locally stored)
- Feedback and support ticket system
- Notifications page
- Splash screen and smooth window transitions

## Tech Stack

| Component        | Technology                          |
|-------------------|--------------------------------------|
| Language          | Python                              |
| UI Framework      | CustomTkinter                       |
| Database          | MySQL (via `mysql.connector`)       |
| AI                | Google Gemini API                   |
| Charts            | Matplotlib                          |
| Password Security | bcrypt                              |
| Config Management | python-dotenv                       |

## Architecture

- One class per page (inherits `ctk.CTk`), navigated via destroy-and-relaunch
- Shared `session.py` manages logged-in user state across pages
- `database.py` centralizes all DB operations with lazy auto-migration
- `app_settings.py` stores local JSON-based user preferences
- Deep teal and mint color palette for a clean, healthcare-oriented feel

## Setup

### Prerequisites
- Python 3.x
- MySQL Server
- A Google Gemini API key

### Installation

1. Clone the repository
```bash
   git clone https://github.com/Piyush00189/AI_diet_and_nutrition_calculator.git
   cd AI_diet_and_nutrition_calculator
```

2. Create and activate a virtual environment
```bash
   python -m venv venv
   venv\Scripts\activate   # Windows
```

3. Install dependencies
```bash
   pip install -r requirements.txt
```

4. Set up the database
   - Create a MySQL database named `diet_app`
   - Import the schema: `diet_app.sql`

5. Configure environment variables
   - Create an `api.env` file in the project root
   - Add your Gemini API key and database credentials:
 GEMINI_API_KEY=your_key_here
 DB_HOST=localhost
 DB_USER=your_mysql_user
 DB_PASSWORD=your_mysql_password

6. Run the app
```bash
   python App.py
```
