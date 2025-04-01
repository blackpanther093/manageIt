from db import get_db_connection
from datetime import datetime, timezone
import pytz
import mysql.connector

def get_fixed_time():
    """Always return UTC time and convert to IST."""
    utc_now = datetime.now(timezone.utc)  # Ensure we use UTC explicitly
    ist = pytz.timezone("Asia/Kolkata")
    return utc_now.astimezone(ist)

def is_odd_week(date=None):
    """Determine if the given date falls in an odd or even week, based on 2025-02-02."""
    if date is None:
        date = get_fixed_time().date()  # Ensure function is called

    start_date = datetime(2025, 2, 2).date()
    days_difference = (date - start_date).days
    return (days_difference // 7) % 2 == 0

def get_current_meal(hour=None):
    """Return the current meal based on IST time."""
    if hour is None:
        hour = get_fixed_time().hour  # Ensure function is called

    if 0 <= hour < 11:
        return "Breakfast"
    elif 11 <= hour < 15:
        return "Lunch"
    elif 15 <= hour < 18:
        return "Snacks"
    elif 18 <= hour <= 23:
        return "Dinner"
    return None

def get_menu(date=None, meal=None):
    """Fetch menu details based on the date and meal."""
    try:
        date = date or get_fixed_time().date()  # Ensure function is called
        meal = meal or get_current_meal()

        if not meal:
            print(f"No current meal available for {date}")
            return None, [], [], []

        week_type = 'Odd' if is_odd_week(date) else 'Even'
        day = date.strftime('%A')
        veg_menu_items, non_veg_menu1, non_veg_menu2 = [], [], []

        # Fetch menu from database
        connection = get_db_connection()
        cursor = connection.cursor()

        # Fetch Veg Menu (Temporary or Default)
        cursor.execute("""
            SELECT food_item FROM temporary_menu
            WHERE week_type = %s AND day = %s AND meal = %s
        """, (week_type, day, meal))
        temp_menu = cursor.fetchall()
        veg_menu_items = [item[0] for item in temp_menu] if temp_menu else []

        if not veg_menu_items:
            cursor.execute("""
                SELECT food_item FROM menu
                WHERE week_type = %s AND day = %s AND meal = %s
            """, (week_type, day, meal))
            veg_menu_items = [item[0] for item in cursor.fetchall()]

        # Fetch Non-Veg Menu from Mess 1
        cursor.execute("""
            SELECT food_item, MIN(cost)
            FROM non_veg_menu_items
            JOIN non_veg_menu_main ON non_veg_menu_items.menu_id = non_veg_menu_main.menu_id
            WHERE menu_date = %s AND meal = %s AND mess='mess1'
            GROUP BY food_item
        """, (date, meal))
        non_veg_menu1 = cursor.fetchall()

        # Fetch Non-Veg Menu from Mess 2
        cursor.execute("""
            SELECT food_item, MIN(cost)
            FROM non_veg_menu_items
            JOIN non_veg_menu_main ON non_veg_menu_items.menu_id = non_veg_menu_main.menu_id
            WHERE menu_date = %s AND meal = %s AND mess='mess2'
            GROUP BY food_item
        """, (date, meal))
        non_veg_menu2 = cursor.fetchall()

        cursor.close()
        connection.close()

        return meal, veg_menu_items, non_veg_menu1, non_veg_menu2

    except mysql.connector.Error as e:
        print(f"Database error: {e}")
        return None, [], [], []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None, [], [], []

def avg_rating():
    meal = get_current_meal()
    if not meal:
        return 0, 0  # Prevent SQL failure if no meal is detected

    try:
        week_type = 'Odd' if is_odd_week() else 'Even'
        connection = get_db_connection()
        cursor = connection.cursor()

        # Execute query for Mess 1
        cursor.execute("""
            SELECT AVG(rating) AS avg_rating
            FROM feedback_details d JOIN feedback_summary s
            ON d.feedback_id = s.feedback_id
            WHERE s.meal = %s AND s.mess='mess1' AND DATEDIFF(CURDATE(), s.feedback_date) % 14 = 0
        """, (meal,))
        avg_rating1 = cursor.fetchone()[0] or 0

        # Execute query for Mess 2
        cursor.execute("""
            SELECT AVG(rating) AS avg_rating
            FROM feedback_details d JOIN feedback_summary s
            ON d.feedback_id = s.feedback_id
            WHERE s.meal = %s AND s.mess='mess2' AND DATEDIFF(CURDATE(), s.feedback_date) % 14 = 0
        """, (meal,))
        avg_rating2 = cursor.fetchone()[0] or 0

        cursor.close()
        connection.close()

        return round(avg_rating1, 2), round(avg_rating2, 2)

    except Exception as e:
        print(f"Error fetching average rating: {e}")
        return 0, 0

def is_valid_student(student_id):
    connection = get_db_connection('mess_management')
    cursor = connection.cursor()

    try:
        cursor.execute("SELECT mess FROM student WHERE s_id = %s", (student_id,))
        student = cursor.fetchone()
        return student[0] if student else None
    except Exception as e:
        print(f"Error: {e}")
        return None
    finally:
        cursor.close()
        connection.close()

def main():
    avg_rating()

if __name__ == "__main__":
    main()
