from flask import Blueprint

dbms_bp = Blueprint('dbms', __name__, template_folder='../../templates/dbms_showcase')

from app.blueprints.dbms_showcase import routes
