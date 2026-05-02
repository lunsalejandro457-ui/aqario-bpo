import io
import streamlit as st
import pandas as pd
import numpy as np
import re
import os
import csv
import hashlib
from datetime import datetime, timedelta
from fpdf import FPDF

st.set_page_config(
    page_title="aQario",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DIR_ACTUAL, "db_axis_recovery.csv")
USERS_PATH = os.path.join(DIR_ACTUAL, "db_users.csv")

PERFILES = {
    "Master": ["auditoria", "fabrica", "configuracion", "informes", "gestion_usuarios", "consolidado"],
    "Gestor": ["auditoria", "fabrica", "informes"],
    "Cliente IPS": ["dashboard_ips"],
}

USUARIOS_DEFAULT = {
    "admin": {"password": hashlib.sha256("axis2026".encode()).hexdigest(), "rol": "Master", "nombre": "Admin AXIS", "eps_asignada": None},
    "ips_sura": {"password": hashlib.sha256("sura2026".encode()).hexdigest(), "rol": "Cliente IPS", "nombre": "IPS SURA", "eps_asignada": "SURA"},
    "gestor1": {"password": hashlib.sha256("gestor2026".encode()).hexdigest(), "rol": "Gestor", "nombre": "Gestor BPO", "eps_asignada": None},
}

COLUMNAS_CRITICAS = [
    "NUMERO_FACTURA",
    "VALOR_TOTAL",
    "NIT_EPS",
    "FECHA_RADICADO",
    "CODIGO_CUPS",
    "DIAGNOSTICO",
]

PROCEDIMIENTOS_MASCULINOS = ["560301", "560302", "630501", "630502", "620501", "630701", "560201"]

NIT_VALORES = [800123456, 800234567, 800345678, 800456789, 900111222]
CUPS_VALORES = ["890308", "906206", "890310", "906212", "890510", "906306", "890102", "906404"]
DIAGNOSTICOS = ["J06.9", "J18.9", "K29.7", "I10", "E11.9", "M54.5", "J45.9", "K21.0"]
PACIENTES = [
    "Carlos Ramirez", "Maria Lopez", "Jorge Herrera", "Ana Martinez",
    "Luis Torres", "Patricia Gomez", "Fernando Diaz", "Sandra Ruiz",
    "Andres Morales", "Claudia Vargas", "Ricardo Silva", "Diana Castro",
]
MEDICOS = [
    "Dr. Alejandro Reyes", "Dra. Valentina Ortiz", "Dr. Miguel Angel Paredes",
    "Dra. Camila Duarte", "Dr. Felipe Navarro",
]
CIUDADES = ["Ibague", "Bogota", "Medellin", "Cali", "Barranquilla", "Bucaramanga"]


def latin(text):
    return str(text).encode("latin-1", "ignore").decode("latin-1")


def cargar_usuarios():
    if os.path.exists(USERS_PATH):
        df = pd.read_csv(USERS_PATH)
        usuarios = {}
        for _, row in df.iterrows():
            usuarios[row["username"]] = {
                "password": row["password_hash"],
                "rol": row["rol"],
                "nombre": row["nombre"],
                "eps_asignada": row.get("eps_asignada", None),
            }
        return usuarios
    usuarios = USUARIOS_DEFAULT.copy()
    guardar_usuarios(usuarios)
    return usuarios


def guardar_usuarios(usuarios):
    rows = []
    for u, data in usuarios.items():
        rows.append({
            "username": u,
            "password_hash": data["password"],
            "rol": data["rol"],
            "nombre": data["nombre"],
            "eps_asignada": data.get("eps_asignada", None),
        })
    pd.DataFrame(rows).to_csv(USERS_PATH, index=False)


def crear_usuario(username, password, rol, nombre, eps_asignada=None):
    usuarios = cargar_usuarios()
    if username in usuarios:
        return False, "El usuario ya existe"
    usuarios[username] = {
        "password": hashlib.sha256(password.encode()).hexdigest(),
        "rol": rol,
        "nombre": nombre,
        "eps_asignada": eps_asignada,
    }
    guardar_usuarios(usuarios)
    return True, "Usuario creado correctamente"


def eliminar_usuario(username):
    usuarios = cargar_usuarios()
    if username in usuarios and username != "admin":
        del usuarios[username]
        guardar_usuarios(usuarios)
        return True, "Usuario eliminado"
    return False, "No se puede eliminar este usuario"


def cargar_db_recovery():
    if os.path.exists(DB_PATH):
        return pd.read_csv(DB_PATH)
    return pd.DataFrame(columns=["fecha", "usuario", "accion", "factura", "eps", "valor", "estado"])


def guardar_db_recovery(registro):
    df = cargar_db_recovery()
    new_row = pd.DataFrame([registro])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(DB_PATH, index=False)


def normalizar_columnas(cols):
    return [
        re.sub(r"\s+", "_", col.strip().upper().replace("-", "_").replace(" ", "_"))
        for col in cols
    ]


def validar_estructura(df):
    df_validado = df.copy()
    df_validado.columns = normalizar_columnas(df_validado.columns)

    columnas_archivo = set(df_validado.columns)
    columnas_esperadas = set(COLUMNAS_CRITICAS)

    encontradas = columnas_esperadas & columnas_archivo
    faltantes = columnas_esperadas - columnas_archivo

    return df_validado, sorted(encontradas), sorted(faltantes)


def validar_cruce_clinico(df):
    alertas = []

    if "SEXO" in df.columns and "CODIGO_CUPS" in df.columns:
        for idx, fila in df.iterrows():
            sexo = str(fila["SEXO"]).strip().upper()
            cups = str(fila["CODIGO_CUPS"]).strip()

            if sexo == "F" and cups in PROCEDIMIENTOS_MASCULINOS:
                alertas.append({
                    "fila": idx + 2,
                    "cups": cups,
                    "sexo": sexo,
                    "tipo": "Procedimiento Exclusivo Masculino en Paciente Femenino",
                })

    return alertas


