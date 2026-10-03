from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import date, timedelta, datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os


app = Flask(__name__)


# Secret key is required for Flask login sessions.
# For deployment, set a real SECRET_KEY environment variable.
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "study-pal-development-secret-key-change-this"
)


DB_NAME = "study_planner.db"


# ==================================================
# DATABASE HELPER
# ==================================================

def get_db():

    connection = sqlite3.connect(DB_NAME)
    connection.row_factory = sqlite3.Row

    return connection


def init_db():

    connection = get_db()
    cursor = connection.cursor()

    # ==================================================
    # USERS
    # ==================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL,
            daily_goal REAL DEFAULT 4.0
        )
    """)

    # Add daily_goal to an older users table
    try:

        cursor.execute("""
            ALTER TABLE users
            ADD COLUMN daily_goal REAL DEFAULT 4.0
        """)

    except sqlite3.OperationalError:
        pass


    # ==================================================
    # STUDY PLANS
    # ==================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS study_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_date TEXT,
            study_hours INTEGER,
            difficulty TEXT,
            days_left INTEGER
        )
    """)


    # ==================================================
    # TASKS
    # ==================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER,
            day INTEGER,
            subject TEXT,
            completed INTEGER DEFAULT 0
        )
    """)


    # ==================================================
    # STUDY PLAN MIGRATIONS
    # ==================================================

    try:

        cursor.execute("""
            ALTER TABLE study_plans
            ADD COLUMN user_id INTEGER
        """)

    except sqlite3.OperationalError:
        pass


    try:

        cursor.execute("""
            ALTER TABLE study_plans
            ADD COLUMN created_date TEXT
        """)

    except sqlite3.OperationalError:
        pass


    # ==================================================
    # TASK MIGRATIONS
    # ==================================================

    columns = [

        ("task_type", "TEXT"),

        ("description", "TEXT"),

        ("planned_hours", "REAL"),

        ("actual_hours", "REAL DEFAULT 0"),

        ("confidence", "TEXT DEFAULT 'Medium'"),

        ("reason", "TEXT"),

        ("completed_date", "TEXT"),

        ("notes", "TEXT"),

        ("start_time", "TEXT"),

        ("end_time", "TEXT"),

        ("reminder_time", "TEXT"),

        ("reminder_enabled", "INTEGER DEFAULT 0")

    ]


    for column_name, column_type in columns:

        try:

            cursor.execute(
                f"ALTER TABLE task_progress "
                f"ADD COLUMN {column_name} {column_type}"
            )

        except sqlite3.OperationalError:
            pass


    connection.commit()
    connection.close()


# ==================================================
# AUTHENTICATION
# ==================================================

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:

            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


def current_user_id():

    return session.get("user_id")


# ==================================================
# REGISTER
# ==================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if "user_id" in session:

        return redirect(url_for("home"))


    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )


        if not username or not email or not password:

            flash(
                "Please fill in all fields.",
                "error"
            )

            return render_template("register.html")


        if len(username) < 3:

            flash(
                "Username must contain at least 3 characters.",
                "error"
            )

            return render_template("register.html")


        if len(password) < 6:

            flash(
                "Password must contain at least 6 characters.",
                "error"
            )

            return render_template("register.html")


        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "error"
            )

            return render_template("register.html")


        connection = get_db()
        cursor = connection.cursor()


        cursor.execute("""
            SELECT id
            FROM users
            WHERE username = ?
            OR email = ?
        """, (
            username,
            email
        ))


        existing_user = cursor.fetchone()


        if existing_user:

            connection.close()

            flash(
                "Username or email is already registered.",
                "error"
            )

            return render_template("register.html")


        hashed_password = generate_password_hash(
            password
        )


        cursor.execute("""
            INSERT INTO users
            (
                username,
                email,
                password,
                created_at,
                daily_goal
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            username,
            email,
            hashed_password,
            datetime.now().isoformat(
                timespec="seconds"
            ),
            4.0
        ))


        new_user_id = cursor.lastrowid


        # If this is the first account created,
        # assign old single-user plans to this account.
        cursor.execute("""
            SELECT COUNT(*)
            FROM users
        """)

        user_count = cursor.fetchone()[0]


        if user_count == 1:

            cursor.execute("""
                UPDATE study_plans
                SET user_id = ?
                WHERE user_id IS NULL
            """, (
                new_user_id,
            ))


        connection.commit()
        connection.close()


        flash(
            "Account created successfully. Please log in.",
            "success"
        )

        return redirect(url_for("login"))


    return render_template("register.html")


# ==================================================
# LOGIN
# ==================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if "user_id" in session:

        return redirect(url_for("home"))


    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )


        connection = get_db()
        cursor = connection.cursor()


        cursor.execute("""
            SELECT
                id,
                username,
                password
            FROM users
            WHERE email = ?
        """, (
            email,
        ))


        user = cursor.fetchone()

        connection.close()


        if user and check_password_hash(
            user["password"],
            password
        ):

            session.clear()

            session["user_id"] = user["id"]

            session["username"] = user["username"]

            return redirect(url_for("home"))


        flash(
            "Invalid email or password.",
            "error"
        )


    return render_template("login.html")


# ==================================================
# LOGOUT
# ==================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ==================================================
# UPDATE DAILY STUDY GOAL
# ==================================================

@app.route("/update-daily-goal", methods=["POST"])
@login_required
def update_daily_goal():

    goal = request.form.get(
        "daily_goal"
    )


    if not goal:

        return "error"


    try:

        goal = float(goal)

        if goal <= 0 or goal > 24:

            return "error"


    except ValueError:

        return "error"


    connection = get_db()
    cursor = connection.cursor()


    cursor.execute("""
        UPDATE users
        SET daily_goal = ?
        WHERE id = ?
    """, (
        goal,
        current_user_id()
    ))


    connection.commit()
    connection.close()


    return redirect(url_for("home"))


# ==================================================
# STUDY STREAK
# ==================================================

