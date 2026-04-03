import re
import os
import time
import qrcode
import sqlite3
import random
import smtplib
from email.mime.text import MIMEText
from flask import flash
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
# In production, this should be stored securely in an environment variable
app.secret_key = "secret123"

# Initialize SQLite Database schema
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            password TEXT,
            role TEXT,
            department TEXT
        )
    ''')

    # Events table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            description TEXT,
            date TEXT,
            start_time TEXT,
            end_time TEXT,
            venue TEXT,
            organizer_id INTEGER,
            max_participants INTEGER,
            status TEXT,
            department TEXT,
            flyer TEXT
        )
    ''')

    # Event registration tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            student_id INTEGER
        )
    ''')

    # Available venues and capacities
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS venues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            capacity INTEGER
        )
    ''')

    # Event attendance tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            student_id INTEGER
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def home():
    # Route users to their specific dashboards based on role
    if 'user_id' in session:
        if session['role'] == 'admin':
            return render_template('admin_dashboard.html')
        elif session['role'] == 'organizer':
            return render_template('organizer_dashboard.html')
        elif session['role'] == 'faculty':
            return render_template('faculty_dashboard.html')
        elif session['role'] == 'student':
            return render_template('student_dashboard.html')

    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email'].strip().lower()
        password = generate_password_hash(request.form['password'])
        role = request.form['role']
        admin_code = request.form.get('admin_code')
        department = request.form['department']

        # Validate college domain requirement
        if not re.match(r'^[a-zA-Z0-9._%+-]+@iar\.ac\.in$', email):
            flash("Only college email allowed (@iar.ac.in) ❌")
            return redirect('/register')

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        # Prevent duplicate email registrations
        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            conn.close()
            flash("Email already registered ❌")
            return redirect('/register')

        # Validate admin registration securely
        if role == "admin":
            # Note: In production, hardcoded secrets should be moved to environment variables
            if admin_code != "12345":
                conn.close()
                flash("Invalid Admin Code ❌")
                return redirect('/register')

        # Create new user record
        cursor.execute(
            "INSERT INTO users (name, email, password, role, department) VALUES (?, ?, ?, ?, ?)",
            (name, email, password, role, department)
        )

        conn.commit()
        conn.close()

        flash("Registration Successful 🎉")
        return redirect('/login')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']

        # Email validation
        if not re.match(r'^[a-zA-Z0-9._%+-]+@iar\.ac\.in$', email):
            flash("Use your college email (@iar.ac.in) ❌")
            return redirect('/login')

        # Database check
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):

            # Generate OTP
            otp = str(random.randint(100000, 999999))

            # Store session
            session['temp_user'] = {
                'id': user[0],
                'role': user[4],
                'department': user[5],
                'email': email
            }
            session['otp'] = otp

            # 🔥 GET EMAIL FROM ENV (SAFE)
            sender_email = os.environ.get("EMAIL_USER")
            sender_password = os.environ.get("EMAIL_PASS")

            try:
                msg = MIMEText(
                    f"Hello {user[1]},\n\nYour OTP is: {otp}\n\nDo not share this code."
                )
                msg['Subject'] = 'IAR Event System - OTP Verification'
                msg['From'] = sender_email
                msg['To'] = email

                server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                server.login(sender_email, sender_password)
                server.send_message(msg)
                server.quit()

                flash("OTP sent to your email 📧")

            except Exception as e:
                print("Email error:", e)
                print(f"OTP (fallback): {otp}")
                flash("Email failed. Check logs 👨‍💻")

            return redirect('/verify_otp')

        else:
            flash("Invalid Credentials ❌")
            return redirect('/login')

    return render_template('login.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    # Ensure they are in the middle of a login attempt
    if 'temp_user' not in session or 'otp' not in session:
        return redirect('/login')
        
    if request.method == 'POST':
        user_otp = request.form.get('otp', '').strip()
        
        if user_otp == session['otp']:
            # Finalize user session securely
            temp_user = session['temp_user']
            session['user_id'] = temp_user['id']
            session['role'] = temp_user['role']
            session['department'] = temp_user['department']
            
            # Clear temporary session authentication footprint
            session.pop('temp_user', None)
            session.pop('otp', None)
            
            flash("Login Successful ✅")
            return redirect('/')
        else:
            flash("Invalid Verification Code ❌")
            return redirect('/verify_otp')
            
    return render_template('verify.html')

@app.route('/create_event', methods=['GET', 'POST'])
def create_event():
    # Restrict to admins and organizers
    if 'user_id' not in session or session['role'] not in ['admin', 'organizer']:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Retrieve available venues for dropdown
    cursor.execute("SELECT * FROM venues")
    venues = cursor.fetchall()

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        date = request.form['date']

        start_time = request.form['start_time']
        end_time = request.form['end_time']

        venue = request.form['venue']
        department = request.form['department']
        organizer_id = session['user_id']

        # Process optional flyer upload
        file = request.files['flyer']

        if file and file.filename != "":
            filename = f"flyer_{int(time.time())}.png"
            filepath = os.path.join("static", filename)
            file.save(filepath)
        else:
            filepath = None

        # Derive capacity limit statically from the selected venue
        cursor.execute("SELECT capacity FROM venues WHERE name=?", (venue,))
        venue_data = cursor.fetchone()
        max_participants = venue_data[0] if venue_data else None

        # Prevent double-booking venues during identical timeframes
        cursor.execute("""
            SELECT * FROM events
            WHERE venue=? AND date=?
        """, (venue, date))

        existing_events = cursor.fetchall()

        for e in existing_events:
            existing_start = e[8]
            existing_end = e[9]

            if not existing_start or not existing_end:
                continue

            # Detect scheduling conflict limits (overlap algorithm)
            if start_time < existing_end and end_time > existing_start:
                conn.close()
                return "Time clash detected ❌ This venue is already booked"

        # Construct and persist event record
        cursor.execute(
            "INSERT INTO events (title, description, date, start_time, end_time, venue, organizer_id, max_participants, status, department, flyer) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, description, date, start_time, end_time, venue, organizer_id, max_participants, 'pending', department, filepath)
        )

        conn.commit()
        conn.close()

        flash("Event Created Successfully 🎉")
        return redirect('/')

    conn.close()
    return render_template('create_event.html', venues=venues)

@app.route('/events')
def view_events():
    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Retrieve events accessible to user's department or generic Universal events
    cursor.execute("""
        SELECT * FROM events 
        WHERE status='approved' 
        AND (department=? OR department='Universal')
    """, (session['department'],))

    events = cursor.fetchall()
    event_list = []

    for event in events:
        event_id = event[0]

        # Calculate remaining capacity metrics
        cursor.execute(
            "SELECT COUNT(*) FROM registrations WHERE event_id=?",
            (event_id,)
        )
        count = cursor.fetchone()[0]

        max_participants = int(event[6]) if event[6] else None

        if max_participants:
            seats_left = max_participants - count
        else:
            seats_left = "Unlimited"

        # Organize resulting event data mapping for the template handler
        event_list.append({
            "id": event[0],
            "title": event[1],
            "description": event[2],
            "date": event[3],
            "venue": event[4],
            "start_time": event[8],
            "end_time": event[9],
            "max": max_participants,
            "count": count,
            "seats_left": seats_left,
            "department": event[10],
            "flyer": event[11]
        })

    conn.close()

    return render_template('events.html', events=event_list)

@app.route('/register_event/<int:event_id>')
def register_event(event_id):
    if 'user_id' not in session:
        return redirect('/login')

    student_id = session['user_id']

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Verify if user has already registered
    cursor.execute(
        "SELECT * FROM registrations WHERE event_id=? AND student_id=?",
        (event_id, student_id)
    )
    existing = cursor.fetchone()

    if existing:
        conn.close()
        return "You already registered for this event ⚠️"

    # Enforce venue capacity restrictions
    cursor.execute(
        "SELECT max_participants FROM events WHERE id=?",
        (event_id,)
    )
    event = cursor.fetchone()

    cursor.execute(
        "SELECT COUNT(*) FROM registrations WHERE event_id=?",
        (event_id,)
    )
    current_count = cursor.fetchone()[0]

    if event and event[0] is not None and current_count >= event[0]:
        conn.close()
        return "Event is full ❌"

    cursor.execute(
        "INSERT INTO registrations (event_id, student_id) VALUES (?, ?)",
        (event_id, student_id)
    )
    conn.commit()
    conn.close()

    return "Registered Successfully 🎉"

@app.route('/my_events')
def my_events():
    if 'user_id' not in session:
        return redirect('/login')

    student_id = session['user_id']
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Query events specific to the authenticated student
    cursor.execute("""
        SELECT events.*
        FROM events
        JOIN registrations ON events.id = registrations.event_id
        WHERE registrations.student_id = ?
    """, (student_id,))

    events = cursor.fetchall()
    event_list = []

    for event in events:
        event_id = event[0]

        cursor.execute(
            "SELECT COUNT(*) FROM registrations WHERE event_id=?",
            (event_id,)
        )
        count = cursor.fetchone()[0]
        max_participants = int(event[6]) if event[6] else None

        if max_participants:
            seats_left = max_participants - count
        else:
            seats_left = "Unlimited"

        event_list.append({
            "id": event[0],
            "title": event[1],
            "description": event[2],
            "date": event[3],
            "venue": event[4],
            "start_time": event[8],
            "end_time": event[9],
            "max": max_participants,
            "count": count,
            "seats_left": seats_left,
            "department": event[10],
            "flyer": event[11]
        })

    conn.close()
    return render_template('my_events.html', events=event_list)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/admin_events')
def admin_events():
    if 'user_id' not in session or session['role'] not in ['admin', 'organizer']:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Handle dual-role logic fetching corresponding events
    if session['role'] == 'admin':
        cursor.execute("SELECT * FROM events")
    else:
        cursor.execute("SELECT * FROM events WHERE organizer_id=?", (session['user_id'],))

    events = cursor.fetchall()
    event_list = []

    for event in events:
        event_id = event[0]

        cursor.execute("SELECT COUNT(*) FROM registrations WHERE event_id=?", (event_id,))
        count = cursor.fetchone()[0]
        max_participants = int(event[6]) if event[6] else None

        if max_participants:
            seats_left = max_participants - count
        else:
            seats_left = "Unlimited"

        event_list.append({
            "id": event[0],
            "title": event[1],
            "description": event[2],
            "date": event[3],
            "venue": event[4],           
            "start_time": event[8],      
            "end_time": event[9],        
            "max": event[6],             
            "count": count,
            "seats_left": seats_left,
            "status": event[7],          
            "department": event[10], 
            "flyer": event[11]      
        })

    conn.close()

    return render_template('admin_events.html', events=event_list)

@app.route('/delete_event/<int:event_id>')
def delete_event(event_id):
    if 'user_id' not in session or session['role'] not in ['admin', 'organizer']:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("DELETE FROM events WHERE id=?", (event_id,))
    conn.commit()
    conn.close()

    flash("Event Deleted Successfully 🎉")
    return redirect('/admin_events')

@app.route('/approve_event/<int:event_id>')
def approve_event(event_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("UPDATE events SET status='approved' WHERE id=?", (event_id,))
    conn.commit()
    conn.close()

    return redirect('/admin_events')

@app.route('/participants/<int:event_id>')
def view_participants(event_id):
    if 'user_id' not in session or session['role'] not in ['admin', 'organizer']:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT users.name, users.email
        FROM registrations
        JOIN users ON registrations.student_id = users.id
        WHERE registrations.event_id = ?
    """, (event_id,))

    participants = cursor.fetchall()
    conn.close()

    return render_template('participants.html', participants=participants)

@app.route('/add_venue', methods=['GET', 'POST'])
def add_venue():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        capacity = request.form['capacity']

        cursor.execute("INSERT INTO venues (name, capacity) VALUES (?, ?)", (name, capacity))
        conn.commit()

    cursor.execute("SELECT * FROM venues")
    venues = cursor.fetchall()
    conn.close()

    return render_template('add_venue.html', venues=venues)

@app.route('/delete_venue', methods=['POST'])
def delete_venue():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect('/login')

    venue_id = request.form['venue_id']
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("DELETE FROM venues WHERE id = ?", (venue_id,))
    conn.commit()
    conn.close()

    return redirect('/add_venue')

@app.route('/generate_qr/<int:event_id>')
def generate_qr(event_id):
    # Generates a dynamic QR code for automated attendance tracking
    url = f"http://127.0.0.1:5000/mark_attendance/{event_id}"
    img = qrcode.make(url)

    path = f"static/qr_{event_id}.png"
    img.save(path)

    return render_template("show_qr.html", qr_image=path)

@app.route('/scan_qr/<int:event_id>')
def scan_qr(event_id):
    return render_template('scan.html')

@app.route('/mark_attendance/<int:event_id>')
def mark_attendance(event_id):
    if 'user_id' not in session:
        return redirect('/login')

    student_id = session['user_id']
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM registrations 
        WHERE event_id=? AND student_id=?
    """, (event_id, student_id))

    registered = cursor.fetchone()

    # Reject non-registered participants securely
    if not registered:
        conn.close()
        return "You are not registered ❌"

    cursor.execute("""
        SELECT * FROM attendance 
        WHERE event_id=? AND student_id=?
    """, (event_id, student_id))

    if cursor.fetchone():
        conn.close()
        return "Already marked ⚠️"

    cursor.execute("""
        INSERT INTO attendance (event_id, student_id)
        VALUES (?, ?)
    """, (event_id, student_id))

    conn.commit()
    conn.close()

    return "Attendance marked successfully ✅"

@app.route('/view_attendance/<int:event_id>')
def view_attendance(event_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT users.name, users.email
        FROM attendance
        JOIN users ON attendance.student_id = users.id
        WHERE attendance.event_id=?
    """, (event_id,))

    data = cursor.fetchall()
    conn.close()

    return render_template('attendance.html', data=data)

@app.route('/certificate/<int:event_id>')
def generate_certificate(event_id):
    if 'user_id' not in session:
        return redirect('/login')

    student_id = session['user_id']
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Validate that the user actually attended before issuing certificate
    cursor.execute("""
        SELECT * FROM attendance
        WHERE event_id=? AND student_id=?
    """, (event_id, student_id))

    attendance = cursor.fetchone()

    if not attendance:
        conn.close()
        return "You did not attend this event ❌"

    cursor.execute("SELECT name FROM users WHERE id=?", (student_id,))
    user = cursor.fetchone()

    cursor.execute("SELECT title, date FROM events WHERE id=?", (event_id,))
    event = cursor.fetchone()

    conn.close()

    name = user[0]
    event_title = event[0]
    event_date = event[1]

    # Generate PDF certificate payload dynamically utilizing ReportLab
    file_path = f"static/certificate_{student_id}_{event_id}.pdf"
    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()
    content = []

    content.append(Paragraph("Certificate of Participation", styles['Title']))
    content.append(Spacer(1, 20))
    content.append(Paragraph(f"This is to certify that <b>{name}</b>", styles['Normal']))
    content.append(Spacer(1, 10))
    content.append(Paragraph(f"has successfully participated in <b>{event_title}</b>", styles['Normal']))
    content.append(Spacer(1, 10))
    content.append(Paragraph(f"Date: {event_date}", styles['Normal']))

    doc.build(content)

    return f"Certificate generated successfully ✅<br><a href='/{file_path}'>Download Certificate</a>"

# Application Entry Point
if __name__ == '__main__':
    init_db()  # initialize your database (keep this if you need it)
    port = int(os.environ.get("PORT", 8000))  # get port from environment or default to 8000
    app.run(host="0.0.0.0", port=port)