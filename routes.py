from flask import Flask,render_template, request, redirect, session, url_for, flash
# from flask import Blueprint
# from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, JWTManager
from utils import get_menu, avg_rating, get_current_meal, is_odd_week
from db import get_db_connection
from datetime import datetime
# from app import app  
import plotly.express as px
import pandas as pd
import logging
import traceback
# import os
app = Flask(__name__)
# app = Blueprint('app', __name__)
# app = Flask(__name__)
# app = Blueprint('app', __name__)
# app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
# jwt = JWTManager(app)

@app.route('/')
@app.route('/home')
def home():
    meal, veg_menu_items, non_veg_menu1, non_veg_menu2 = get_menu() or (None, [], [], [])
    current_avg_rating_mess1, current_avg_rating_mess2 = avg_rating() or (None, None)
    if not meal or (not veg_menu_items and not non_veg_menu1 and not non_veg_menu2):
        return render_template("home_page.html", meal=None)
    return render_template("home_page.html",
        meal=meal,
        veg_menu_items=veg_menu_items,
        non_veg_menu1=non_veg_menu1,
        non_veg_menu2=non_veg_menu2,
        current_avg_rating_mess1=current_avg_rating_mess1,
        current_avg_rating_mess2=current_avg_rating_mess2)

# app = Flask(__name__)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        id = request.form.get('id')
        password = request.form.get('password')

        connection = get_db_connection()
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
            return redirect(url_for('student_dashboard'))

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

    # Check if the user is an admin
        cursor.execute("SELECT admin_id, username FROM admin WHERE admin_id = %s AND password = %s", (id, password))
        admin = cursor.fetchone()

        if admin:
            session['admin_id'] = admin[0]
            session['admin_name'] = admin[1]
            # session['admin_mess'] = mess_official[1]
            session['role'] = 'admin'
            cursor.close()
            connection.close()
            return redirect(url_for('admin_dashboard'))
        cursor.close()
        connection.close()
        flash("Invalid id or Password.",'error')
        return redirect(url_for('login'))
        
        # cursor.close()
        # connection.close()
    return render_template('login.html')

