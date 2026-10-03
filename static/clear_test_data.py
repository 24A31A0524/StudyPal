import sqlite3

connection = sqlite3.connect("study_planner.db")
cursor = connection.cursor()

# Delete task/progress data first
cursor.execute("DELETE FROM task_progress")

# Delete all saved study plans
cursor.execute("DELETE FROM study_plans")

connection.commit()
connection.close()

print("All old test data has been deleted successfully.")