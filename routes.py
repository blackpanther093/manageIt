from flask import Flask,render_template, request, redirect, session, url_for, flash
# from flask import Blueprint
# from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, JWTManager
from utils import get_menu, avg_rating, get_current_meal, is_odd_week, get_fixed_time
from db import get_db_connection
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
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
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        id = request.form.get('id')
        password = request.form.get('password')

        connection = get_db_connection()
        cursor = connection.cursor()

        # Check if the user is a student
        cursor.execute("SELECT s_id, name, mess, password FROM student WHERE BINARY s_id = %s", (id,))
        student = cursor.fetchone()

        if student and check_password_hash(student[3], password):
            session['student_id'] = student[0]
            session['student_name'] = student[1]
            session['mess'] = student[2]
            session['role'] = 'student'
            cursor.close()
            connection.close()
            return redirect(url_for('student_dashboard'))

        # Check if the user is a mess official
        cursor.execute("SELECT mess_id, mess, password FROM mess_data WHERE BINARY mess_id = %s", (id,))
        mess_official = cursor.fetchone()

        if mess_official and check_password_hash(mess_official[2], password):
            session['mess_id'] = mess_official[0]
            session['mess'] = mess_official[1]
            session['role'] = 'mess_official'
            # print(session)
            cursor.close()
            connection.close()
            return redirect(url_for('mess_dashboard'))

        # Check if the user is an admin
        cursor.execute("SELECT admin_id, username, password FROM admin WHERE BINARY admin_id = %s", (id,))
        admin = cursor.fetchone()

        if admin and check_password_hash(admin[2], password):
            session['admin_id'] = admin[0]
            session['admin_name'] = admin[1]
            session['role'] = 'admin'
            cursor.close()
            connection.close()
            return redirect(url_for('admin_dashboard'))

        cursor.close()
        connection.close()
        flash("Invalid ID or Password.", 'error')
        return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    student_id = session.get('student_id')
    student_name = session.get('student_name')
    mess = session.get('mess')
    meal = get_current_meal()
    if student_id:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT DISTINCT s_id FROM feedback_summary WHERE s_id = %s AND feedback_date = CURDATE() AND mess = %s AND meal = %s", (student_id, mess, meal))
        feedback_given = set(row[0] for row in cursor.fetchall())
        cursor.close()
        connection.close()
        if student_id in feedback_given:
            flash("Feedback already submitted for today.", "error")
            return redirect(url_for('home'))
    
    if not student_id or not student_name or not mess:
        flash("Session expired. Please log in again.", "error")
        return redirect(url_for('home'))

    # Time check and meal filtering logic
    current_hour = get_fixed_time().hour
    meal, veg_menu_items, non_veg_menu1, non_veg_menu2 = get_menu()
    if((meal == 'Breakfast' and current_hour < 7) or 
       (meal == 'Lunch' and current_hour < 12) or 
       (meal == 'Snacks' and current_hour < 17) or 
       (meal == 'Dinner' and current_hour < 19)):
        meal = None

    if not meal:
        flash("No meal available at the moment", "error")
        return redirect('/')

    # Filter veg menu
    exclusions = {'salt', 'sugar', 'ghee', 'podi', 'coffee', 'bbj', 'sprouts', 'curd', 'papad'}
    veg_items = [
        item for item in veg_menu_items 
        if item.lower() not in exclusions 
        and not any(keyword in item.lower() for keyword in ['banana', 'pickle', 'salad', 'cut fruit', 'sauce', 'chutney'])
    ]

    if request.method == 'POST' and student_id:
        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            # Check for duplicate feedback
            cursor.execute("""
                SELECT COUNT(*) FROM feedback_summary
                WHERE s_id = %s AND feedback_date = CURDATE() AND meal = %s
            """, (student_id, meal))
            if cursor.fetchone()[0]:
                flash("You have already submitted feedback for this meal today.", "error")
                return redirect('/')

            # Collect ratings and comments
            food_ratings = {}
            comments = {}
            non_veg_menu = non_veg_menu1 if mess == 'mess1' else non_veg_menu2
            menu_items = veg_items + non_veg_menu

            for item in menu_items:
                rating = request.form.get(f'rating_{item}')
                comment = request.form.get(f'comment_{item}')
                if rating:
                    food_ratings[item] = int(rating)
                    comments[item] = comment or None

            if not food_ratings:
                flash("No ratings submitted. Please provide at least one rating.", "error")
                return redirect(url_for('feedback'))

            # Insert into summary
            cursor.execute("""
                INSERT INTO feedback_summary (s_id, feedback_date, meal, mess)
                VALUES (%s, CURDATE(), %s, %s)
            """, (student_id, meal, mess))
            feedback_id = cursor.lastrowid

            # Insert into details
            for item, rating in food_ratings.items():
                food_item = item[0] if isinstance(item, tuple) else item
                cursor.execute("""
                    INSERT INTO feedback_details (feedback_id, food_item, rating, comments)
                    VALUES (%s, %s, %s, %s)
                """, (feedback_id, food_item, rating, comments.get(item)))

            connection.commit()
            flash("Feedback submitted successfully!", "success")
            return redirect('/')

        except Exception as e:
            connection.rollback()
            flash(f"An error occurred while submitting feedback: {e}", "error")
            return redirect(url_for('feedback'))

        finally:
            cursor.close()
            connection.close()

    return render_template(
        'feedback.html',
        meal=meal,
        veg_menu_items=veg_items,
        non_veg_menu1=non_veg_menu1 if mess == 'mess1' else [],
        non_veg_menu2=non_veg_menu2 if mess == 'mess2' else [],
        student_name=student_name,
        mess=mess
    )