@app.route('/feedback', methods=['GET','POST'])
def feedback():
    # Ensure student is logged in
    if 'student_id' not in session:
        return redirect(url_for('login'))

    student_id = session['student_id']
    student_name = session['student_name']
    mess = session['mess']

    # Select the appropriate database
    # db_name = 'mess1' if mess == 'mess1' else 'mess2'

    meal, veg_menu_items, non_veg_menu1, non_veg_menu2 = get_menu()
    if not meal:
        flash("No meal available at the moment.", "error")
        return redirect(url_for('feedback'))

    exclusions = {'salt', 'sugar', 'ghee', 'podi', 'coffee', 'bbj', 'sprouts', 'curd', 'papad'}
    veg_items = [
        item for item in veg_menu_items 
        if item.lower() not in exclusions 
        and not any(keyword in item.lower() for keyword in ['banana', 'pickle', 'salad', 'cut fruit', 'sauce', 'chutney'])
    ]

    if request.method == 'POST':
        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            # Check if feedback already exists
            cursor.execute("""
                SELECT COUNT(*) FROM feedback_summary
                WHERE s_id = %s AND feedback_date = CURDATE() AND meal = %s
            """, (student_id, meal))
            feedback_exists = cursor.fetchone()[0]

            if feedback_exists:
                flash("You have already submitted feedback for this meal today.", "error")
                return redirect(url_for('feedback'))

            # Collect Feedback Data
            food_ratings = {}
            comments = {}
            non_veg_menu = non_veg_menu1 if mess == 'mess1' else non_veg_menu2
            menu_items = veg_items + non_veg_menu

            for item in menu_items:
                rating = request.form.get(f'rating_{item}')
                comment = request.form.get(f'comment_{item}')
                if rating:
                    food_ratings[item] = int(rating)
                    comments[item] = comment if comment else None

            if not food_ratings:
                flash("No ratings submitted. Please provide at least one rating.", "error")
                return redirect(url_for('feedback'))

            # Insert into feedback_summary
            cursor.execute("""
                INSERT INTO feedback_summary (s_id, feedback_date, meal, mess)
                VALUES (%s, CURDATE(), %s, %s)
            """, (student_id, meal, mess))
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

            flash("Feedback submitted successfully!", "success")
            return redirect(url_for('feedback'))

        except Exception as e:
            connection.rollback()
            flash("An error occurred while submitting feedback. Please try again.", "error")
            return redirect(url_for('feedback'))

    return render_template(
        'feedback.html',
        meal=meal,
        veg_menu_items=veg_items,
        non_veg_menu1=non_veg_menu1 if mess == 'mess1' else [],
        non_veg_menu2=non_veg_menu2 if mess == 'mess2' else [],
        student_name=student_name,
        mess=mess
    )

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

    exclusions = {'salt', 'sugar', 'ghee', 'podi', 'coffee', 'bbj', 'sprouts', 'curd', 'papad', 'rasam', 'fryums'}
    veg_items = [
        item for item in veg_menu_items 
        if item.lower() not in exclusions 
        and not any(keyword in item.lower() for keyword in ['banana', 'pickle', 'salad', 'cut fruit', 'sauce', 'chutney', 'juice'])
    ]

    if request.method == 'POST':
        floor = request.form.get('floor')
        waste_amount = request.form.get('waste_amount') 
        if floor not in ['Ground', 'First', 'Second', 'Third']:
            return "Invalid floor."

        prepared_amounts = {}
        leftover_amounts = {}

        # Determine menu based on floor
        if floor in ['Ground', 'First']:
            menu_items = veg_items + [item[0] for item in non_veg_menu1]
        else:
            menu_items = veg_items + [item[0] for item in non_veg_menu2]

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
            connection = get_db_connection()
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
    session.pop('_flashes', None)
    return render_template('waste_feedback.html', meal=meal, veg_menu_items=veg_items, 
                            non_veg_menu1=non_veg_menu1, non_veg_menu2=non_veg_menu2, mess=mess)

@app.route('/add_non_veg_menu', methods=['GET', 'POST'])
def add_non_veg_menu():
    # Ensure only mess officials can access this page
    if 'role' not in session or session['role'] != 'mess_official':
        flash ("Access Denied: Only mess officials can access this page",'error')
        return redirect(url_for('login'))
    
    mess = session.get('mess')
    if not mess:
        return "Error: Mess information not found."

    # Get meal using the existing function
    meal, _, _, _ = get_menu()
    if not meal:
        return "No meal available at the moment."
            
        # prvs_item = []
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT item_id, food_item, cost 
            FROM non_veg_menu_items i JOIN non_veg_menu_main m
            ON i.menu_id = m.menu_id
            WHERE menu_date = CURDATE() AND meal = %s AND mess = %s;
        """,(meal, mess))
        previous_items = cursor.fetchall()

        if request.method == 'POST':
            food_items = request.form.getlist('food_item[]')
            costs = request.form.getlist('cost[]')

            if not food_items or not costs or len(food_items) != len(costs):
                return "Invalid input. Ensure all fields are filled."
       
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
                """, (menu_id, item, cost))

            connection.commit()

            # Refresh `previous_items` after insert
            cursor.execute("""
                SELECT item_id, food_item, cost 
                FROM non_veg_menu_items i 
                JOIN non_veg_menu_main m ON i.menu_id = m.menu_id
                WHERE DATE(menu_date) = CURDATE() AND meal = %s AND mess = %s;
            """, (meal, mess))
            previous_items = cursor.fetchall()

        cursor.close()
        connection.close()
                
        # connection.commit()
        # cursor.close()
        # connection.close()
        # return "Non-Veg menu added successfully!"

    except Exception as e:
        print(f"Error adding non-veg menu: {e}")
        return "An error occurred while adding the menu."

    return render_template('add_non_veg_menu.html', meal=meal, mess=mess,  previous_items=previous_items)

