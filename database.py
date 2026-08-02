"""
database.py
-----------
MySQL database layer for the AI Diet Chart & Nutrition Calculator app.

Handles the connection, one-time table creation, inserting new users
(with bcrypt-hashed passwords), resetting a user's password from the
Forgot Password page, storing user feedback from the Feedback page,
storing/checking Face ID biometric login data, the "today"/streak
lookups used by the Dashboard's live stat cards and the Nutrition
Calculator's persistent history, the AI Diet Planner's saved
plan history (view past generated plans / clear history), and the
`admins` table used by the Login page to route admin credentials to
the Admin Dashboard instead of the regular user Dashboard — including
full CRUD for admin accounts (list/search, create, update, delete)
used by the Admin Dashboard's Admin Management page.

Setup:
    1. pip install mysql-connector-python bcrypt python-dotenv
    2. Create the database once in MySQL:
           CREATE DATABASE diet_app;
    3. Create a `db.env` file next to this one with:
           DB_HOST=localhost
           DB_USER=root
           DB_PASSWORD=your_mysql_password
           DB_NAME=diet_app
           DEFAULT_ADMIN_EMAIL=admin1@gmail.com
           DEFAULT_ADMIN_PASSWORD=choose_a_strong_password
       Make sure db.env (and api.env) are listed in .gitignore.
    4. Run this file directly once to create the `users` table:
           python database.py
"""

import json
import os
from datetime import date, timedelta

import mysql.connector
from mysql.connector import errorcode
import bcrypt
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Credentials are loaded from env files, never hardcoded here.
# api.env holds the Gemini API key; db.env holds the MySQL credentials
# and the default admin login. Both must be listed in .gitignore.
# ---------------------------------------------------------------------------
load_dotenv("api.env")
load_dotenv("db.env")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME", "diet_app"),
}

# Default admin account, auto-created (if missing) every time this module
# is imported — see ensure_default_admin(). Both the email and the
# initial password come from db.env now, since a hardcoded password here
# is just as much a leaked credential as a hardcoded DB password. Change
# the password afterwards by logging in and rotating it, not by editing
# db.env, since it's only used the very first time the row is created.
# This account is also protected from deletion in the Admin Dashboard's
# Admin Management page (see delete_admin) so there's always at least
# one working admin login.
DEFAULT_ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "admin1@gmail.com")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD")
DEFAULT_ADMIN_FULL_NAME = "Admin"

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    age INT NOT NULL,
    gender VARCHAR(20) NOT NULL,
    height_cm FLOAT NOT NULL,
    weight_kg FLOAT NOT NULL,
    activity_level VARCHAR(30) NOT NULL,
    fitness_goal VARCHAR(30) NOT NULL,
    profile_picture_path VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
"""


CREATE_WATER_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS water_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(150) NOT NULL,
    log_date DATE NOT NULL,
    total_ml FLOAT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_day (email, log_date),
    FOREIGN KEY (email) REFERENCES users(email)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;
"""

CREATE_WATER_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS water_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(150) NOT NULL,
    ml FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email) REFERENCES users(email)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;
"""

CREATE_CALORIE_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS calorie_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(150) NOT NULL,
    log_date DATE NOT NULL,
    total_kcal FLOAT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_day (email, log_date),
    FOREIGN KEY (email) REFERENCES users(email)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;
"""


# food_log stores the FULL per-item nutrient breakdown (not just
# calories) so the Nutrition Calculator can reload a user's exact
# table — including protein/carbs/fat/fiber/sugar — when they reopen
# the page, instead of starting from an empty table every time.
CREATE_FOOD_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS food_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(150) NOT NULL,
    food_name VARCHAR(150) NOT NULL,
    quantity_g FLOAT NOT NULL,
    calories FLOAT NOT NULL,
    protein FLOAT NOT NULL DEFAULT 0,
    carbohydrates FLOAT NOT NULL DEFAULT 0,
    fat FLOAT NOT NULL DEFAULT 0,
    fiber FLOAT NOT NULL DEFAULT 0,
    sugar FLOAT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email) REFERENCES users(email)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;