def generar_fecha(base, max_dias=180):
    delta = np.random.randint(0, max_dias)
    return (base - timedelta(days=delta)).strftime("%Y-%m-%d")


def generar_datos_perfectos(n=20):
    np.random.seed(42)
    data = {
        "Numero_Factura": [f"FAC-{i+1001}" for i in range(n)],
        "Valor_Total": np.round(np.random.uniform(150000, 12500000, n), 0).astype(int),
        "NIT_EPS": np.random.choice(NIT_VALORES, n),
        "Fecha_Radicado": [generar_fecha(datetime(2026, 4, 15)) for _ in range(n)],
        "Codigo_CUPS": np.random.choice(CUPS_VALORES, n),
        "Diagnostico": np.random.choice(DIAGNOSTICOS, n),
        "Nombre_Paciente": np.random.choice(PACIENTES, n),
        "Medico_Tratante": np.random.choice(MEDICOS, n),
        "SEXO": np.random.choice(["M", "F"], n),
        "Ciudad": np.random.choice(CIUDADES, n),
        "Fecha_Atencion": [generar_fecha(datetime(2026, 3, 1)) for _ in range(n)],
    }
    return pd.DataFrame(data)


def generar_datos_con_errores(n=20):
    np.random.seed(43)
    data = {
        "numero_factura": [f"FAC-{i+2001}" for i in range(n)],
        "VALOR_TOTAL": np.round(np.random.uniform(200000, 9800000, n), 0).astype(int),
        "nit_eps": np.random.choice(NIT_VALORES, n),
        "codigo_cups": np.random.choice(CUPS_VALORES, n),
        "diagnostico": np.random.choice(DIAGNOSTICOS, n),
        "Nombre_Paciente": np.random.choice(PACIENTES, n),
        "Medico_Tratante": np.random.choice(MEDICOS, n),
    }
    return pd.DataFrame(data)


def generar_archivos_prueba():
    ruta_perfectos = os.path.join(DIR_ACTUAL, "datos_perfectos.xlsx")
    ruta_errores = os.path.join(DIR_ACTUAL, "datos_con_errores.xlsx")

    df_perfectos = generar_datos_perfectos()
    df_perfectos.to_excel(ruta_perfectos, index=False)

    df_errores = generar_datos_con_errores()
    df_errores.to_excel(ruta_errores, index=False)


class TituloPDF(FPDF):
    def __init__(self, *args, **kwargs):
        self.logo_path = kwargs.pop("logo_path", None)
        super().__init__(*args, **kwargs)

    def header(self):
        if self.logo_path:
            try:
                if os.path.exists(self.logo_path):
                    self.image(self.logo_path, x=25, y=15, w=35)
            except Exception:
                pass
        self.set_xy(25, 52)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(28, 61, 115)
        self.cell(0, 5, latin("aQario: Software de Gestion de Cartera de Grupo AXIS S.A.S. - NIT 902021366"), ln=1, align="L")
        self.ln(10)

    def footer(self):
        self.set_y(-35)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(0, 0, 0)
        self.cell(0, 6, latin("Documento generado por: " + self.usuario_impresion), ln=1, align="C")
        self.cell(0, 6, latin("aQario es un software creado por grupo axis sas 902021366"), ln=1, align="C")


def generar_titulo_pdf(datos_factura, eps, ips, usuario):
    try:
        logo_path = os.path.join(DIR_ACTUAL, "logo_aqario.png")
        if not os.path.exists(logo_path):
            logo_path = None

        pdf = TituloPDF(format="Letter", logo_path=logo_path)
        pdf.usuario_impresion = latin(usuario)
        pdf.set_auto_page_break(auto=True, margin=45)
        pdf.add_page()
        pdf.set_margins(left=25, top=65, right=25)

        asunto = latin(f"Cobro Prejuridico - Factura {datos_factura.get('NUMERO_FACTURA', 'N/A')}")
        ips_nombre = latin(str(ips))
        nit_eps = latin(str(eps))
        valor_total = datos_factura.get("VALOR_TOTAL", 0)
        valor = latin(f"$ {int(valor_total):,.0f} COP") if isinstance(valor_total, (int, float)) else latin(str(valor_total))
        num_factura = latin(str(datos_factura.get("NUMERO_FACTURA", "N/A")))
        fecha_radicado = latin(str(datos_factura.get("FECHA_RADICADO", "N/A")))
        cups = latin(str(datos_factura.get("CODIGO_CUPS", "N/A")))
        diagnostico = latin(str(datos_factura.get("DIAGNOSTICO", "N/A")))
        ahora = latin(datetime.now().strftime("%d/%m/%Y - %H:%M:%S"))

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 6, f"Fecha de impresion: {ahora}", ln=1, align="R")

        pdf.ln(8)

        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(10, 26, 63)
        if asunto.strip():
            pdf.cell(0, 7, asunto, ln=1, align="L")

        pdf.ln(6)

        pdf.set_draw_color(92, 160, 242)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(6)

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)

        cuerpo = latin(f"Senores:\n{ips_nombre}\n\nReferencia: Notificacion de cobro prejudicial por concepto de servicios de salud prestados.")
        pdf.multi_cell(0, 6, cuerpo)

        pdf.ln(6)

        parrafo_legal = latin(
            f"La entidad beneficiaria {ips_nombre}, actuando bajo el respectivo Contrato de Mandato con "
            f"GRUPO AXIS S.A.S., mediante el presente documento EXIGE formalmente el pago de las obligaciones "
            f"economicas derivadas de la prestacion de servicios de salud que se detallan a continuacion. "
            f"El incumplimiento en el pago dentro de los terminos legales facultara al acreedor para iniciar "
            f"las acciones judiciales correspondientes con el fin de obtener el pago mediante proceso ejecutivo."
        )
        pdf.multi_cell(0, 6, parrafo_legal)

        pdf.ln(8)

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(10, 26, 63)
        pdf.cell(0, 7, latin("Detalle del Titulo Ejecutivo"), ln=1)
        pdf.ln(2)

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)

        detalles = [
            (latin("Numero de Factura:"), num_factura),
            (latin("Fecha de Radicado:"), fecha_radicado),
            (latin("Codigo CUPS:"), cups),
            (latin("Diagnostico Principal:"), diagnostico),
            (latin("NIT de la EPS Deudora:"), nit_eps),
            (latin("Valor Total a Cobrar:"), valor),
        ]

        for etiqueta, valor_item in detalles:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 7, etiqueta, ln=1)
            pdf.set_x(pdf.l_margin + 5)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 7, valor_item, ln=1)
            pdf.ln(1)

        pdf.ln(10)

        cierre = latin(
            "Quedan ustedes formalmente notificados. Agradecemos su pronta gestion de pago para evitar "
            "el inicio de acciones legales.\n\n"
            "Cordialmente,\n"
            "Departamento de Recaudo y Cartera\n"
            "GRUPO AXIS S.A.S."
        )
        pdf.multi_cell(0, 6, cierre)

        return pdf.output(dest="S").encode("latin-1")

    except Exception as e:
        st.error(f"Error al generar el PDF: {str(e)}")
        return None


