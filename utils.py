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

    start_date = datetime(2025, 7, 27).date()
    days_difference = (date - start_date).days
    return (days_difference // 7) % 2 == 0

def get_current_meal(hour=None):
    """ Deleting the temporary menu and Return the current meal based on IST time."""
    connection = get_db_connection()
    cursor = connection.cursor()
    query = "DELETE FROM temporary_menu WHERE created_at < %s"  # or use appropriate condition
    # query1 = "SELECT menu_id from non_veg_menu_main WHERE menu_date < %s"
    query1 = "DELETE FROM non_veg_menu_items WHERE menu_id IN (SELECT menu_id FROM non_veg_menu_main WHERE menu_date < %s)"
    query2 = "DELETE FROM non_veg_menu_main WHERE menu_date < %s"
    cursor.execute(query, (get_fixed_time().date(),))
    cursor.execute(query1, (get_fixed_time().date(),))
    # menu_ids = cursor.fetchall()
    cursor.execute(query2, (get_fixed_time().date(),))
    # print("Temporary menu deleted successfully.") 
    connection.commit()
    cursor.close()
    connection.close()
    if hour is None:
        hour = get_fixed_time().hour  # Ensure function is called
        minute = get_fixed_time().minute
        total_time = hour * 60 + minute
    if 0 <= total_time < 11*60:
        return "Breakfast"
    elif 11*60 <= total_time < 16*60:
        return "Lunch"
    elif 16*60 <= total_time <= 18*60 + 30:
        return "Snacks"
    elif 18*60 + 30 < total_time <= 23*60 + 59:
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
        return (0, 0.0, 0, 0.0)

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        created_at = get_fixed_time().date()

        query_avg = """
            SELECT AVG(rating) AS avg_rating
            FROM feedback_details d
            JOIN feedback_summary s ON d.feedback_id = s.feedback_id
            WHERE s.meal = %s AND s.mess = %s AND DATEDIFF(%s, s.feedback_date) % 14 = 0;
        """

        query_count = """
            SELECT COUNT(*) AS count
            FROM feedback_summary
            WHERE meal = %s AND mess = %s AND DATEDIFF(%s, feedback_date) % 14 = 0;
        """

        # MESS 1
        cursor.execute(query_avg, (meal, 'mess1', created_at))
        avg1 = cursor.fetchone() or {"avg_rating": 0.0}

        cursor.execute(query_count, (meal, 'mess1', created_at))
        count1 = cursor.fetchone() or {"count": 0}

        # MESS 2
        cursor.execute(query_avg, (meal, 'mess2', created_at))
        avg2 = cursor.fetchone() or {"avg_rating": 0.0}

        cursor.execute(query_count, (meal, 'mess2', created_at))
        count2 = cursor.fetchone() or {"count": 0}

        cursor.close()
        connection.close()

        # Ensure proper rounding & defaults
        avg1["avg_rating"] = round(avg1["avg_rating"] or 0.0, 2)
        avg2["avg_rating"] = round(avg2["avg_rating"] or 0.0, 2)
        count1["count"] = count1["count"] or 0
        count2["count"] = count2["count"] or 0

        return (count1["count"], avg1["avg_rating"], count2["count"], avg2["avg_rating"])

    except Exception as e:
        print(f"Error fetching average rating: {e}")
        return (0, 0.0, 0, 0.0)


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

# def main():
#     avg_rating()

# if __name__ == "__main__":
#     main()