"""


CREATE_MEAL_PLANS_TABLE = """
CREATE TABLE IF NOT EXISTS meal_plans (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(150) NOT NULL,
    day_of_week VARCHAR(10) NOT NULL,
    meal_type VARCHAR(20) NOT NULL,
    meal_description TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_slot (email, day_of_week, meal_type),
    FOREIGN KEY (email) REFERENCES users(email)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;
"""


CREATE_BMI_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS bmi_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(150) NOT NULL,
    height_cm FLOAT NOT NULL,
    weight_kg FLOAT NOT NULL,
    bmi FLOAT NOT NULL,
    category VARCHAR(30) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email) REFERENCES users(email)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;
"""


CREATE_CALORIE_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS calorie_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(150) NOT NULL,
    age INT NOT NULL,
    gender VARCHAR(20) NOT NULL,
    height_cm FLOAT NOT NULL,
    weight_kg FLOAT NOT NULL,
    activity_level VARCHAR(30) NOT NULL,
    bmr FLOAT NOT NULL,
    tdee FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email) REFERENCES users(email)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;
"""


CREATE_FEEDBACK_TABLE = """
CREATE TABLE IF NOT EXISTS feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(150) NOT NULL,
    rating TINYINT NOT NULL,
    comment TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email) REFERENCES users(email)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_feedback_rating CHECK (rating BETWEEN 1 AND 5)
) ENGINE=InnoDB;
"""


# diet_plan_history stores every AI-generated diet plan (the full input
# profile AND the full returned plan, each as JSON) so the AI Diet
# Planner's "History" panel can list and re-display past plans, and so
# "Clear History" has something well-defined to delete.
CREATE_DIET_PLAN_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS diet_plan_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(150) NOT NULL,
    profile_json TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    calorie_target INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email) REFERENCES users(email)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;
"""


# admins is a separate table from users — admin accounts have their own
# login credentials and are never mixed into the regular users list (the
# Admin Dashboard's Users/Manage Users page only ever queries `users`).
CREATE_ADMINS_TABLE = """
CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
"""


def get_connection():
    """Opens and returns a new MySQL connection using DB_CONFIG."""
    return mysql.connector.connect(**DB_CONFIG)


def create_users_table():
    """Creates the `users` table if it doesn't already exist, and makes
    sure a table created by an older version of this file has the
    profile_picture_path column too."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(CREATE_USERS_TABLE)
        conn.commit()
        cursor.close()
    finally:
        conn.close()

    _ensure_profile_picture_column()
    _ensure_biometric_columns()
    create_bmi_history_table()
    create_calorie_history_table()
    create_meal_plans_table()
    create_water_log_table()
    create_water_events_table()
    create_calorie_log_table()
    create_food_log_table()
    create_feedback_table()
    create_diet_plan_history_table()
    create_admins_table()
    ensure_default_admin()


def create_bmi_history_table():
    """Creates the `bmi_history` table if it doesn't already exist.
    Depends on `users` already existing (foreign key on email)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(CREATE_BMI_HISTORY_TABLE)
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def create_calorie_history_table():
    """Creates the `calorie_history` table if it doesn't already exist.
    Depends on `users` already existing (foreign key on email)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(CREATE_CALORIE_HISTORY_TABLE)
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def create_meal_plans_table():
    """Creates the `meal_plans` table if it doesn't already exist.
    Depends on `users` already existing (foreign key on email)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(CREATE_MEAL_PLANS_TABLE)
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def create_water_log_table():
    """Creates the `water_log` table if it doesn't already exist."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(CREATE_WATER_LOG_TABLE)
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def create_calorie_log_table():
    """Creates the `calorie_log` table if it doesn't already exist."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(CREATE_CALORIE_LOG_TABLE)
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def create_water_events_table():
    """Creates the `water_events` table if it doesn't already exist. Each
    row is one water log with its own timestamp — this is what lets
    "today's" water intake reset on a rolling 24-hour window (see
    get_water_intake_today) instead of jumping to 0 at midnight."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(CREATE_WATER_EVENTS_TABLE)
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def create_food_log_table():
    """Creates the `food_log` table if it doesn't already exist (with
    full per-item nutrient columns), and migrates an older table created
    before those nutrient columns existed. Each row is one item added in
    the Nutrition Calculator — this is what lets that page reload a
    user's exact table (calories AND macros) when they reopen it, and
    what powers the Dashboard's "Recent Meals" card with real data."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(CREATE_FOOD_LOG_TABLE)
        conn.commit()
        cursor.close()
    finally:
        conn.close()

    _ensure_food_log_nutrient_columns()


