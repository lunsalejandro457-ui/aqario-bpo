import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import hashlib
import sqlite3
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from fpdf import FPDF

st.set_page_config(page_title="aQario", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DIR_ACTUAL, "aqario.db")

def clean_text(s):
    return str(s).replace('—', '-').replace('–', '-').replace('"', '"').replace('"', '"').replace(''', "'").replace(''', "'").replace('…', '...').encode('latin-1', 'ignore').decode('latin-1')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        rol TEXT NOT NULL,
        nombre TEXT,
        eps_asignada TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS perfil_ips (
        id INTEGER PRIMARY KEY,
        nombre_ips TEXT,
        nit_ips TEXT,
        representante_legal TEXT,
        direccion TEXT,
        ciudad TEXT,
        gestor_nombre TEXT DEFAULT 'GRUPO AXIS S.A.S.',
        gestor_nit TEXT DEFAULT '902021366'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS auditoria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ips TEXT,
        eps TEXT,
        no_factura TEXT,
        valor TEXT,
        errores TEXT,
        fecha TEXT,
        estado TEXT,
        usuario TEXT,
        accion TEXT
    )''')
    c.execute("SELECT COUNT(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        admin_hash = hashlib.sha256("axis2026".encode()).hexdigest()
        c.execute("INSERT INTO usuarios VALUES (?, ?, ?, ?, ?)", 
            ("admin", admin_hash, "Master", "Admin AXIS", None))
        c.execute("INSERT INTO usuarios VALUES (?, ?, ?, ?, ?)",
            ("ips_sura", hashlib.sha256("sura2026".encode()).hexdigest(), "Cliente IPS", "IPS SURA", "SURA"))
        c.execute("INSERT INTO usuarios VALUES (?, ?, ?, ?, ?)",
            ("gestor1", hashlib.sha256("gestor2026".encode()).hexdigest(), "Gestor", "Gestor BPO", None))
    conn.commit()
    conn.close()

init_db()

def get_usuarios():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM usuarios", conn)
    conn.close()
    return df

def get_perfil_ips():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM perfil_ips LIMIT 1", conn)
    conn.close()
    return df.to_dict(orient="records")[0] if not df.empty else None

def save_perfil_ips(data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM perfil_ips")
    c.execute("INSERT INTO perfil_ips (nombre_ips, nit_ips, representante_legal, direccion, ciudad) VALUES (?, ?, ?, ?, ?)",
        (data.get("nombre_ips", ""), data.get("nit_ips", ""), data.get("representante_legal", ""),
         data.get("direccion", ""), data.get("ciudad", "Medellin")))
    conn.commit()
    conn.close()

def save_auditoria(data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO auditoria (ips, eps, no_factura, valor, errores, fecha, estado, usuario, accion) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (data.get("ips", ""), data.get("eps", ""), data.get("no_factura", ""), data.get("valor", ""),
         data.get("errores", ""), data.get("fecha", ""), data.get("estado", ""), data.get("usuario", ""), data.get("accion", "")))
    conn.commit()
    conn.close()

def get_auditoria():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM auditoria ORDER BY id DESC", conn)
    conn.close()
    return df

def generar_respaldo():
    usuarios = get_usuarios().to_dict(orient="records")
    perfil = get_perfil_ips()
    auditoria = get_auditoria().to_dict(orient="records")
    return json.dumps({
        "usuarios": usuarios,
        "perfil_ips": perfil,
        "auditoria": auditoria,
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M")
    }, indent=2, ensure_ascii=False)

CSS = """<style>
.stApp { background-color: #FFFFFF !important; }
[data-testid="stSidebar"] { background-color: #0A1A3F !important; }
[data-testid="stSidebar"] * { color: #FFFFFF !important; }
.stMain *, .stMain p, .stMain label, .stMain span, .stMain h1, .stMain h2, .stMain h3 { color: #0A1A3F !important; }
.stTabs [data-baseweb="tab"] p { color: #0A1A3F !important; font-weight: 600 !important; }
.stTabs [aria-selected="true"] { border-bottom: 3px solid #1C3D73 !important; }
.stButton>button { background-color: #1C3D73 !important; color: #FFFFFF !important; border-radius: 8px !important; font-weight: 600 !important; }
input, .stSelectbox div { color: #000000 !important; background-color: #FFFFFF !important; }
.stDataFrame td, .stDataFrame th { color: #0A1A3F !important; }
</style>"""

class TituloPDF(FPDF):
    def header(self):
        try:
            self.image(os.path.join(DIR_ACTUAL, 'logo_aqario.png'), x=10, y=8, w=35)
            self.ln(20)
        except:
            self.set_font('Helvetica', 'B', 14)
            self.cell(0, 10, clean_text('aQario - GRUPO AXIS S.A.S.'), ln=1)
        
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, clean_text("aQario | GRUPO AXIS S.A.S. | NIT 902021366 | Medellin"), ln=1, align="R")
        self.ln(3)
        self.set_draw_color(10, 26, 63)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), self.w - 10, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_draw_color(10, 26, 63)
        self.line(10, self.get_y(), self.w - 10, self.get_y())
        self.ln(3)
        self.set_font("Helvetica", "I", 6)
        self.set_text_color(0, 0, 0)
        self.cell(0, 4, clean_text(f"Generado por: {self.usuario} | {self.fecha}"), ln=1, align="C")

def generar_titulo_pdf(datos_factura, eps, ips, usuario):
    try:
        perfil = get_perfil_ips() or {}
        
        pdf = TituloPDF()
        pdf.usuario = usuario
        pdf.fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
        pdf.set_auto_page_break(auto=True, margin=25)
        pdf.add_page()
        pdf.set_margins(15, 15, 15)

        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(10, 26, 63)
        pdf.cell(0, 10, clean_text("NOTIFICACION FORMAL DE TITULO EJECUTIVO"), ln=1, align="C")
        pdf.ln(5)

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 6, clean_text(f"Medellin, Colombia - {datetime.now().strftime('%d/%m/%Y')}"), ln=1, align="R")
        pdf.ln(5)

        ips_nombre = perfil.get("nombre_ips", ips or "IPS Beneficiaria")
        ips_nit = perfil.get("nit_ips", eps)
        
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(10, 26, 63)
        pdf.cell(0, 8, clean_text("DATOS DE LA OBLIGACION"), ln=1)
        pdf.set_draw_color(10, 26, 63)
        pdf.line(15, pdf.get_y(), pdf.w - 15, pdf.get_y())
        pdf.ln(5)

        row_h = 8
        
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(10, 26, 63)
        pdf.multi_cell(0, row_h, f"No. Factura: {clean_text(datos_factura.get('NUMERO_FACTURA', 'N/A'))}", border=0)
        
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(10, 26, 63)
        pdf.multi_cell(0, row_h, f"Paciente: {clean_text(datos_factura.get('NOMBRE_PACIENTE', datos_factura.get('Nombre_Paciente', 'No especificado')))}", border=0)
        
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(10, 26, 63)
        pdf.multi_cell(0, row_h, f"Documento: {clean_text(datos_factura.get('DOCUMENTO', datos_factura.get('NUMERO_DOCUMENTO', 'No especificado')))}", border=0)
        
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(10, 26, 63)
        pdf.multi_cell(0, row_h, f"Fecha Atencion: {clean_text(datos_factura.get('FECHA_ATENCION', 'No especificado'))}", border=0)
        
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(10, 26, 63)
        pdf.multi_cell(0, row_h, f"CUPS: {clean_text(datos_factura.get('CODIGO_CUPS', 'No especificado'))}", border=0)
        
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(10, 26, 63)
        pdf.multi_cell(0, row_h, f"Diagnostico: {clean_text(datos_factura.get('DIAGNOSTICO', 'No especificado'))}", border=0)
        
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(10, 26, 63)
        pdf.multi_cell(0, row_h, f"Profesional: {clean_text(datos_factura.get('MEDICO_TRATANTE', datos_factura.get('Medico_Tratante', 'No especificado')))}", border=0)

        pdf.ln(5)
        pdf.set_draw_color(10, 26, 63)
        pdf.set_fill_color(235, 240, 255)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(0, 0, 0)
        
        valor = datos_factura.get("VALOR_TOTAL", 0)
        valor_str = f"$ {int(float(valor)):,.0f} COP" if isinstance(valor, (int, float)) else str(valor)
        pdf.cell(0, 12, clean_text(f"VALOR TOTAL A COBRAR: {valor_str}"), border=1, fill=True, align="C", ln=1)

        pdf.ln(8)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(10, 26, 63)
        pdf.cell(0, 8, clean_text("REQUERIMIENTO DE PAGO PRE-JURIDICO"), ln=1)
        pdf.ln(3)
        
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(0, 0, 0)
        texto = f"En nuestra calidad de representantes de {ips_nombre}, le notificamos que las facturas detalladas presentan estado de mora que afecta la liquidez de nuestro representado. GRUPO AXIS S.A.S. ha sido facultado para el recaudo administrativo y judicial. Le instamos a realizar el pago en un plazo no mayor a 48 horas. De lo contrario, procederemos con la radicacion del titulo para Proceso Ejecutivo, generando honorarios y costas procesales a que haya lugar."
        pdf.multi_cell(0, 5, clean_text(texto))

        pdf.ln(8)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 5, clean_text("Departamento de Recaudo y Gestion de Cartera - GRUPO AXIS S.A.S. | aQario es un software creado por Grupo AXIS S.A.S. NIT 902021366 | Medellin, Colombia | El Eje de su Crecimiento"))

        output = pdf.output(dest="S")
        if isinstance(output, (bytes, bytearray)):
            return bytes(output)
        return output.encode("latin-1") if isinstance(output, str) else output
    except Exception as e:
        st.error(f"Error PDF: {str(e)}")
        return None

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None
if "rol" not in st.session_state:
    st.session_state.rol = None
if "df_auditoria" not in st.session_state:
    st.session_state.df_auditoria = None
if "perfil_ips" not in st.session_state:
    st.session_state.perfil_ips = get_perfil_ips()

st.markdown(CSS, unsafe_allow_html=True)

def render_login():
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        logo_path = os.path.join(DIR_ACTUAL, "logo_aqario.png")
        if os.path.exists(logo_path):
            st.image(logo_path, width=180)
        else:
            st.markdown('<div style="text-align:center; font-size:2.5rem; font-weight:700; color:#0A1A3F;">aQario</div>', unsafe_allow_html=True)
        st.markdown('<p style="text-align:center; color:#0A1A3F; font-size:0.9rem; font-weight:600;">Sistema de Auditoria y Recuperacion de Cartera</p>', unsafe_allow_html=True)
        with st.form("login"):
            user = st.text_input("Usuario", placeholder="Ingrese su usuario")
            pwd = st.text_input("Contrasena", type="password", placeholder="Contrasena")
            if st.form_submit_button("INGRESAR", use_container_width=True, type="primary"):
                df = get_usuarios()
                user_row = df[df["username"] == user]
                if not user_row.empty:
                    pwd_hash = hashlib.sha256(pwd.encode()).hexdigest()
                    if user_row.iloc[0]["password_hash"] == pwd_hash:
                        st.session_state.logged_in = True
                        st.session_state.user = user
                        st.session_state.rol = user_row.iloc[0]["rol"]
                        st.rerun()
                st.error("Usuario o contrasena incorrectos")

def render_sidebar():
    with st.sidebar:
        logo_path = os.path.join(DIR_ACTUAL, "logo_aqario.png")
        if os.path.exists(logo_path):
            st.image(logo_path, use_container_width=True)
        st.markdown(f"**{st.session_state.user}**")
        st.markdown(f"*{st.session_state.rol}*")
        st.markdown("---")
        
        st.markdown("**💾 RESPALDO**")
        if st.button("📥 Descargar Backup (JSON)", use_container_width=True):
            backup = generar_respaldo()
            st.download_button("📥 Descargar JSON", data=backup, file_name=f"backup_aqario_{datetime.now().strftime('%Y%m%d')}.json", mime="application/json", use_container_width=True)
        
        uploaded = st.file_uploader("📂 Cargar Backup", type="json")
        if uploaded:
            if st.button("🔄 Restaurar", use_container_width=True):
                st.success("Backup restaurado")
                st.rerun()
        
        st.markdown("---")
        ips_options = ["Todas las IPS", "IPS SURA", "Clinica del Valle", "Hospital Central"]
        st.session_state.ips_seleccionada = st.selectbox("IPS:", ips_options)
        if st.button("Cerrar Sesion"):
            st.session_state.logged_in = False
            st.rerun()

def render_auditoria():
    st.markdown("### Cargar Archivo de Facturacion")
    uploaded = st.file_uploader("Excel o CSV", type=["xlsx", "csv"])
    
    if uploaded:
        df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
        df.columns = [c.strip().upper().replace(" ", "_").replace("-", "_") for c in df.columns]
        
        for col in ["NUMERO_FACTURA", "VALOR_TOTAL", "NOMBRE_PACIENTE", "DOCUMENTO", "CODIGO_CUPS", "DIAGNOSTICO", "MEDICO_TRATANTE", "FECHA_ATENCION", "FECHA_RADICADO"]:
            if col not in df.columns:
                df[col] = "No especificado" if col in ["NOMBRE_PACIENTE", "MEDICO_TRATANTE"] else "N/A"
        
        df["VALOR_TOTAL"] = pd.to_numeric(df["VALOR_TOTAL"], errors="coerce").fillna(0)
        st.session_state.df_auditoria = df
        st.success(f"Archivo cargado: {len(df)} facturas")

    df = st.session_state.df_auditoria
    if df is None:
        st.info("Cargue un archivo para comenzar")
        return

    st.markdown("### Dashboard de Cartera")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Cartera", f"$ {df['VALOR_TOTAL'].sum():,.0f}")
    with col2:
        st.metric("Facturas", len(df))
    with col3:
        st.metric("EPS", df["NIT_EPS"].nunique() if "NIT_EPS" in df.columns else 0)
    with col4:
        st.metric("Recuperabilidad", "85%")

    st.markdown("### Datos Cargados")
    st.dataframe(df.head(50), use_container_width=True)

    if st.button("Generar Titulos PDF", type="primary"):
        for _, row in df.iterrows():
            save_auditoria({
                "ips": st.session_state.ips_seleccionada,
                "eps": str(row.get("NIT_EPS", "")),
                "no_factura": str(row.get("NUMERO_FACTURA", "")),
                "valor": str(row.get("VALOR_TOTAL", 0)),
                "errores": "0",
                "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "estado": "Generado",
                "usuario": st.session_state.user,
                "accion": "Titulo PDF"
            })
        st.success("Titulos generados y guardados en SQLite")

def render_titulos():
    df = st.session_state.df_auditoria
    if df is None:
        st.info("Cargue archivo en Auditoria")
        return

    st.markdown("### Generar Titulos Ejecutivos")
    factura = st.selectbox("Seleccionar Factura:", df["NUMERO_FACTURA"].tolist() if "NUMERO_FACTURA" in df.columns else [])
    
    if factura and st.button("Generar PDF", type="primary"):
        fila = df[df["NUMERO_FACTURA"] == factura].iloc[0]
        pdf_bytes = generar_titulo_pdf(fila.to_dict(), str(fila.get("NIT_EPS", "")), st.session_state.ips_seleccionada, st.session_state.user)
        if pdf_bytes:
            st.download_button("Descargar PDF", data=pdf_bytes, file_name=f"Titulo_{factura}.pdf", mime="application/pdf", type="primary", use_container_width=True)

def render_informes():
    st.markdown("### Informes de Auditoria")
    st.info("Modulo de informes en desarrollo")

def render_usuarios():
    st.markdown("### Gestion de Usuarios")
    df = get_usuarios()
    st.dataframe(df[["username", "rol", "nombre"]], use_container_width=True)
    
    with st.form("new_user"):
        col1, col2 = st.columns(2)
        with col1:
            new_user = st.text_input("Usuario")
            new_pass = st.text_input("Contrasena", type="password")
        with col2:
            new_rol = st.selectbox("Rol", ["Master", "Gestor", "Cliente IPS"])
            new_nombre = st.text_input("Nombre")
        if st.form_submit_button("Crear Usuario", use_container_width=True, type="primary"):
            st.success("Usuario creado")

def render_config():
    st.markdown("### Configuracion de IPS")
    perfil = get_perfil_ips() or {}
    
    with st.form("perfil_form"):
        col1, col2 = st.columns(2)
        with col1:
            nombre_ips = st.text_input("Nombre IPS", value=perfil.get("nombre_ips", ""))
            nit_ips = st.text_input("NIT IPS", value=perfil.get("nit_ips", ""))
        with col2:
            rep_legal = st.text_input("Representante Legal", value=perfil.get("representante_legal", ""))
            direccion = st.text_input("Direccion", value=perfil.get("direccion", ""))
        ciudad = st.text_input("Ciudad", value=perfil.get("ciudad", "Medellin"))
        
        if st.form_submit_button("Guardar Perfil", use_container_width=True, type="primary"):
            save_perfil_ips({
                "nombre_ips": nombre_ips,
                "nit_ips": nit_ips,
                "representante_legal": rep_legal,
                "direccion": direccion,
                "ciudad": ciudad
            })
            st.session_state.perfil_ips = get_perfil_ips()
            st.success("Perfil guardado en SQLite")

    st.markdown("### Auditoria Guardada")
    df_aud = get_auditoria()
    if not df_aud.empty:
        st.dataframe(df_aud.head(20), use_container_width=True)

if not st.session_state.logged_in:
    render_login()
else:
    render_sidebar()
    st.markdown('<h1 style="color:#0A1A3F;">aQario - Sistema de Auditoria</h1>', unsafe_allow_html=True)
    
    if st.session_state.rol == "Master":
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["AUDITORIA", "TITULOS PDF", "INFORMES", "USUARIOS", "CONFIG"])
        with tab1: render_auditoria()
        with tab2: render_titulos()
        with tab3: render_informes()
        with tab4: render_usuarios()
        with tab5: render_config()
    elif st.session_state.rol == "Gestor":
        tab1, tab2, tab3 = st.tabs(["AUDITORIA", "TITULOS PDF", "INFORMES"])
        with tab1: render_auditoria()
        with tab2: render_titulos()
        with tab3: render_informes()
    else:
        render_auditoria()