@app.route('/enter-id', methods=['GET', 'POST'])
def enter_id():
    student_id = session.get('student_id')  # Safe way to check if logged in
    # student_name = session.get('student_name')
    mess = session.get('mess')
    meal = get_current_meal()
    if student_id:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT DISTINCT s_id FROM feedback_summary WHERE s_id = %s AND feedback_date = CURDATE() AND mess = %s AND meal = %s", (student_id, mess, meal))
        feedback_given = set(row[0] for row in cursor.fetchall())
        cursor.close()
        connection.close()
        if student_id in feedback_given:
            flash("Feedback already submitted for today.", "error")
            return redirect(url_for('home'))
        else:
           return redirect(url_for('feedback'))
        
    if request.method == 'POST':
        student_id = request.form.get('s_id')

        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT name, mess FROM student WHERE s_id = %s", (student_id,))
            data = cursor.fetchone()

            if not data:
                flash("Invalid student ID. Please try again.", "error")
                return redirect(url_for('enter_id'))

            student_name, mess = data
            session['student_id'] = student_id
            session['student_name'] = student_name
            session['mess'] = mess

            return redirect(url_for('feedback'))  # All set, go to feedback

        except Exception as e:
            flash(f"Database error: {e}", "error")
            return redirect(url_for('enter_id'))

        finally:
            cursor.close()
            connection.close()

    return render_template('enter_id.html')  # First-time load or failed submission

