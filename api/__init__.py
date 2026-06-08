from flask import Flask


def register_api_blueprints(app: Flask) -> None:
    from api.system import system_bp
    from api.users import users_bp
    app.register_blueprint(system_bp)
    app.register_blueprint(users_bp)