def create_feedback_table():
    """Creates the `feedback` table if it doesn't already exist.
    Depends on `users` already existing (foreign key on email)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(CREATE_FEEDBACK_TABLE)
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def create_diet_plan_history_table():
    """Creates the `diet_plan_history` table if it doesn't already exist.
    Depends on `users` already existing (foreign key on email)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(CREATE_DIET_PLAN_HISTORY_TABLE)
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def create_admins_table():
    """Creates the `admins` table if it doesn't already exist. Independent
    of `users` — no foreign key, since admin accounts aren't user
    accounts."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(CREATE_ADMINS_TABLE)
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def ensure_default_admin():
    """Creates the default admin account (DEFAULT_ADMIN_EMAIL /
    DEFAULT_ADMIN_PASSWORD, both from db.env) the first time this runs.
    Safe to call every time the app starts — does nothing if that email
    is already present in `admins` (e.g. because the password was
    changed since), and does nothing if DEFAULT_ADMIN_PASSWORD isn't set
    (so a missing db.env doesn't create an account with a None
    password)."""
    if not DEFAULT_ADMIN_PASSWORD:
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM admins WHERE email = %s LIMIT 1",
            (DEFAULT_ADMIN_EMAIL,),
        )
        exists = cursor.fetchone() is not None
        cursor.close()
    finally:
        conn.close()

    if exists:
        return

    password_hash = hash_password(DEFAULT_ADMIN_PASSWORD)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO admins (full_name, email, password_hash)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE email = email
            """,
            (DEFAULT_ADMIN_FULL_NAME, DEFAULT_ADMIN_EMAIL, password_hash),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def get_admin_by_email(email: str):
    """Returns the admin row (dict: id, full_name, email, password_hash,
    created_at) for this email, or None if it isn't an admin account.
    Used by the Login page to decide whether to route to the Admin
    Dashboard instead of the regular user Dashboard."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admins WHERE email = %s LIMIT 1", (email,))
        admin = cursor.fetchone()
        cursor.close()
        return admin
    finally:
        conn.close()


def admin_email_exists(email: str) -> bool:
    """Returns True if an admin account with this email already exists."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM admins WHERE email = %s LIMIT 1", (email,))
        exists = cursor.fetchone() is not None
        cursor.close()
        return exists
    finally:
        conn.close()


def get_all_admins(search: str = ""):
    """Returns admin accounts (id, full_name, email, created_at — never
    password_hash) as a list of dicts, oldest first so the default admin
    created by ensure_default_admin() naturally sorts to the top. If
    `search` is given, filters by full_name or email (case-insensitive
    substring match). Used by the Admin Dashboard's Admin Management
    page."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        if search:
            cursor.execute(
                """
                SELECT id, full_name, email, created_at
                FROM admins
                WHERE full_name LIKE %s OR email LIKE %s
                ORDER BY created_at ASC
                """,
                (f"%{search}%", f"%{search}%"),
            )
        else:
            cursor.execute(
                "SELECT id, full_name, email, created_at FROM admins ORDER BY created_at ASC"
            )
        rows = cursor.fetchall()
        cursor.close()
        return rows
    finally:
        conn.close()


def insert_admin(full_name: str, email: str, password: str) -> None:
    """Creates a new admin account with a bcrypt-hashed password.
    Raises ValueError if an admin with this email already exists."""
    if admin_email_exists(email):
        raise ValueError("An admin account with this email already exists.")

    password_hash = hash_password(password)

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO admins (full_name, email, password_hash)
            VALUES (%s, %s, %s)
            """,
            (full_name, email, password_hash),
        )
        conn.commit()
        cursor.close()
    except mysql.connector.IntegrityError:
        # Safety net in case of a race condition with admin_email_exists()
        raise ValueError("An admin account with this email already exists.")
    finally:
        conn.close()


