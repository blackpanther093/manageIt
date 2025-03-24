from flask import Flask, render_template, request, redirect, session, url_for, flash
from utils import get_menu, is_valid_student, avg_rating, get_current_meal
from db import get_db_connection
from datetime import datetime   
import plotly.express as px
import pandas as pd


app = Flask(__name__)

@app.route('/')
@app.route('/home')
def home():
    meal, veg_menu_items, non_veg_menu1, non_veg_menu2 = get_menu()
    current_avg_rating_mess1, current_avg_rating_mess2 = avg_rating()
    if not meal or (not veg_menu_items and not non_veg_menu1 and not non_veg_menu2):
        return "No meal available."
    return render_template('home_page.html', meal=meal, veg_menu_items=veg_menu_items, non_veg_menu1=non_veg_menu1, non_veg_menu2=non_veg_menu2, current_avg_rating_mess1 = current_avg_rating_mess1, current_avg_rating_mess2 = current_avg_rating_mess2)

# app = Flask(__name__)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        id = request.form.get('id')
        password = request.form.get('password')

        connection = get_db_connection('mess_management')
        cursor = connection.cursor()

        # Check if the user is a student
        cursor.execute("SELECT s_id, name, mess FROM student WHERE s_id = %s AND password = %s", (id, password))
        student = cursor.fetchone()

        if student:
            session['student_id'] = student[0]
            session['student_name'] = student[1]
            session['mess'] = student[2]
            session['role'] = 'student'
            cursor.close()
            connection.close()
            return redirect(url_for('feedback'))

        # Check if the user is a mess official
        cursor.execute("SELECT mess_id, mess FROM mess_data WHERE mess_id = %s AND password = %s", (id, password))
        mess_official = cursor.fetchone()

        if mess_official:
            session['mess_id'] = mess_official[0]
            session['mess'] = mess_official[1]
            session['role'] = 'mess_official'
            cursor.close()
            connection.close()
            return redirect(url_for('mess_dashboard'))

        cursor.close()
        connection.close()
        return "Invalid id or Password. Please try again."

    return render_template('login.html')

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    # Ensure student is logged in
    if 'student_id' not in session:
        return redirect(url_for('login'))

    student_id = session['student_id']
    student_name = session['student_name']
    mess = session['mess']

    # Select the appropriate database
    db_name = 'mess1' if mess == 'mess1' else 'mess2'

    meal, veg_menu_items, non_veg_menu1, non_veg_menu2 = get_menu()
    if not meal:
        return "No meal available at the moment."

    if request.method == 'POST':
        # Collect Feedback Data
        food_ratings = {}
        comments = {}
        non_veg_menu = non_veg_menu1 if mess == 'mess1' else non_veg_menu2
        menu_items = veg_menu_items + non_veg_menu

        for item in menu_items:
            rating = request.form.get(f'rating_{item}')
            comment = request.form.get(f'comment_{item}')
            if rating:
                food_ratings[item] = int(rating)
                comments[item] = comment if comment else None

        if not food_ratings:
            return "No ratings submitted."

        # Store Feedback in Database
        try:
            connection = get_db_connection(db_name)
            cursor = connection.cursor()

            # Insert into feedback_summary
            cursor.execute("""
                INSERT INTO feedback_summary (s_id, feedback_date, meal)
                VALUES (%s, CURDATE(), %s)
            """, (student_id, meal))
            feedback_id = cursor.lastrowid

            # Insert into feedback_details
            for item, rating in food_ratings.items():
                food_item = item[0] if isinstance(item, tuple) else item
                cursor.execute("""
                    INSERT INTO feedback_details (feedback_id, food_item, rating, comments)
                    VALUES (%s, %s, %s, %s)
                """, (feedback_id, food_item, rating, comments.get(item, None)))

            connection.commit()
            cursor.close()
            connection.close()
        except Exception as e:
            import traceback
            print("Error details:", traceback.format_exc())
            print(f"Error storing feedback: {e}")
            connection.rollback()
            return "An error occurred while submitting feedback."

        return "Feedback submitted successfully!"
    
    return render_template('feedback.html', meal=meal, veg_menu_items=veg_menu_items, non_veg_menu1=non_veg_menu1 if mess == 'mess1' else [], non_veg_menu2=non_veg_menu2 if mess == 'mess2' else [], student_name=student_name, mess=mess)


