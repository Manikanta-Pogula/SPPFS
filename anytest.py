import sys
sys.path.insert(0, r".")

try:
    from app import create_app
    app = create_app()
    print("DB_URI:", app.config.get("SQLALCHEMY_DATABASE_URI"))
except Exception as e:
    try:
        import app as _app
        print("DB_URI:", getattr(_app, "SQLALCHEMY_DATABASE_URI", None))
    except Exception as e2:
        print("ERROR_LOADING_APP:", str(e)[:180])