def get_study_streak(user_id):

    connection = get_db()
    cursor = connection.cursor()


    cursor.execute("""
        SELECT DISTINCT tp.completed_date
        FROM task_progress tp
        JOIN study_plans sp
            ON tp.plan_id = sp.id
        WHERE sp.user_id = ?
        AND tp.completed = 1
        AND tp.completed_date IS NOT NULL
        ORDER BY tp.completed_date DESC
    """, (
        user_id,
    ))


    rows = cursor.fetchall()

    connection.close()


    completed_dates = []


    for row in rows:

        try:

            completed_dates.append(
                date.fromisoformat(
                    row["completed_date"]
                )
            )

        except (ValueError, TypeError):

            continue


    if not completed_dates:

        return 0


    today = date.today()

    latest_study_date = completed_dates[0]


    if latest_study_date < today - timedelta(days=1):

        return 0


    current_date = latest_study_date

    streak = 0


    for completed_date in completed_dates:

        if completed_date == current_date:

            streak += 1

            current_date -= timedelta(days=1)

        else:

            break


    return streak


def get_weekly_study_days(user_id):

    connection = get_db()
    cursor = connection.cursor()


    cursor.execute("""
        SELECT DISTINCT tp.completed_date
        FROM task_progress tp
        JOIN study_plans sp
            ON tp.plan_id = sp.id
        WHERE sp.user_id = ?
        AND tp.completed = 1
        AND tp.completed_date IS NOT NULL
    """, (
        user_id,
    ))


    rows = cursor.fetchall()

    connection.close()


    completed_dates = set()


    for row in rows:

        try:

            completed_dates.add(
                date.fromisoformat(
                    row["completed_date"]
                )
            )

        except (ValueError, TypeError):

            continue


    today = date.today()

    weekly_days = []


    for i in range(6, -1, -1):

        current_date = today - timedelta(
            days=i
        )


        weekly_days.append({

            "date": current_date,

            "day": current_date.strftime(
                "%a"
            ).upper(),

            "completed":
                current_date in completed_dates

        })


    return weekly_days


# ==================================================
# HOME / DASHBOARD
# ==================================================

