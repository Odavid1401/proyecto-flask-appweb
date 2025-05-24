from flask import Flask
from flask_mysqldb import MySQL
import MySQLdb.cursors

app = Flask(__name__)
@app.template_filter('formato_cop')
def formato_cop(precio):
    try:
        return "${:,.0f}".format(float(precio)).replace(",", ".")
    except (ValueError, TypeError):
        return precio

# carga config.py que está en la raíz:
app.config.from_pyfile('config.py')


app.secret_key = app.config.get('SECRET_KEY')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'


mysql = MySQL(app)

from app import routes