@app.route('/waste', methods=['GET', 'POST'])
def waste():
    # Ensure only mess officials can access this page
    if 'role' not in session or session['role'] != 'mess_official':
        return "Access Denied: Only mess officials can access this page."

    mess = session.get('mess')
    if not mess:
        return "Error: Mess information not found."

    meal, veg_menu_items, non_veg_menu1, non_veg_menu2 = get_menu()
    if not meal:
        return "No meal available at the moment."

    if request.method == 'POST':
        floor = request.form.get('floor')
        waste_amount = request.form.get('waste_amount') 
        if floor not in ['Ground', 'First', 'Second', 'Third']:
            return "Invalid floor."

        prepared_amounts = {}
        leftover_amounts = {}

        # Determine menu based on floor
        if floor in ['Ground', 'First']:
            menu_items = veg_menu_items + [item[0] for item in non_veg_menu1]
        else:
            menu_items = veg_menu_items + [item[0] for item in non_veg_menu2]

        for food_item in menu_items:
            prepared = request.form.get(f'prepared_{food_item}')
            leftover = request.form.get(f'leftover_{food_item}')

            if prepared and leftover:
                try:
                    prepared_amounts[food_item] = int(prepared)
                    leftover_amounts[food_item] = int(leftover)
                except ValueError:
                    return f"Invalid input for {food_item}. Please enter numbers only."

        if not prepared_amounts:
            return "No valid data submitted."

        try:
            connection = get_db_connection('mess_management')
            cursor = connection.cursor()

            # Insert into waste_summary
            cursor.execute("""
                INSERT INTO waste_summary (waste_date, meal, floor, total_waste)
                VALUES (CURDATE(), %s, %s, %s)
            """, (meal, floor, waste_amount))
            waste_id = cursor.lastrowid

            # Insert into waste_details
            for food_item in prepared_amounts:
                cursor.execute("""
                    INSERT INTO waste_details (waste_id, food_item, prepared_amount, leftover_amount)
                    VALUES (%s, %s, %s, %s)
                """, (waste_id, food_item, prepared_amounts[food_item], leftover_amounts[food_item]))

            connection.commit()
            cursor.close()
            connection.close()
            return "Waste data submitted successfully!"
        except Exception as e:
            print(f"Error storing waste data: {e}")
            return "An error occurred while submitting waste data."

    return render_template('waste_feedback.html', meal=meal, veg_menu_items=veg_menu_items, 
                            non_veg_menu1=non_veg_menu1, non_veg_menu2=non_veg_menu2, mess=mess)


@app.route('/add_non_veg_menu', methods=['GET', 'POST'])
def add_non_veg_menu():
    # Ensure only mess officials can access this page
    if 'role' not in session or session['role'] != 'mess_official':
        return "Access Denied: Only mess officials can access this page."

    mess = session.get('mess')
    if not mess:
        return "Error: Mess information not found."

    # Get meal using the existing function
    meal, _, _, _ = get_menu()
    if not meal:
        return "No meal available at the moment."

    if request.method == 'POST':
        food_items = request.form.getlist('food_item[]')
        costs = request.form.getlist('cost[]')

        if not food_items or not costs or len(food_items) != len(costs):
            return "Invalid input. Ensure all fields are filled."

        try:
            connection = get_db_connection(mess)
            cursor = connection.cursor()

            # Insert into non_veg_menu_main
            cursor.execute("""
                INSERT INTO non_veg_menu_main (menu_date, meal, mess)
                VALUES (CURDATE(), %s, %s)
            """, (meal, mess))
            menu_id = cursor.lastrowid

            # Insert into non_veg_menu_items
            for item, cost in zip(food_items, costs):
                cursor.execute("""
                    INSERT INTO non_veg_menu_items (menu_id, food_item, cost)
                    VALUES (%s, %s, %s)
                """, (menu_id, item, int(cost)))

            connection.commit()
            cursor.close()
            connection.close()
            return "Non-Veg menu added successfully!"

        except Exception as e:
            print(f"Error adding non-veg menu: {e}")
            return "An error occurred while adding the menu."

    return render_template('add_non_veg_menu.html', meal=meal, mess=mess)


