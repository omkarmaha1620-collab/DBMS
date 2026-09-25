import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', '1') == '1'
    print(f"\n=======================================================")
    print(f" Attendance Monitoring System (College DBMS Project)")
    print(f" Running at: http://127.0.0.1:{port}/")
    print(f"=======================================================\n")
    app.run(host='0.0.0.0', port=port, debug=debug)