@app.route('/delete_item', methods=['POST'])
def delete_item():
    if 'role' not in session or session['role'] != 'mess_official':
        flash ("Access Denied: Only mess officials can access this page",'error')
        return redirect(url_for('login'))

    mess = session.get('mess')
    if not mess:
        flash("Error: mess not found",'error')
        return redirect(url_for('login'))

    item_id = request.form.get('item_id')
    if not item_id:
        flash("Error: Item with given id not found",'error')
        return redirect(url_for('add_non_veg_menu'))

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("DELETE FROM non_veg_menu_items WHERE item_id = %s;", (item_id,))
        connection.commit()
        flash('Item deleted successfully!','success')
        return redirect(url_for('add_non_veg_menu'))
    
    except Exception as e:
        # connection.rollback()
        print(f"Error deleting item: {e}")
        flash('An error occurred while deleting the item.','error')
        return redirect(url_for('add_non_veg_menu'))
    
    finally:
        cursor.close()
        connection.close()

@app.route('/mess_dashboard')
def mess_dashboard():
    if 'role' not in session or session.get('role') != 'mess_official':
        return "Access Denied: Only mess officials can access this page."

    if 'mess_id' not in session:
        return redirect(url_for('login'))

    mess_id = session['mess_id']
    mess_name = session['mess']
    username = session.get('student_name', 'Mess Official')
    profile_image_url = "/static/profile_default.png"  # Change to actual profile image URL if available

    # Fetch Notification Count
    notification_count = 0
    try:
        connection = get_db_connection(mess_name)
        cursor = connection.cursor()

        # Check for High Waste Notifications
        cursor.execute(
            """
            SELECT COUNT(*) 
            FROM waste_summary
            GROUP BY floor
            HAVING SUM(total_waste) > 50
            """
        )
        notification_count += cursor.rowcount

        # Check for Low Feedback Notifications
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM feedback_details d
            JOIN feedback_summary s ON d.feedback_id = s.feedback_id
            WHERE mess=%s
            GROUP BY s.meal, s.feedback_date
            HAVING AVG(d.rating) < 3.0
            """
        ,(mess_name,))
        notification_count += cursor.rowcount
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error fetching notifications: {e}")
    # finally:
        

    return render_template('mess_dashboard.html', 
                            mess_id=mess_id, 
                            mess_name=mess_name, 
                            username=username,
                            profile_image_url=profile_image_url,
                            notification_count=notification_count)

@app.route('/add_payment_details', methods=['GET', 'POST'])
def add_payment():
    # Check session for authorization
    if 'mess_id' not in session or session.get('role') != 'mess_official':
        return redirect(url_for('login'))

    mess_name = session['mess']
    meal = get_current_meal()

    if request.method == 'POST':
        try:
            s_id = request.form.get('s_id')
            food_item = request.form.get('food_item')
            payment_mode = request.form.get('payment_mode')

            # Validate student
            with get_db_connection() as connection_main, connection_main.cursor() as cursor_main:
                cursor_main.execute("SELECT mess FROM student WHERE s_id = %s", (s_id,))
                student_data = cursor_main.fetchone()
                
                if not student_data or student_data[0] != mess_name:
                    flash("Invalid student ID or student not from your mess.", "error")
                    return redirect(url_for('add_payment'))
                cursor_main.fetchall()
                # Fetch amount for the selected food item
                # with get_db_connection() as connection, connection.cursor() as cursor:
                cursor_main.execute("""
                    SELECT cost FROM non_veg_menu_items n
                    JOIN non_veg_menu_main m ON n.menu_id = m.menu_id
                    WHERE n.food_item = %s AND m.menu_date = CURDATE() AND m.meal = %s AND mess = %s
                """, (food_item, meal, mess_name))
                amount_data = cursor_main.fetchone()

                if not amount_data:
                    flash("Invalid food item selected.", "error")
                    return redirect(url_for('add_payment'))

                amount = amount_data[0]
                cursor_main.fetchall()
                # Insert payment record
                cursor_main.execute("""
                    INSERT INTO payment (s_id, mess, meal, payment_date, food_item, amount, payment_mode)
                    VALUES (%s, %s, %s, CURDATE(), %s, %s, %s)
                """, (s_id, mess_name, meal, food_item, amount, payment_mode))

                connection_main.commit()
                cursor_main.close()
                connection_main.close()
                
                flash("Payment details entered successfully!", "success")
                return redirect(url_for('add_payment'))

        except Exception as e:
            print(f"Error adding payment: {e}")
            traceback.print_exc()
            flash("An error occurred while adding the payment.", "error")
            return redirect(url_for('add_payment'))

    # Fetch available food items
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute("""
                SELECT n.food_item, n.cost
                FROM non_veg_menu_items n
                JOIN non_veg_menu_main m ON n.menu_id = m.menu_id
                WHERE m.menu_date = CURDATE() AND m.meal = %s AND m.mess = %s
            """, (meal, mess_name))
            food_items = cursor.fetchall()
            connection.commit()
            cursor.close()
            connection.close()
            if not food_items:
                print("No food items found for the current meal.")
    except Exception as e:
        print(f"Error fetching food items: {e}")
        food_items = []

    return render_template('add_payment.html', food_items=food_items, meal=meal, mess_name=mess_name)

@app.route('/review_payment_details', methods=['GET'])
def payment_summary():
    if 'role' not in session or (session['role'] != 'mess_official' and session['role'] != 'admin'):
        return redirect(url_for('login'))

    if session['role'] == 'admin':
        # Ensure the admin has selected a mess
        if 'admin_mess' not in session:
            flash("Select mess first", "error")
            return redirect(url_for('select_mess'))
        mess_name = session['admin_mess']
        # print(mess_name)
    else:
        mess_name = session.get('mess')
        if not mess_name:
            flash("Invalid session. Please log in again.", "error")
            return redirect(url_for('login'))

    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            # Query to get the summary of total amounts per day and meal
            cursor.execute("""
                SELECT payment_date, GROUP_CONCAT(food_item SEPARATOR ', ') AS food_item, meal, SUM(amount) AS total_amount
                FROM payment
                WHERE mess = %s AND payment_date >= CURDATE() - INTERVAL 30 DAY
                GROUP BY payment_date, meal
                ORDER BY payment_date DESC;
            """, (mess_name,))
            summary_data = cursor.fetchall()

            if not summary_data:
                flash("No payment data found for the last 30 days.", "error")
                return render_template('payment_summary.html', summary_data=[], mess_name=mess_name)
            connection.commit()
            connection.close()
            cursor.close()
    except Exception as e:
        print("Error fetching payment summary:")
        logging.error("Error fetching payment summary", exc_info=True)
        flash("An error occurred while fetching payment data.", "error")
        return render_template('payment_summary.html', summary_data=[], mess_name=mess_name)

    # Pass data to the template
    return render_template('payment_summary.html', summary_data=summary_data, mess_name=mess_name)

@app.route('/payment_details/<food_item>/<payment_date>/<meal>', methods=['GET'])
def view_payment_details(food_item, payment_date, meal):
    if 'role' not in session or (session.get('role') != 'mess_official' and session['role'] != 'admin'):
        return redirect(url_for('login'))

    # mess_name = session.get('mess')
    if session['role'] == 'admin':
        # Ensure the admin has selected a mess
        if 'admin_mess' not in session:
            flash("Select mess first", "error")
            return redirect(url_for('select_mess'))
        mess_name = session['admin_mess']
        # print(mess_name)
    else:
        mess_name = session.get('mess')
        if not mess_name:
            flash("Invalid session. Please log in again.", "error")
            return redirect(url_for('login'))

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        food_items = tuple(food_item.split(', '))
        placeholders = ','.join(['%s'] * len(food_items))
        query = f"""
            SELECT s_id, food_item, amount, payment_mode
            FROM payment
            WHERE mess = %s AND payment_date = %s AND meal = %s AND food_item IN ({placeholders})
        """
        
        cursor.execute(query, (mess_name, payment_date, meal, *food_items))
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
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Fetch waste data
        cursor.execute("""
            SELECT w.waste_date, w.floor, w.meal, wd.food_item, wd.leftover_amount, w.total_waste
            FROM waste_summary w
            JOIN waste_details wd ON w.waste_id = wd.waste_id
            WHERE w.waste_date >= CURDATE() - INTERVAL 30 DAY;
        """)
        waste_data = cursor.fetchall()
        connection.close()

        if not waste_data:
            return render_template('review_waste_feedback.html', no_data=True)

        df = pd.DataFrame(waste_data)

        # Pie Chart for Waste Distribution (Mess1 vs Mess2)
        df['mess'] = df['floor'].apply(lambda x: 'mess1' if x in ['Ground', 'First'] else 'mess2')
        pie_fig = px.pie(df, names='mess', values='leftover_amount', title='Waste Distribution Between Mess1 and Mess2')
        pie_plot = pie_fig.to_html(full_html=False)

        # Drill-Down Pie Chart for Floor-wise Waste Distribution
        floor_pie_fig = px.pie(df, names='floor', values='leftover_amount', title='Floor-wise Waste Distribution')
        floor_pie_plot = floor_pie_fig.to_html(full_html=False)

        # Line Chart for Odd and Even Week Waste Trend
        df['week_type'] = df['waste_date'].apply(lambda x: 'Odd' if is_odd_week(x) else 'Even')
        odd_fig = px.line(df[df['week_type'] == 'Odd'], x='waste_date', y='total_waste', color='floor', title='Odd Week Waste Trend')
        even_fig = px.line(df[df['week_type'] == 'Even'], x='waste_date', y='total_waste', color='floor', title='Even Week Waste Trend')
        odd_plot = odd_fig.to_html(full_html=False)
        even_plot = even_fig.to_html(full_html=False)

        # Line Chart with Moving Average
        df['moving_avg'] = df['total_waste'].rolling(window=7, min_periods=1).mean()
        moving_avg_fig = px.line(df, x='waste_date', y='moving_avg', color='floor', title='7-Day Moving Average of Waste')
        moving_avg_plot = moving_avg_fig.to_html(full_html=False)

        # Scatter Plot for Waste Trends
        scatter_fig = px.scatter(df, x='food_item', y='leftover_amount', color='floor', size='leftover_amount', title='Scatter Plot of Food Waste')
        scatter_plot = scatter_fig.to_html(full_html=False)

        return render_template('review_waste_feedback.html', pie_plot=pie_plot, floor_pie_plot=floor_pie_plot, odd_plot=odd_plot, even_plot=even_plot, moving_avg_plot=moving_avg_plot, scatter_plot=scatter_plot)

    except Exception as e:
        print(f"Error: {e}")
        return f"An error occurred while fetching waste data: {e}"

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# Notifications Route
@app.route('/notifications')
def notifications():
    if 'role' not in session or (session['role'] == 'student' and 'student_id' not in session) or (session['role'] == 'mess_official' and 'mess_id' not in session):
        return redirect(url_for('home'))


    mess_name = session['mess']
    notifications = []
    # print(mess_name)
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        # connection1 = get_db_connection(mess_name)
        # cursor1 = connection1.cursor()
        # Check for high waste
        cursor.execute(
            """
            SELECT floor, SUM(total_waste) as total_waste
            FROM waste_summary
            GROUP BY floor
            HAVING SUM(total_waste) > 50
            """
        )
        for floor, waste in cursor.fetchall():
            notifications.append(f"⚠️ High waste recorded on Floor {floor} with {waste} Kg.")

        # Check for low feedback
        cursor.execute(
            """
            SELECT AVG(d.rating), s.meal, s.feedback_date FROM feedback_details d
            JOIN feedback_summary s ON d.feedback_id = s.feedback_id
            WHERE mess = %s
            GROUP BY s.meal, s.feedback_date
            HAVING AVG(d.rating) < 3.0
            """,(mess_name,)
        )
        for rating, meal, day in cursor.fetchall():
            notifications.append(f"❗ Low feedback detected for {meal} on {day} with Avg. Rating {round(rating, 2)}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        connection.close()
        # cursor1.close()
        # connection1.close()

    return render_template('notifications.html', notifications=notifications)

# Profile Route
@app.route('/profile')
def profile():
    role = session.get('role')
    user_id = session.get('student_id') or session.get('mess_id')

    if not user_id:
        return "Error: No user logged in."

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        if role == 'student':
            cursor.execute("SELECT name, mess FROM student WHERE s_id = %s", (user_id,))
        elif role == 'mess_official':
            cursor.execute("SELECT mess FROM mess_data WHERE mess_id = %s", (user_id,))
        else:
            return "Error: Invalid user role."

        user_data = cursor.fetchone()

        if not user_data:
            return "Error: User not found."
        
        # Convert to dictionary
        user_data = dict(zip([desc[0] for desc in cursor.description], user_data))
        return render_template('profile.html', user_data=user_data, role=role)

    except Exception as e:
        return f"Database error: {e}"
    finally:
        cursor.close()
        connection.close()

# Admin selection for mess
@app.route('/select_mess', methods=['GET', 'POST'])
def select_mess():
    if request.method == 'POST':
        selected_mess = request.form.get('selected_mess')

        # Check if the mess selection is valid
        if selected_mess in ['mess1', 'mess2']:
            session['admin_mess'] = selected_mess
            flash(f"{selected_mess} selected successfully!", "success")
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid mess selection. Please try again.", "error")

    return render_template('admin_select_mess.html')

# Admin Dashboard
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    # if session['admin_mess'] not in ['mess1', 'mess2']:
    #     return redirect(url_for('select_mess'))
    # mess_name = session['admin_mess']
    return render_template('admin_dashboard.html')

# Waste Summary
@app.route('/review_waste', methods=['GET'])
def waste_summary():
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    # mess_name = session['admin_mess']
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute("""
                SELECT floor, SUM(total_waste) AS total_waste
                FROM waste_summary
                WHERE waste_date >= CURDATE() - INTERVAL 30 DAY
                GROUP BY floor
                ORDER BY floor;
            """)
            waste_data = cursor.fetchall()
    except Exception as e:
        print("Error fetching waste summary:")
        traceback.print_exc()
        flash("An error occurred while fetching waste data.", "error")
        waste_data = []

    return render_template('waste_summary.html', waste_data=waste_data)

@app.route('/waste_detail/<floor>', methods=['GET'])
def waste_detail(floor):
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute('''
                SELECT waste_date AS date, SUM(total_waste) AS total_waste
                FROM waste_summary
                WHERE floor = %s AND (waste_date >= CURDATE() - INTERVAL 30 DAY)
                GROUP BY waste_date
                ORDER BY waste_date DESC;
            ''',(floor,))
            waste_data = cursor.fetchall()

    except Exception as e:
        print("Error fetching waste summary:")
        traceback.print_exc()
        flash("An error occurred while fetching waste data.", "error")
        waste_data = []
    
    return render_template('waste_detail.html', waste_data = waste_data, floor=floor )
    
@app.route('/daily_waste/<floor>/<waste_date>', methods=['GET'])
def daily_waste(floor, waste_date):
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute('''
                SELECT meal, total_waste
                FROM waste_summary
                WHERE floor = %s AND waste_date = %s
            ''',(floor, waste_date))
            waste_data = cursor.fetchall()

    except Exception as e:
        print("Error fetching waste summary:")
        traceback.print_exc()
        flash("An error occurred while fetching waste data.", "error")
        waste_data = []
    
    return render_template('daily_waste.html', waste_data = waste_data, floor=floor, waste_date=waste_date)

@app.route('/timely_waste_detail/<floor>/<waste_date>/<meal>', methods=['GET'])
def timely_waste_detail(floor, waste_date, meal):
    if 'admin_id' not in session:
        return redirect(url_for('login'))
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            cursor.execute('''
                SELECT food_item, prepared_amount, leftover_amount
                FROM waste_details d JOIN waste_summary s
                ON d.waste_id = s.waste_id
                WHERE floor = %s AND waste_date = %s AND meal = %s
            ''',(floor, waste_date, meal))
            waste_data = cursor.fetchall()

    except Exception as e:
        print("Error fetching waste summary:")
        traceback.print_exc()
        flash("An error occurred while fetching waste data.", "error")
        waste_data = []

    return render_template('timely_waste_detail.html', waste_data = waste_data, floor=floor, waste_date=waste_date, meal=meal)

@app.route('/feedback_summary', methods=['GET'])
def feedback_summary():
    if 'admin_id' not in session:
        flash("Please log in as an admin to access this page.", "error")
        return redirect(url_for('login'))

    mess_name = session.get('admin_mess')
    if not mess_name:
        return redirect(url_for('select_mess'))
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            # Query to get the feedback summary with average ratings
            cursor.execute('''
                SELECT s.feedback_date, s.meal, COUNT(DISTINCT s.s_id) AS total_students, AVG(d.rating) AS avg_rating
                FROM feedback_summary s
                JOIN feedback_details d ON s.feedback_id = d.feedback_id
                WHERE mess = %s
                GROUP BY s.feedback_date, s.meal
                ORDER BY s.feedback_date DESC;
            ''',(mess_name,))
            feedback_summary_data = cursor.fetchall()

            connection.close()
            cursor.close()
            if not feedback_summary_data:
                flash("No feedback data available.", "info")
                return render_template('feedback_summary.html', feedback_summary_data=[])

    except Exception as e:
        print(f"Error fetching feedback summary: {e}")
        flash("An error occurred while fetching feedback data.", "error")
        return render_template('feedback_summary.html', feedback_summary_data=[])

    return render_template('feedback_summary.html', feedback_summary_data=feedback_summary_data)

@app.route('/feedback_detail/<feedback_date>/<meal>', methods=['GET'])
def feedback_detail(feedback_date, meal):
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    mess_name = session.get('admin_mess')
    if not mess_name:
        flash("Please select a mess.", "error")
        return redirect(url_for('select_mess'))
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            # Fetch student IDs and their average feedback rating for the selected date and meal
            cursor.execute('''
                SELECT fs.s_id, ROUND(AVG(fd.rating), 2) AS avg_rating
                FROM feedback_summary fs
                JOIN feedback_details fd ON fs.feedback_id = fd.feedback_id
                WHERE fs.feedback_date = %s AND fs.meal = %s AND mess = %s
                GROUP BY fs.s_id
                HAVING COUNT(fd.rating) > 0
            ''', (feedback_date, meal, mess_name))
            feedback_data = cursor.fetchall()
            connection.close()
            cursor.close()
    except Exception as e:
        print(f"Error fetching feedback details: {e}")
        flash(f"An error occurred: {str(e)}", "error")
        return redirect(url_for('feedback_summary'))

    return render_template('feedback_details.html', feedback_data=feedback_data, feedback_date=feedback_date, meal=meal)

@app.route('/student_feedback/<s_id>/<feedback_date>/<meal>', methods=['GET'])
def student_feedback(s_id, feedback_date, meal):
    if 'admin_id' not in session:
        return redirect(url_for('login'))

    mess_name = session.get('admin_mess')
    if not mess_name:
        flash("Please select a mess.", "error")
        return redirect(url_for('select_mess'))
    try:
        with get_db_connection() as connection, connection.cursor() as cursor:
            # Fetch detailed feedback for a specific student
            cursor.execute('''
                SELECT fd.food_item, fd.rating, fd.comments
                FROM feedback_summary fs
                JOIN feedback_details fd ON fs.feedback_id = fd.feedback_id
                WHERE fs.s_id = %s AND fs.feedback_date = %s AND fs.meal = %s AND mess = %s
            ''', (s_id, feedback_date, meal, mess_name))
            feedback_details = cursor.fetchall()
            connection.close()
            cursor.close()
    except Exception as e:
        print(f"Error fetching student feedback: {e}")
        flash("An error occurred while fetching student feedback.", "error")
        return redirect(url_for('feedback_detail', feedback_date=feedback_date, meal=meal))

    return render_template('student_feedback_details.html', feedback_details=feedback_details, s_id=s_id, feedback_date=feedback_date, meal=meal)

@app.route('/update_veg_menu', methods=['GET', 'POST'])
def update_veg_menu():
    if 'admin_id' not in session:
        flash('Unauthorized access. Please log in.', 'error')
        return redirect(url_for('login'))

    week_type = 'Odd' if is_odd_week() else 'Even'
    day = datetime.now().strftime('%A')
    meal = get_current_meal()

    if request.method == 'POST':
        try:
            food_items = request.form.getlist('food_item[]')

            if not food_items or any(not item.strip() for item in food_items):
                flash('Please enter valid food items.', 'error')
                return redirect(url_for('update_veg_menu'))

            connection = get_db_connection()
            cursor = connection.cursor()

            # Clear previous data for today
            cursor.execute('''
                DELETE FROM temporary_menu WHERE week_type=%s AND day=%s AND meal=%s
            ''', (week_type, day, meal))

            # Insert new data
            for item in food_items:
                cursor.execute('''
                    INSERT INTO temporary_menu (week_type, day, meal, food_item)
                    VALUES (%s, %s, %s, %s)
                ''', (week_type, day, meal, item.strip()))

            connection.commit()
            flash('Veg menu updated temporarily for today.', 'success')
        except Exception as e:
            connection.rollback()
            flash(f'Error: {e}', 'error')
        finally:
            cursor.close()
            connection.close()
        return redirect(url_for('update_veg_menu'))

    return render_template('update_veg_menu.html', week_type=week_type, day=day, meal=meal)

@app.route('/student_dashboard')
def student_dashboard():
    if 'student_id' not in session or session['role'] != 'student':
        flash("Not yet logged in",'error')
        return redirect(url_for('login'))
    
    student_id = session['student_id']
    mess_name = session['mess']
    connection = get_db_connection()
    cursor = connection.cursor()

    # Greeting
    current_hour = datetime.now().hour
    if current_hour < 12:
        greeting = 'Good Morning'
    elif current_hour < 18:
        greeting = 'Good Afternoon'
    else:
        greeting = 'Good Evening'

    # Meal Reminder
    cursor.execute("SELECT DISTINCT s_id FROM feedback_summary WHERE s_id = %s AND feedback_date = CURDATE() AND mess = %s", (student_id, mess_name))
    feedback_given = set(row[0] for row in cursor.fetchall())
    if (student_id) in feedback_given:
        feedback_status = "Feedback Submitted"
    else:
        feedback_status = "Feedback Pending"

    # Leaderboard (Top-rated meals)
    cursor.execute("""
        SELECT food_item, ROUND(AVG(d.rating), 2) as avg_rating
        FROM feedback_details d
        JOIN feedback_summary s ON d.feedback_id = s.feedback_id
        WHERE mess = %s
        GROUP BY food_item
        ORDER BY avg_rating DESC
        LIMIT 5
        """,(mess_name,))
    leaderboard = cursor.fetchall()

    # Waste Tracking Insight
    fr = ['Ground', 'First'] if mess_name == 'mess1' else ['Second', 'Third']
    cursor.execute("""
        SELECT floor, SUM(total_waste) as total_waste
        FROM waste_summary
        WHERE floor IN (%s, %s)
        GROUP BY floor
    """, tuple(fr))
    waste_insight = cursor.fetchall()

    # Monthly Average Rating
    cursor.execute("""
        SELECT s.mess, ROUND(AVG(d.rating), 2) as avg_rating
        FROM feedback_details d
        JOIN feedback_summary s ON d.feedback_id = s.feedback_id
        WHERE MONTH(d.created_at) = MONTH(CURDATE())-1
        GROUP BY s.mess
    """)
    monthly_avg_ratings = cursor.fetchall()

    # Clamp the avg_rating to be between 1 and 5
    monthly_avg_ratings = [(mess, max(1, min(avg_rating, 5))) for mess, avg_rating in monthly_avg_ratings]

    connection.close()

    return render_template('student_dashboard.html',
                           greeting=greeting,
                           feedback_status=feedback_status,
                           leaderboard=leaderboard,
                           waste_insight=waste_insight,
                           monthly_avg_ratings=monthly_avg_ratings)

def main():
    login()
    payment_summary()

if __name__=="__main__":
    main()
