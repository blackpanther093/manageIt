from db import get_db_connection
from datetime import datetime, timezone
import pytz
import mysql.connector
# from utils import is_odd_week, get_current_meal

def get_fixed_time():
    """Always return UTC time and convert to IST."""
    utc_now = datetime.now(timezone.utc)  # Ensure we use UTC explicitly
    ist = pytz.timezone("Asia/Kolkata")
    return utc_now.astimezone(ist)

def is_odd_week(date=None):
    """Determine if the given date falls in an odd or even week, based on 2025-02-02."""
    # utc = pytz.utc
    # ist = pytz.timezone("Asia/Kolkata")

    if date is None:
        date = get_fixed_time.date()  # Get IST date from UTC

    start_date = datetime(2025, 2, 2).date()
    days_difference = (date - start_date).days
    return (days_difference // 7) % 2 == 0

def get_current_meal(hour=None):
    """Return the current meal based on IST time."""
    # utc = pytz.utc
    # ist = pytz.timezone("Asia/Kolkata")

    if hour is None:
        hour = get_fixed_time().hour  # Convert UTC to IST

    if 6 <= hour < 11:
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
    # utc = pytz.utc
    # ist = pytz.timezone("Asia/Kolkata")

    try:
        # Get the current IST date & meal if not provided
        date = date or get_fixed_time.date()
        meal = meal or get_current_meal()

        if not meal:
            print(f"No current meal available for {date}")
            return None, [], [], []

        week_type = 'Odd' if is_odd_week(date) else 'Even'
        day = date.strftime('%A')
        veg_menu_items, non_veg_menu1, non_veg_menu2 = [], [], []

        # Fetch menu from database
        from utils import get_db_connection
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                
                # Fetch Veg Menu (Temporary or Default)
                cursor.execute(
                    """
                    SELECT food_item FROM temporary_menu
                    WHERE week_type = %s AND day = %s AND meal = %s
                    """, (week_type, day, meal)
                )
                temp_menu = cursor.fetchall()
                veg_menu_items = [item[0] for item in temp_menu] if temp_menu else []
                
                if not veg_menu_items:
                    cursor.execute(
                        """
                        SELECT food_item FROM menu
                        WHERE week_type = %s AND day = %s AND meal = %s
                        """, (week_type, day, meal)
                    )
                    veg_menu_items = [item[0] for item in cursor.fetchall()]

                # Fetch Non-Veg Menu from Mess 1
                cursor.execute(
                    """
                    SELECT food_item, MIN(cost)
                    FROM non_veg_menu_items
                    JOIN non_veg_menu_main ON non_veg_menu_items.menu_id = non_veg_menu_main.menu_id
                    WHERE menu_date = %s AND meal = %s AND mess='mess1'
                    GROUP BY food_item
                    """, (date, meal)
                )
                non_veg_menu1 = cursor.fetchall()

                # Fetch Non-Veg Menu from Mess 2
                cursor.execute(
                    """
                    SELECT food_item, MIN(cost)
                    FROM non_veg_menu_items
                    JOIN non_veg_menu_main ON non_veg_menu_items.menu_id = non_veg_menu_main.menu_id
                    WHERE menu_date = %s AND meal = %s AND mess='mess2'
                    GROUP BY food_item
                    """, (date, meal)
                )
                non_veg_menu2 = cursor.fetchall()

        return meal, veg_menu_items, non_veg_menu1, non_veg_menu2

    except mysql.connector.Error as e:
        print(f"Database error: {e}")
        return None, [], [], []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None, [], [], []

def avg_rating():
    meal = get_current_meal()
    try:
        week_type = 'Odd' if is_odd_week() else 'Even'
        connection = get_db_connection()
        # connection2 = get_db_connection('mess2')
        cursor = connection.cursor()
        # cursor2 = connection2.cursor()

        # Execute query for Mess 1
        cursor.execute("""
            SELECT AVG(rating) AS avg_rating
            FROM feedback_details d JOIN feedback_summary s
            ON d.feedback_id = s.feedback_id
            WHERE s.meal = %s AND s.mess='mess1' AND DATEDIFF(CURDATE(), s.feedback_date) % 14 = 0
        """, (meal,))
        # print(f"Meal (Mess 1): {meal}")
        avg_rating1 = cursor.fetchone()[0] or 0
        # print(f"Average Rating (Mess 1): {avg_rating1}")
        # cursor1.close()
        # connection1.close()

        cursor.execute("""SELECT AVG(rating) AS avg_rating
        FROM feedback_details d JOIN feedback_summary s
        ON d.feedback_id = s.feedback_id
        WHERE meal = %s AND s.mess='mess2' AND DATEDIFF(CURDATE(), s.feedback_date) % 14 = 0;""",(meal,))
        
        # result2 = cursor2.fetchone()
        avg_rating2 = cursor.fetchone()[0] or 0
        # print(f"Average Rating (Mess 2): {avg_rating2}")

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

        if student:
            return student[0]  # Return the mess value if student exists
        else:
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None
    finally:
        cursor.close()
        connection.close()

def main():
    avg_rating()
if __name__=="__main__":
    main()
