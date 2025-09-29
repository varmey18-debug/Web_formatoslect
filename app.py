from flask import Flask, render_template, request, send_file, redirect, flash
import pandas as pd
import sqlite3
import webbrowser
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "secretkey123"

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

@app.route("/", methods=["GET", "POST"])
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
                                   total_observaciones=total_observaciones)
        except Exception as e:
            flash(f"❌ Error: {e}")
            return redirect(request.url)
    
    return render_template("index.html", data=None)

@app.route("/export", methods=["POST"])
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

# ✅ Esta línea es clave para que Flask arranque
if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

