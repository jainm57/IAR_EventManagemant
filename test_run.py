import os
from app import app
import builtins
import traceback

os.environ['DATABASE_URL'] = 'postgres://dummy:dummy@localhost:5432/dummy'
try:
    with app.test_client() as client:
        response = client.get('/')
        print("Root response:", response.status_code)
except Exception as e:
    print("Exception running test client:")
    traceback.print_exc()

