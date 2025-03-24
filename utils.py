from datetime import datetime
from db import get_db_connection
def is_odd_week():
    start_date = datetime(2025, 3, 16)
    current_date = datetime.now()
    days_difference = (current_date - start_date).days
    return (days_difference // 7) % 2 == 0

def get_current_meal():
    hour = datetime.now().hour
    if 6 <= hour < 11:
        return "Breakfast"
    elif 11 <= hour < 15:
        return "Lunch"
    elif 16 <= hour < 18:
        return "Snacks"
    elif 18 <= hour <= 24:
        return "Dinner"
    return None

def get_menu():
    week_type = 'Odd' if is_odd_week() else 'Even'
    day = datetime.now().strftime('%A')
    meal = get_current_meal()

    if not meal:
        return None, None, None, None
    
    # Fetch Veg Menu (common for both messes)
    connection = get_db_connection('mess_management')
    cursor = connection.cursor()
    cursor.execute("""
        SELECT food_item FROM menu
        WHERE week_type = %s AND day = %s AND meal = %s
    """, (week_type, day, meal))
    veg_menu_items = [item[0] for item in cursor.fetchall()]
    cursor.close()
    connection.close()

    # Fetch Non-Veg Menu from Mess 1 (No Week Type)
    connection = get_db_connection('mess1')
    cursor = connection.cursor()
    cursor.execute("""
        SELECT DISTINCT food_item,MIN(cost) FROM non_veg_menu_items 
        JOIN non_veg_menu_main
        ON non_veg_menu_items.menu_id = non_veg_menu_main.menu_id
        WHERE menu_date = %s AND meal = %s
        GROUP BY food_item
    """, (datetime.now().date(), meal))
    non_veg_menu1 = cursor.fetchall()
    cursor.close()
    connection.close()

    # Fetch Non-Veg Menu from Mess 2 (No Week Type)
    connection = get_db_connection('mess2')
    cursor = connection.cursor()
    cursor.execute("""
        SELECT DISTINCT food_item,MIN(cost) FROM non_veg_menu_items 
        JOIN non_veg_menu_main
        ON non_veg_menu_items.menu_id = non_veg_menu_main.menu_id
        WHERE menu_date = %s AND meal = %s
        GROUP BY food_item
    """, (datetime.now().date(), meal))
    non_veg_menu2 = cursor.fetchall()
    cursor.close()
    connection.close()


    return meal, veg_menu_items, non_veg_menu1, non_veg_menu2

def avg_rating():
    meal = get_current_meal()
    try:
        week_type = 'Odd' if is_odd_week() else 'Even'
        # day = datetime.now().strftime('%A')
        connection1 = get_db_connection('mess1')
        connection2 = get_db_connection('mess2')
        cursor1 = connection1.cursor()
        cursor2 = connection2.cursor()

        cursor1.execute("""
            SELECT AVG(rating) AS avg_rating
            FROM feedback_details d JOIN feedback_summary s
            ON d.feedback_id = s.feedback_id
            WHERE s.meal = %s AND DATEDIFF(CURDATE(), s.feedback_date) % 14 = 0
        """,(meal,))

        avg_rating1 = cursor1.fetchone()[0] or 0
        cursor1.close()
        connection1.close()
        cursor2.execute("""
            SELECT AVG(rating) AS avg_rating
            FROM feedback_details d JOIN feedback_summary s
            ON d.feedback_id = s.feedback_id
            WHERE s.meal = %s AND DATEDIFF(CURDATE(), s.feedback_date) % 14 = 0
        """,(meal,))
        avg_rating2 = cursor2.fetchone()[0] or 0
        cursor2.close()
        connection2.close()
        return round(avg_rating1,2), round(avg_rating2,2)

    except Exception as e:
        print(f"Error fetching average rating: {e}")
        return 0,0
    
def is_valid_student(student_id):
    connection = get_db_connection('mess_management')
    cursor = connection.cursor()

    try:
        # Execute the query to check if the student exists
        cursor.execute("SELECT mess FROM students WHERE s_id = %s", (student_id,))
        student = cursor.fetchone()

        if student:
            return student[0]  # Return the mess value if student exists
        else:
            return None  # Return None if no student found
    except Exception as e:
        print(f"Error: {e}")
        return None
    finally:
        cursor.close()
        connection.close() 