def generar_consolidado_pdf(facturas_df, eps, ips, usuario):
    try:
        logo_path = os.path.join(DIR_ACTUAL, "logo_aqario.png")
        if not os.path.exists(logo_path):
            logo_path = None

        pdf = TituloPDF(format="Letter", logo_path=logo_path)
        pdf.usuario_impresion = latin(usuario)
        pdf.set_auto_page_break(auto=True, margin=45)
        pdf.add_page()
        pdf.set_margins(left=25, top=65, right=25)

        ahora = latin(datetime.now().strftime("%d/%m/%Y - %H:%M:%S"))
        total_facturas = len(facturas_df)
        valor_total = latin(f"$ {int(facturas_df['VALOR_TOTAL'].sum()):,.0f} COP")
        nit_eps = latin(str(eps))
        ips_nombre = latin(str(ips))

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 6, f"Fecha de impresion: {ahora}", ln=1, align="R")

        pdf.ln(8)

        titulo = latin(f"TITULO VALOR - COBRO PREJURIDICO MASIVO ({total_facturas} FACTURAS)")
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(10, 26, 63)
        pdf.cell(0, 8, titulo, ln=1, align="C")

        pdf.ln(4)

        subtitulo = latin(f"EPS Deudora: NIT {nit_eps} | IPS: {ips_nombre}")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 6, subtitulo, ln=1, align="C")

        pdf.ln(6)

        pdf.set_draw_color(92, 160, 242)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(8)

        parrafo = latin(
            f"Por medio del presente documento, GRUPO AXIS S.A.S., en su calidad de mandatario de la IPS {ips_nombre}, "
            f"certifica que los servicios de salud descritos a continuación fueron efectivamente prestados y no han sido "
            f"pagados por la entidad deudora. Este documento constituye un Titulo Valor de conformidad con el Codigo de "
            f"Comercio colombiano y se adjuntan como soporte las Historias Clinicas y RIPS correspondientes."
        )
        pdf.multi_cell(0, 6, parrafo)

        pdf.ln(8)

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(10, 26, 63)
        pdf.cell(0, 7, latin("Detalle de Facturas Incluidas"), ln=1)
        pdf.ln(2)

        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(10, 26, 63)
        cols_tamano = [30, 35, 30, 30, 25, 30]
        headers = [latin("No. Factura"), latin("Paciente"), latin("Ciudad"), latin("Fecha Atencion"), latin("CUPS/SOAT"), latin("Valor")]
        x = pdf.l_margin
        for i, (header, tam) in enumerate(zip(headers, cols_tamano)):
            pdf.set_xy(x, pdf.get_y())
            pdf.cell(tam, 7, header, border=1, fill=True, align="C")
            x += tam
        pdf.ln()

        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(0, 0, 0)

        for _, fila in facturas_df.iterrows():
            campos = [
                latin(str(fila.get("NUMERO_FACTURA", "N/A"))),
                latin(str(fila.get("NOMBRE_PACIENTE", "N/A"))),
                latin(str(fila.get("CIUDAD", "N/A"))),
                latin(str(fila.get("FECHA_ATENCION", "N/A"))),
                latin(str(fila.get("CODIGO_CUPS", "N/A"))),
                latin(f"$ {int(fila['VALOR_TOTAL']):,.0f}"),
            ]
            x = pdf.l_margin
            for val, tam in zip(campos, cols_tamano):
                pdf.set_xy(x, pdf.get_y())
                pdf.cell(tam, 6, val, border=1, align="C")
                x += tam
            pdf.ln()

        pdf.ln(6)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(10, 26, 63)
        pdf.cell(0, 8, latin(f"VALOR TOTAL A COBRAR: {valor_total}"), ln=1)

        pdf.ln(10)

        cierre = latin(
            "Se adjuntan como soporte las Historias Clinicas, RIPS y demas documentos que acreditan la prestacion "
            "de los servicios de salud. Este documento tiene plena validez juridica como titulo valor.\n\n"
            "Departamento de Recaudo y Cartera\n"
            "GRUPO AXIS S.A.S."
        )
        pdf.multi_cell(0, 6, cierre)

        return pdf.output(dest="S").encode("latin-1")

    except Exception as e:
        st.error(f"Error al generar el consolidado PDF: {str(e)}")
        return None


