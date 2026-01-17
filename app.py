import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
from datetime import datetime


app = Flask(__name__)

# Generate a secure secret key
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret')

# MySQL Configuration

app.config['MYSQL_HOST'] = os.environ.get('DB_HOST')
app.config['MYSQL_USER'] = os.environ.get('DB_USER')
app.config['MYSQL_PASSWORD'] = os.environ.get('DB_PASSWORD')
app.config['MYSQL_DB'] = os.environ.get('DB_NAME')
app.config['MYSQL_PORT'] = int(os.environ.get('DB_PORT', 3306))
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

# Make datetime available in all templates
@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

# Database Helper Functions
def execute_query(query, args=(), one=False, commit=False):
    try:
        cur = mysql.connection.cursor()
        cur.execute(query, args)
        if commit:
            mysql.connection.commit()
        rv = cur.fetchall()
        cur.close()
        return (rv[0] if rv else None) if one else rv
    except Exception as e:
        mysql.connection.rollback()
        raise e

def get_current_user():
    if 'user_id' in session:
        user_id = session['user_id']
        user = execute_query("SELECT * FROM users WHERE id = %s", (user_id,), one=True)
        return user
    return None

# Custom Jinja2 test for month comparison
def is_month_equal(date, month):
    return date.month == month

# Register the custom test
app.jinja_env.tests['month_equal'] = is_month_equal

# Authentication Routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        
        try:
            execute_query(
                "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                (username, email, password),
                commit=True
            )
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'danger')
    
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = execute_query(
            "SELECT * FROM users WHERE username = %s",
            (username,),
            one=True
        )

        if user and check_password_hash(user['password'], password):
            # ✅ STORE USER ID IN SESSION
            session['user_id'] = user['id']
            session['username'] = user['username']  # optional but useful

            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

# Main Application Routes
@app.route("/")
def home():
    user = get_current_user()
    return render_template("maybefinal3.html", user=user)

@app.route("/aboutus1")
def aboutus1():
    return render_template("aboutus1.html", user=get_current_user())

@app.route("/termsofservice")
def termsofservice():
    return render_template("termsofservice.html", user=get_current_user())

@app.route("/progress")
def progress():
    user = get_current_user()
    if not user:
        flash('Please login to view your progress', 'warning')
        return redirect(url_for('login'))
    
    mood_stats = execute_query("""
        SELECT mood, COUNT(*) as count, AVG(intensity) as avg_intensity 
        FROM mood_entries 
        WHERE user_id = %s 
        GROUP BY mood
    """, (user['id'],))
    
    journal_count = execute_query(
        "SELECT COUNT(*) as count FROM journal_entries WHERE user_id = %s",
        (user['id'],),
        one=True
    )
    
    # Get current month entries count
    current_month = datetime.now().month
    month_entries = execute_query(
        "SELECT COUNT(*) as count FROM journal_entries WHERE user_id = %s AND MONTH(created_at) = %s",
        (user['id'], current_month),
        one=True
    )
    
    return render_template("progress.html", 
                         mood_stats=mood_stats,
                         journal_count=journal_count['count'],
                         month_entries=month_entries['count'],
                         user=user)

@app.route("/games")
def games():
    return render_template("games.html", user=get_current_user())

@app.route("/setting", methods=['GET', 'POST'])
def setting():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        new_username = request.form.get('username')
        new_email = request.form.get('email')
        
        try:
            execute_query(
                "UPDATE users SET username = %s, email = %s WHERE id = %s",
                (new_username, new_email, user['id']),
                commit=True
            )
            flash('Settings updated successfully!', 'success')
            return redirect(url_for('setting'))
        except Exception as e:
            flash(f'Error updating settings: {str(e)}', 'danger')
    
    return render_template("setting.html", user=user)

@app.route("/contactus", methods=['GET', 'POST'])
def contactus():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        
        # Here you would typically save to database or send email
        flash('Thank you for your message! We will get back to you soon.', 'success')
        return redirect(url_for('contactus'))
    
    return render_template("contactus.html", user=get_current_user())