@app.route("/")
@login_required
def home():

    user_id = current_user_id()

    connection = get_db()
    cursor = connection.cursor()


    # ==================================================
    # DAILY STUDY GOAL
    # ==================================================

    cursor.execute("""
        SELECT COALESCE(daily_goal, 4.0)
        FROM users
        WHERE id = ?
    """, (
        user_id,
    ))


    result = cursor.fetchone()


    if result:

        daily_goal = result[0] or 4.0

    else:

        daily_goal = 4.0


    daily_goal = round(
        float(daily_goal),
        1
    )


    # ==================================================
    # BASIC DASHBOARD STATISTICS
    # ==================================================

    cursor.execute("""
        SELECT COUNT(*)
        FROM study_plans
        WHERE user_id = ?
    """, (
        user_id,
    ))


    total_plans = cursor.fetchone()[0]


    cursor.execute("""
        SELECT COALESCE(SUM(tp.planned_hours), 0)
        FROM task_progress tp
        JOIN study_plans sp
            ON tp.plan_id = sp.id
        WHERE sp.user_id = ?
    """, (
        user_id,
    ))


    total_planned_hours = cursor.fetchone()[0]


    cursor.execute("""
        SELECT COUNT(*)
        FROM task_progress tp
        JOIN study_plans sp
            ON tp.plan_id = sp.id
        WHERE sp.user_id = ?
        AND tp.completed = 1
    """, (
        user_id,
    ))


    completed_tasks = cursor.fetchone()[0]


    cursor.execute("""
        SELECT COUNT(*)
        FROM task_progress tp
        JOIN study_plans sp
            ON tp.plan_id = sp.id
        WHERE sp.user_id = ?
    """, (
        user_id,
    ))


    total_tasks = cursor.fetchone()[0]


    completion_rate = (

        round(
            (
                completed_tasks /
                total_tasks
            ) * 100,
            1
        )

        if total_tasks > 0

        else 0
    )


    # ==================================================
    # LATEST PLAN
    # ==================================================

    cursor.execute("""
        SELECT
            id,
            created_date,
            days_left
        FROM study_plans
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (
        user_id,
    ))


    latest_plan = cursor.fetchone()


    # ==================================================
    # SUBJECT PROGRESS
    # ==================================================

    subject_progress = []


    if latest_plan:

        latest_plan_id = latest_plan["id"]


        cursor.execute("""
            SELECT
                subject,
                COUNT(*) AS total_tasks,
                SUM(
                    CASE
                        WHEN completed = 1 THEN 1
                        ELSE 0
                    END
                ) AS completed_tasks,
                COALESCE(
                    SUM(planned_hours),
                    0
                ) AS planned_hours,
                COALESCE(
                    SUM(actual_hours),
                    0
                ) AS actual_hours
            FROM task_progress
            WHERE plan_id = ?
            GROUP BY subject
            ORDER BY subject
        """, (
            latest_plan_id,
        ))


        subject_rows = cursor.fetchall()


        for row in subject_rows:

            subject_total_tasks = (
                row["total_tasks"]
            )

            subject_completed_tasks = (
                row["completed_tasks"] or 0
            )


            subject_percentage = (

                round(
                    (
                        subject_completed_tasks /
                        subject_total_tasks
                    ) * 100,
                    1
                )

                if subject_total_tasks > 0

                else 0
            )


            subject_progress.append({

                "subject":
                    row["subject"],

                "percentage":
                    subject_percentage,

                "completed_tasks":
                    subject_completed_tasks,

                "total_tasks":
                    subject_total_tasks,

                "planned_hours":
                    round(
                        row["planned_hours"] or 0,
                        1
                    ),

                "actual_hours":
                    round(
                        row["actual_hours"] or 0,
                        1
                    )

            })


    # ==================================================
    # TODAY
    # ==================================================

    today = date.today()

    today_tasks = []

    today_day = None

    today_completed = 0

    today_total = 0


    # ==================================================
    # TODAY'S ACTUAL STUDY HOURS
    # ==================================================

    cursor.execute("""
        SELECT COALESCE(SUM(tp.actual_hours), 0)
        FROM task_progress tp
        JOIN study_plans sp
            ON tp.plan_id = sp.id
        WHERE sp.user_id = ?
        AND sp.created_date IS NOT NULL
        AND date(
            sp.created_date,
            '+' || (tp.day - 1) || ' days'
        ) = ?
    """, (
        user_id,
        today.isoformat()
    ))


    today_actual_hours = (
        cursor.fetchone()[0] or 0
    )


    today_actual_hours = round(
        float(today_actual_hours),
        1
    )


    # ==================================================
    # DAILY GOAL PROGRESS
    # ==================================================

    daily_goal_percentage = (

        round(
            (
                today_actual_hours /
                daily_goal
            ) * 100,
            1
        )

        if daily_goal > 0

        else 0
    )


    daily_goal_percentage = min(
        daily_goal_percentage,
        100
    )


    remaining_goal_hours = round(

        max(
            daily_goal -
            today_actual_hours,
            0
        ),

        1
    )


    # ==================================================
    # TODAY'S TASKS
    # ==================================================

    if latest_plan and latest_plan["created_date"]:

        plan_id = latest_plan["id"]


        try:

            created_date = date.fromisoformat(
                latest_plan["created_date"]
            )

        except (ValueError, TypeError):

            created_date = today


        days_left = latest_plan["days_left"]


        today_day = (
            today - created_date
        ).days + 1


        if 1 <= today_day <= days_left:

            cursor.execute("""
                SELECT
                    id,
                    subject,
                    task_type,
                    description,
                    planned_hours,
                    actual_hours,
                    confidence,
                    completed,
                    notes,
                    start_time,
                    end_time,
                    reminder_time,
                    reminder_enabled
                FROM task_progress
                WHERE plan_id = ?
                AND day = ?
                ORDER BY id
            """, (
                plan_id,
                today_day
            ))


            tasks = cursor.fetchall()


            for task in tasks:

                today_tasks.append({

                    "task_id":
                        task["id"],

                    "subject":
                        task["subject"],

                    "task_type":
                        task["task_type"],

                    "description":
                        task["description"],

                    "planned_hours":
                        task["planned_hours"] or 0,

                    "actual_hours":
                        task["actual_hours"] or 0,

                    "confidence":
                        task["confidence"] or "Medium",

                    "completed":
                        task["completed"],

                    "notes":
                        task["notes"] or "",

                    "start_time":
                        task["start_time"] or "",

                    "end_time":
                        task["end_time"] or "",

                    "reminder_time":
                        task["reminder_time"] or "",

                    "reminder_enabled":
                        task["reminder_enabled"] or 0

                })


            today_total = len(
                today_tasks
            )


            today_completed = sum(

                1

                for task in today_tasks

                if task["completed"] == 1

            )


    # ==================================================
    # STUDY STREAK
    # ==================================================

    study_streak = get_study_streak(
        user_id
    )


    weekly_study_days = (
        get_weekly_study_days(
            user_id
        )
    )


    # ==================================================
    # WEEKLY COMPLETION
    # ==================================================

    week_start = (
        today -
        timedelta(days=6)
    )


    cursor.execute("""
        SELECT
            COUNT(*),
            SUM(
                CASE
                    WHEN tp.completed = 1 THEN 1
                    ELSE 0
                END
            )
        FROM task_progress tp
        JOIN study_plans sp
            ON tp.plan_id = sp.id
        WHERE sp.user_id = ?
        AND sp.created_date IS NOT NULL
        AND date(
            sp.created_date,
            '+' || (tp.day - 1) || ' days'
        ) BETWEEN ? AND ?
    """, (
        user_id,
        week_start.isoformat(),
        today.isoformat()
    ))


    weekly_row = cursor.fetchone()


    weekly_total = (
        weekly_row[0] or 0
    )

    weekly_completed = (
        weekly_row[1] or 0
    )


    weekly_completion = (

        round(
            (
                weekly_completed /
                weekly_total
            ) * 100,
            1
        )

        if weekly_total > 0

        else 0
    )


    # ==================================================
    # TOTAL ACTUAL HOURS
    # ==================================================

    cursor.execute("""
        SELECT COALESCE(SUM(tp.actual_hours), 0)
        FROM task_progress tp
        JOIN study_plans sp
            ON tp.plan_id = sp.id
        WHERE sp.user_id = ?
    """, (
        user_id,
    ))


    total_actual_hours = (
        cursor.fetchone()[0] or 0
    )


    total_actual_hours = round(
        float(total_actual_hours),
        1
    )


    # ==================================================
    # ACHIEVEMENTS
    # ==================================================

    achievements = [

        {
            "icon": "🥇",
            "title": "First Plan Created",
            "description":
                "Create your first study plan",
            "unlocked":
                total_plans >= 1
        },

        {
            "icon": "🔥",
            "title": "7-Day Streak",
            "description":
                "Study for 7 consecutive days",
            "unlocked":
                study_streak >= 7
        },

        {
            "icon": "📚",
            "title": "10 Tasks Completed",
            "description":
                "Complete 10 study tasks",
            "unlocked":
                completed_tasks >= 10
        },

        {
            "icon": "⏱️",
            "title": "10 Hours Studied",
            "description":
                "Study for 10 total hours",
            "unlocked":
                total_actual_hours >= 10
        },

        {
            "icon": "🎯",
            "title": "90% Weekly Completion",
            "description":
                "Complete at least 90% of this week's tasks",
            "unlocked":
                weekly_completion >= 90
        }

    ]


    connection.close()


    # ==================================================
    # SEND DATA TO TEMPLATE
    # ==================================================

    return render_template(

        "index.html",

        username=session.get(
            "username",
            "Student"
        ),

        daily_goal=daily_goal,

        today_actual_hours=
            today_actual_hours,

        daily_goal_percentage=
            daily_goal_percentage,

        remaining_goal_hours=
            remaining_goal_hours,

        total_plans=
            total_plans,

        total_planned_hours=
            round(
                total_planned_hours or 0,
                1
            ),

        completed_tasks=
            completed_tasks,

        completion_rate=
            completion_rate,

        total_tasks=
            total_tasks,

        study_streak=
            study_streak,

        weekly_study_days=
            weekly_study_days,

        achievements=
            achievements,

        subject_progress=
            subject_progress,

        today_tasks=
            today_tasks,

        today_day=
            today_day,

        today_completed=
            today_completed,

        today_total=
            today_total

    )


# ==================================================
# CONFIDENCE
# ==================================================

def get_confidence_weight(confidence):

    if confidence == "Low":

        return 1.5


    if confidence == "High":

        return 0.75


    return 1.0


def get_subject_confidence(
    subject,
    user_id
):

    connection = get_db()
    cursor = connection.cursor()


    cursor.execute("""
        SELECT tp.confidence
        FROM task_progress tp
        JOIN study_plans sp
            ON tp.plan_id = sp.id
        WHERE tp.subject = ?
        AND sp.user_id = ?
        ORDER BY tp.id DESC
        LIMIT 1
    """, (
        subject,
        user_id
    ))


    result = cursor.fetchone()

    connection.close()


    if result and result["confidence"]:

        return result["confidence"]


    return "Medium"


# ==================================================
# GENERATE SMART TASK DETAILS
# ==================================================

def generate_task_details(
    subject,
    difficulty,
    day,
    subject_index,
    days_left,
    study_hours,
    user_id
):

    task_types = [

        "Learn Concept",

        "Practice Problems",

        "Application",

        "Revision",

        "Test Yourself",

        "Important Questions"

    ]


    task_type = task_types[
        (
            (day - 1) +
            subject_index
        ) % len(task_types)
    ]


    subject_topics = {

        "Java": [

            "classes and objects",

            "methods and constructors",

            "inheritance",

            "polymorphism",

            "exception handling",

            "collections"

        ],

        "DBMS": [

            "database fundamentals",

            "ER diagrams",

            "SQL queries",

            "normalization",

            "JOIN operations",

            "transactions"

        ],

        "CN": [

            "OSI model",

            "TCP/IP model",

            "IP addressing",

            "TCP and UDP",

            "routing",

            "network security"

        ],

        "Python": [

            "variables and data types",

            "functions",

            "lists and dictionaries",

            "loops",

            "file handling",

            "exception handling"

        ],

        "C": [

            "variables and data types",

            "functions",

            "arrays",

            "pointers",

            "structures",

            "file handling"

        ]

    }


    topics = subject_topics.get(

        subject,

        [

            "basic concepts",

            "important topics",

            "problem solving",

            "key definitions",

            "important questions",

            "revision"

        ]

    )


    topic = topics[
        (
            (day - 1) +
            subject_index
        ) % len(topics)
    ]


    descriptions = {

        "Learn Concept":
            f"Study and understand {topic} in {subject}. "
            f"Focus on the main concepts and examples.",

        "Practice Problems":
            f"Solve practice problems related to "
            f"{topic} in {subject}.",

        "Application":
            f"Apply your knowledge of {topic} "
            f"in {subject} using examples or practical problems.",

        "Revision":
            f"Review {topic} in {subject}. "
            f"Go through your notes, examples, and key points.",

        "Test Yourself":
            f"Test yourself on {topic} in {subject} "
            f"without looking at your notes.",

        "Important Questions":
            f"Practice important exam questions "
            f"related to {topic} in {subject}."

    }


    confidence = get_subject_confidence(
        subject,
        user_id
    )


    base_hours = study_hours / 2


    hours = round(

        base_hours *
        get_confidence_weight(
            confidence
        ),

        1
    )


    if hours < 0.5:

        hours = 0.5


    reason = (

        f"{subject} is scheduled for {hours} hours "
        f"because your confidence is {confidence} "
        f"and the exam is in {days_left} days. "
        f"Today's focus is {task_type.lower()}."

    )


    if difficulty == "Hard":

        reason += (

            " Since the difficulty is Hard, extra "
            "attention should be given to "
            "understanding and practice."

        )


    elif difficulty == "Medium":

        reason += (

            " Since the difficulty is Medium, "
            "balance learning and practice."

        )


    else:

        reason += (

            " Since the difficulty is Easy, "
            "focus on understanding the fundamentals."

        )


    return {

        "task_type":
            task_type,

        "description":
            descriptions[task_type],

        "hours":
            hours,

        "reason":
            reason,

        "confidence":
            confidence

    }


# ==================================================
# UPDATE TASK
# ==================================================

@app.route(
    "/update-task",
    methods=["POST"]
)
@login_required
def update_task():

    task_id = request.form.get(
        "task_id"
    )

    completed = request.form.get(
        "completed"
    )


    if not task_id:

        return "error"


    connection = get_db()
    cursor = connection.cursor()


    # Make sure task belongs to logged-in user
    cursor.execute("""
        SELECT tp.id
        FROM task_progress tp
        JOIN study_plans sp
            ON tp.plan_id = sp.id
        WHERE tp.id = ?
        AND sp.user_id = ?
    """, (
        task_id,
        current_user_id()
    ))


    if not cursor.fetchone():

        connection.close()

        return "unauthorized", 403


    if completed == "1":

        cursor.execute("""
            UPDATE task_progress
            SET completed = 1,
                completed_date = ?
            WHERE id = ?
        """, (
            date.today().isoformat(),
            task_id
        ))


    else:

        cursor.execute("""
            UPDATE task_progress
            SET completed = 0,
                completed_date = NULL
            WHERE id = ?
        """, (
            task_id,
        ))


    connection.commit()
    connection.close()


    return "success"


# ==================================================
# I'M BEHIND / MISSED DAY RECOVERY
# ==================================================

@app.route(
    "/missed-day",
    methods=["POST"]
)
@login_required
def missed_day():

    user_id = current_user_id()

    connection = get_db()
    cursor = connection.cursor()


    cursor.execute("""
        SELECT
            id,
            created_date,
            days_left,
            study_hours
        FROM study_plans
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (
        user_id,
    ))


    plan = cursor.fetchone()


    if not plan:

        connection.close()

        return "no_plan"


    plan_id = plan["id"]

    created_date_text = (
        plan["created_date"]
    )

    days_left = plan["days_left"]

    study_hours = plan["study_hours"]


    if not created_date_text:

        connection.close()

        return "error"


    try:

        created_date = date.fromisoformat(
            created_date_text
        )

    except (ValueError, TypeError):

        connection.close()

        return "error"


    today = date.today()


    today_day = (
        today - created_date
    ).days + 1


    if (
        today_day < 1
        or today_day > days_left
    ):

        connection.close()

        return "no_active_day"


    cursor.execute("""
        SELECT
            id,
            planned_hours
        FROM task_progress
        WHERE plan_id = ?
        AND day = ?
        AND completed = 0
        ORDER BY id
    """, (
        plan_id,
        today_day
    ))


    unfinished_tasks = cursor.fetchall()


    if not unfinished_tasks:

        connection.close()

        return "nothing_to_move"


    remaining_days = list(
        range(
            today_day + 1,
            days_left + 1
        )
    )


    if not remaining_days:

        connection.close()

        return "no_remaining_days"


    day_capacity = {}


    for day_number in remaining_days:

        cursor.execute("""
            SELECT COALESCE(
                SUM(planned_hours),
                0
            )
            FROM task_progress
            WHERE plan_id = ?
            AND day = ?
            AND completed = 0
        """, (
            plan_id,
            day_number
        ))


        already_planned = (
            cursor.fetchone()[0] or 0
        )


        available_hours = round(

            float(study_hours)
            - float(already_planned),

            1
        )


        day_capacity[day_number] = max(
            available_hours,
            0
        )


    moved_count = 0


    for task in unfinished_tasks:

        task_id = task["id"]

        task_hours = float(
            task["planned_hours"] or 0
        )


        assigned_day = None


        for day_number in remaining_days:

            if (
                day_capacity[day_number]
                >= task_hours
            ):

                assigned_day = day_number

                break


        if assigned_day is None:

            assigned_day = max(
                remaining_days,
                key=lambda d:
                    day_capacity[d]
            )


        cursor.execute("""
            UPDATE task_progress
            SET day = ?
            WHERE id = ?
        """, (
            assigned_day,
            task_id
        ))


        day_capacity[assigned_day] = round(

            day_capacity[assigned_day]
            - task_hours,

            1
        )


        moved_count += 1


    connection.commit()
    connection.close()


    if moved_count > 0:

        return "success"


    return "nothing_to_move"