def generar_informe_hallazgos(df_alertas, ips_nombre, periodo, usuario):
    try:
        logo_path = os.path.join(DIR_ACTUAL, "logo_aqario.png")
        if not os.path.exists(logo_path):
            logo_path = None

        pdf = TituloPDF(format="Letter", logo_path=logo_path)
        pdf.usuario_impresion = latin(usuario)
        pdf.set_auto_page_break(auto=True, margin=45)
        pdf.add_page()
        pdf.set_margins(left=25, top=65, right=25)

        ahora = latin(datetime.now().strftime("%d/%m/%Y - %H:%M:%S"))
        total_errores = len(df_alertas)

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 6, f"Fecha de impresion: {ahora}", ln=1, align="R")

        pdf.ln(8)

        titulo = latin(f"INFORME DE HALLAZGOS - DIAGNOSTICO {periodo.upper()}")
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(10, 26, 63)
        pdf.cell(0, 8, titulo, ln=1, align="C")

        pdf.ln(4)

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 6, latin(f"Dirigido a: IPS {ips_nombre}"), ln=1)

        pdf.ln(6)

        pdf.set_draw_color(92, 160, 242)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(8)

        parrafo = latin(
            f"Senores {ips_nombre}:\n\n"
            f"Hemos detectado {total_errores} errores de digitacion este periodo ({periodo}). "
            f"Observaciones: Mejorar la codificacion SOAT en el servicio de urgencias. Se identificaron "
            f"inconsistencias entre el sexo del paciente y los procedimientos registrados, lo cual genera "
            f"riesgo de glosa por parte de la EPS. Se recomienda capacitar al personal de digitacion en "
            f"codificacion CUPS y validacion de datos clinicos antes de la radicacion de facturas."
        )
        pdf.multi_cell(0, 6, parrafo)

        pdf.ln(8)

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(10, 26, 63)
        pdf.cell(0, 7, latin("Detalle de Errores Detectados"), ln=1)
        pdf.ln(4)

        if total_errores > 0:
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(255, 255, 255)
            pdf.set_fill_color(10, 26, 63)
            cols_tamano = [15, 25, 35, 55]
            headers = [latin("Fila"), latin("CUPS"), latin("Sexo"), latin("Tipo de Error")]
            x = pdf.l_margin
            for header, tam in zip(headers, cols_tamano):
                pdf.set_xy(x, pdf.get_y())
                pdf.cell(tam, 7, header, border=1, fill=True, align="C")
                x += tam
            pdf.ln()

            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(0, 0, 0)

            for _, alerta in df_alertas.iterrows():
                campos = [
                    latin(str(alerta.get("fila", "N/A"))),
                    latin(str(alerta.get("cups", "N/A"))),
                    latin(str(alerta.get("sexo", "N/A"))),
                    latin(str(alerta.get("tipo", "N/A"))),
                ]
                x = pdf.l_margin
                for val, tam in zip(campos, cols_tamano):
                    pdf.set_xy(x, pdf.get_y())
                    pdf.cell(tam, 6, val, border=1, align="C")
                    x += tam
                pdf.ln()

        pdf.ln(8)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        cierre = latin(
            "Este informe fue generado automaticamente por el sistema aQario. "
            "Para aclaraciones, contactar al equipo de Grupo AXIS S.A.S."
        )
        pdf.multi_cell(0, 6, cierre)

        return pdf.output(dest="S").encode("latin-1")

    except Exception as e:
        st.error(f"Error al generar el informe: {str(e)}")
        return None


CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    * {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background-color: #FFFFFF !important;
    }

    .main-header {
        color: #0A1A3F;
        font-size: 2.5rem;
        font-weight: 700;
        letter-spacing: -0.5px;
        margin-bottom: 0.25rem;
    }

    .main-subheader {
        color: #5CA0F2;
        font-size: 1rem;
        font-weight: 500;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-bottom: 1.5rem;
    }

    .description-text {
        color: #1C3D73;
        font-size: 0.95rem;
        line-height: 1.7;
        max-width: 720px;
    }

    .section-title {
        color: #0A1A3F;
        font-size: 1.25rem;
        font-weight: 600;
        margin-top: 2rem;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #5CA0F2;
    }

    .upload-container {
        background-color: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        padding: 2rem;
        box-shadow: 0 1px 3px rgba(10, 26, 63, 0.08);
    }

    .stFileUploader > div {
        border: 2px dashed #5CA0F2;
        border-radius: 8px;
        background-color: #FFFFFF;
    }

    div[data-testid="stFileUploader"] button {
        background-color: #0A1A3F;
        color: #FFFFFF;
        border: none;
        border-radius: 6px;
        font-weight: 500;
    }

    div[data-testid="stFileUploader"] button:hover {
        background-color: #1C3D73;
    }

    .footer {
        margin-top: 3rem;
        padding-top: 1.5rem;
        border-top: 1px solid #E5E7EB;
        color: #9CA3AF;
        font-size: 0.8rem;
        text-align: center;
    }

    hr.divider {
        border: none;
        height: 1px;
        background: linear-gradient(to right, transparent, #5CA0F2, transparent);
        margin: 2rem 0;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        background-color: #FFFFFF;
        border-radius: 8px;
        padding: 12px 24px;
        border: 1px solid #E5E7EB;
        color: #1C3D73;
        font-weight: 500;
    }

    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        background-color: #0A1A3F;
        color: #FFFFFF;
        border-color: #0A1A3F;
    }

    .action-button-container {
        background-color: #F9FAFB;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 2px 8px rgba(10, 26, 63, 0.06);
    }

    div[data-testid="stExpander"] {
        background-color: transparent;
    }

    [data-testid="stExpander"] .streamlit-expanderHeader {
        background-color: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        color: #0A1A3F !important;
        font-weight: 600;
    }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

st.markdown('''
<style>
    [data-testid="stSidebar"] { background-color: #0A1A3F !important; }

    [data-testid="stSidebar"] *, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
        color: #FFFFFF !important;
        font-weight: 600 !important;
    }

    .stMain p, .stMain label, .stMain h1, .stMain h2, .stMain h3, .stMain span {
        color: #0A1A3F !important;
    }

    input { color: #000000 !important; }

    [data-testid="stSidebar"] img {
        margin-top: -20px;
        margin-bottom: 20px;
    }

    div[data-testid="stMarkdownContainer"] p, label, span {
        color: #0A1A3F !important;
        font-weight: bold !important;
    }

    .stError, .stWarning, .stInfo, .stSuccess {
        color: #0A1A3F !important;
    }

    div[data-testid="stAlert"] {
        color: #0A1A3F !important;
    }

    button[kind="primary"] {
        background-color: #1C3D73 !important;
        color: #FFFFFF !important;
        border-radius: 10px !important;
        font-size: 16px !important;
        font-weight: 600 !important;
        padding: 12px 24px !important;
        border: none !important;
    }

    button[kind="primary"]:hover {
        background-color: #0A1A3F !important;
        color: #FFFFFF !important;
        box-shadow: 0 4px 12px rgba(10, 26, 63, 0.3) !important;
    }
</style>
''', unsafe_allow_html=True)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None
if "rol" not in st.session_state:
    st.session_state.rol = None
