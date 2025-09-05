import sys
import threading
import subprocess
import time
import requests
import os
from PyQt5.QtWidgets import QApplication
from main_gui import MainWindow
from app import load_model, app

# --- FIX: Set environment variable to prevent TensorFlow import ---
# This is required because some dependencies in transformers attempt to import TensorFlow,
# which can fail if it's not correctly installed on the system.
os.environ['TRANSFORMERS_USE_TF'] = '0'

def run_flask_app():
    """Function to run the Flask app. This will be targeted by the thread."""
    app.run(debug=False, use_reloader=False, port=5000)

def health_check(url, timeout=30):
    """
    Pings the Flask server's status endpoint to ensure it's ready.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url)
            if response.status_code == 200 and response.json().get('status') == 'ready':
                print("Flask server is ready!")
                return True
        except requests.exceptions.ConnectionError:
            pass
        print("Waiting for Flask server to start...")
        time.sleep(2)
    return False

def main():
    # Load the model directly in the main thread before starting the server
    load_model()
    
    # Start Flask server in a separate thread
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()
    
    # Perform a health check to wait for the server to be ready
    if not health_check('http://127.0.0.1:5000/status'):
        print("Error: Flask server did not start within the timeout period.")
        sys.exit(1)
        
    # Start the PyQt5 application
    qt_app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(qt_app.exec_())

if __name__ == "__main__":
    main()