def update_admin(original_email: str, full_name: str, new_email: str, new_password: str = None) -> None:
    """
    Updates an admin's name and email, identified by `original_email`;
    pass the same value for `new_email` if the email is unchanged. Pass
    `new_password` to also rotate the password (bcrypt-hashed), or leave
    it as None to keep the existing password unchanged.

    Raises ValueError if:
      - no admin account exists with `original_email`, or
      - `new_email` is already used by a *different* admin account.
    """
    if not admin_email_exists(original_email):
        raise ValueError("No admin account found with this email.")

    if new_email != original_email and admin_email_exists(new_email):
        raise ValueError("That email is already in use by another admin account.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        if new_password:
            password_hash = hash_password(new_password)
            cursor.execute(
                """
                UPDATE admins
                SET full_name = %s, email = %s, password_hash = %s
                WHERE email = %s
                """,
                (full_name, new_email, password_hash, original_email),
            )
        else:
            cursor.execute(
                "UPDATE admins SET full_name = %s, email = %s WHERE email = %s",
                (full_name, new_email, original_email),
            )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def delete_admin(email: str) -> None:
    """Deletes an admin account. Raises ValueError if `email` is the
    default admin account (DEFAULT_ADMIN_EMAIL) — that account is
    protected so there's always at least one working admin login — or if
    no admin account exists with this email."""
    if email == DEFAULT_ADMIN_EMAIL:
        raise ValueError("The default admin account can't be deleted.")

    if not admin_email_exists(email):
        raise ValueError("No admin account found with this email.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admins WHERE email = %s", (email,))
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def log_water_intake(email: str, ml_to_add: float) -> None:
    """Adds `ml_to_add` to today's running water total for this user
    (creates today's row if it doesn't exist yet), and also records a
    timestamped entry in `water_events` so intake can be reported on a
    rolling 24-hour window (see get_water_intake_today) rather than only
    resetting at the calendar-day boundary."""
    if not email_exists(email):
        raise ValueError(f"No account found for '{email}'.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO water_log (email, log_date, total_ml)
            VALUES (%s, CURDATE(), %s)
            ON DUPLICATE KEY UPDATE total_ml = total_ml + VALUES(total_ml)
            """,
            (email, ml_to_add),
        )
        cursor.execute(
            "INSERT INTO water_events (email, ml) VALUES (%s, %s)",
            (email, ml_to_add),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def log_calorie_intake(email: str, kcal_to_add: float) -> None:
    """Adds `kcal_to_add` to today's running calorie total for this user
    (creates today's row if it doesn't exist yet)."""
    if not email_exists(email):
        raise ValueError(f"No account found for '{email}'.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO calorie_log (email, log_date, total_kcal)
            VALUES (%s, CURDATE(), %s)
            ON DUPLICATE KEY UPDATE total_kcal = total_kcal + VALUES(total_kcal)
            """,
            (email, kcal_to_add),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def get_water_log(email: str, days: int = 30):
    """Returns the user's daily water totals for the last `days` days
    (oldest first) as a list of dicts: log_date, total_ml."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT log_date, total_ml FROM water_log
            WHERE email = %s AND log_date >= (CURDATE() - INTERVAL %s DAY)
            ORDER BY log_date ASC
            """,
            (email, days),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows
    finally:
        conn.close()


def get_calorie_log(email: str, days: int = 30):
    """Returns the user's daily calorie intake totals for the last `days`
    days (oldest first) as a list of dicts: log_date, total_kcal."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT log_date, total_kcal FROM calorie_log
            WHERE email = %s AND log_date >= (CURDATE() - INTERVAL %s DAY)
            ORDER BY log_date ASC
            """,
            (email, days),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows
    finally:
        conn.close()


def get_water_intake_today(email: str) -> float:
    """Returns the user's water intake over the rolling last 24 hours (not
    the calendar day), so the total naturally resets exactly 24 hours
    after each log instead of jumping to 0 at midnight. Used by the
    Dashboard's live Water Intake stat card."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COALESCE(SUM(ml), 0) FROM water_events
            WHERE email = %s AND created_at >= (NOW() - INTERVAL 24 HOUR)
            """,
            (email,),
        )
        (total,) = cursor.fetchone()
        cursor.close()
        return float(total)
    finally:
        conn.close()


def get_calories_consumed_today(email: str) -> float:
    """Returns the user's calories consumed over the rolling last 24 hours
    (not the calendar day), based on individually-timestamped food_log
    entries, so the total naturally resets exactly 24 hours after each
    logged item instead of jumping to 0 at midnight. Used by the
    Dashboard's live Calorie Goal stat card."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COALESCE(SUM(calories), 0) FROM food_log
            WHERE email = %s AND created_at >= (NOW() - INTERVAL 24 HOUR)
            """,
            (email,),
        )
        (total,) = cursor.fetchone()
        cursor.close()
        return float(total)
    finally:
        conn.close()