# --------------------------------------------------
# ADAPTIVE STUDY PLAN ADJUSTMENT
# --------------------------------------------------

@app.route("/adaptive-adjust", methods=["POST"])
@login_required
def adaptive_adjust():

    user_id = session.get("user_id")

    try:
        conn = get_db()

        # Get the user's latest study plan
        plan = conn.execute(
            """
            SELECT *
            FROM study_plans
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,)
        ).fetchone()

        if not plan:
            conn.close()
            return "no_plan"

        # --------------------------------------------------
        # FIND CURRENT DAY
        # --------------------------------------------------

        created_date = plan["created_date"]

        if not created_date:
            conn.close()
            return "no_active_day"

        created = datetime.strptime(
            created_date,
            "%Y-%m-%d"
        ).date()

        today_day = (
            date.today() - created
        ).days + 1

        total_days = plan["days_left"]

        # If the study period is already over
        if today_day > total_days:
            conn.close()
            return "no_active_day"

        # Remaining days including today
        remaining_days = list(
            range(
                today_day,
                total_days + 1
            )
        )

        if not remaining_days:
            conn.close()
            return "no_remaining_days"

        # --------------------------------------------------
        # GET ALL INCOMPLETE TASKS
        # --------------------------------------------------

        tasks = conn.execute(
            """
            SELECT
                id,
                day,
                subject,
                planned_hours,
                confidence,
                task_type
            FROM task_progress
            WHERE plan_id = ?
            AND completed = 0
            """,
            (plan["id"],)
        ).fetchall()

        if not tasks:
            conn.close()
            return "all_complete"

        # --------------------------------------------------
        # FIND OVERDUE TASKS
        # --------------------------------------------------

        overdue_tasks = [
            task
            for task in tasks
            if task["day"] < today_day
        ]

        # --------------------------------------------------
        # CHECK WHETHER PLAN NEEDS REBALANCING
        # --------------------------------------------------

        if not overdue_tasks:

            unique_days = set(
                task["day"]
                for task in tasks
            )

            if (
                len(unique_days) <= 1
                and len(remaining_days) <= 1
            ):
                conn.close()
                return "already_balanced"

        # --------------------------------------------------
        # CONFIDENCE PRIORITY
        # LOW CONFIDENCE TASKS GET PRIORITY
        # --------------------------------------------------

        confidence_priority = {
            "Low": 0,
            "Medium": 1,
            "High": 2
        }

        sorted_tasks = sorted(
            tasks,
            key=lambda task: (
                confidence_priority.get(
                    task["confidence"],
                    1
                ),
                -(task["planned_hours"] or 0)
            )
        )

        # --------------------------------------------------
        # DAILY CAPACITY
        # --------------------------------------------------

        daily_capacity = float(
            plan["study_hours"] or 0
        )

        if daily_capacity <= 0:
            conn.close()
            return "invalid_capacity"

        # Track workload assigned to each day
        day_load = {
            day: 0.0
            for day in remaining_days
        }

        # --------------------------------------------------
        # REDISTRIBUTE UNFINISHED TASKS
        # --------------------------------------------------

        moved_tasks = 0

        for task in sorted_tasks:

            planned_hours = float(
                task["planned_hours"] or 0
            )

            if planned_hours <= 0:
                planned_hours = 0.5

            # Find days where the task can fit
            available_days = [
                day
                for day in remaining_days
                if (
                    day_load[day] +
                    planned_hours
                    <= daily_capacity
                )
            ]

            # Prefer the day with the least workload
            if available_days:

                target_day = min(
                    available_days,
                    key=lambda day: day_load[day]
                )

            else:

                # If every day is already near capacity,
                # place it on the least-loaded day.
                target_day = min(
                    remaining_days,
                    key=lambda day: day_load[day]
                )

            # Count tasks whose day actually changed
            if task["day"] != target_day:
                moved_tasks += 1

            conn.execute(
                """
                UPDATE task_progress
                SET day = ?
                WHERE id = ?
                """,
                (
                    target_day,
                    task["id"]
                )
            )

            day_load[target_day] += planned_hours

        # --------------------------------------------------
        # CHECK TOTAL REMAINING WORKLOAD
        # --------------------------------------------------

        total_remaining_hours = sum(
            float(
                task["planned_hours"] or 0
            )
            for task in sorted_tasks
        )

        total_capacity = (
            daily_capacity *
            len(remaining_days)
        )

        overloaded = (
            total_remaining_hours >
            total_capacity
        )

        conn.commit()
        conn.close()

        # --------------------------------------------------
        # RETURN RESULT
        # --------------------------------------------------

        if moved_tasks == 0:

            if overloaded:
                return (
                    "adjusted_over_capacity|"
                    + str(len(sorted_tasks))
                )

            return "already_balanced"

        if overloaded:

            return (
                "adjusted_over_capacity|"
                + str(moved_tasks)
            )

        return (
            "adjusted|"
            + str(moved_tasks)
        )

    except Exception as e:

        print(
            "Adaptive adjustment error:",
            e
        )

        try:
            conn.close()
        except:
            pass

        return "error"


# ==================================================
# UPDATE CONFIDENCE
# ==================================================

@app.route(
    "/update-confidence",
    methods=["POST"]
)
@login_required
def update_confidence():

    task_id = request.form.get(
        "task_id"
    )

    confidence = request.form.get(
        "confidence"
    )


    if not task_id:

        return "error"


    if confidence not in [
        "Low",
        "Medium",
        "High"
    ]:

        return "error"


    connection = get_db()
    cursor = connection.cursor()


    cursor.execute("""
        UPDATE task_progress
        SET confidence = ?
        WHERE id = ?
        AND plan_id IN (
            SELECT id
            FROM study_plans
            WHERE user_id = ?
        )
    """, (
        confidence,
        task_id,
        current_user_id()
    ))


    connection.commit()
    connection.close()


    return "success"


# ==================================================
# UPDATE ACTUAL HOURS
# ==================================================

@app.route(
    "/update-hours",
    methods=["POST"]
)
@login_required
def update_hours():

    task_id = request.form.get(
        "task_id"
    )

    actual_hours = request.form.get(
        "actual_hours"
    )


    if (
        not task_id
        or actual_hours is None
    ):

        return "error"


    try:

        actual_hours = float(
            actual_hours
        )


        if actual_hours < 0:

            return "error"


    except ValueError:

        return "error"


    connection = get_db()
    cursor = connection.cursor()


    cursor.execute("""
        UPDATE task_progress
        SET actual_hours = ?
        WHERE id = ?
        AND plan_id IN (
            SELECT id
            FROM study_plans
            WHERE user_id = ?
        )
    """, (
        actual_hours,
        task_id,
        current_user_id()
    ))


    connection.commit()
    connection.close()


    return "success"


# ==================================================
# SAVE STUDY TIMER SESSION
# ==================================================

@app.route(
    "/save-timer",
    methods=["POST"]
)
@login_required
def save_timer():

    task_id = request.form.get(
        "task_id"
    )

    seconds = request.form.get(
        "seconds"
    )


    if (
        not task_id
        or not seconds
    ):

        return "error"


    try:

        task_id = int(task_id)

        seconds = float(seconds)


    except ValueError:

        return "error"


    if seconds <= 0:

        return "error"


    session_hours = (
        seconds / 3600
    )


    connection = get_db()
    cursor = connection.cursor()


    cursor.execute("""
        UPDATE task_progress
        SET actual_hours =
            COALESCE(
                actual_hours,
                0
            ) + ?
        WHERE id = ?
        AND plan_id IN (
            SELECT id
            FROM study_plans
            WHERE user_id = ?
        )
    """, (
        session_hours,
        task_id,
        current_user_id()
    ))


    connection.commit()
    connection.close()


    return "success"


# ==================================================
# SAVE TASK NOTE
# ==================================================

@app.route(
    "/save-note",
    methods=["POST"]
)
@login_required
def save_note():

    task_id = request.form.get(
        "task_id"
    )

    notes = request.form.get(
        "notes",
        ""
    )


    if not task_id:

        return "error"


    connection = get_db()
    cursor = connection.cursor()


    cursor.execute("""
        UPDATE task_progress
        SET notes = ?
        WHERE id = ?
        AND plan_id IN (
            SELECT id
            FROM study_plans
            WHERE user_id = ?
        )
    """, (
        notes.strip(),
        task_id,
        current_user_id()
    ))


    connection.commit()
    connection.close()


    return "success"


# ==================================================
# SAVE STUDY REMINDER
# ==================================================

@app.route(
    "/save-reminder",
    methods=["POST"]
)
@login_required
def save_reminder():

    task_id = request.form.get(
        "task_id"
    )

    start_time = request.form.get(
        "start_time",
        ""
    ).strip()

    end_time = request.form.get(
        "end_time",
        ""
    ).strip()

    reminder_time = request.form.get(
        "reminder_time",
        ""
    ).strip()

    reminder_enabled = request.form.get(
        "reminder_enabled",
        "0"
    )


    if not task_id:

        return "error"


    try:

        task_id = int(task_id)

    except ValueError:

        return "error"


    # Validate time values
    for value in [
        start_time,
        end_time,
        reminder_time
    ]:

        if value:

            try:

                datetime.strptime(
                    value,
                    "%H:%M"
                )

            except ValueError:

                return "error"


    enabled = (
        1
        if reminder_enabled == "1"
        else 0
    )


    if enabled and not reminder_time:

        return "missing_time"


    connection = get_db()
    cursor = connection.cursor()


    cursor.execute("""
        UPDATE task_progress
        SET
            start_time = ?,
            end_time = ?,
            reminder_time = ?,
            reminder_enabled = ?
        WHERE id = ?
        AND plan_id IN (
            SELECT id
            FROM study_plans
            WHERE user_id = ?
        )
    """, (
        start_time or None,
        end_time or None,
        reminder_time or None,
        enabled,
        task_id,
        current_user_id()
    ))


    connection.commit()
    connection.close()


    return "success"


# ==================================================
# ANALYTICS
# ==================================================

@app.route("/analytics")
@login_required
def analytics():

    user_id = current_user_id()

    connection = get_db()
    cursor = connection.cursor()


    # ==================================================
    # TOTAL PLANNED HOURS
    # ==================================================

    cursor.execute("""
        SELECT COALESCE(
            SUM(tp.planned_hours),
            0
        )
        FROM task_progress tp
        JOIN study_plans sp
            ON tp.plan_id = sp.id
        WHERE sp.user_id = ?
    """, (
        user_id,
    ))


    total_planned = (
        cursor.fetchone()[0]
    )


    # ==================================================
    # TOTAL ACTUAL HOURS
    # ==================================================

    cursor.execute("""
        SELECT COALESCE(
            SUM(tp.actual_hours),
            0
        )
        FROM task_progress tp
        JOIN study_plans sp
            ON tp.plan_id = sp.id
        WHERE sp.user_id = ?
    """, (
        user_id,
    ))


    total_actual = (
        cursor.fetchone()[0]
    )


    # ==================================================
    # TOTAL TASKS
    # ==================================================

    cursor.execute("""
        SELECT COUNT(*)
        FROM task_progress tp
        JOIN study_plans sp
            ON tp.plan_id = sp.id
        WHERE sp.user_id = ?
    """, (
        user_id,
    ))


    total_tasks = (
        cursor.fetchone()[0]
    )


    # ==================================================
    # COMPLETED TASKS
    # ==================================================

    cursor.execute("""
        SELECT COUNT(*)
        FROM task_progress tp
        JOIN study_plans sp
            ON tp.plan_id = sp.id
        WHERE sp.user_id = ?
        AND tp.completed = 1
    """, (
        user_id,
    ))


    completed_tasks = (
        cursor.fetchone()[0]
    )


    completion_percentage = (

        round(
            (
                completed_tasks /
                total_tasks
            ) * 100,
            1
        )

        if total_tasks > 0

        else 0
    )


    # ==================================================
    # SUBJECT STATISTICS
    # ==================================================

    cursor.execute("""
        SELECT
            tp.subject,
            COALESCE(
                SUM(tp.planned_hours),
                0
            ),
            COALESCE(
                SUM(tp.actual_hours),
                0
            ),
            COUNT(*),
            SUM(
                CASE
                    WHEN tp.completed = 1
                    THEN 1
                    ELSE 0
                END
            )
        FROM task_progress tp
        JOIN study_plans sp
            ON tp.plan_id = sp.id
        WHERE sp.user_id = ?
        GROUP BY tp.subject
        ORDER BY tp.subject
    """, (
        user_id,
    ))


    subject_stats = cursor.fetchall()


    connection.close()


    return render_template(

        "analytics.html",

        username=session.get(
            "username",
            "Student"
        ),

        total_planned=round(
            total_planned or 0,
            1
        ),

        total_actual=round(
            total_actual or 0,
            1
        ),

        total_tasks=total_tasks,

        completed_tasks=
            completed_tasks,

        completion_percentage=
            completion_percentage,

        subject_stats=
            subject_stats

    )


# ==================================================
# PREVIOUS PLANS
# ==================================================

@app.route("/plans")
@login_required
def previous_plans():

    connection = get_db()
    cursor = connection.cursor()


    cursor.execute("""
        SELECT *
        FROM study_plans
        WHERE user_id = ?
        ORDER BY id DESC
    """, (
        current_user_id(),
    ))


    plans = cursor.fetchall()


    connection.close()


    return render_template(

        "previous_plans.html",

        plans=plans,

        username=session.get(
            "username",
            "Student"
        )

    )


# ==================================================
# OPEN PLAN
# ==================================================

@app.route(
    "/open-plan/<int:plan_id>"
)
@login_required
def open_plan(plan_id):

    user_id = current_user_id()

    connection = get_db()
    cursor = connection.cursor()


    cursor.execute("""
        SELECT
            exam_date,
            study_hours,
            difficulty,
            days_left
        FROM study_plans
        WHERE id = ?
        AND user_id = ?
    """, (
        plan_id,
        user_id
    ))


    plan = cursor.fetchone()


    if not plan:

        connection.close()

        return (
            "Study plan not found",
            404
        )


    cursor.execute("""
        SELECT
            id,
            day,
            subject,
            task_type,
            description,
            planned_hours,
            actual_hours,
            confidence,
            reason,
            completed,
            notes,
            start_time,
            end_time,
            reminder_time,
            reminder_enabled
        FROM task_progress
        WHERE plan_id = ?
        ORDER BY day, id
    """, (
        plan_id,
    ))


    tasks = cursor.fetchall()

    connection.close()


    study_plan = []

    current_day = None

    daily_tasks = []


    for task in tasks:

        if current_day != task["day"]:

            if current_day is not None:

                study_plan.append({

                    "day":
                        current_day,

                    "tasks":
                        daily_tasks

                })


            current_day = task["day"]

            daily_tasks = []


        daily_tasks.append({

            "task_id":
                task["id"],

            "subject":
                task["subject"],

            "task_type":
                task["task_type"],

            "description":
                task["description"],

            "hours":
                task["planned_hours"],

            "planned_hours":
                task["planned_hours"],

            "actual_hours":
                task["actual_hours"] or 0,

            "confidence":
                task["confidence"] or "Medium",

            "reason":
                task["reason"] or "",

            "completed":
                task["completed"],

            "notes":
                task["notes"] or "",

            "start_time":
                task["start_time"] or "",

            "end_time":
                task["end_time"] or "",

            "reminder_time":
                task["reminder_time"] or "",

            "reminder_enabled":
                task["reminder_enabled"] or 0

        })


    if current_day is not None:

        study_plan.append({

            "day":
                current_day,

            "tasks":
                daily_tasks

        })


    return render_template(

        "plan.html",

        study_plan=study_plan,

        exam_date=
            plan["exam_date"],

        study_hours=
            plan["study_hours"],

        difficulty=
            plan["difficulty"],

        days_left=
            plan["days_left"]

    )


# ==================================================
# GENERATE STUDY PLAN
# ==================================================

@app.route(
    "/generate",
    methods=["POST"]
)
@login_required
def generate():

    subjects = request.form.get(
        "subjects",
        ""
    ).strip()

    exam_date = request.form.get(
        "exam_date",
        ""
    )

    difficulty = request.form.get(
        "difficulty",
        "Medium"
    )

    user_id = current_user_id()


    # ==================================================
    # VALIDATE STUDY HOURS
    # ==================================================

    try:

        study_hours = int(
            request.form.get(
                "study_hours",
                0
            )
        )

    except ValueError:

        return "Invalid study hours."


    if study_hours < 1 or study_hours > 24:

        return (
            "Study hours must be between "
            "1 and 24."
        )


    # ==================================================
    # VALIDATE EXAM DATE
    # ==================================================

    if not exam_date:

        return "Please select an exam date."


    try:

        exam = date.fromisoformat(
            exam_date
        )

    except ValueError:

        return "Invalid exam date."


    today = date.today()


    days_left = (
        exam - today
    ).days


    if days_left <= 0:

        days_left = 1


    # ==================================================
    # SUBJECT LIST
    # ==================================================

    subject_list = [

        subject.strip()

        for subject in subjects.split(",")

        if subject.strip()

    ]


    if not subject_list:

        return (
            "Please enter at least one subject."
        )


    # ==================================================
    # GENERATE PLAN
    # ==================================================

    study_plan = []


    for day in range(
        1,
        days_left + 1
    ):

        daily_tasks = []

        remaining_hours = float(
            study_hours
        )

        subject_priority = []


        # ----------------------------------------------
        # DETERMINE SUBJECT PRIORITY
        # ----------------------------------------------

        for subject in subject_list:

            confidence = (
                get_subject_confidence(
                    subject,
                    user_id
                )
            )


            priority = {

                "Low": 1,

                "Medium": 2,

                "High": 3

            }.get(
                confidence,
                2
            )


            subject_priority.append(
                (
                    subject,
                    priority
                )
            )


        subject_priority.sort(
            key=lambda item:
                item[1]
        )


        total_subjects = len(
            subject_priority
        )


        # ----------------------------------------------
        # CREATE DAILY TASKS
        # ----------------------------------------------

        for i, (
            subject,
            priority
        ) in enumerate(
            subject_priority
        ):

            task_details = (
                generate_task_details(

                    subject,

                    difficulty,

                    day,

                    i,

                    days_left,

                    study_hours,

                    user_id

                )
            )


            basic_hours = (
                study_hours /
                total_subjects
            )


            if (
                task_details["confidence"]
                == "Low"
            ):

                task_hours = (
                    basic_hours * 1.5
                )


            elif (
                task_details["confidence"]
                == "High"
            ):

                task_hours = (
                    basic_hours * 0.75
                )


            else:

                task_hours = (
                    basic_hours
                )


            task_hours = round(
                task_hours,
                1
            )


            if task_hours < 0.5:

                task_hours = 0.5


            if task_hours > remaining_hours:

                task_hours = round(
                    remaining_hours,
                    1
                )


            if task_hours <= 0:

                break


            remaining_hours = round(

                remaining_hours -
                task_hours,

                1

            )


            daily_tasks.append({

                "subject":
                    subject,

                "task_type":
                    task_details[
                        "task_type"
                    ],

                "description":
                    task_details[
                        "description"
                    ],

                "hours":
                    task_hours,

                "reason":
                    task_details[
                        "reason"
                    ],

                "confidence":
                    task_details[
                        "confidence"
                    ],

                "notes":
                    ""

            })


        study_plan.append({

            "day":
                day,

            "tasks":
                daily_tasks

        })


    # ==================================================
    # SAVE PLAN TO DATABASE
    # ==================================================

    connection = get_db()
    cursor = connection.cursor()


    cursor.execute("""
        INSERT INTO study_plans
        (
            user_id,
            exam_date,
            study_hours,
            difficulty,
            days_left,
            created_date
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (

        user_id,

        exam_date,

        study_hours,

        difficulty,

        days_left,

        date.today().isoformat()

    ))


    plan_id = cursor.lastrowid


    # ==================================================
    # SAVE TASKS
    # ==================================================

    for day_data in study_plan:

        for task in day_data["tasks"]:

            cursor.execute("""
                INSERT INTO task_progress
                (
                    plan_id,
                    day,
                    subject,
                    task_type,
                    description,
                    planned_hours,
                    confidence,
                    reason,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (

                plan_id,

                day_data["day"],

                task["subject"],

                task["task_type"],

                task["description"],

                task["hours"],

                task["confidence"],

                task["reason"],

                task["notes"]

            ))


            task["task_id"] = (
                cursor.lastrowid
            )

            task["completed"] = 0


    connection.commit()
    connection.close()


    # ==================================================
    # SHOW GENERATED PLAN
    # ==================================================

    return render_template(

        "plan.html",

        study_plan=study_plan,

        exam_date=exam_date,

        study_hours=study_hours,

        difficulty=difficulty,

        days_left=days_left

    )


# ==================================================
# RUN APPLICATION
# ==================================================

if __name__ == "__main__":

    init_db()

    app.run(
        port=5001
    )