@app.route('/waste', methods=['GET', 'POST'])
def waste():
    # Ensure only mess officials can access this page
    if 'role' not in session or session['role'] != 'mess_official':
        flash ("Access Denied: Only mess officials can access this page.",'error')
        return redirect(url_for('login'))
    
    mess = session.get('mess')
    if not mess:
        flash ("Error: Mess information not found.",'error')
        return redirect(url_for('login'))
    
    current_hour = get_fixed_time().hour

    meal, veg_menu_items, non_veg_menu1, non_veg_menu2 = get_menu()
    if((meal == 'Breakfast' and current_hour < 9) or (meal == 'Lunch' and current_hour < 14) or (meal == 'Snacks' and current_hour < 18) or (meal == 'Dinner' and current_hour < 21)):
        meal = None
    if not meal:
        flash( "No meal available at the moment.",'error')
        return redirect(url_for('mess_dashboard'))

    exclusions = {'salt', 'sugar', 'ghee', 'podi', 'coffee', 'bbj', 'sprouts', 'curd', 'papad', 'rasam', 'fryums', 'milk', 'tea'}
    veg_items = [
        item for item in veg_menu_items 
        if item.lower() not in exclusions 
        and not any(keyword in item.lower() for keyword in ['banana', 'pickle', 'salad', 'cut fruit', 'sauce', 'chutney', 'juice'])
    ]

    if request.method == 'POST':
        floor = request.form.get('floor')
        waste_amount = request.form.get('waste_amount') 
        if floor not in ['Ground', 'First', 'Second', 'Third']:
            flash ("Invalid floor.",'error')
            return redirect(url_for('waste'))

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
                    flash (f"Invalid input for {food_item}. Please enter numbers only.",'error')
                    return redirect(url_for('waste'))
                
        if not prepared_amounts:
            flash ("No valid data submitted.",'error')
            return redirect(url_for('waste'))
        
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
            flash ("Waste data submitted successfully!",'success')
            return redirect(url_for('mess_dashboard'))
        except Exception as e:
            print(f"Error storing waste data: {e}")
            flash ("An error occurred while submitting waste data.",'error')
            return redirect(url_for('waste'))
        
    # session.pop("flashed_messages", None)
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
        flash ("Error: Mess information not found.",'error')
        return redirect(url_for(login))

    # Get meal using the existing function
    meal, _, _, _ = get_menu()
    if not meal:
        flash ("No meal available at the moment.",'error')
        return redirect(url_for(home))
        
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
                flash ("Invalid input. Ensure all fields are filled.",'error')
                return redirect(url_for(add_non_veg_menu))
       
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
            flash( "Item added successfully.",'success')
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
        flash( "An error occurred while adding the menu.",'error')
        return redirect(url_for(add_non_veg_menu))

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
        flash('Item deleted successfully!','error')
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
    # if session.get('role') != 'mess_official':
    #     flash ("Access Denied: Only mess officials can access this page.",'error')

    if 'mess_id' not in session or session.get('role') != 'mess_official':
        flash("Access Denied, Login again",'error')
        return redirect(url_for('login'))

    mess_id = session['mess_id']
    mess_name = session['mess']
    # print(mess_name)
    username = session.get('student_name', 'Mess Official')
    profile_image_url = "/static/profile_default.png"  # Change to actual profile image URL if available 

    return render_template('mess_dashboard.html', 
                            mess_id=mess_id, 
                            mess_name=mess_name, 
                            username=username,
                            profile_image_url=profile_image_url,
    )

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
                    SELECT item_id,cost FROM non_veg_menu_items n
                    JOIN non_veg_menu_main m ON n.menu_id = m.menu_id
                    WHERE n.food_item = %s AND m.menu_date = CURDATE() AND m.meal = %s AND mess = %s
                """, (food_item, meal, mess_name))
                amount_data = cursor_main.fetchone()

                if not amount_data:
                    flash("Invalid food item selected.", "error")
                    return redirect(url_for('add_payment'))

                item_id, amount = amount_data
                cursor_main.fetchall()
                # Insert payment record
                cursor_main.execute("""
                    INSERT INTO payment (s_id, mess, meal, payment_date, food_item, amount, payment_mode, item_id)
                    VALUES (%s, %s, %s, CURDATE(), %s, %s, %s, %s)
                """, (s_id, mess_name, meal, food_item, amount, payment_mode, item_id))

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

        # Fetch waste data for the last 30 days
        cursor.execute("""
            SELECT w.waste_date, w.floor, w.meal, wd.food_item, wd.leftover_amount, w.total_waste
            FROM waste_summary w
            JOIN waste_details wd ON w.waste_id = wd.waste_id
            WHERE w.waste_date >= CURDATE() - INTERVAL 30 DAY;
        """)
        waste_data = cursor.fetchall()
        
        if not waste_data:
            connection.close()
            return render_template('review_waste_feedback.html', no_data=True)
        
        # Convert data to DataFrame for analysis
        df = pd.DataFrame(waste_data)
        
        # Convert waste_date to Pandas Timestamp and remove timezone info
        df['waste_date'] = pd.to_datetime(df['waste_date']).dt.tz_localize(None)
        
        # Determine mess based on floor names
        df['mess'] = df['floor'].apply(lambda x: 'mess1' if x in ['Ground', 'First'] else 'mess2')
        
        # Total Waste Comparison Pie Chart (Mess1 vs Mess2)
        total_waste_pie_fig = px.pie(df, names='mess', values='total_waste', title='Total Waste Distribution (Mess1 vs Mess2)')
        total_waste_pie = total_waste_pie_fig.to_html(full_html=False)
        
        # Pie Chart for Floor-wise Waste Distribution (using leftover_amount)
        floor_pie_fig = px.pie(df, names='floor', values='leftover_amount', title='Floor-wise Waste Distribution')
        floor_pie_plot = floor_pie_fig.to_html(full_html=False)
        
        # Line Charts for Odd and Even Week Waste Trends using x.date() for is_odd_week()
        df['week_type'] = df['waste_date'].apply(lambda x: 'Odd' if is_odd_week(x.date()) else 'Even')
        odd_fig = px.line(df[df['week_type'] == 'Odd'], x='waste_date', y='total_waste', color='floor', title='Odd Week Waste Trend')
        even_fig = px.line(df[df['week_type'] == 'Even'], x='waste_date', y='total_waste', color='floor', title='Even Week Waste Trend')
        odd_plot = odd_fig.to_html(full_html=False)
        even_plot = even_fig.to_html(full_html=False)
        
        # Line Chart with 7-Day Moving Average of Waste
        df['moving_avg'] = df['total_waste'].rolling(window=7, min_periods=1).mean()
        moving_avg_fig = px.line(df, x='waste_date', y='moving_avg', color='floor', title='7-Day Moving Average of Waste')
        moving_avg_plot = moving_avg_fig.to_html(full_html=False)
        
        # Scatter Plot for Correlation Analysis: (Food Rating vs Waste)
        scatter_fig = px.scatter(df, x='food_item', y='leftover_amount', color='floor',
                                 size='leftover_amount', title='Correlation Analysis: Food Rating vs Waste')
        correlation_plot = scatter_fig.to_html(full_html=False)
        
        # Predictive Analysis: Simple Forecast using the latest moving average as a placeholder
        last_date = df['waste_date'].max()
        future_dates = pd.date_range(last_date, periods=8, freq='D')[1:]
        last_avg = df['moving_avg'].iloc[-1]
        predicted_waste = [last_avg for _ in range(len(future_dates))]
        pred_df = pd.DataFrame({'waste_date': future_dates, 'predicted_waste': predicted_waste})
        predictive_fig = px.line(pred_df, x='waste_date', y='predicted_waste', title='Predictive Analysis: Future Waste Trends')
        predictive_plot = predictive_fig.to_html(full_html=False)
        
        # Use get_fixed_time() and convert its return value to a Pandas Timestamp for calculations
        current_time = get_fixed_time()  # Returns a datetime object in IST
        current_ts = pd.Timestamp(current_time).tz_localize(None)
        current_week_start = current_ts - pd.Timedelta(days=current_ts.weekday())
        two_weeks_ago = current_ts - pd.Timedelta(days=14)
        
        # Top 5 Most Wasted Food Items This Week (by leftover_amount)
        df_current_week = df[df['waste_date'] >= current_week_start]
        top5_df = df_current_week.groupby('food_item', as_index=False)['leftover_amount'].sum().nlargest(5, 'leftover_amount')
        top5_waste_list = top5_df.to_dict(orient='records')
        
        # Best Waste-Reduction Day over the past 2 weeks and its menu
        df_two_weeks = df[df['waste_date'] >= two_weeks_ago]
        day_waste = df_two_weeks.groupby('waste_date', as_index=False)['total_waste'].mean()
        best_day_row = day_waste.nsmallest(1, 'total_waste').iloc[0]
        best_day = pd.to_datetime(best_day_row['waste_date']).strftime('%A, %Y-%m-%d')
        best_day_week_type = 'Odd' if is_odd_week(pd.to_datetime(best_day_row['waste_date']).date()) else 'Even'
        
        # Fetch the menu for the best day using your get_menu() function
        best_day_menu = get_menu(best_day_row['waste_date'])
        
        connection.close()
        
        return render_template('review_waste_feedback.html',
                               no_data=False,
                               total_waste_pie=total_waste_pie,
                               floor_pie_plot=floor_pie_plot,
                               odd_plot=odd_plot,
                               even_plot=even_plot,
                               moving_avg_plot=moving_avg_plot,
                               correlation_plot=correlation_plot,
                               predictive_plot=predictive_plot,
                               top_5_wasted_food=top5_waste_list,
                               best_day=best_day,
                               best_day_week_type=best_day_week_type,
                               best_day_menu=best_day_menu)
    except Exception as e:
        print(f"Error: {e}")
        flash(f"An error occurred while fetching waste data: {e}", 'error')
        return redirect(url_for('mess_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# Notifications Route
@app.route('/notifications')
def notifications():
    if 'role' not in session or (session['role'] == 'student' and 'student_id' not in session) or (session['role'] == 'mess_official' and 'mess_id' not in session):
        flash("Unauthorized access!", "error")
        return redirect(url_for('login'))

    mess_name = session['mess']
    role = session['role']
    notifications = []
    back_url = '/mess_dashboard' if role == 'mess_official' else '/student_dashboard'
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # 📌 1️⃣ Fetch notifications from the `notifications` table (last 7 days only)
        if role == 'student':
            cursor.execute(
                "SELECT message, created_at FROM notifications WHERE recipient_type IN ('student') AND created_at >= NOW() - INTERVAL 7 DAY ORDER BY created_at DESC"
            )
        elif role == 'mess_official':
            cursor.execute(
                "SELECT message, created_at FROM notifications WHERE recipient_type IN ('mess_official') AND created_at >= NOW() - INTERVAL 7 DAY ORDER BY created_at DESC"
            )

        # 📌 Store message with timestamp
        notifications += [(row[0], row[1]) for row in cursor.fetchall()]

        if role == 'mess_official':
            # ⚠️ High waste warning
            if mess_name == 'mess1':
                floor1, floor2 = 'Ground', 'First'
            elif mess_name == 'mess2':
                floor1, floor2 = 'Second', 'Third'

            # placeholders = ', '.join(['%s'] * len(floor))
            cursor.execute("""
                SELECT floor, SUM(total_waste) as total_waste, waste_date 
                FROM waste_summary 
                WHERE waste_date >= CURDATE()  - INTERVAL 7 DAY AND (floor = %s OR floor = %s)
                GROUP BY floor, waste_date
                HAVING SUM(total_waste) > 50
                ORDER BY waste_date DESC;
            """, (floor1, floor2))
            
            # cursor.execute(query, floor)
            rows = cursor.fetchall()
            # print("⚠️ High waste rows:", rows)
            for fl, waste, time in rows:
                notifications.append((f"⚠️ High waste recorded on {fl} Floor with {waste} Kg.", time))

            # ❗ Low feedback alert
            cursor.execute(
                """
                SELECT AVG(d.rating), s.meal, s.feedback_date 
                FROM feedback_details d
                JOIN feedback_summary s ON d.feedback_id = s.feedback_id
                WHERE mess = %s AND s.feedback_date >= NOW() - INTERVAL 7 DAY
                GROUP BY s.meal, s.feedback_date
                HAVING AVG(d.rating) < 3.0
                ORDER BY s.feedback_date DESC;
                """, (mess_name,)
            )
            rows = cursor.fetchall()
            # print("⚠️ Low feedback rows:", rows)
            for rating, meal, day in rows:
                notifications.append((f"❗ Low feedback detected for {meal} on {day} with Avg. Rating {round(rating, 2)}", day))

    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        connection.close()

    return render_template('notifications.html', notifications=notifications, back_url = back_url)

# Profile Route
@app.route('/profile')
def profile():
    role = session.get('role')
    
    if not role:
        flash("You must be logged in to access your profile.", "error")
        return redirect(url_for('login'))

    user_id = None
    table = None
    id_column = None
    columns = None

    if role == 'student':
        user_id = session.get('student_id')
        table = 'student'
        id_column = 's_id'
        columns = "s_id, name, mess"
    elif role == 'mess_official':
        user_id = session.get('mess_id')
        table = 'mess_data'
        id_column = 'mess_id'
        columns = "mess_id, mess"
    elif role == 'admin':
        user_id = session.get('admin_id')
        table = 'admin'
        id_column = 'admin_id'
        columns = "admin_id, username"

    if not user_id:
        flash("Error: No user ID found in session.", "error")
        return redirect(url_for('login'))

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Fetch user details based on role
        query = f"SELECT {columns} FROM {table} WHERE {id_column} = %s"
        cursor.execute(query, (user_id,))
        user_data = cursor.fetchone()

        if not user_data:
            flash("Error: User not found.", "error")
            return redirect(url_for('login'))

        # Convert fetched data to dictionary
        user_data = dict(zip([desc[0] for desc in cursor.description], user_data))

        return render_template('profile.html', user_data=user_data, role=role)

    except Exception as e:
        flash(f"Database error: {e}", "error")
        return redirect(url_for('login'))
    
    finally:
        cursor.close()
        connection.close()

@app.route('/update-password', methods=['GET', 'POST'])
def update_password():
    # Check if user is logged in
    if 'role' not in session or (session['role'] != 'student' and session['role'] != 'mess_official' and session['role'] != 'admin'):
        return redirect(url_for('login'))

    if session['role'] == 'admin':
        user_id = session['admin_id']  # Student ID from session
    elif session['role'] == 'student':
        user_id = session['student_id']
    elif session['role'] == 'mess_official':
        user_id = session['mess_id']
    
    role = session['role']

    # Determine table name and primary key based on role
    table_mapping = {
        'student': ('student', 's_id'),
        'mess_official': ('mess_data', 'mess_id'),
        'admin': ('admin', 'admin_id')
    }

    if role not in table_mapping:
        flash("Invalid user role.", "error")
        return redirect(url_for('login'))

    table_name, user_column = table_mapping[role]

    if request.method == 'POST':
        try:
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            if new_password != confirm_password:
                flash("New password and confirm password do not match.", "error")
                return redirect(url_for('profile'))

            with get_db_connection() as connection, connection.cursor() as cursor:
                # Fetch current password from DB
                cursor.execute(f"SELECT password FROM {table_name} WHERE {user_column} = %s", (user_id,))
                user_data = cursor.fetchone()

                if not user_data:
                    flash("User not found.", "error")
                    return redirect(url_for('profile'))

                stored_password = user_data[0]

                # Check if current password is correct (for mess_data, it's not hashed yet)
                
                if not check_password_hash(stored_password, current_password):
                    flash("Incorrect current password.", "error")
                    return redirect(url_for('profile'))

                # Hash the new password
                new_password_hash = generate_password_hash(new_password)

                # Update password in DB
                cursor.execute(f"UPDATE {table_name} SET password = %s WHERE {user_column} = %s", 
                               (new_password_hash, user_id))
                connection.commit()

                flash("Password updated successfully!", "success")
                return redirect(url_for('profile'))

        except Exception as e:
            print(f"Error updating password: {e}")
            traceback.print_exc()
            flash("An error occurred while updating the password.", "error")
            return redirect(url_for('profile'))

    return render_template('update_password.html')

# Admin selection for mess
@app.route('/select_mess', methods=['GET', 'POST'])
def select_mess():
    if 'admin_id' not in session:  # Only admin can send notifications
        flash("Unauthorized access!", "error")
        return redirect(url_for('login'))

    if request.method == 'POST':
        selected_mess = request.form.get('selected_mess')
        if selected_mess == 'mess1':
            mess = 'Mess Sai'
        else:
            mess = 'Mess Sheila'
            
        # Check if the mess selection is valid
        if selected_mess in ['mess1', 'mess2']:
            session['admin_mess'] = selected_mess
            flash(f"{mess} selected successfully!", "success")
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

@app.route('/send_notification', methods=['GET','POST'])
def send_notification():
    if 'admin_id' not in session:  # Only admin can send notifications
        flash("Unauthorized access!", "error")
        return redirect(url_for('login'))

    if request.method == 'POST':
        message = request.form.get('message')
        recipient_type = request.form.get('recipient_type')

        if not message or recipient_type not in ['student', 'mess_official', 'both']:
            flash("Invalid input!", "error")
            return redirect(url_for('admin_dashboard'))

        # Insert the notification into the database
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO notifications (message, recipient_type) VALUES (%s, %s)",
                (message, recipient_type)
            )
            conn.commit()
            cursor.close()
            conn.close()

            flash("Notification sent successfully!", "success")
        except Exception as e:
            flash(f"Error sending notification: {e}", "error")

    return render_template('send_notifications.html')

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
    day = get_fixed_time().strftime('%A')
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
            flash('Veg menu updated temporarily for today.', 'success')
            connection.commit()
            
        except Exception as e:
            connection.rollback()
            flash(f'Error: {e}', 'error')
        finally:
            cursor.close()
            connection.close()
        return redirect(url_for('update_veg_menu'))

    return render_template('update_veg_menu.html', week_type=week_type, day=day, meal=meal)

@app.route('/restore_default_veg_menu', methods=['POST'])
def restore_default_veg_menu():
    if 'admin_id' not in session:
        flash('Unauthorized access. Please log in.', 'error')
        return redirect(url_for('login'))

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        week_type = 'Odd' if is_odd_week() else 'Even'
        day = datetime.now().strftime('%A')
        meal = get_current_meal()

        # print(f"Restoring default menu for {week_type} - {day} - {meal}")  # Debugging
        cursor.execute('''
            DELETE FROM temporary_menu WHERE week_type=%s AND day=%s AND meal=%s
        ''', (week_type, day, meal))

        if cursor.rowcount > 0:
            flash('Veg menu restored to default.', 'success')
            # print("Menu restored successfully.")  # Debugging
        else:
            flash('No temporary menu found to restore.', 'info')
            # print("No temporary menu found.")  # Debugging

        connection.commit()
    except Exception as e:
        connection.rollback()
        flash(f'Error: {e}', 'error')
        print(f"Error: {e}")  # Debugging
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('update_veg_menu'))

#student_dashboard
@app.route('/student_dashboard', methods=['GET'])
def student_dashboard():
    if 'student_id' not in session or session['role'] != 'student':
        flash("Not yet logged in",'error')
        return redirect(url_for('login'))
    
    student_id = session['student_id']
    mess_name = session['mess']
    meal = get_current_meal()
    connection = get_db_connection()
    cursor = connection.cursor()

    # Greeting
    current_hour = get_fixed_time().hour
    if current_hour < 12:
        greeting = 'Good Morning'
    elif current_hour < 17:
        greeting = 'Good Afternoon'
    else:
        greeting = 'Good Evening'

    # Meal Reminder
    cursor.execute("SELECT DISTINCT s_id FROM feedback_summary WHERE s_id = %s AND feedback_date = CURDATE() AND mess = %s AND meal = %s", (student_id, mess_name, meal))
    feedback_given = set(row[0] for row in cursor.fetchall())
    if (student_id) in feedback_given:
        feedback_status = "Feedback Submitted"
    else:
        feedback_status = "Feedback Pending"

    weekday = get_fixed_time().strftime('%A')
    week_type = 'odd' if is_odd_week() else 'even'
    # Leaderboard (Top-rated meals)
    cursor.execute("""
        SELECT d.food_item, ROUND(AVG(d.rating), 2) as avg_rating
        FROM feedback_details d
        JOIN feedback_summary s ON d.feedback_id = s.feedback_id
        JOIN menu m ON d.food_item = m.food_item  
        WHERE s.mess = %s
        AND m.day = %s  
        AND m.week_type = %s
        GROUP BY d.food_item
        ORDER BY avg_rating DESC
        LIMIT 5