def insert_food_log(
    email: str,
    food_name: str,
    quantity_g: float,
    calories: float,
    protein: float = 0,
    carbohydrates: float = 0,
    fat: float = 0,
    fiber: float = 0,
    sugar: float = 0,
) -> None:
    """Records one food item added in the Nutrition Calculator — full
    nutrient breakdown included — so the page can reload it later and so
    it can show up in the Dashboard's "Recent Meals" card. Raises
    ValueError if no account with this email exists."""
    if not email_exists(email):
        raise ValueError(f"No account found for '{email}'.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO food_log
                (email, food_name, quantity_g, calories, protein, carbohydrates, fat, fiber, sugar)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (email, food_name, quantity_g, calories, protein, carbohydrates, fat, fiber, sugar),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def get_recent_food_log(email: str, limit: int = 5):
    """Returns up to `limit` of this user's most recently logged food
    items (most recent first) as a list of dicts: food_name, quantity_g,
    calories, protein, carbohydrates, fat, fiber, sugar, created_at."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT food_name, quantity_g, calories, protein, carbohydrates, fat, fiber, sugar, created_at
            FROM food_log
            WHERE email = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (email, limit),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows
    finally:
        conn.close()


def get_food_log_today(email: str):
    """Returns every food_log row created today (calendar day, oldest
    first) as a list of dicts: food_name, quantity_g, calories, protein,
    carbohydrates, fat, fiber, sugar, created_at. Used by the Nutrition
    Calculator to reload the user's exact table when they reopen the
    page, instead of starting from an empty table every time."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT food_name, quantity_g, calories, protein, carbohydrates, fat, fiber, sugar, created_at
            FROM food_log
            WHERE email = %s AND DATE(created_at) = CURDATE()
            ORDER BY created_at ASC
            """,
            (email,),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows
    finally:
        conn.close()


def clear_food_log_today(email: str) -> None:
    """Deletes today's food_log rows for this user — used by the
    Nutrition Calculator's "Clear History" button. No error if there's
    nothing to delete."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM food_log WHERE email = %s AND DATE(created_at) = CURDATE()",
            (email,),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def get_activity_streak_days(email: str) -> int:
    """Returns the user's current consecutive-day activity streak, based
    on any day that has a water_log or calorie_log entry. Today not
    having an entry yet doesn't break a streak that's still active from
    yesterday; a day with no activity at all (yesterday included) does."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT log_date FROM water_log WHERE email = %s
            UNION
            SELECT log_date FROM calorie_log WHERE email = %s
            """,
            (email, email),
        )
        rows = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()

    active_dates = {row[0] for row in rows}
    today = date.today()
    cursor_date = today if today in active_dates else today - timedelta(days=1)

    streak = 0
    while cursor_date in active_dates:
        streak += 1
        cursor_date -= timedelta(days=1)
    return streak


def upsert_meal_plan(email: str, day_of_week: str, meal_type: str, meal_description: str) -> None:
    """
    Saves (or updates, if this day/meal slot already has an entry) one
    meal plan slot for the user. Raises ValueError if no account with
    this email exists.
    """
    if not email_exists(email):
        raise ValueError(
            f"No account found for '{email}'. Log in with a real registered "
            "account before saving meal plans."
        )

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO meal_plans (email, day_of_week, meal_type, meal_description)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE meal_description = VALUES(meal_description)
            """,
            (email, day_of_week, meal_type, meal_description),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def delete_meal_plan(email: str, day_of_week: str, meal_type: str) -> None:
    """Deletes one meal plan slot, if it exists. No error if it doesn't."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM meal_plans WHERE email = %s AND day_of_week = %s AND meal_type = %s",
            (email, day_of_week, meal_type),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def get_meal_plans(email: str):
    """Returns all of the user's saved meal plan slots as a list of dicts
    with keys: day_of_week, meal_type, meal_description."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT day_of_week, meal_type, meal_description
            FROM meal_plans
            WHERE email = %s
            """,
            (email,),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows
    finally:
        conn.close()


