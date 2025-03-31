import mysql.connector
from faker import Faker
import random
from utils import get_db_connection, get_menu
from datetime import datetime, timedelta
from itertools import count

def generate_students(n=50):
    fake = Faker()
    connection = get_db_connection()
    cursor = connection.cursor()

    departments = ['cs', 'ec', 'me']  # Add more if needed
    batches = ['23b', '22b', '21b']  # Modify based on available years
    assigned_ids = set()

    student_count = count(1000)  # Ensures unique numbers (1000, 1001, ...)

    while len(assigned_ids) < n:
        dept = random.choice(departments)
        batch = random.choice(batches)
        num = next(student_count)

        s_id = f"{dept}{batch}{num}"  # Example: cs23b1001
        if s_id in assigned_ids:
            continue  # Skip duplicates

        assigned_ids.add(s_id)

        name = fake.name()
        password = s_id
        mess = random.choice(['mess1', 'mess2'])

        cursor.execute(
            "INSERT INTO student (s_id, name, password, mess) VALUES (%s, %s, %s, %s)",
            (s_id, name, password, mess)
        )

    connection.commit()
    cursor.close()
    connection.close()

    print(f"{n} student records inserted.")

def generate_feedback(num_feedback=50):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT s_id, mess FROM student")
        students = cursor.fetchall()
    
        for day in range(50):
            feedback_date = (datetime.now() - timedelta(days=day)).date()
            for meal in ['Breakfast', 'Lunch', 'Snacks', 'Dinner']:
                selected_students = random.sample(students, min(20, len(students)))
                for student_id, mess in selected_students:
                    meal, veg_menu_items, non_veg_menu1, non_veg_menu2 = get_menu(feedback_date, meal)
                    # menu_items = veg_menu_items + (non_veg_menu1 if mess == 'mess1' else non_veg_menu2)
                    menu_items = veg_menu_items + [item[0] for item in (non_veg_menu1 if mess == 'mess1' else non_veg_menu2)]
                    # Insert feedback summary
                    try:
                        # mess_connection = get_db_connection(mess)
                        # with mess_connection.cursor() as crsr:
                        cursor.execute(
                            """
                            INSERT INTO feedback_summary (s_id, feedback_date, meal, mess)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (student_id, feedback_date, meal, mess)
                        )
                        feedback_id = cursor.lastrowid
                        
                        # Insert feedback details
                        for food_item in menu_items:
                            rating = random.randint(1, 5)
                            comment = random.choice(["Good", "Average", "Excellent", "Not Great", "Bad"])
                            cursor.execute(
                                """
                                INSERT INTO feedback_details (feedback_id, food_item, rating, comments)
                                VALUES (%s, %s, %s, %s)
                                """,
                                (feedback_id, food_item, rating, comment)
                            )
                        connection.commit()
                        print(f"Inserted feedback for {meal} on {feedback_date} in {mess}")
                    except mysql.connector.Error as e:
                        print(f"MySQL Error: {e}")
                # finally:
                    #     if mess_connection.is_connected():
                    #         mess_connection.close()
    
        connection.close()
        print(f"Feedback generation completed.")

    except Exception as e:
        print(f"Error: {e}")

# generate_feedback()
def generate_waste(num_days=30):
    fake = Faker()
    connection = get_db_connection()
    cursor = connection.cursor()

    for day_offset in range(num_days):
        waste_date = (datetime.now() - timedelta(days=day_offset)).date()
        for meal in ['Breakfast', 'Lunch', 'Snacks', 'Dinner']:
            for floor in ['Ground', 'First', 'Second', 'Third']:
                _, veg_menu_items, non_veg_menu1, non_veg_menu2 = get_menu(waste_date, meal)
                
                if not veg_menu_items:
                    print(f"No menu found for {waste_date} - {meal}")
                    continue

                menu_items = veg_menu_items + (non_veg_menu1 if floor == 'First' else non_veg_menu2 if floor == 'Third' else [])
                total_waste = sum(random.randint(10, 300) for _ in menu_items)

                cursor.execute("""
                    INSERT INTO waste_summary (waste_date, meal, floor, total_waste)
                    VALUES (%s, %s, %s, %s)
                """, (waste_date, meal, floor, total_waste))
                waste_id = cursor.lastrowid

                for item in menu_items:
                    prepared_amount = random.randint(50, 500)
                    leftover_amount = random.randint(10, prepared_amount)
                    cursor.execute("""
                        INSERT INTO waste_details (waste_id, food_item, prepared_amount, leftover_amount)
                        VALUES (%s, %s, %s, %s)
                    """, (waste_id, item, prepared_amount, leftover_amount))

    connection.commit()
    cursor.close()
    connection.close()
    print("Waste data generated for all days and meals.")

def generate_non_veg_menu(num_days=30):
    connection = get_db_connection()
    # connection2 = get_db_connection('mess2')
    cursor = connection.cursor()
    # cursor2 = connection2.cursor()
    
    non_veg_items_mess1 = [
        ("Chicken Curry", 150),
        ("Fish Fry", 180),
        ("Egg Biryani", 120),
        ("Mutton Korma", 200),
        ("Prawn Masala", 250)
    ]

    non_veg_items_mess2 = [
        ("Butter Chicken", 160),
        ("Grilled Fish", 190),
        ("Egg Curry", 110),
        ("Lamb Rogan Josh", 210),
        ("Crab Masala", 260)
    ]

    for _ in range(num_days):
        menu_date = (datetime.now() - timedelta(days=random.randint(1, 30))).date()
        meal = random.choice(['Breakfast', 'Lunch', 'Snacks', 'Dinner'])

        # Insert into mess1
        cursor.execute("""
            INSERT INTO non_veg_menu_main (menu_date, meal, mess)
            VALUES (%s, %s, %s)
        """, (menu_date, meal, 'mess1'))
        menu_id1 = cursor.lastrowid

        num_items1 = random.randint(1, len(non_veg_items_mess1))
        selected_items1 = random.sample(non_veg_items_mess1, num_items1)

        for item, cost in selected_items1:
            cursor.execute("""
                INSERT INTO non_veg_menu_items (menu_id, food_item, cost)
                VALUES (%s, %s, %s)
            """, (menu_id1, item, cost))

        # Insert into mess2
        cursor.execute("""
            INSERT INTO non_veg_menu_main (menu_date, meal, mess)
            VALUES (%s, %s, %s)
        """, (menu_date, meal, 'mess2'))
        menu_id2 = cursor.lastrowid

        num_items2 = random.randint(1, len(non_veg_items_mess2))
        selected_items2 = random.sample(non_veg_items_mess2, num_items2)

        for item, cost in selected_items2:
            cursor.execute("""
                INSERT INTO non_veg_menu_items (menu_id, food_item, cost)
                VALUES (%s, %s, %s)
            """, (menu_id2, item, cost))

    connection.commit()
    # connection2.commit()
    cursor.close()
    # cursor2.close()
    connection.close()
    # connection2.close()
    print("Non-veg menus generated for random dates and meals in both messes over the last 30 days.")

def generate_payments(n=100):
    fake = Faker()
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
    except mysql.connector.Error as e:
        print(f"Error connecting to database: {e}")
        return
    cursor.execute("SELECT s_id, mess FROM student")
    students = cursor.fetchall()

    for _ in range(n):
        s_id, mess = random.choice(students)
        # mess_db = 'mess1' if mess == 'mess1' else 'mess2'
        # mess_connection = get_db_connection(mess_db)
        # mess_cursor = mess_connection.cursor()

        cursor.execute("""
            SELECT n.menu_date, n.meal, i.food_item, i.cost
            FROM non_veg_menu_main n
            JOIN non_veg_menu_items i ON n.menu_id = i.menu_id
            WHERE n.mess = %s
        """, (mess,))

        non_veg_data = cursor.fetchall()
        
        if non_veg_data:
            menu_date, meal, food_item, cost = random.choice(non_veg_data)
            payment_date = menu_date
            payment_mode = random.choice(['Cash', 'Card', 'UPI', 'Net Banking'])
            
            cursor.execute("""
                INSERT INTO payment (s_id, mess, meal, payment_date, food_item, amount, payment_mode)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (s_id, mess, meal, payment_date, food_item, cost, payment_mode))
        
        # mess_cursor.close()
        # mess_connection.close()

    connection.commit()
    cursor.close()
    connection.close()
    print(f"{n} payment records inserted.")


if __name__ == "__main__":
    # generate_students()
    generate_feedback()
    # generate_waste()
    # generate_non_veg_menu()
    # generate_payments()