@app.route('/mess_dashboard')
def mess_dashboard():
    if session.get('role') != 'mess_official':
        return "Access Denied: Only mess officials can access this page."

    if 'mess_id' not in session:
        return redirect(url_for('login'))

    mess_id = session['mess_id']
    mess_name = session['mess']

    return render_template('mess_dashboard.html', mess_id=mess_id, mess_name=mess_name)

@app.route('/add_payment_details', methods=['GET', 'POST'])
def add_payment():
    if 'mess_id' not in session or session.get('role') != 'mess_official':
        return redirect(url_for('login'))

    mess_name = session.get('mess')
    meal = get_current_meal()

    if request.method == 'POST':
        s_id = request.form.get('s_id')
        food_item = request.form.get('food_item')
        payment_mode = request.form.get('payment_mode')
        flash("Payment details entered successfully!", "success")

        try:
            with get_db_connection('mess_management') as connection_main, connection_main.cursor() as cursor_main:
                # Validate student
                cursor_main.execute("SELECT mess FROM student WHERE s_id = %s", (s_id,))
                student_data = cursor_main.fetchone()

                if not student_data or student_data[0] != mess_name:
                    flash("Invalid student ID or student not from your mess.", "error")
                    return redirect(url_for('add_payment'))


                # Fetch amount for the food item using the mess database
                with get_db_connection(mess_name) as connection, connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT cost FROM non_veg_menu_items n
                        JOIN non_veg_menu_main m ON n.menu_id = m.menu_id
                        WHERE n.food_item = %s AND m.menu_date = CURDATE() AND m.meal = %s
                    """, (food_item, meal))
                    amount_data = cursor.fetchone()

                    if not amount_data:
                        flash("Invalid food item selected.", "error")
                        return redirect(url_for('add_payment'))
                    amount = amount_data[0]

                    # Insert payment
                    cursor_main.execute("""
                        INSERT INTO payment (s_id, mess, meal, food_item, payment_date, amount, payment_mode)
                        VALUES (%s, %s, %s, %s, CURDATE(), %s, %s)
                    """, (s_id, mess_name, meal, food_item, amount, payment_mode))

                    connection_main.commit()
                    return redirect(url_for('add_payment'))

        except Exception as e:
            print(f"Error adding payment: {e}")
            return "An error occurred while adding the payment."

    # Fetch available food items
    try:
        with get_db_connection(mess_name) as connection, connection.cursor() as cursor:
            cursor.execute("""
                SELECT n.food_item, n.cost
                FROM non_veg_menu_items n
                JOIN non_veg_menu_main m ON n.menu_id = m.menu_id
                WHERE m.menu_date = CURDATE() AND m.meal = %s
            """, (meal,))
            food_items = cursor.fetchall()

            if not food_items:
                print("No food items found for the current meal.")
    except Exception as e:
        print(f"Error fetching food items: {e}")
        food_items = []

    return render_template('add_payment.html', food_items=food_items, meal=meal, mess_name=mess_name)

@app.route('/review_payment_details', methods=['GET'])
def payment_summary():
    if 'mess_id' not in session or session['role'] != 'mess_official':
        return redirect(url_for('login'))

    mess_name = session.get('mess')

    try:
        connection = get_db_connection('mess_management')
        cursor = connection.cursor()

        # Query to get the summary of total amounts per food item per day per meal
        cursor.execute("""
            SELECT food_item, payment_date, meal, SUM(amount) AS total_amount
            FROM payment
            WHERE mess = %s AND payment_date >= CURDATE() - INTERVAL 30 DAY
            GROUP BY food_item, payment_date, meal
            ORDER BY payment_date DESC;
        """, (mess_name,))
        summary_data = cursor.fetchall()

    except Exception as e:
        print(f"Error fetching payment summary: {e}")
        summary_data = []
    finally:
        cursor.close()
        connection.close()

    return render_template('payment_summary.html', summary_data=summary_data, mess_name=mess_name)

@app.route('/payment_details/<food_item>/<payment_date>/<meal>', methods=['GET'])
def view_payment_details(food_item, payment_date, meal):
    if 'mess_id' not in session or session.get('role') != 'mess_official':
        return redirect(url_for('login'))

    mess_name = session.get('mess')

    try:
        connection = get_db_connection('mess_management')
        cursor = connection.cursor()
        cursor.execute("""
            SELECT s_id, amount, payment_mode
            FROM payment
            WHERE mess = %s AND payment_date = %s AND meal = %s AND food_item = %s
        """, (mess_name, payment_date, meal, food_item))
        details = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching student details: {e}")
        details = []
    finally:
        cursor.close()
        connection.close()

    return render_template('payment_details.html', details=details, payment_date=payment_date, meal=meal, food_item=food_item)

@app.route('/review_waste_feedback', methods=['GET'])
def review_waste_feedback():
    if 'mess_id' not in session or session['role'] != 'mess_official':
        return redirect(url_for('login'))

    try:
        connection = get_db_connection('mess_management')
        cursor = connection.cursor(dictionary=True)

        # Identify mess using floor information
        floor_to_mess = {
            'Ground': 'mess1',
            'First': 'mess1',
            'Second': 'mess2',
            'Third': 'mess2'
        }

        # Fetch waste summary data
        cursor.execute("""
            SELECT waste_date, floor, meal, SUM(total_waste) AS total_waste
            FROM waste_summary
            WHERE waste_date >= CURDATE() - INTERVAL 30 DAY
            GROUP BY waste_date, floor, meal
            ORDER BY waste_date DESC;
        """)
        waste_summary = cursor.fetchall()

        # Fetch detailed waste data
        cursor.execute("""
            SELECT w.waste_date, w.floor, w.meal, wd.food_item, wd.leftover_amount
            FROM waste_summary w
            JOIN waste_details wd ON w.waste_id = wd.waste_id
            WHERE w.waste_date >= CURDATE() - INTERVAL 30 DAY;
        """)
        waste_details = cursor.fetchall()

        # Add mess name to the results using floor info
        for data in waste_summary:
            data['mess'] = floor_to_mess.get(data['floor'])
        for data in waste_details:
            data['mess'] = floor_to_mess.get(data['floor'])

        # Convert to DataFrames for plotting
        df_summary = pd.DataFrame(waste_summary)
        df_details = pd.DataFrame(waste_details)

        # Plotly Graphs
        line_plot, bar_plot, pie_plot = None, None, None

        if not df_summary.empty:
            line_fig = px.line(df_summary, x='waste_date', y='total_waste', color='floor',
                                title='Total Waste Over Time (Per Floor)')
            line_plot = line_fig.to_html(full_html=False)

        if not df_details.empty:
            bar_fig = px.bar(df_details, x='food_item', y='leftover_amount', color='floor',
                              title='Food Item-wise Waste')
            bar_plot = bar_fig.to_html(full_html=False)

            pie_fig = px.pie(df_details, names='floor', values='leftover_amount',
                              title='Floor-wise Waste Distribution')
            pie_plot = pie_fig.to_html(full_html=False)

        return render_template('review_waste_feedback.html', 
                        line_plot=line_plot or '',
                        bar_plot=bar_plot or '',
                        pie_plot=pie_plot or '')

    except Exception as e:
        print(f"Error: {e}")
        return f"An error occurred while fetching waste data: {e}"
    finally:
        cursor.close()
        connection.close()

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