def insert_feedback(email: str, rating: int, comment: str = "") -> None:
    """
    Saves one piece of app feedback (a 1-5 star rating plus an optional
    comment) for the given user.

    Raises ValueError if no account with this email exists, or if
    `rating` is not an integer from 1 to 5.
    """
    if not email_exists(email):
        raise ValueError(
            f"No account found for '{email}'. Log in with a real registered "
            "account before submitting feedback."
        )

    if not isinstance(rating, int) or not (1 <= rating <= 5):
        raise ValueError("Rating must be an integer between 1 and 5.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO feedback (email, rating, comment)
            VALUES (%s, %s, %s)
            """,
            (email, rating, (comment or "").strip() or None),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def get_feedback(email: str, limit: int = 10):
    """Returns up to `limit` of this user's most recent feedback
    submissions (most recent first) as a list of dicts: rating,
    comment, created_at."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT rating, comment, created_at
            FROM feedback
            WHERE email = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (email, limit),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows
    finally:
        conn.close()


def get_average_rating():
    """Returns (average_rating, total_count) across all feedback in the
    app, or (None, 0) if there's no feedback yet. Handy for an admin
    view or an 'Average rating so far' label."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT AVG(rating), COUNT(*) FROM feedback")
        avg_rating, total_count = cursor.fetchone()
        cursor.close()
        return (float(avg_rating) if avg_rating is not None else None, total_count or 0)
    finally:
        conn.close()


def enable_biometric(email: str, encoding_bytes: bytes) -> None:
    """
    Stores `encoding_bytes` (a serialized face encoding — see
    face_auth.encoding_to_bytes) for this user and flips
    biometric_enabled on, so they show up as a Face ID candidate on
    the Face Login page.

    Raises ValueError if no account with this email exists.
    """
    if not email_exists(email):
        raise ValueError(f"No account found for '{email}'.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET face_encoding = %s, biometric_enabled = 1 WHERE email = %s",
            (encoding_bytes, email),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def disable_biometric(email: str) -> None:
    """Clears the stored face encoding and flips biometric_enabled off
    for this user. No error if biometric login wasn't enabled."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET face_encoding = NULL, biometric_enabled = 0 WHERE email = %s",
            (email,),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def is_biometric_enabled(email: str) -> bool:
    """Returns True if this user currently has Face ID login enabled."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT biometric_enabled FROM users WHERE email = %s LIMIT 1", (email,)
        )
        row = cursor.fetchone()
        cursor.close()
        return bool(row and row[0])
    finally:
        conn.close()


def get_biometric_users():
    """Returns [{email, full_name, face_encoding}, ...] for every user
    who currently has Face ID login enabled. Used by the Face Login
    page to figure out whose face is in front of the camera — only
    users who explicitly opted in via Settings are ever included."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT email, full_name, face_encoding FROM users
            WHERE biometric_enabled = 1 AND face_encoding IS NOT NULL
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows
    finally:
        conn.close()


def insert_diet_plan_record(email: str, profile: dict, plan: dict) -> None:
    """Saves one AI-generated diet plan — the full input profile and the
    full returned plan (each serialized to JSON) — to this user's
    history. Used by the AI Diet Planner's "History" panel so a past
    plan can be viewed again later without regenerating it.

    Raises ValueError if no account with this email exists."""
    if not email_exists(email):
        raise ValueError(f"No account found for '{email}'.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO diet_plan_history (email, profile_json, plan_json, calorie_target)
            VALUES (%s, %s, %s, %s)
            """,
            (
                email,
                json.dumps(profile),
                json.dumps(plan),
                plan.get("calorie_target"),
            ),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def get_diet_plan_history(email: str, limit: int = 20):
    """Returns up to `limit` of this user's most recently generated AI
    diet plans (most recent first) as a list of dicts with keys: id,
    profile, plan, created_at — profile/plan are parsed back into dicts
    from their stored JSON. Rows with unreadable JSON are skipped."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, profile_json, plan_json, created_at
            FROM diet_plan_history
            WHERE email = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (email, limit),
        )
        rows = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()

    history = []
    for row in rows:
        try:
            profile = json.loads(row["profile_json"])
            plan = json.loads(row["plan_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        history.append({
            "id": row["id"],
            "profile": profile,
            "plan": plan,
            "created_at": row["created_at"],
        })
    return history


def clear_diet_plan_history(email: str) -> None:
    """Deletes all of this user's saved AI diet plan history. Used by the
    AI Diet Planner's "Clear History" button. No error if there's
    nothing to delete."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM diet_plan_history WHERE email = %s", (email,))
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def _ensure_profile_picture_column():
    """Migration step: adds profile_picture_path to a `users` table that
    was created before this column existed. Safe to call every time —
    does nothing if the column is already there."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = %s AND table_name = 'users'
              AND column_name = 'profile_picture_path'
            """,
            (DB_CONFIG["database"],),
        )
        (exists,) = cursor.fetchone()
        if not exists:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN profile_picture_path VARCHAR(255) NULL"
            )
            conn.commit()
        cursor.close()
    finally:
        conn.close()


def _ensure_biometric_columns():
    """Migration step: adds face_encoding and biometric_enabled to a
    `users` table that was created before Face ID login existed. Safe
    to call every time — does nothing if the columns are already there.

    face_encoding stores the 512-dimension InsightFace/ArcFace
    embedding (see face_auth.encoding_to_bytes) as raw bytes; biometric_enabled is a
    simple on/off flag checked by the Face Login page and by Settings."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = %s AND table_name = 'users'
              AND column_name IN ('face_encoding', 'biometric_enabled')
            """,
            (DB_CONFIG["database"],),
        )
        existing = {row[0] for row in cursor.fetchall()}

        if "face_encoding" not in existing:
            cursor.execute("ALTER TABLE users ADD COLUMN face_encoding LONGBLOB NULL")
        if "biometric_enabled" not in existing:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN biometric_enabled TINYINT(1) NOT NULL DEFAULT 0"
            )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def _ensure_food_log_nutrient_columns():
    """Migration step: adds protein/carbohydrates/fat/fiber/sugar to a
    `food_log` table that was created before this file tracked the full
    nutrient breakdown (older versions only stored calories). Safe to
    call every time — does nothing if the columns are already there."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = %s AND table_name = 'food_log'
              AND column_name IN ('protein', 'carbohydrates', 'fat', 'fiber', 'sugar')
            """,
            (DB_CONFIG["database"],),
        )
        existing = {row[0] for row in cursor.fetchall()}

        for column in ("protein", "carbohydrates", "fat", "fiber", "sugar"):
            if column not in existing:
                cursor.execute(
                    f"ALTER TABLE food_log ADD COLUMN {column} FLOAT NOT NULL DEFAULT 0"
                )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def email_exists(email: str) -> bool:
    """Returns True if a user with this email is already registered."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE email = %s LIMIT 1", (email,))
        exists = cursor.fetchone() is not None
        cursor.close()
        return exists
    finally:
        conn.close()


