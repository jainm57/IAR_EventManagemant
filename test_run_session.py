import os
from app import app
import traceback

os.environ['DATABASE_URL'] = 'postgres://dummy:dummy@localhost:5432/dummy'
try:
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'admin'
        response = client.get('/')
        print("Admin response:", response.status_code)
except Exception as e:
    print("Exception running test client:")
    traceback.print_exc()