if "df_auditoria" not in st.session_state:
    st.session_state.df_auditoria = None
if "uploaded_file_name" not in st.session_state:
    st.session_state.uploaded_file_name = None
if "historial" not in st.session_state:
    st.session_state.historial = []
if "usuarios" not in st.session_state:
    st.session_state.usuarios = cargar_usuarios()
if "alertas_detectadas" not in st.session_state:
    st.session_state.alertas_detectadas = []


def agregar_historial(nombre_archivo, tipo):
    entrada = {
        "archivo": nombre_archivo,
        "tipo": tipo,
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "usuario": st.session_state.user,
    }
    st.session_state.historial.insert(0, entrada)
    if len(st.session_state.historial) > 50:
        st.session_state.historial = st.session_state.historial[:50]


def render_login():
    col_c1, col_c2, col_c3 = st.columns([1, 1.2, 1])
    with col_c2:
        try:
            st.image("logo_aqario.png", width=160)
        except Exception:
            st.markdown(
                '<div style="text-align:center; font-size:2.5rem; font-weight:700; color:#0A1A3F; margin-bottom:1rem;">aQario</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            '<p style="text-align:center; color:#5CA0F2; font-size:0.75rem; font-weight:600; letter-spacing:2px; text-transform:uppercase; margin-top:-0.75rem; margin-bottom:2rem;">Sistema de Auditoria y Recuperacion de Cartera</p>',
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            username = st.text_input("Usuario", placeholder="Ingrese su usuario")
            password = st.text_input("Contraseña", type="password", placeholder="Ingrese su contraseña")
            submitted = st.form_submit_button("Ingresar", use_container_width=True, type="primary")

            if submitted:
                usuarios = cargar_usuarios()
                pwd_hash = hashlib.sha256(password.encode()).hexdigest()
                if username in usuarios and usuarios[username]["password"] == pwd_hash:
                    st.session_state.logged_in = True
                    st.session_state.user = username
                    st.session_state.rol = usuarios[username]["rol"]
                    st.session_state.usuarios = usuarios
                    st.rerun()
                else:
                    st.error("Usuario o contrasena incorrectos.")


def render_sidebar():
    with st.sidebar:
        st.markdown('<div style="text-align:center; padding: 1rem 0; border-bottom: 1px solid rgba(255,255,255,0.15); margin-bottom: 1rem;">', unsafe_allow_html=True)
        try:
            st.sidebar.image("logo_aqario.png", use_container_width=True)
        except Exception:
            pass

        st.markdown(f"**{st.session_state.get('user', '')}**")
        st.markdown(f"*{st.session_state.rol}*")
        if st.button("Cerrar Sesion", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.session_state.rol = None
            st.session_state.df_auditoria = None
            st.session_state.uploaded_file_name = None
            st.session_state.alertas_detectadas = []
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        if st.session_state.rol == "Master":
            with st.expander("Herramientas de Desarrollo", expanded=False):
                if st.button("Generar Archivos de Prueba", use_container_width=True):
                    generar_archivos_prueba()
                    st.sidebar.success("Archivos generados correctamente.")


def render_auditoria_tab():
    st.markdown('<p class="section-title" style="margin-top: 0.5rem;">Cargar Archivo de Facturacion o RIPS</p>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="upload-container">', unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            label="Seleccione un archivo",
            type=["xlsx", "csv"],
            key="auditoria_uploader",
            help="Formatos aceptados: .xlsx, .csv",
        )
        st.markdown('</div>', unsafe_allow_html=True)

    if uploaded_file is not None:
        st.session_state.uploaded_file_name = uploaded_file.name
        st.success(f"Archivo cargado: **{uploaded_file.name}**")

        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        st.session_state.df_auditoria = df

    df = st.session_state.df_auditoria

    if df is None:
        st.info("No hay datos cargados. Suba un archivo Excel o CSV para comenzar la auditoria.")
        return

    st.markdown('<p class="section-title">Auditoria de Estructura de Datos</p>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="upload-container">', unsafe_allow_html=True)

        col_check1, col_check2 = st.columns(2)

        df, encontradas, faltantes = validar_estructura(df)

        with col_check1:
            st.markdown("**Columnas Encontradas**")
            if encontradas:
                for col in encontradas:
                    st.success(col)
            else:
                st.info("Ninguna columna critica detectada")

        with col_check2:
            st.markdown("**Columnas Faltantes**")
            if faltantes:
                for col in faltantes:
                    st.error(col)
            else:
                st.success("Todas las columnas criticas presentes")

        st.markdown('</div>', unsafe_allow_html=True)

    if faltantes:
        st.warning(
            f"**Archivo no apto para generacion de titulos ejecutivos.** "
            f"Faltan {len(faltantes)} campo(s) critico(s) requeridos: "
            f"{', '.join(faltantes)}."
        )
    else:
        st.success(
            "**Estructura valida.** El archivo contiene todos los campos criticos para generar titulos ejecutivos seguros."
        )

    st.markdown('<p class="section-title">Motor de Validacion Avanzada - Cruce de Datos Clinicos</p>', unsafe_allow_html=True)

    alertas = validar_cruce_clinico(df)
    st.session_state.alertas_detectadas = alertas

    if alertas:
        st.error(
            "ERROR DE IPS DETECTADO: Incoherencia Sexo-Procedimiento. Riesgo de Glosa Alto."
        )
        df_alertas = pd.DataFrame(alertas)
        st.dataframe(df_alertas, use_container_width=True, hide_index=True)
        for a in alertas:
            st.warning(f"Fila {a['fila']}: {a['tipo']} | CUPS: {a['cups']} | Sexo: {a['sexo']}")
    else:
        if "SEXO" in df.columns:
            st.success("Cruce clinico completado. No se detectaron incoherencias Sexo-Procedimiento.")
        else:
            st.info("La columna 'SEXO' no esta presente en el archivo. El cruce clinico no aplica para este dataset.")

    st.markdown('<p class="section-title">Vista Previa de Datos</p>', unsafe_allow_html=True)
    st.dataframe(df.head(10), use_container_width=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Filas", len(df))
    with col2:
        st.metric("Columnas", len(df.columns))
    with col3:
        st.metric("Tamano del archivo", f"{uploaded_file.size / 1024:.1f} KB" if hasattr(uploaded_file, 'size') else "N/A")

    if not faltantes:
        df["VALOR_TOTAL"] = pd.to_numeric(df["VALOR_TOTAL"], errors="coerce").fillna(0).astype(int)

        st.divider()
        st.markdown('<h3 style="color: #1C3D73; font-size: 1.5rem; font-weight: 600; margin-bottom: 1.25rem;">Resumen Ejecutivo de Cartera</h3>', unsafe_allow_html=True)

        total_titulos = len(df)
        proyeccion_liquidez = df["VALOR_TOTAL"].sum()
        promedio_cuenta = df["VALOR_TOTAL"].mean()

        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("Total de Titulos", f"{total_titulos:,}")
        with col_m2:
            st.metric(
                "Proyeccion de Liquidez",
                f"$ {proyeccion_liquidez:,.0f}",
                delta="Activos en cartera",
            )
        with col_m3:
            st.metric("Promedio por Cuenta", f"$ {promedio_cuenta:,.0f}")

        st.markdown('<p class="section-title">Titulos Ejecutivos Consolidados</p>', unsafe_allow_html=True)

        df_consolidado = df[["NUMERO_FACTURA", "NIT_EPS", "VALOR_TOTAL"]].copy()
        df_consolidado["ESTADO_LEGAL"] = "Listo para Radicar"

        df_display = df_consolidado.copy()
        df_display["VALOR_TOTAL"] = df_display["VALOR_TOTAL"].apply(lambda x: f"$ {x:,.0f}")

        st.dataframe(df_display, use_container_width=True, hide_index=True)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_consolidado.to_excel(writer, index=False, sheet_name="Titulos_Ejecutivos")

        st.markdown('<div class="action-button-container">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.download_button(
                label="Descargar Consolidado para Radicacion",
                data=buffer.getvalue(),
                file_name="Titulos_Ejecutivos_Rescate.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)


def render_fabrica_pdf_tab():
    df = st.session_state.df_auditoria

    if df is None:
        st.info("Cargue un archivo valido en la pestana de Auditoria para generar titulos PDF.")
        return

    df, encontradas, faltantes = validar_estructura(df)

    if faltantes:
        st.warning("El archivo cargado no tiene todas las columnas criticas.")
        return

    df["VALOR_TOTAL"] = pd.to_numeric(df["VALOR_TOTAL"], errors="coerce").fillna(0).astype(int)

    st.markdown('<p class="section-title" style="margin-top: 0.5rem;">Generar Titulo Individual</p>', unsafe_allow_html=True)

    opciones_facturas = df["NUMERO_FACTURA"].tolist()
    factura_seleccionada = st.selectbox(
        "Seleccione una factura:",
        opciones_facturas,
        key="pdf_selector",
    )

    if factura_seleccionada:
        fila_factura = df[df["NUMERO_FACTURA"] == factura_seleccionada].iloc[0]
        col_sel1, col_sel2 = st.columns([2, 1])
        with col_sel1:
            st.caption(f"NIT EPS: {fila_factura['NIT_EPS']} | CUPS: {fila_factura['CODIGO_CUPS']} | Valor: $ {fila_factura['VALOR_TOTAL']:,.0f}")
        with col_sel2:
            pdf_bytes = generar_titulo_pdf(
                datos_factura=fila_factura.to_dict(),
                eps=str(fila_factura["NIT_EPS"]),
                ips="IPS Beneficiaria",
                usuario=st.session_state.user,
            )
            if pdf_bytes is not None:
                st.markdown('<div class="action-button-container">', unsafe_allow_html=True)
                st.download_button(
                    label="Generar Titulo Legal (PDF)",
                    data=pdf_bytes,
                    file_name=f"Titulo_Ejecutivo_{factura_seleccionada}.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )
                st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    st.markdown('<p class="section-title">Super PDF Consolidado - Titulo Valor Masivo</p>', unsafe_allow_html=True)
    st.info("Seleccione una EPS para agrupar todas sus facturas en un unico titulo valor.")

    eps_disponibles = df["NIT_EPS"].unique().tolist()
    eps_seleccionada = st.selectbox("EPS Deudora:", eps_disponibles, key="consolidado_eps")

    if eps_seleccionada:
        df_eps = df[df["NIT_EPS"] == eps_seleccionada].copy()
        st.markdown(f"**{len(df_eps)} facturas** | Total: **$ {df_eps['VALOR_TOTAL'].sum():,.0f}**")

        facturas_a_incluir = st.multiselect(
            "Seleccione las facturas a incluir:",
            options=df_eps["NUMERO_FACTURA"].tolist(),
            default=df_eps["NUMERO_FACTURA"].tolist(),
            key="multi_select_facturas",
        )

        if facturas_a_incluir:
            df_filtrado = df_eps[df_eps["NUMERO_FACTURA"].isin(facturas_a_incluir)]

            if st.button("Generar Consolidado PDF", type="primary", use_container_width=True):
                with st.spinner("Generando titulo valor masivo..."):
                    pdf_bytes = generar_consolidado_pdf(
                        facturas_df=df_filtrado,
                        eps=eps_seleccionada,
                        ips="IPS Beneficiaria",
                        usuario=st.session_state.user,
                    )
                    if pdf_bytes:
                        guardar_db_recovery({
                            "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "usuario": st.session_state.user,
                            "accion": "Consolidado PDF",
                            "factura": f"{len(df_filtrado)} facturas",
                            "eps": str(eps_seleccionada),
                            "valor": str(df_filtrado["VALOR_TOTAL"].sum()),
                            "estado": "Generado",
                        })
                        st.success("Consolidado generado exitosamente.")
                        st.download_button(
                            label="Descargar Consolidado PDF",
                            data=pdf_bytes,
                            file_name=f"Consolidado_EPS_{eps_seleccionada}.pdf",
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True,
                        )


def render_informes_tab():
    df = st.session_state.df_auditoria
    alertas = st.session_state.alertas_detectadas

    if df is None:
        st.info("Cargue un archivo primero para generar informes de hallazgos.")
        return

    st.markdown('<p class="section-title" style="margin-top: 0.5rem;">Informe de Hallazgos - Diagnostico para la IPS</p>', unsafe_allow_html=True)

    col_info1, col_info2 = st.columns(2)
    with col_info1:
        ips_nombre = st.text_input("Nombre de la IPS Mandataria", value="IPS Beneficiaria")
    with col_info2:
        periodo = st.selectbox("Periodo de Analisis", ["Mensual", "Semanal", "Trimestral"])

    if st.button("Generar Informe de Hallazgos", type="primary", use_container_width=True):
        if alertas:
            df_alertas = pd.DataFrame(alertas)
            pdf_bytes = generar_informe_hallazgos(
                df_alertas=df_alertas,
                ips_nombre=ips_nombre,
                periodo=periodo,
                usuario=st.session_state.user,
            )
            if pdf_bytes:
                guardar_db_recovery({
                    "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "usuario": st.session_state.user,
                    "accion": "Informe Hallazgos",
                    "factura": f"{len(alertas)} errores",
                    "eps": ips_nombre,
                    "valor": "N/A",
                    "estado": "Generado",
                })
                st.success(f"Informe generado: {len(alertas)} errores detectados en periodo {periodo.lower()}.")
                st.download_button(
                    label="Descargar Informe PDF",
                    data=pdf_bytes,
                    file_name=f"Informe_Hallazgos_{periodo}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )
        else:
            df_alertas_vacia = pd.DataFrame(columns=["fila", "cups", "sexo", "tipo"])
            pdf_bytes = generar_informe_hallazgos(
                df_alertas=df_alertas_vacia,
                ips_nombre=ips_nombre,
                periodo=periodo,
                usuario=st.session_state.user,
            )
            if pdf_bytes:
                st.success("Informe generado sin errores detectados.")
                st.download_button(
                    label="Descargar Informe PDF",
                    data=pdf_bytes,
                    file_name=f"Informe_Hallazgos_{periodo}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )


def render_gestion_usuarios():
    st.markdown('<p class="section-title" style="margin-top: 0.5rem;">Gestion de Usuarios y Permisos</p>', unsafe_allow_html=True)

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown('<div class="upload-container">', unsafe_allow_html=True)
        st.markdown("**Crear Nuevo Usuario**")

        with st.form("new_user_form"):
            new_user = st.text_input("Nombre de Usuario", placeholder="ej: gestor_nuevo")
            new_pass = st.text_input("Contraseña", type="password", placeholder="Minimo 6 caracteres")
            new_rol = st.selectbox("Perfil", ["Master", "Gestor", "Cliente IPS"])
            new_nombre = st.text_input("Nombre Completo", placeholder="ej: Juan Perez")
            new_eps = st.text_input("EPS Asignada (opcional)", placeholder="Para perfil Cliente IPS")
            submitted_new = st.form_submit_button("Crear Usuario", type="primary", use_container_width=True)

            if submitted_new:
                if len(new_pass) < 4:
                    st.error("La contraseña debe tener al menos 4 caracteres.")
                elif not new_user:
                    st.error("El nombre de usuario es obligatorio.")
                else:
                    ok, msg = crear_usuario(new_user, new_pass, new_rol, new_nombre, new_eps if new_eps else None)
                    if ok:
                        st.session_state.usuarios = cargar_usuarios()
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        st.markdown('</div>', unsafe_allow_html=True)

    with col_g2:
        st.markdown('<div class="upload-container">', unsafe_allow_html=True)
        st.markdown("**Usuarios Registrados**")

        usuarios = st.session_state.usuarios
        df_users = pd.DataFrame([
            {"Usuario": u, "Rol": data["rol"], "Nombre": data["nombre"], "EPS": data.get("eps_asignada", "-")}
            for u, data in usuarios.items()
        ])
        st.dataframe(df_users, use_container_width=True, hide_index=True)

        usuarios_eliminar = [u for u in usuarios.keys() if u != "admin"]
        if usuarios_eliminar:
            user_to_delete = st.selectbox("Seleccionar usuario para eliminar:", usuarios_eliminar)
            if st.button("Eliminar Usuario", use_container_width=True):
                ok, msg = eliminar_usuario(user_to_delete)
                if ok:
                    st.session_state.usuarios = cargar_usuarios()
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        st.markdown('</div>', unsafe_allow_html=True)


def render_configuracion_tab():
    st.markdown('<p class="section-title" style="margin-top: 0.5rem;">Identidad Visual del Documento</p>', unsafe_allow_html=True)

    st.markdown('<div class="upload-container">', unsafe_allow_html=True)

    col_logo1, col_logo2 = st.columns([1, 2])

    with col_logo1:
        st.markdown("**Logo Institucional**")
        uploaded_logo = st.file_uploader("Cargar Logo (.png)", type=["png"], key="logo_uploader")
        if uploaded_logo is not None:
            logo_dest = os.path.join(DIR_ACTUAL, "logo_aqario.png")
            with open(logo_dest, "wb") as f:
                f.write(uploaded_logo.getbuffer())
            agregar_historial("logo_aqario.png", "Logo Institucional")
            st.success("Logo actualizado correctamente.")
            st.rerun()

    with col_logo2:
        st.markdown("**Vista Previa del Logo Actual**")
        try:
            logo_path = os.path.join(DIR_ACTUAL, "logo_aqario.png")
            if os.path.exists(logo_path):
                st.image(logo_path, width=180)
                st.success("Logo cargado correctamente.")
            else:
                st.warning("No hay logo configurado. Suba un archivo PNG.")
        except Exception:
            st.error("Error al cargar el logo.")

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<p class="section-title">Carga de Manuales y Diccionarios</p>', unsafe_allow_html=True)

    st.markdown('<div class="upload-container">', unsafe_allow_html=True)

    col_dict1, col_dict2, col_dict3 = st.columns(3)

    with col_dict1:
        st.markdown("**Manual Tarifario SOAT**")
        uploaded_soat = st.file_uploader("Cargar SOAT", type=["xlsx", "pdf"], key="soat_uploader")
        if uploaded_soat is not None:
            handle_manual_upload(uploaded_soat, "Manual Tarifario SOAT")
            st.success(f"**{uploaded_soat.name}** cargado correctamente.")

    with col_dict2:
        st.markdown("**Manual ISS**")
        uploaded_iss = st.file_uploader("Cargar ISS", type=["xlsx", "pdf"], key="iss_uploader")
        if uploaded_iss is not None:
            handle_manual_upload(uploaded_iss, "Manual ISS")
            st.success(f"**{uploaded_iss.name}** cargado correctamente.")

    with col_dict3:
        st.markdown("**Diccionario CIE-10**")
        uploaded_cie = st.file_uploader("Cargar CIE-10", type=["xlsx", "pdf"], key="cie10_uploader")
        if uploaded_cie is not None:
            handle_manual_upload(uploaded_cie, "Diccionario CIE-10")
            st.success(f"**{uploaded_cie.name}** cargado correctamente.")

    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.historial:
        st.markdown('<p class="section-title">Historial de Actualizaciones de Normatividad</p>', unsafe_allow_html=True)

        df_hist = pd.DataFrame(st.session_state.historial)
        st.dataframe(df_hist, use_container_width=True, hide_index=True)

    st.markdown('<p class="section-title">Base de Datos de Recuperacion</p>', unsafe_allow_html=True)

    df_db = cargar_db_recovery()
    if not df_db.empty:
        st.dataframe(df_db, use_container_width=True, hide_index=True)
    else:
        st.info("No hay registros aun. Los datos se guardaran automaticamente al procesar facturas.")


def handle_manual_upload(uploaded, tipo_manual):
    if uploaded is not None:
        agregar_historial(uploaded.name, tipo_manual)


def render_portal_ips():
    st.markdown('<h1 class="main-header">Bienvenido al Portal de IPS - Grupo AXIS</h1>', unsafe_allow_html=True)
    st.markdown('<p class="description-text">Panel de consulta y monitoreo de su cartera.</p>', unsafe_allow_html=True)

    df = st.session_state.df_auditoria

    if df is None:
        st.info("No hay datos cargados. Contacte al administrador del BPO para cargar su cartera.")
        return

    df, encontradas, faltantes = validar_estructura(df)
    df["VALOR_TOTAL"] = pd.to_numeric(df["VALOR_TOTAL"], errors="coerce").fillna(0).astype(int)

    st.divider()
    st.markdown('<h3 style="color: #1C3D73; font-size: 1.5rem; font-weight: 600; margin-bottom: 1.25rem;">Dashboard de Cartera (Solo Lectura)</h3>', unsafe_allow_html=True)

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("Total de Titulos", f"{len(df):,}")
    with col_m2:
        st.metric(
            "Proyeccion de Liquidez",
            f"$ {df['VALOR_TOTAL'].sum():,.0f}",
            delta="Activos en cartera",
        )
    with col_m3:
        st.metric("Promedio por Cuenta", f"$ {df['VALOR_TOTAL'].mean():,.0f}")

    st.markdown('<p class="section-title">Detalle de Facturas</p>', unsafe_allow_html=True)

    df_display = df[["NUMERO_FACTURA", "NIT_EPS", "VALOR_TOTAL"]].copy()
    df_display["ESTADO"] = "En Proceso"
    df_display["VALOR_TOTAL"] = df_display["VALOR_TOTAL"].apply(lambda x: f"$ {x:,.0f}")

    st.dataframe(df_display, use_container_width=True, hide_index=True)


def render_app():
    render_sidebar()
    permisos = PERFILES.get(st.session_state.rol, [])

    if st.session_state.rol == "Cliente IPS":
        render_portal_ips()
    elif st.session_state.rol == "Master":
        tab_auditoria, tab_fabrica, tab_informes, tab_usuarios, tab_config = st.tabs([
            "AUDITORIA",
            "TITULOS PDF",
            "INFORMES",
            "GESTION USUARIOS",
            "CONFIGURACION",
        ])

        with tab_auditoria:
            render_auditoria_tab()

        with tab_fabrica:
            render_fabrica_pdf_tab()

        with tab_informes:
            render_informes_tab()

        with tab_usuarios:
            render_gestion_usuarios()

        with tab_config:
            render_configuracion_tab()
    else:
        tab_auditoria, tab_fabrica, tab_informes = st.tabs([
            "AUDITORIA",
            "TITULOS PDF",
            "INFORMES",
        ])

        with tab_auditoria:
            render_auditoria_tab()

        with tab_fabrica:
            render_fabrica_pdf_tab()

        with tab_informes:
            render_informes_tab()


if not st.session_state.logged_in:
    render_login()
else:
    st.markdown(
        '<p class="main-subheader">Sistema de Auditoria y Recuperacion de Cartera</p>',
        unsafe_allow_html=True,
    )
    st.markdown('<h1 class="main-header">aQario</h1>', unsafe_allow_html=True)

    st.markdown(
        """
        <p class="description-text">
            Plataforma interna para la auditoria, analisis y recuperacion de cartera del sector salud.
        </p>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    render_app()

    st.markdown(
        '<p class="footer">&copy; 2026 Grupo AXIS S.A.S. | 902021366-2 | www.grupoaxis.com.co</p>',
        unsafe_allow_html=True,
    )
