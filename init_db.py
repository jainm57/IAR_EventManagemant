import os
import psycopg2

def init_db():
    print("🔥 Connecting to PostgreSQL to initialize tables...")
    try:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL environment variable is missing. On Railway, make sure you created a DATABASE_URL variable set to ${{ Postgres.DATABASE_URL }}")
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

        # USERS TABLE
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT,
                email TEXT UNIQUE,
                password TEXT,
                role TEXT,
                department TEXT
            )
        ''')

        # EVENTS TABLE
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
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

        # REGISTRATIONS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS registrations (
                id SERIAL PRIMARY KEY,
                event_id INTEGER,
                student_id INTEGER
            )
        ''')

        # VENUES
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS venues (
                id SERIAL PRIMARY KEY,
                name TEXT,
                capacity INTEGER
            )
        ''')

        # ATTENDANCE
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id SERIAL PRIMARY KEY,
                event_id INTEGER,
                student_id INTEGER
            )
        ''')

        conn.commit()

        # ✅ CHECK IF ADMIN EXISTS
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]

        if count == 0:
            from werkzeug.security import generate_password_hash
            cursor.execute("""
                INSERT INTO users (name, email, password, role, department)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                "Admin",
                "admin@iar.ac.in",
                generate_password_hash("admin123"),
                "admin",
                "CSE"
            ))
            print("✅ Default admin created")

        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Database initialization complete.")
    except Exception as e:
        print("❌ Error initializing database:", e)
        exit(1)

if __name__ == '__main__':
    if not os.environ.get("DATABASE_URL"):
        print("⚠️ DATABASE_URL environment variable is missing. Skip init_db.")
    else:
        init_db()