def hash_password(plain_password: str) -> str:
    """Hashes a password with bcrypt (includes a random salt)."""
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Checks a plain-text password against a stored bcrypt hash.
    Useful for the Login page."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), password_hash.encode("utf-8")
    )


def insert_user(
    full_name: str,
    email: str,
    password: str,
    phone: str,
    age: int,
    gender: str,
    height_cm: float,
    weight_kg: float,
    activity_level: str,
    fitness_goal: str,
) -> None:
    """
    Inserts a new user into the database.
    Raises ValueError if the email is already registered.
    Raises mysql.connector.Error for other database problems.
    """
    if email_exists(email):
        raise ValueError("An account with this email already exists.")

    password_hash = hash_password(password)

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO users
                (full_name, email, password_hash, phone, age, gender,
                 height_cm, weight_kg, activity_level, fitness_goal)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                full_name,
                email,
                password_hash,
                phone,
                age,
                gender,
                height_cm,
                weight_kg,
                activity_level,
                fitness_goal,
            ),
        )
        conn.commit()
        cursor.close()
    except mysql.connector.IntegrityError:
        # Safety net in case of a race condition with email_exists()
        raise ValueError("An account with this email already exists.")
    finally:
        conn.close()


def get_user_by_email(email: str):
    """Returns the full user row (dict) for this email, or None if not found."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s LIMIT 1", (email,))
        user = cursor.fetchone()
        cursor.close()
        return user
    finally:
        conn.close()


def update_password(email: str, new_password: str) -> None:
    """
    Hashes `new_password` with bcrypt and updates it for the given email.
    Raises ValueError if no account with this email exists.
    """
    if not email_exists(email):
        raise ValueError("No account found with this email.")

    new_hash = hash_password(new_password)

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE email = %s",
            (new_hash, email),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def update_profile(
    original_email: str,
    full_name: str,
    new_email: str,
    age: int,
    gender: str,
    height_cm: float,
    weight_kg: float,
    activity_level: str,
    fitness_goal: str,
    phone: str = None,
    profile_picture_path: str = None,
) -> None:
    """
    Updates a user's profile: name, email, phone, and the editable
    health fields. `original_email` identifies which row to update;
    `new_email` is the value to save (pass the same value as
    original_email if it's unchanged). Pass phone=None to leave the
    current phone number unchanged (e.g. for callers that don't collect
    it). Pass profile_picture_path=None to leave the current picture
    unchanged.

    Raises ValueError if:
      - no account exists with `original_email`, or
      - `new_email` is already used by a *different* account.
    """
    if not email_exists(original_email):
        raise ValueError("No account found with this email.")

    if new_email != original_email and email_exists(new_email):
        raise ValueError("That email is already in use by another account.")

    # Build the SET clause dynamically so phone and/or the profile
    # picture path are only touched when a caller actually supplies
    # them — everything else is always updated.
    set_clauses = [
        "full_name = %s", "email = %s", "age = %s", "gender = %s",
        "height_cm = %s", "weight_kg = %s", "activity_level = %s",
        "fitness_goal = %s",
    ]
    params = [
        full_name, new_email, age, gender, height_cm, weight_kg,
        activity_level, fitness_goal,
    ]

    if phone is not None:
        set_clauses.append("phone = %s")
        params.append(phone)

    if profile_picture_path is not None:
        set_clauses.append("profile_picture_path = %s")
        params.append(profile_picture_path)

    params.append(original_email)

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE users SET {', '.join(set_clauses)} WHERE email = %s",
            tuple(params),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def insert_bmi_record(email: str, height_cm: float, weight_kg: float, bmi: float, category: str) -> None:
    """Saves one BMI calculation to the user's history.
    Raises ValueError if no account with this email exists (this is
    checked explicitly so the error is clear, instead of a raw MySQL
    foreign-key exception)."""
    if not email_exists(email):
        raise ValueError(
            f"No account found for '{email}'. Log in with a real registered "
            "account before saving BMI history (this can happen if you're "
            "running this page standalone with placeholder demo data)."
        )

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO bmi_history (email, height_cm, weight_kg, bmi, category)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (email, height_cm, weight_kg, bmi, category),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def get_bmi_history(email: str, limit: int = 10):
    """Returns up to `limit` of the user's most recent BMI records
    (most recent first) as a list of dicts."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT height_cm, weight_kg, bmi, category, created_at
            FROM bmi_history
            WHERE email = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (email, limit),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows
    finally:
        conn.close()


def get_bmi_history_range(email: str, days: int = 30):
    """Returns the user's BMI/weight records from the last `days` days,
    oldest first — convenient for plotting a trend line."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT height_cm, weight_kg, bmi, category, created_at
            FROM bmi_history
            WHERE email = %s AND created_at >= (NOW() - INTERVAL %s DAY)
            ORDER BY created_at ASC
            """,
            (email, days),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows
    finally:
        conn.close()


def clear_bmi_history(email: str) -> None:
    """Deletes all of this user's saved BMI records. Used by the BMI
    Calculator's "Clear History" button. No error if there's nothing to
    delete."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bmi_history WHERE email = %s", (email,))
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def insert_calorie_record(
    email: str, age: int, gender: str, height_cm: float, weight_kg: float,
    activity_level: str, bmr: float, tdee: float,
) -> None:
    """Saves one BMR/calorie calculation to the user's history.
    Raises ValueError if no account with this email exists (checked
    explicitly so the error is clear, instead of a raw MySQL
    foreign-key exception)."""
    if not email_exists(email):
        raise ValueError(
            f"No account found for '{email}'. Log in with a real registered "
            "account before saving calorie history (this can happen if you're "
            "running this page standalone with placeholder demo data)."
        )

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO calorie_history
                (email, age, gender, height_cm, weight_kg, activity_level, bmr, tdee)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (email, age, gender, height_cm, weight_kg, activity_level, bmr, tdee),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def get_calorie_history(email: str, limit: int = 10):
    """Returns up to `limit` of the user's most recent calorie
    calculations (most recent first) as a list of dicts."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT age, gender, height_cm, weight_kg, activity_level,
                   bmr, tdee, created_at
            FROM calorie_history
            WHERE email = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (email, limit),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows
    finally:
        conn.close()


def clear_calorie_history(email: str) -> None:
    """Deletes all of this user's saved calorie calculations. Used by the
    "Clear History" button on the Daily Calorie Calculator page. No error
    if there's nothing to delete."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM calorie_history WHERE email = %s", (email,))
        conn.commit()
        cursor.close()
    finally:
        conn.close()


# Auto-run schema migrations whenever this module is imported (by
# login_page.py, profile_page.py, etc.) — not just when database.py is
# run directly. This means a column/table added here (like
# profile_picture_path or feedback) gets added to an existing database
# the next time ANY part of the app starts, instead of requiring you to
# remember to manually run `python database.py` again. This is also what
# guarantees the default admin account (see ensure_default_admin) exists
# before the Login page's first admin-credential check.
try:
    _ensure_profile_picture_column()
    _ensure_biometric_columns()
    create_bmi_history_table()
    create_calorie_history_table()
    create_meal_plans_table()
    create_water_log_table()
    create_water_events_table()
    create_calorie_log_table()
    create_food_log_table()
    create_feedback_table()
    create_diet_plan_history_table()
    create_admins_table()
    ensure_default_admin()
except mysql.connector.Error:
    # DB not reachable / not set up yet — ignore here; running
    # `python database.py` directly will surface the real error.
    pass


if __name__ == "__main__":
    # Running this file directly sets up the database table.
    if not DB_CONFIG["password"]:
        print("DB_PASSWORD is not set — check that db.env exists and is filled in.")
    else:
        try:
            create_users_table()
            print("Connected successfully. 'users' table is ready.")
            print(f"Default admin ready: {DEFAULT_ADMIN_EMAIL}")
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                print("Access denied — check db.env's DB_USER/DB_PASSWORD.")
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                print("Database does not exist — create it first with:")
                print("  CREATE DATABASE diet_app;")
            else:
                print(f"Database error: {err}")