""", (mess_name, weekday, week_type))
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
        WHERE d.created_at >= DATE_SUB(CURDATE(), INTERVAL 1 MONTH)
        AND d.created_at < CURDATE()
        GROUP BY s.mess;
    """)
    monthly_avg_ratings = cursor.fetchall()
    # for mess, avg in monthly_avg_ratings:
    #     print(mess)
    #     print(avg)
    # if not monthly_avg_ratings:
    #     print("No ratings available for last month.")
    # Clamp the avg_rating to be between 1 and 5
    connection.close()
    # flashed_messages = get_flashed_messages(with_categories=True)
    session.pop('_flashes', None)
    return render_template('student_dashboard.html',
                           greeting=greeting,
                           feedback_status=feedback_status,
                           leaderboard=leaderboard,
                           waste_insight=waste_insight,
                           monthly_avg_ratings=monthly_avg_ratings)

@app.route('/public-notifications')
def public_notifications():
    notifications = []
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # ✅ Fetch notifications meant for students
        cursor.execute("""
            SELECT message, created_at 
            FROM notifications 
            WHERE recipient_type IN ('both') 
            AND created_at >= NOW() - INTERVAL 7 DAY 
            ORDER BY created_at DESC
        """)
        notifications = cursor.fetchall()

    except Exception as e:
        print("Error fetching public notifications:", e)
    finally:
        cursor.close()
        connection.close()

    return render_template("notifications.html", notifications=notifications, back_url='/home')

@app.route('/student_payment_details', methods=['GET'])
def payment():
    if 'student_id' not in session or session['role'] != 'student':
        flash("Not yet logged in",'error')
        return redirect(url_for('login'))
    
    student_id = session['student_id']
    mess_name = session['mess']
    # meal = get_current_meal()
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
                    SELECT payment_date, meal, food_item, amount
                    FROM payment
                    WHERE mess = %s AND payment_date >= CURDATE() - INTERVAL 30 DAY
                    AND s_id = %s
                    GROUP BY payment_date, meal
                    ORDER BY payment_date DESC;
                """, (mess_name, student_id))
        data = cursor.fetchall()

        if not data:
            flash("No payment data found for the last 30 days.", "error")
            return render_template('payment.html', data=[], mess_name=mess_name)
        connection.commit()
        connection.close()
        cursor.close()
    except Exception as e:
        print("Error fetching payment summary:")
        logging.error("Error fetching payment summary", exc_info=True)
        flash("An error occurred while fetching payment data.", "error")
        return render_template('payment.html', data=[], mess_name=mess_name)

    # Pass data to the template
    return render_template('payment.html', data= data, mess_name=mess_name)

# def main():
#     login()
#     payment_summary()

# if __name__=="__main__":
#     main()