@app.route('/notification')
def notification():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    notifications = execute_query(
        "SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC",
        (user_id,)
    ) or []

    return render_template(
        'notification.html',
        notifications=notifications
    )


@app.route("/moodtracker", methods=['GET', 'POST'])
def moodtracker():
    user = get_current_user()
    if not user:
        flash('Please login to track your mood', 'warning')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        mood = request.form.get('mood')
        intensity = int(request.form.get('intensity', 5))
        notes = request.form.get('notes', '')
        
        try:
            execute_query(
                "INSERT INTO mood_entries (user_id, mood, intensity, notes) VALUES (%s, %s, %s, %s)",
                (user['id'], mood, intensity, notes),
                commit=True
            )
            flash('Mood entry saved successfully!', 'success')
        except Exception as e:
            flash(f'Error saving mood entry: {str(e)}', 'danger')
        
        return redirect(url_for('moodtracker'))
    
    entries = execute_query(
        "SELECT * FROM mood_entries WHERE user_id = %s ORDER BY created_at DESC LIMIT 10",
        (user['id'],)
    )
    
    mood_stats = {
        'total_entries': len(entries),
        'avg_intensity': None,
        'recent_trend': None,
        'mood_distribution': {}
    }
    
    if entries:
        intensities = [e['intensity'] for e in entries if e['intensity'] is not None]
        if intensities:
            mood_stats['avg_intensity'] = sum(intensities) / len(intensities)
        
        if len(entries) >= 2:
            mood_stats['recent_trend'] = entries[0]['intensity'] - entries[1]['intensity']
        
        for entry in entries:
            mood = entry['mood']
            mood_stats['mood_distribution'][mood] = mood_stats['mood_distribution'].get(mood, 0) + 1
    
    return render_template(
        "moodtracker.html",
        entries=entries,
        mood_stats=mood_stats,
        user=user
    )

@app.route("/journaling", methods=['GET', 'POST'])
def journaling():
    user = get_current_user()
    if not user:
        flash('Please login to access journaling', 'warning')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form.get('title', 'Untitled')
        content = request.form.get('content', '')
        
        try:
            execute_query(
                "INSERT INTO journal_entries (user_id, title, content) VALUES (%s, %s, %s)",
                (user['id'], title, content),
                commit=True
            )
            flash('Journal entry saved successfully!', 'success')
        except Exception as e:
            flash(f'Error saving journal entry: {str(e)}', 'danger')
        
        return redirect(url_for('journaling'))
    
    entries = execute_query(
        "SELECT * FROM journal_entries WHERE user_id = %s ORDER BY created_at DESC",
        (user['id'],)
    )
    return render_template("journaling.html", entries=entries, user=user)

@app.route('/journal/delete/<int:entry_id>', methods=['DELETE'])
def delete_journal_entry(entry_id):
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': 'Please login'}), 401
    
    try:
        execute_query(
            "DELETE FROM journal_entries WHERE id = %s AND user_id = %s",
            (entry_id, user['id']),
            commit=True
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/journal/update/<int:entry_id>', methods=['POST'])
def update_journal_entry(entry_id):
    user = get_current_user()
    if not user:
        flash('Please login to update journal entries', 'warning')
        return redirect(url_for('login'))
    
    title = request.form.get('title', 'Untitled')
    content = request.form.get('content', '')
    
    try:
        execute_query(
            "UPDATE journal_entries SET title = %s, content = %s WHERE id = %s AND user_id = %s",
            (title, content, entry_id, user['id']),
            commit=True
        )
        flash('Journal entry updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating journal entry: {str(e)}', 'danger')
    
    return redirect(url_for('journaling'))

@app.route("/community")
def community():
    return render_template("community.html", user=get_current_user())

@app.route("/musictherapy")
def musictherapy():
    return render_template("musictherapy.html", user=get_current_user())

@app.route("/privacypolicy")
def privacypolicy():
    return render_template("privacypolicy.html", user=get_current_user())

# Error Handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', user=get_current_user()), 404

@app.errorhandler(500)
def internal_error(e):
    try:
        if mysql.connection:
            mysql.connection.rollback()
    except:
        pass
    return render_template('500.html'), 500


if __name__ == "__main__":
    app.run()