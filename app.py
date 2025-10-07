from flask import Flask, render_template, request, send_file, redirect, flash, url_for
import pandas as pd
import sqlite3
import os
from werkzeug.utils import secure_filename
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt  # 🔐 para encriptar contraseñas

app = Flask(__name__)
app.secret_key = "secretkey123"

# 🔐 Configuración de login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
bcrypt = Bcrypt(app)

# 🔐 Usuarios (por ahora en memoria)
# 👉 Puedes agregar más copiando una línea:
# USERS["usuario"] = bcrypt.generate_password_hash("clave").decode("utf-8")
USERS = {
    "admin": bcrypt.generate_password_hash("1234").decode("utf-8"),
    "rommel": bcrypt.generate_password_hash("vargas").decode("utf-8")
}

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    if user_id in USERS:
        return User(user_id)
    return None


UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

QUERY_BASE = """
SELECT lc.TomaId, lc.CuentaNro, lc.NombreCliente, lc.Direccion,
       ll.FechaHora, ll.Lectura, ll.Consumo,
       li.IncidenciaDsc, lo.LectObservacionDsc,
       lc.BarrioId
FROM LectClientes lc
JOIN LectLectura ll ON lc.TomaId = ll.TomaId
LEFT JOIN LectIncidencia li ON ll.IdIncidencia = li.Id
LEFT JOIN LectObservacion lo ON ll.IdObservacion = lo.Id
"""

def calcular_estadisticas(df):
    total_cuentas = df['CuentaNro'].nunique()
    total_incidencias = df['IncidenciaDsc'].notna().sum()
    total_observaciones = df['LectObservacionDsc'].notna().sum()
    return total_cuentas, total_incidencias, total_observaciones

# 🔐 Ruta de login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username in USERS and bcrypt.check_password_hash(USERS[username], password):
            user = User(username)
            login_user(user)
            flash("Inicio de sesión exitoso ✅", "success")
            return redirect(url_for("index"))
        else:
            flash("Usuario o contraseña incorrectos ❌", "danger")

    return render_template("login.html")

# 🔐 Ruta para agregar nuevos usuarios (solo para admin)
@app.route("/add_user", methods=["GET", "POST"])
@login_required
def add_user():
    if current_user.id != "admin":
        flash("Solo el administrador puede agregar usuarios ⚠️", "warning")
        return redirect(url_for("index"))

    if request.method == "POST":
        new_username = request.form["username"]
        new_password = request.form["password"]

        if new_username in USERS:
            flash("Ese usuario ya existe ❌", "danger")
        else:
            USERS[new_username] = bcrypt.generate_password_hash(new_password).decode("utf-8")
            flash(f"Usuario '{new_username}' agregado correctamente ✅", "success")

    return render_template("add_user.html", user=current_user.id)

# 🔐 Cerrar sesión
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada correctamente 👋", "info")
    return redirect(url_for("login"))

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        file = request.files.get("sqlite_file")
        if not file:
            flash("❌ No se subió ningún archivo")
            return redirect(request.url)
        
        filename = secure_filename(file.filename)
        db_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(db_path)

        excel_name = request.form.get("excel_name") or "lecturas_exportadas.xlsx"
        if not excel_name.lower().endswith(".xlsx"):
            excel_name += ".xlsx"

        try:
            conn = sqlite3.connect(db_path)
            df = pd.read_sql_query(QUERY_BASE, conn)
            conn.close()
            
            df['FechaHora'] = pd.to_datetime(df['FechaHora'], unit='s', errors='coerce')
            total_cuentas, total_incidencias, total_observaciones = calcular_estadisticas(df)
            preview_df = df.drop(columns=['TomaId','BarrioId']).head(50)
            preview_data = preview_df.to_dict(orient='records')
            
            return render_template("index.html",
                                   data=preview_data,
                                   db_path=db_path,
                                   excel_name=excel_name,
                                   total_cuentas=total_cuentas,
                                   total_incidencias=total_incidencias,
                                   total_observaciones=total_observaciones,
                                   user=current_user.id)
        except Exception as e:
            flash(f"❌ Error: {e}")
            return redirect(request.url)
    
    return render_template("index.html", data=None, user=current_user.id)

@app.route("/export", methods=["POST"])
@login_required
def export():
    db_path = request.form.get("db_path")
    excel_name = request.form.get("excel_name") or "lecturas_exportadas.xlsx"

    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(QUERY_BASE, conn)
        conn.close()
        
        df['FechaHora'] = pd.to_datetime(df['FechaHora'], unit='s', errors='coerce')
        df.drop(columns=['TomaId','BarrioId'], inplace=True)
        df.to_excel(excel_name, index=False)
        return send_file(excel_name, as_attachment=True)
    except Exception as e:
        flash(f"❌ Error: {e}")
        return redirect("/")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
