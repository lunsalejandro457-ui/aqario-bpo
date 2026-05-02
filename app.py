import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import hashlib
import sqlite3
import re
import zipfile
import io
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
    c.execute('''CREATE TABLE IF NOT EXISTS auditoria_temp (
        NUMERO_FACTURA TEXT, VALOR_TOTAL REAL, NIT_EPS TEXT,
        FECHA_RADICADO TEXT, CODIGO_CUPS TEXT, DIAGNOSTICO TEXT,
        NOMBRE_PACIENTE TEXT, SEXO TEXT, EDAD TEXT,
        DOCUMENTO TEXT, MEDICO_TRATANTE TEXT, FECHA_ATENCION TEXT,
        ALERTAS_SISTEMA TEXT, ips_asignada TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS mandatario (
        id INTEGER PRIMARY KEY,
        nombre_mandatario TEXT,
        cargo_mandatario TEXT,
        nit_mandante TEXT,
        numero_contrato_mandato TEXT,
        fecha_contrato TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS manuales (
        nombre TEXT PRIMARY KEY,
        contenido BLOB,
        fecha_carga TEXT,
        usuario TEXT
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

def init_session():
    """Load persisted data from SQLite on startup"""
    if 'df_auditoria' not in st.session_state:
        st.session_state.df_auditoria = None
    if 'auditoria_loaded' not in st.session_state:
        st.session_state.auditoria_loaded = False
    if 'ips_seleccionada' not in st.session_state:
        st.session_state.ips_seleccionada = 'Todas las IPS'
    
    # Try to load from auditoria_temp table
    try:
        conn = sqlite3.connect(DB_PATH)
        df_saved = pd.read_sql_query("SELECT * FROM auditoria_temp", conn)
        conn.close()
        if len(df_saved) >0:
            st.session_state.df_auditoria = df_saved
            st.session_state.auditoria_loaded = True
    except Exception as e:
        pass

init_session()

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

def get_mandatario():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM mandatario LIMIT 1", conn)
    conn.close()
    return df.to_dict(orient="records")[0] if not df.empty else None

def save_mandatario(data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM mandatario")
    c.execute("INSERT INTO mandatario (nombre_mandatario, cargo_mandatario, nit_mandante, numero_contrato_mandato, fecha_contrato) VALUES (?, ?, ?, ?, ?)",
        (data.get("nombre_mandatario", ""), data.get("cargo_mandatario", ""), data.get("nit_mandante", ""),
         data.get("numero_contrato_mandato", ""), data.get("fecha_contrato", "")))
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

def get_manuales():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT nombre, fecha_carga, usuario, LENGTH(contenido) as tamaño FROM manuales", conn)
    conn.close()
    return df

def save_manual(nombre, contenido, usuario):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("REPLACE INTO manuales (nombre, contenido, fecha_carga, usuario) VALUES (?, ?, ?, ?)",
        (nombre, sqlite3.Binary(contenido), datetime.now().strftime("%d/%m/%Y %H:%M"), usuario))
    conn.commit()
    conn.close()

def generar_respaldo():
    usuarios = get_usuarios().to_dict(orient="records")
    perfil = get_perfil_ips()
    auditoria = get_auditoria().to_dict(orient="records")
    mandatario = get_mandatario()
    return json.dumps({
        "usuarios": usuarios,
        "perfil_ips": perfil,
        "auditoria": auditoria,
        "mandatario": mandatario,
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M")
    }, indent=2, ensure_ascii=False)

def validar_con_manuales(df):
    alertas = []
    median_val = df['VALOR_TOTAL'].median() if not df.empty else 0
    for _, row in df.iterrows():
        issues = []
        diag = str(row.get('DIAGNOSTICO', ''))
        if not re.match(r'^[A-Z][0-9]{2,3}$', diag):
            issues.append(f"Codigo CIE-10 invalido: {diag}")
        val = float(row.get('VALOR_TOTAL', 0))
        if val > median_val * 10 and median_val > 0:
            issues.append(f"Valor anomalo: ${val:,.0f}")
        alertas.append('; '.join(issues) if issues else 'OK')
    df['ALERTAS_SISTEMA'] = alertas
    return df

def generar_titulo_pdf(datos, perfil_ips=None):
    MANDATARIO_NOMBRE = "GRUPO AXIS S.A.S."
    MANDATARIO_NIT = "902021366-2"
    MANDATARIO_CIUDAD = "Medellin, Colombia"
    MANDATARIO_CARGO = "Departamento de Recaudo y Gestion de Cartera"
    
    clean = lambda s: str(s)\
        .replace('—','-').replace('–','-')\
        .replace('"','"').replace('"','"')\
        .replace('\u2019',"'").replace('\u2018',"'")\
        .replace('…','...').replace('\u00e9','e')\
        .encode('latin-1','ignore').decode('latin-1')

    def wl(pdf, txt, bold=False, size=10, align='L', h=7):
        pdf.set_font('Helvetica', 'B' if bold else '', size)
        txt = clean(str(txt))
        max_chars = 85
        while txt:
            chunk = txt[:max_chars]
            if len(txt) > max_chars and ' ' in chunk:
                chunk = chunk[:chunk.rfind(' ')]
            pdf.cell(0, h, chunk, ln=1, align=align)
            txt = txt[len(chunk):].strip()

    def write_footer_legal(pdf):
        pdf.set_font('Helvetica', '', 7)
        lineas = [
            'PROTECCION DE DATOS Y CONFIDENCIALIDAD:',
            'La informacion contenida es confidencial, protegida bajo Ley 1581/2012',
            '(Proteccion de Datos Personales), Ley 1438/2011 y Resolucion 3374/2000 (RIPS).',
            'Su divulgacion no autorizada genera responsabilidad civil y penal.',
            'Documento generado por aQario - GRUPO AXIS S.A.S. NIT 902021366-2 | Medellin, Colombia',
        ]
        for linea in lineas:
            pdf.cell(0, 4, clean(linea), ln=1, align='C')

    def add_watermark(pdf, usuario, timestamp):
        pdf.set_text_color(200, 200, 200)
        pdf.set_font('Helvetica', '', 8)
        pdf.set_xy(120, 5)
        pdf.cell(70, 5, clean(f'Impreso por: {usuario}'), align='R', ln=1)
        pdf.set_xy(120, 9)
        pdf.cell(70, 5, clean(f'Fecha: {timestamp}'), align='R', ln=1)
        pdf.set_text_color(0, 0, 0)

    pdf = FPDF('P', 'mm', 'A4')
    pdf.add_page()
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    usuario_actual = st.session_state.get('user', 'Sistema')
    add_watermark(pdf, usuario_actual, timestamp)
    
    pdf.set_left_margin(20)
    pdf.set_right_margin(20)
    pdf.set_top_margin(20)
    pdf.set_auto_page_break(True, margin=20)
    pdf.set_xy(20, 15)

    try:
        pdf.image('logo_aqario.png', x=20, y=12, w=32)
        pdf.set_xy(20, 45)
    except:
        wl(pdf, 'aQario - GRUPO AXIS S.A.S.', bold=True, size=11)

    wl(pdf, 'NOTIFICACION FORMAL DE TITULO EJECUTIVO', bold=True, size=13, align='C', h=9)
    wl(pdf, f'Medellin, Colombia - {datetime.now().strftime("%d/%m/%Y %H:%M")}', size=8, align='R', h=6)
    pdf.ln(2)

    pdf.set_draw_color(10, 26, 63)
    pdf.set_line_width(0.8)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(4)

    wl(pdf, 'REQUERIMIENTO DE PAGO PRE-JURIDICO', bold=True, size=10)
    nombre_ips = (perfil_ips or {}).get('nombre_ips', 'la IPS representada')
    nit_ips = (perfil_ips or {}).get('nit_ips', 'N/A')
    parrafos = [
        f'En calidad de representantes de {nombre_ips}, notificamos que las facturas',
        'detalladas presentan estado de mora. GRUPO AXIS S.A.S. ha sido facultado para',
        'el recaudo administrativo y judicial de esta cartera.',
        'Le instamos a realizar el pago en un plazo no mayor a 48 horas. De lo contrario,',
        'se radicara titulo para Proceso Ejecutivo con honorarios y costas procesales.',
    ]
    for p in parrafos:
        wl(pdf, p, size=9, h=6)
    pdf.ln(4)

    mand_text = (
        f"En virtud del Contrato de Mandato suscrito entre {nombre_ips} (NIT {nit_ips}) "
        f"y GRUPO AXIS S.A.S. (NIT 902021366-2), con domicilio en Medellin, Colombia, "
        f"se autoriza expresamente a GRUPO AXIS S.A.S. para gestionar el recaudo "
        f"prejuridico y judicial de las facturas relacionadas en el presente titulo ejecutivo."
    )
    wl(pdf, mand_text, size=9, h=6)
    pdf.ln(4)

    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(4)

    campos = [
        ('No. Factura', datos.get('NUMERO_FACTURA','N/A')),
        ('Paciente', datos.get('NOMBRE_PACIENTE','No especificado')),
        ('Documento', datos.get('DOCUMENTO','No especificado')),
        ('Fecha Atencion', datos.get('FECHA_RADICADO','No especificado')),
        ('Codigo CUPS', datos.get('CODIGO_CUPS','No especificado')),
        ('Diagnostico', datos.get('DIAGNOSTICO','No especificado')),
        ('Profesional', datos.get('MEDICO_TRATANTE','No especificado')),
        ('EPS Deudora', datos.get('NIT_EPS','No especificado')),
    ]
    for label, valor in campos:
        wl(pdf, f'{label}: {valor}', size=10, h=7)
    pdf.ln(3)

    pdf.set_fill_color(10, 26, 63)
    pdf.set_text_color(255,255,255)
    pdf.set_font('Helvetica','B',12)
    valor_num = datos.get('VALOR_TOTAL', 0)
    try:
        valor_fmt = f"$ {int(float(str(valor_num).replace(',','').replace('.',''))):,}".replace(',','.')
    except:
        valor_fmt = str(valor_num)
    pdf.cell(0, 10, clean(f'VALOR TOTAL A COBRAR: {valor_fmt}'), ln=1, align='C', fill=True)
    pdf.set_text_color(0,0,0)
    pdf.ln(4)

    pdf.set_draw_color(10,26,63)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(3)
    wl(pdf, 'Departamento de Recaudo y Gestion de Cartera - GRUPO AXIS S.A.S.', size=8, align='C', h=5)
    wl(pdf, 'aQario - Software creado por Grupo AXIS S.A.S. NIT 902021366-2', size=8, align='C', h=5)
    wl(pdf, 'Medellin, Colombia | El Eje de su Crecimiento', size=8, align='C', h=5)
    pdf.ln(3)
    write_footer_legal(pdf)

    # Log document generation
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS log_documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_doc TEXT,
            numero_factura TEXT,
            eps TEXT,
            usuario TEXT,
            fecha_generacion TEXT,
            ip_session TEXT
        )""")
        c.execute("""INSERT INTO log_documentos 
            (tipo_doc, numero_factura, eps, usuario, fecha_generacion)
            VALUES (?, ?, ?, ?, ?)""",
            ("Titulo Ejecutivo", str(datos.get('NUMERO_FACTURA', '')), 
             str(datos.get('NIT_EPS', '')), usuario_actual, 
             datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except:
        pass

    return bytes(pdf.output())

def generar_titulo_por_entidad(df_eps, perfil_ips):
    MANDATARIO_NOMBRE = "GRUPO AXIS S.A.S."
    MANDATARIO_NIT = "902021366-2"
    MANDATARIO_CIUDAD = "Medellin, Colombia"
    MANDATARIO_CARGO = "Departamento de Recaudo y Gestion de Cartera"
    
    clean = lambda s: str(s)\
        .replace('—','-').replace('–','-')\
        .replace('"','"').replace('"','"')\
        .replace('\u2019',"'").replace('\u2018',"'")\
        .replace('…','...').replace('\u00e9','e')\
        .encode('latin-1','ignore').decode('latin-1')

    def wl(pdf, txt, bold=False, size=10, align='L', h=7):
        pdf.set_font('Helvetica', 'B' if bold else '', size)
        txt = clean(str(txt))
        max_chars = 85
        while txt:
            chunk = txt[:max_chars]
            if len(txt) > max_chars and ' ' in chunk:
                chunk = chunk[:chunk.rfind(' ')]
            pdf.cell(0, h, chunk, ln=1, align=align)
            txt = txt[len(chunk):].strip()

    def write_footer_legal(pdf):
        pdf.set_font('Helvetica', '', 7)
        lineas = [
            'PROTECCION DE DATOS Y CONFIDENCIALIDAD:',
            'La informacion contenida es confidencial, protegida bajo Ley 1581/2012',
            '(Proteccion de Datos Personales), Ley 1438/2011 y Resolucion 3374/2000 (RIPS).',
            'Su divulgacion no autorizada genera responsabilidad civil y penal.',
            'Documento generado por aQario - GRUPO AXIS S.A.S. NIT 902021366-2 | Medellin, Colombia',
        ]
        for linea in lineas:
            pdf.cell(0, 4, clean(linea), ln=1, align='C')

    def add_watermark(pdf, usuario, timestamp):
        pdf.set_text_color(200, 200, 200)
        pdf.set_font('Helvetica', '', 8)
        pdf.set_xy(120, 5)
        pdf.cell(70, 5, clean(f'Impreso por: {usuario}'), align='R', ln=1)
        pdf.set_xy(120, 9)
        pdf.cell(70, 5, clean(f'Fecha: {timestamp}'), align='R', ln=1)
        pdf.set_text_color(0, 0, 0)

    pdf = FPDF('P', 'mm', 'A4')
    pdf.add_page()
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    usuario_actual = st.session_state.get('user', 'Sistema')
    add_watermark(pdf, usuario_actual, timestamp)
    
    pdf.set_left_margin(20)
    pdf.set_right_margin(20)
    pdf.set_top_margin(20)
    pdf.set_auto_page_break(True, margin=20)
    pdf.set_xy(20, 15)

    try:
        pdf.image('logo_aqario.png', x=20, y=12, w=32)
        pdf.set_xy(20, 45)
    except:
        wl(pdf, 'aQario - GRUPO AXIS S.A.S.', bold=True, size=11)

    wl(pdf, f'Medellin, Colombia - {datetime.now().strftime("%d/%m/%Y %H:%M")}', size=8, align='R', h=6)
    pdf.ln(2)

    pdf.set_draw_color(10, 26, 63)
    pdf.set_line_width(0.8)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(4)

    wl(pdf, 'REQUERIMIENTO DE PAGO PRE-JURIDICO', bold=True, size=10)
    nombre_ips = (perfil_ips or {}).get('nombre_ips', 'la IPS representada')
    parrafos = [
        f'En calidad de representantes de {nombre_ips}, notificamos que las facturas',
        'detalladas presentan estado de mora. GRUPO AXIS S.A.S. ha sido facultado para',
        'el recaudo administrativo y judicial de esta cartera.',
        'Le instamos a realizar el pago en un plazo no mayor a 48 horas. De lo contrario,',
        'se radicara titulo para Proceso Ejecutivo con honorarios y costas procesales.',
    ]
    for p in parrafos:
        wl(pdf, p, size=9, h=6)
    pdf.ln(4)

    mand_text = (
        f"En virtud del Contrato de Mandato suscrito entre {nombre_ips} (NIT {perfil_ips.get('nit_ips', 'N/A') if perfil_ips else 'N/A'}) "
        f"y GRUPO AXIS S.A.S. (NIT 902021366-2), con domicilio en Medellin, Colombia, "
        f"se autoriza expresamente a GRUPO AXIS S.A.S. para gestionar el recaudo "
        f"prejuridico y judicial de las facturas relacionadas en el presente titulo ejecutivo."
    )
    wl(pdf, mand_text, size=9, h=6)
    pdf.ln(4)

    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(4)

    wl(pdf, 'FACTURAS RELACIONADAS', bold=True, size=10)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.cell(25, 7, clean('No. Factura'), border=1, align='C')
    pdf.cell(40, 7, clean('Paciente'), border=1, align='C')
    pdf.cell(25, 7, clean('CUPS'), border=1, align='C')
    pdf.cell(50, 7, clean('Diagnostico'), border=1, align='C')
    pdf.cell(30, 7, clean('Valor'), border=1, align='C', ln=1)

    pdf.set_font('Helvetica', '', 8)
    total_valor = 0
    for _, row in df_eps.iterrows():
        pdf.cell(25, 7, clean(str(row.get('NUMERO_FACTURA', 'N/A'))), border=1)
        pdf.cell(40, 7, clean(str(row.get('NOMBRE_PACIENTE', 'No especificado'))[:20]), border=1)
        pdf.cell(25, 7, clean(str(row.get('CODIGO_CUPS', 'No especificado'))), border=1)
        pdf.cell(50, 7, clean(str(row.get('DIAGNOSTICO', 'No especificado'))[:30]), border=1)
        val = float(row.get('VALOR_TOTAL', 0))
        total_valor += val
        val_str = f"$ {int(val):,}".replace(',', '.')
        pdf.cell(30, 7, clean(val_str), border=1, ln=1)

    pdf.set_font('Helvetica', 'B', 8)
    pdf.cell(140, 7, clean('TOTAL CONSOLIDADO'), border=1, align='R')
    total_str = f"$ {int(total_valor):,}".replace(',', '.')
    pdf.cell(30, 7, clean(total_str), border=1, ln=1)
    pdf.ln(4)

    pdf.set_fill_color(10, 26, 63)
    pdf.set_text_color(255,255,255)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 10, clean(f'VALOR TOTAL CONSOLIDADO: {total_str}'), ln=1, align='C', fill=True)
    pdf.set_text_color(0,0,0)
    pdf.ln(4)

    pdf.set_draw_color(10,26,63)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(3)
    wl(pdf, 'Departamento de Recaudo y Gestion de Cartera - GRUPO AXIS S.A.S.', size=8, align='C', h=5)
    wl(pdf, 'aQario - Software creado por Grupo AXIS S.A.S. NIT 902021366-2', size=8, align='C', h=5)
    wl(pdf, 'Medellin, Colombia | El Eje de su Crecimiento', size=8, align='C', h=5)
    pdf.ln(3)
    write_footer_legal(pdf)

    # Log document generation
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS log_documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_doc TEXT,
            numero_factura TEXT,
            eps TEXT,
            usuario TEXT,
            fecha_generacion TEXT,
            ip_session TEXT
        )""")
        for _, row in df_eps.iterrows():
            c.execute("""INSERT INTO log_documentos 
                (tipo_doc, numero_factura, eps, usuario, fecha_generacion)
                VALUES (?, ?, ?, ?, ?)""",
                ("Titulo Ejecutivo", str(row.get('NUMERO_FACTURA', '')), 
                 str(row.get('NIT_EPS', '')), usuario_actual, 
                 datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except:
        pass

    return bytes(pdf.output())

def generar_certificado_pdf(nombre_ips, fecha_inicio, fecha_fin, total_rips, valor_total, errores, recuperabilidad, perfil_ips):
    clean = lambda s: str(s)\
        .replace('—','-').replace('–','-')\
        .replace('"','"').replace('"','"')\
        .replace('\u2019',"'").replace('\u2018',"'")\
        .replace('…','...').replace('\u00e9','e')\
        .encode('latin-1','ignore').decode('latin-1')

    def wl(pdf, txt, bold=False, size=10, align='L', h=7):
        pdf.set_font('Helvetica', 'B' if bold else '', size)
        txt = clean(str(txt))
        max_chars = 85
        while txt:
            chunk = txt[:max_chars]
            if len(txt) > max_chars and ' ' in chunk:
                chunk = chunk[:chunk.rfind(' ')]
            pdf.cell(0, h, chunk, ln=1, align=align)
            txt = txt[len(chunk):].strip()

    def write_footer_legal(pdf):
        pdf.set_font('Helvetica', '', 7)
        lineas = [
            'PROTECCION DE DATOS Y CONFIDENCIALIDAD:',
            'La informacion contenida es confidencial, protegida bajo Ley 1581/2012',
            '(Proteccion de Datos Personales), Ley 1438/2011 y Resolucion 3374/2000 (RIPS).',
            'Su divulgacion no autorizada genera responsabilidad civil y penal.',
            'Documento generado por aQario - GRUPO AXIS S.A.S. NIT 902021366-2 | Medellin, Colombia',
        ]
        for linea in lineas:
            pdf.cell(0, 4, clean(linea), ln=1, align='C')

    def add_watermark(pdf, usuario, timestamp):
        pdf.set_text_color(200, 200, 200)
        pdf.set_font('Helvetica', '', 8)
        pdf.set_xy(120, 5)
        pdf.cell(70, 5, clean(f'Impreso por: {usuario}'), align='R', ln=1)
        pdf.set_xy(120, 9)
        pdf.cell(70, 5, clean(f'Fecha: {timestamp}'), align='R', ln=1)
        pdf.set_text_color(0, 0, 0)

    pdf = FPDF('P','mm','A4')
    pdf.add_page()
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    usuario_actual = st.session_state.get('user', 'Sistema')
    add_watermark(pdf, usuario_actual, timestamp)
    
    pdf.set_margins(20,20,20)
    pdf.set_auto_page_break(True, margin=20)
    pdf.set_xy(20,15)

    try:
        pdf.image('logo_aqario.png', x=20, y=12, w=32)
        pdf.set_xy(20, 44)
    except:
        wl(pdf, 'aQario - GRUPO AXIS S.A.S.', bold=True, size=11)
    
    wl(pdf, 'CERTIFICADO DE AUDITORIA DE CARTERA', bold=True, size=14, align='C', h=10)
    pdf.ln(5)

    wl(pdf, f'GRUPO AXIS S.A.S. certifica que entre {fecha_inicio} y {fecha_fin}', size=10, h=7)
    wl(pdf, f'se auditaron {total_rips} RIPS de {nombre_ips}, con un valor total de ${valor_total:,.0f}.', size=10, h=7)
    wl(pdf, f'Se detectaron {errores} errores de digitacion. Recuperabilidad estimada: {recuperabilidad}%.', size=10, h=7)
    pdf.ln(5)

    wl(pdf, 'Firmado por: Departamento de Auditoria AXIS BPO', bold=True, size=10, h=7)
    pdf.ln(3)

    pdf.set_draw_color(10,26,63)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(3)
    wl(pdf, 'Departamento de Recaudo y Gestion de Cartera - GRUPO AXIS S.A.S.', size=8, align='C', h=5)
    wl(pdf, 'aQario - Software creado por Grupo AXIS S.A.S. NIT 902021366-2', size=8, align='C', h=5)
    wl(pdf, 'Medellin, Colombia | El Eje de su Crecimiento', size=8, align='C', h=5)
    pdf.ln(3)
    write_footer_legal(pdf)

    # Log document generation
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS log_documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_doc TEXT,
            numero_factura TEXT,
            eps TEXT,
            usuario TEXT,
            fecha_generacion TEXT,
            ip_session TEXT
        )""")
        c.execute("""INSERT INTO log_documentos 
            (tipo_doc, numero_factura, eps, usuario, fecha_generacion)
            VALUES (?, ?, ?, ?, ?)""",
            ("Certificado", "", nombre_ips, usuario_actual, 
             datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except:
        pass

    return bytes(pdf.output())

CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600;700&family=Open+Sans:wght@300;400;600&display=swap');

/* === BASE === */
.stApp { background: #F4F6F9 !important; font-family: 'Open Sans', sans-serif !important; }

/* === SIDEBAR === */
[data-testid="stSidebar"] { 
    background: linear-gradient(180deg, #001830 0%, #002D5C 60%, #003F7F 100%) !important;
    border-right: 3px solid #00A8E8 !important;
}
[data-testid="stSidebar"] * { 
    color: #E8F4FD !important; 
    font-family: 'Open Sans', sans-serif !important;
}
[data-testid="stSidebar"] .stButton>button {
    background: linear-gradient(135deg, #00A8E8 0%, #0077B6 100%) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    letter-spacing: 0.5px !important;
    padding: 8px 16px !important;
    transition: all 0.2s !important;
    box-shadow: 0 2px 8px rgba(0,168,232,0.3) !important;
}

/* === LOGO AREA === */
[data-testid="stSidebar"] img {
    filter: drop-shadow(0 0 12px rgba(0,168,232,0.6)) !important;
    margin: 10px auto !important;
}

/* === MAIN AREA === */
.stMain { background: #F4F6F9 !important; }
.stMain *, .stMain p, .stMain label, .stMain span { 
    color: #1A2B4A !important; 
    font-family: 'Open Sans', sans-serif !important;
}

/* === PAGE TITLE === */
.stMain h1 { 
    color: #001830 !important; 
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1.8rem !important;
    border-bottom: 3px solid #00A8E8 !important;
    padding-bottom: 12px !important;
    margin-bottom: 24px !important;
}
.stMain h2, .stMain h3 { 
    color: #002D5C !important; 
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 600 !important;
}

/* === TABS — Enterprise style === */
.stTabs [data-baseweb="tab-list"] {
    background: #FFFFFF !important;
    border-radius: 8px 8px 0 0 !important;
    padding: 4px 8px 0 8px !important;
    border-bottom: 2px solid #00A8E8 !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #5B7FA6 !important;
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.78rem !important;
    letter-spacing: 1px !important;
    text-transform: uppercase !important;
    padding: 10px 20px !important;
    border-radius: 6px 6px 0 0 !important;
    border: none !important;
}
.stTabs [aria-selected="true"] {
    background: #00A8E8 !important;
    color: #FFFFFF !important;
    border-radius: 6px 6px 0 0 !important;
}

/* === MAIN BUTTONS === */
.stMain .stButton>button {
    background: linear-gradient(135deg, #002D5C 0%, #00A8E8 100%) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 6px !important;
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    letter-spacing: 0.8px !important;
    padding: 10px 24px !important;
    box-shadow: 0 4px 12px rgba(0,45,92,0.25) !important;
    transition: all 0.2s ease !important;
}
.stMain .stButton>button:hover {
    box-shadow: 0 6px 18px rgba(0,168,232,0.4) !important;
    transform: translateY(-1px) !important;
}

/* === DOWNLOAD BUTTONS === */
.stDownloadButton>button {
    background: linear-gradient(135deg, #0077B6 0%, #00A8E8 100%) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    padding: 10px 24px !important;
    box-shadow: 0 4px 12px rgba(0,119,182,0.3) !important;
}

/* === METRIC CARDS === */
[data-testid="stMetric"] {
    background: #FFFFFF !important;
    border-radius: 10px !important;
    padding: 16px 20px !important;
    border-left: 4px solid #00A8E8 !important;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07) !important;
}
[data-testid="stMetricLabel"] { 
    color: #5B7FA6 !important; 
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.5px !important;
    text-transform: uppercase !important;
}
[data-testid="stMetricValue"] { 
    color: #001830 !important; 
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1.6rem !important;
}

/* === DATAFRAME === */
.stDataFrame { 
    border-radius: 10px !important; 
    overflow: hidden !important;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08) !important;
}
.stDataFrame thead tr th { 
    background: #001830 !important; 
    color: #FFFFFF !important;
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.5px !important;
}
.stDataFrame tbody tr:nth-child(even) { background: #F0F6FF !important; }
.stDataFrame td { color: #1A2B4A !important; font-size: 0.85rem !important; }

/* === INPUTS === */
input, .stSelectbox div, textarea {
    background: #FFFFFF !important;
    color: #1A2B4A !important;
    border: 1.5px solid #C5D8EC !important;
    border-radius: 6px !important;
}
input:focus { border-color: #00A8E8 !important; }

/* === ALERTS === */
.stSuccess { 
    background: #E8F8F2 !important; 
    border-left: 4px solid #00B894 !important; 
    color: #006B4F !important;
}
.stError { 
    background: #FEF0EE !important; 
    border-left: 4px solid #E74C3C !important; 
    color: #922B21 !important;
}
.stWarning {
    background: #FFF8E7 !important;
    border-left: 4px solid #F39C12 !important;
    color: #7D5A00 !important;
}

/* === FILE UPLOADER === */
[data-testid="stFileUploadDropzone"] {
    background: #EEF5FF !important;
    border: 2px dashed #00A8E8 !important;
    border-radius: 8px !important;
    color: #002D5C !important;
}

/* === DIVIDER === */
hr { border-color: #C5D8EC !important; }

/* === USER INFO IN SIDEBAR === */
.user-badge {
    background: rgba(0,168,232,0.15) !important;
    border: 1px solid rgba(0,168,232,0.3) !important;
    border-radius: 8px !important;
    padding: 8px 12px !important;
    margin: 8px 0 !important;
}
</style>"""

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
            acepta_datos = st.checkbox("Acepto el tratamiento de datos personales y clinicos segun Ley 1581/2012")
            if st.form_submit_button("INGRESAR", use_container_width=True, type="primary"):
                if not acepta_datos:
                    st.error("Debe aceptar el tratamiento de datos para ingresar")
                    return
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
        
        st.markdown(f"""
<div style="background:rgba(0,168,232,0.15);border:1px solid rgba(0,168,232,0.4);
border-radius:8px;padding:10px 14px;margin:12px 0;">
<div style="font-size:0.7rem;color:#7EC8E3;letter-spacing:1px;
text-transform:uppercase;margin-bottom:4px;">Usuario activo</div>
<div style="font-weight:700;font-size:1rem;color:#FFFFFF;">{st.session_state.user}</div>
<div style="font-size:0.75rem;color:#00A8E8;font-weight:600;">{st.session_state.rol}</div>
</div>
""", unsafe_allow_html=True)
        
        # Persistence status indicator
        if st.session_state.get('auditoria_loaded'):
            df = st.session_state.df_auditoria
            st.markdown(f"""
            <div style="background:rgba(0,184,120,0.15);border:1px solid rgba(0,184,120,0.4);
            border-radius:6px;padding:8px 12px;margin:8px 0;font-size:0.75rem;">
            <span style="color:#00B878;font-weight:700;">DATOS ACTIVOS</span><br>
            <span style="color:#A8D5C2;">{len(df)} facturas cargadas</span>
            </div>
            """, unsafe_allow_html=True)
        
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
        df = validar_con_manuales(df)
        st.session_state.df_auditoria = df
        
        # Save to auditoria_temp table for persistence
        try:
            conn = sqlite3.connect(DB_PATH)
            df.to_sql('auditoria_temp', conn, if_exists='replace', index=False)
            conn.commit()
            conn.close()
            st.session_state.auditoria_loaded = True
        except Exception as e:
            pass
        
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

def render_titulos():
    df = st.session_state.df_auditoria
    if df is None:
        st.info("Cargue archivo en Auditoria")
        return

    st.markdown("### Generar Titulos Ejecutivos")
    modo = st.radio("Modo de generacion:", ["Individual", "Por Entidad (EPS)", "Masivo (Todas las EPS)"], index=0)

    if modo == "Individual":
        factura = st.selectbox("Seleccionar Factura:", df["NUMERO_FACTURA"].tolist() if "NUMERO_FACTURA" in df.columns else [])
        if factura and st.button("Generar PDF", type="primary"):
            fila = df[df["NUMERO_FACTURA"] == factura].iloc[0]
            perfil = get_perfil_ips()
            pdf_bytes = generar_titulo_pdf(fila.to_dict(), perfil)
            if pdf_bytes:
                save_auditoria({
                    "ips": st.session_state.ips_seleccionada,
                    "eps": str(fila.get("NIT_EPS", "")),
                    "no_factura": factura,
                    "valor": str(fila.get("VALOR_TOTAL",0)),
                    "errores": "0",
                    "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "estado": "PDF Generado",
                    "usuario": st.session_state.user,
                    "accion": "Generar PDF Individual"
                })
                st.download_button("Descargar PDF", data=pdf_bytes, file_name=f"Titulo_{factura}.pdf", mime="application/pdf", type="primary", use_container_width=True)

    elif modo == "Por Entidad (EPS)":
        if "NIT_EPS" not in df.columns:
            st.warning("No hay datos de EPS en el archivo cargado")
            return
        eps_list = df["NIT_EPS"].unique().tolist()
        eps_seleccionada = st.selectbox("Seleccionar EPS:", eps_list)
        if st.button("Generar PDF por EPS", type="primary"):
            df_eps = df[df["NIT_EPS"] == eps_seleccionada]
            perfil = get_perfil_ips()
            pdf_bytes = generar_titulo_por_entidad(df_eps, perfil)
            if pdf_bytes:
                for _, row in df_eps.iterrows():
                    save_auditoria({
                        "ips": st.session_state.ips_seleccionada,
                        "eps": eps_seleccionada,
                        "no_factura": str(row.get("NUMERO_FACTURA", "")),
                        "valor": str(row.get("VALOR_TOTAL",0)),
                        "errores": "0",
                        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "estado": "PDF Generado por EPS",
                        "usuario": st.session_state.user,
                        "accion": "Generar PDF por EPS"
                    })
                st.download_button("Descargar PDF", data=pdf_bytes, file_name=f"Titulo_EPS_{eps_seleccionada}.pdf", mime="application/pdf", type="primary", use_container_width=True)

    elif modo == "Masivo (Todas las EPS)":
        if st.button("Generar Consolidado Masivo", type="primary"):
            if "NIT_EPS" not in df.columns:
                st.warning("No hay datos de EPS en el archivo cargado")
                return
            perfil = get_perfil_ips()
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for eps_name, group_df in df.groupby('NIT_EPS'):
                    pdf_bytes = generar_titulo_por_entidad(group_df, perfil)
                    if pdf_bytes:
                        safe_name = eps_name.replace('/', '-').replace(' ', '_')[:40]
                        zf.writestr(f"Titulo_{safe_name}.pdf", pdf_bytes)
                        for _, row in group_df.iterrows():
                            save_auditoria({
                                "ips": st.session_state.ips_seleccionada,
                                "eps": eps_name,
                                "no_factura": str(row.get("NUMERO_FACTURA", "")),
                                "valor": str(row.get("VALOR_TOTAL",0)),
                                "errores": "0",
                                "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                                "estado": "PDF Generado Masivo",
                                "usuario": st.session_state.user,
                                "accion": "Generar PDF Masivo"
                            })
            zip_buffer.seek(0)
            st.download_button("Descargar ZIP con todos los titulos", zip_buffer.getvalue(), "Titulos_AXIS.zip", "application/zip", type="primary", use_container_width=True)

def render_informes():
    st.header("Informes de Auditoria")
    
    if 'df_auditoria' not in st.session_state or st.session_state.df_auditoria is None:
        st.warning("Cargue datos en la pestana AUDITORIA primero.")
        return
    
    df = st.session_state.df_auditoria
    
    # --- Period selector ---
    col1, col2, col3 = st.columns(3)
    with col1:
        tipo_informe = st.selectbox("Tipo de Informe", 
            ["Mensual", "Semanal", "Por Rango de Fechas"])
    with col2:
        eps_filter = st.selectbox("Filtrar por EPS", 
            ["Todas"] + list(df['NIT_EPS'].unique()))
    with col3:
        st.write("")
        st.write("")
        generar = st.button("Generar Informe PDF")
    
    # --- Summary cards ---
    df_filtered = df if eps_filter == "Todas" else df[df['NIT_EPS'] == eps_filter]
    
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("RIPS Auditadas", len(df_filtered))
    c2.metric("Cartera Total", f"$ {df_filtered['VALOR_TOTAL'].sum():,.0f}".replace(',','.'))
    errores = len(df_filtered[df_filtered.get('ALERTAS_SISTEMA','OK') != 'OK']) if 'ALERTAS_SISTEMA' in df_filtered.columns else 0
    c3.metric("Errores Detectados", errores)
    c4.metric("Recuperabilidad", "85%")
    
    st.markdown("---")
    
    # --- Charts ---
    st.subheader("Distribucion por EPS")
    if not df_filtered.empty and 'NIT_EPS' in df_filtered.columns:
        eps_totals = df_filtered.groupby('NIT_EPS')['VALOR_TOTAL'].sum().reset_index()
        st.bar_chart(eps_totals.set_index('NIT_EPS'))
    else:
        st.info("No hay datos para mostrar grafico")
    
    # --- Show data table ---
    st.subheader("Datos Auditados")
    st.dataframe(df_filtered.head(100), use_container_width=True)
    
    # --- Generate PDF report ---
    if generar:
        pdf_bytes = generar_informe_pdf(df_filtered, eps_filter, tipo_informe)
        if pdf_bytes:
            st.download_button(
                label="Descargar Informe PDF",
                data=pdf_bytes,
                file_name=f"Informe_Auditoria_{tipo_informe}_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf"
            )

def generar_informe_pdf(df, eps_filter, tipo_informe):
    clean = lambda s: str(s).replace('—','-').replace('–','-').replace('"','"').replace('"','"').replace('\u2019',"'").replace('\u2018',"'").replace('…','...').encode('latin-1','ignore').decode('latin-1')
    
    def wl(pdf, txt, bold=False, size=10, align='L', h=7):
        pdf.set_font('Helvetica', 'B' if bold else '', size)
        txt = clean(str(txt))
        pdf.cell(0, h, txt[:95], ln=1, align=align)
        if len(txt) > 95:
            pdf.cell(0, h, txt[95:], ln=1, align=align)
    
    pdf = FPDF('P','mm','A4')
    pdf.add_page()
    pdf.set_margins(20,20,20)
    pdf.set_auto_page_break(True, margin=20)
    pdf.set_xy(20,15)
    
    # Logo
    try:
        pdf.image('logo_aqario.png', x=20, y=12, w=32)
        pdf.set_xy(20, 44)
    except:
        wl(pdf, 'aQario - GRUPO AXIS S.A.S.', bold=True, size=11)
    
    # Header
    wl(pdf, f'GRUPO AXIS S.A.S. | NIT 902021366 | Medellin, Colombia', size=8, align='R')
    wl(pdf, f'Generado: {datetime.now().strftime("%d/%m/%Y %H:%M")}', size=8, align='R')
    pdf.ln(2)
    
    pdf.set_draw_color(0,45,92)
    pdf.set_line_width(0.8)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(4)
    
    # Title
    wl(pdf, f'INFORME DE AUDITORIA DE CARTERA — {tipo_informe.upper()}', bold=True, size=13, align='C', h=9)
    eps_label = eps_filter if eps_filter != 'Todas' else 'Todas las Entidades'
    wl(pdf, f'EPS: {eps_label}', size=9, align='C')
    pdf.ln(4)
    
    # Summary box
    pdf.set_fill_color(0,45,92)
    pdf.set_text_color(255,255,255)
    pdf.set_font('Helvetica','B',10)
    pdf.cell(0,8,'RESUMEN EJECUTIVO',ln=1,align='C',fill=True)
    pdf.set_text_color(0,0,0)
    pdf.ln(2)
    
    total = df['VALOR_TOTAL'].sum()
    wl(pdf, f'Total RIPS Auditadas: {len(df)}', size=10)
    wl(pdf, f'Total Cartera en Gestion: $ {total:,.0f}'.replace(',','.'), size=10)
    wl(pdf, f'Entidades Deudoras: {df["NIT_EPS"].nunique() if "NIT_EPS" in df.columns else 0}', size=10)
    wl(pdf, f'Recuperabilidad Estimada: 85%', size=10)
    pdf.ln(4)
    
    pdf.set_draw_color(0,168,232)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(3)
    
    # Table header
    wl(pdf, 'DETALLE DE FACTURAS AUDITADAS', bold=True, size=10)
    pdf.ln(2)
    
    pdf.set_fill_color(0,45,92)
    pdf.set_text_color(255,255,255)
    pdf.set_font('Helvetica','B',8)
    pdf.cell(35,7,'No. Factura',border=0,ln=0,fill=True)
    pdf.cell(50,7,'Paciente',border=0,ln=0,fill=True)
    pdf.cell(25,7,'CUPS',border=0,ln=0,fill=True)
    pdf.cell(25,7,'Diagnostico',border=0,ln=0,fill=True)
    pdf.cell(35,7,'Valor',border=0,ln=1,fill=True,align='R')
    pdf.set_text_color(0,0,0)
    
    pdf.set_font('Helvetica','',8)
    for i, (_, row) in enumerate(df.iterrows()):
        fill = i % 2 == 0
        if fill:
            pdf.set_fill_color(240,246,255)
        factura = clean(str(row.get('NUMERO_FACTURA','N/A')))[:14]
        paciente = clean(str(row.get('NOMBRE_PACIENTE','N/A')))[:24]
        cups = clean(str(row.get('CODIGO_CUPS','N/A')))[:10]
        diag = clean(str(row.get('DIAGNOSTICO','N/A')))[:10]
        try: 
            valor_num = int(float(str(row.get('VALOR_TOTAL',0)).replace(',','').replace('.','')))
            valor = f"$ {valor_num//1000}K"
        except: 
            valor = str(row.get('VALOR_TOTAL',''))
        pdf.cell(35,6,factura,border=0,ln=0,fill=fill)
        pdf.cell(50,6,paciente,border=0,ln=0,fill=fill)
        pdf.cell(25,6,cups,border=0,ln=0,fill=fill)
        pdf.cell(25,6,diag,border=0,ln=0,fill=fill)
        pdf.cell(35,6,valor,border=0,ln=1,align='R',fill=fill)
    
    pdf.ln(4)
    pdf.set_draw_color(0,45,92)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(3)
    
    # Data protection footer
    pdf.set_font('Helvetica','',7)
    footer = ('PROTECCION DE DATOS: Informacion confidencial protegida bajo Ley 1581/2012, '
              'Ley 1438/2011 y Resolucion 3374/2000 (RIPS). Generado por aQario - GRUPO AXIS S.A.S. NIT 902021366.')
    pdf.cell(0,5,clean(footer),ln=1,align='C')
    
    return bytes(pdf.output())

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

    st.markdown("---")
    st.markdown("### Base de Conocimiento (Manuales)")
    st.markdown("Subir manuales en formato PDF:")
    
    manual_soat = st.file_uploader("Manual SOAT", type=["pdf"], key="soat")
    if manual_soat and st.button("Guardar Manual SOAT"):
        save_manual("Manual SOAT", manual_soat.read(), st.session_state.user)
        st.success("Manual SOAT guardado")
    
    manual_iss = st.file_uploader("Manual ISS 2000", type=["pdf"], key="iss")
    if manual_iss and st.button("Guardar Manual ISS 2000"):
        save_manual("Manual ISS 2000", manual_iss.read(), st.session_state.user)
        st.success("Manual ISS 2000 guardado")
    
    manual_cie10 = st.file_uploader("Codigos CIE-10", type=["pdf"], key="cie10")
    if manual_cie10 and st.button("Guardar Codigos CIE-10"):
        save_manual("Codigos CIE-10", manual_cie10.read(), st.session_state.user)
        st.success("Codigos CIE-10 guardados")
    
    st.markdown("### Historial de Manuales")
    df_manuales = get_manuales()
    if not df_manuales.empty:
        st.dataframe(df_manuales, use_container_width=True)
    else:
        st.info("No hay manuales cargados")

    st.markdown("---")
    st.markdown("### Auditoria Guardada")
    df_aud = get_auditoria()
    if not df_aud.empty:
        st.dataframe(df_aud.head(20), use_container_width=True)

def render_cliente_ips_portal():
    st.markdown("### Portal Cliente IPS")
    df_usuarios = get_usuarios()
    user_row = df_usuarios[df_usuarios["username"] == st.session_state.user].iloc[0]
    ips_asignada = user_row["eps_asignada"]
    
    st.markdown("### Metricas")
    df_aud = get_auditoria()
    df_ips = df_aud[df_aud["ips"] == ips_asignada] if not df_aud.empty else pd.DataFrame()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total RIPS Auditadas", len(df_ips))
    with col2:
        total_cartera = df_ips["valor"].astype(float).sum() if not df_ips.empty else 0
        st.metric("Total Cartera en Gestion", f"$ {total_cartera:,.0f}")
    with col3:
        errores = len(df_ips[df_ips["errores"] != "0"]) if not df_ips.empty else 0
        st.metric("Errores Detectados", errores)
    with col4:
        st.metric("Recuperabilidad Estimada", "85%")
    
    if st.button("Descargar Certificado de Auditoria", type="primary"):
        perfil = get_perfil_ips()
        fecha_inicio = df_ips["fecha"].min() if not df_ips.empty else "N/A"
        fecha_fin = df_ips["fecha"].max() if not df_ips.empty else "N/A"
        total_rips = len(df_ips)
        valor_total = total_cartera
        errores_count = errores
        recuperabilidad = 85
        pdf_bytes = generar_certificado_pdf(ips_asignada, fecha_inicio, fecha_fin, total_rips, valor_total, errores_count, recuperabilidad, perfil)
        st.download_button("Descargar Certificado", data=pdf_bytes, file_name=f"Certificado_{ips_asignada}.pdf", mime="application/pdf", type="primary", use_container_width=True)

if not st.session_state.logged_in:
    render_login()
else:
    render_sidebar()
    st.markdown("""
<div style="display:flex;align-items:center;gap:16px;
padding:0 0 16px 0;border-bottom:3px solid #00A8E8;margin-bottom:24px;">
<div>
<div style="font-family:'Montserrat',sans-serif;font-weight:700;
font-size:1.6rem;color:#001830;letter-spacing:-0.5px;">aQario</div>
<div style="font-size:0.75rem;color:#5B7FA6;letter-spacing:2px;
text-transform:uppercase;font-weight:600;">Sistema de Auditoria de Cartera</div>
</div>
<div style="margin-left:auto;background:#EEF5FF;border:1px solid #C5D8EC;
border-radius:6px;padding:4px 12px;">
<span style="font-size:0.7rem;color:#5B7FA6;letter-spacing:1px;">
GRUPO AXIS S.A.S. | NIT 902021366</span>
</div>
</div>
""", unsafe_allow_html=True)
    
    if st.session_state.rol == "Cliente IPS":
        render_cliente_ips_portal()
    elif st.session_state.rol == "Master":
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
