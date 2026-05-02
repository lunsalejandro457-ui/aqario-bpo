import io
import streamlit as st
import pandas as pd
import numpy as np
import re
import os
import hashlib
import smtplib
import ssl
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from fpdf import FPDF

st.set_page_config(page_title="aQario", page_icon="", layout="wide", initial_sidebar_state="expanded")

DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DIR_ACTUAL, "db_axis_recovery.csv")
USERS_PATH = os.path.join(DIR_ACTUAL, "db_users.csv")

PERFILES = {
    "Master": ["auditoria", "fabrica", "informes", "gestion_usuarios", "configuracion"],
    "Gestor": ["auditoria", "fabrica", "informes"],
    "Cliente IPS": ["dashboard_ips"],
}

USUARIOS_DEFAULT = {
    "admin": {"password": hashlib.sha256("axis2026".encode()).hexdigest(), "rol": "Master", "nombre": "Admin AXIS", "eps_asignada": None},
    "ips_sura": {"password": hashlib.sha256("sura2026".encode()).hexdigest(), "rol": "Cliente IPS", "nombre": "IPS SURA", "eps_asignada": "SURA"},
    "gestor1": {"password": hashlib.sha256("gestor2026".encode()).hexdigest(), "rol": "Gestor", "nombre": "Gestor BPO", "eps_asignada": None},
}

COLUMNAS_CRITICAS = ["NUMERO_FACTURA", "VALOR_TOTAL", "NIT_EPS", "FECHA_RADICADO", "CODIGO_CUPS", "DIAGNOSTICO"]
PROCEDIMIENTOS_MASCULINOS = ["560301", "560302", "630501", "630502", "620501", "630701", "560201"]

NIT_VALORES = [800123456, 800234567, 800345678, 800456789, 900111222]
EPS_NOMBRES = {800123456: "Nueva EPS", 800234567: "SURA EPS", 800345678: "Salud Total", 800456789: "Coomeva", 900111222: "Sanitas"}
CUPS_VALORES = ["890308", "906206", "890310", "906212", "890510", "906306", "890102", "906404"]
DIAGNOSTICOS = ["J06.9", "J18.9", "K29.7", "I10", "E11.9", "M54.5", "J45.9", "K21.0"]
PACIENTES = ["Carlos Ramirez", "Maria Lopez", "Jorge Herrera", "Ana Martinez", "Luis Torres", "Patricia Gomez", "Fernando Diaz", "Sandra Ruiz"]
MEDICOS = ["Dr. Alejandro Reyes", "Dra. Valentina Ortiz", "Dr. Miguel Angel Paredes", "Dra. Camila Duarte"]
CIUDADES = ["Ibague", "Bogota", "Medellin", "Cali", "Barranquilla"]

EMAIL_CONFIG_PATH = os.path.join(DIR_ACTUAL, "email_config.json")


def cargar_config_email():
    if os.path.exists(EMAIL_CONFIG_PATH):
        import json
        with open(EMAIL_CONFIG_PATH, "r") as f:
            return json.load(f)
    return {"smtp_server": "smtp.gmail.com", "smtp_port": 587, "email": "", "password": "", "enabled": False}


def guardar_config_email(config):
    import json
    with open(EMAIL_CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def enviar_titulo_email(destinatario, asunto, cuerpo, pdf_bytes, nombre_archivo, config):
    try:
        msg = MIMEMultipart()
        msg["From"] = config["email"]
        msg["To"] = destinatario
        msg["Subject"] = latin(asunto)
        msg.attach(MIMEText(cuerpo, "plain"))
        part = MIMEBase("application", "octet-stream")
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={nombre_archivo}")
        msg.attach(part)
        context = ssl.create_default_context()
        with smtplib.SMTP(config["smtp_server"], config["smtp_port"]) as server:
            server.starttls(context=context)
            server.login(config["email"], config["password"])
            server.send_message(msg)
        return True, "Correo enviado correctamente"
    except Exception as e:
        return False, f"Error al enviar: {str(e)}"


def latin(text):
    return str(text).encode("latin-1", "ignore").decode("latin-1")


def resolver_nombre_eps(nit):
    try:
        nit_int = int(nit)
        return EPS_NOMBRES.get(nit_int, f"EPS NIT {nit}")
    except (ValueError, TypeError):
        return f"EPS NIT {nit}"


def cargar_usuarios():
    if os.path.exists(USERS_PATH):
        try:
            df = pd.read_csv(USERS_PATH)
            usuarios = {}
            for _, row in df.iterrows():
                usuarios[row["username"]] = {"password": row["password_hash"], "rol": row["rol"], "nombre": row["nombre"], "eps_asignada": row.get("eps_asignada", None)}
            return usuarios
        except Exception:
            pass
    guardar_usuarios(USUARIOS_DEFAULT.copy())
    return USUARIOS_DEFAULT.copy()


def guardar_usuarios(usuarios):
    rows = [{"username": u, "password_hash": d["password"], "rol": d["rol"], "nombre": d["nombre"], "eps_asignada": d.get("eps_asignada", "")} for u, d in usuarios.items()]
    pd.DataFrame(rows).to_csv(USERS_PATH, index=False)


def crear_usuario(username, password, rol, nombre, eps_asignada=None):
    usuarios = cargar_usuarios()
    if username in usuarios:
        return False, "El usuario ya existe"
    usuarios[username] = {"password": hashlib.sha256(password.encode()).hexdigest(), "rol": rol, "nombre": nombre, "eps_asignada": eps_asignada}
    guardar_usuarios(usuarios)
    return True, "Usuario creado correctamente"


def eliminar_usuario(username):
    usuarios = cargar_usuarios()
    if username in usuarios and username != "admin":
        del usuarios[username]
        guardar_usuarios(usuarios)
        return True, "Usuario eliminado"
    return False, "No se puede eliminar este usuario"


def cargar_db():
    if os.path.exists(DB_PATH):
        try:
            return pd.read_csv(DB_PATH)
        except Exception:
            pass
    return pd.DataFrame(columns=["ips", "eps", "no_factura", "valor", "errores", "fecha", "estado", "usuario"])


def guardar_db(registro):
    df = cargar_db()
    new_row = pd.DataFrame([registro])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(DB_PATH, index=False)


def normalizar_columnas(cols):
    return [re.sub(r"\s+", "_", col.strip().upper().replace("-", "_").replace(" ", "_")) for col in cols]


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
                alertas.append({"fila": idx + 2, "cups": cups, "sexo": sexo, "tipo": "Procedimiento Exclusivo Masculino en Paciente Femenino"})
    return alertas


def calcular_riesgo_cartera(df, alertas):
    resultados = []
    hoy = datetime.now()
    for _, fila in df.iterrows():
        riesgo = "Recuperable"
        icono = "🟢"
        observaciones = "Datos completos y cartera vigente"
        fecha_rad = str(fila.get("FECHA_RADICADO", ""))
        antiguedad = 0
        try:
            fecha_dt = datetime.strptime(fecha_rad, "%Y-%m-%d")
            antiguedad = (hoy - fecha_dt).days
        except Exception:
            pass

        factura_alertas = [a for a in alertas if a.get("fila") == int(_.split("-")[1]) + 2] if isinstance(_, int) else []

        if antiguedad > 360 or len(factura_alertas) > 0:
            riesgo = "Perdida Total"
            icono = "🔴"
            observaciones = f"Factura con {antiguedad} dias o errores criticos de auditoria"
        elif antiguedad > 90:
            riesgo = "Arriesgado"
            icono = "🟡"
            observaciones = f"Cartera con {antiguedad} dias. Riesgo medio por antiguedad"

        valor_total = float(fila.get("VALOR_TOTAL", 0))
        resultados.append({
            "no_factura": fila.get("NUMERO_FACTURA", ""),
            "eps": fila.get("NIT_EPS", ""),
            "valor": valor_total,
            "riesgo": riesgo,
            "icono": icono,
            "antiguedad_dias": antiguedad,
            "observaciones": observaciones,
        })
    return pd.DataFrame(resultados)


def calcular_porcentaje_recuperacion(df_riesgo):
    if df_riesgo.empty:
        return 0, "Sin datos"
    total = df_riesgo["valor"].sum()
    if total == 0:
        return 0, "Sin datos"
    recuperable = df_riesgo[df_riesgo["riesgo"] == "Recuperable"]["valor"].sum()
    arriesgado = df_riesgo[df_riesgo["riesgo"] == "Arriesgado"]["valor"].sum()
    estimado = recuperable + (arriesgado * 0.5)
    porcentaje = (estimado / total) * 100
    if porcentaje >= 80:
        return porcentaje, "Bueno"
    elif porcentaje >= 50:
        return porcentaje, "Moderado"
    return porcentaje, "Critico"


def generar_fecha(base, max_dias=180):
    delta = np.random.randint(0, max_dias)
    return (base - timedelta(days=delta)).strftime("%Y-%m-%d")


def generar_datos_perfectos(n=20):
    np.random.seed(42)
    return pd.DataFrame({
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
    })


def generar_datos_con_errores(n=20):
    np.random.seed(43)
    return pd.DataFrame({
        "numero_factura": [f"FAC-{i+2001}" for i in range(n)],
        "VALOR_TOTAL": np.round(np.random.uniform(200000, 9800000, n), 0).astype(int),
        "nit_eps": np.random.choice(NIT_VALORES, n),
        "codigo_cups": np.random.choice(CUPS_VALORES, n),
        "diagnostico": np.random.choice(DIAGNOSTICOS, n),
        "Nombre_Paciente": np.random.choice(PACIENTES, n),
        "Medico_Tratante": np.random.choice(MEDICOS, n),
    })


def generar_archivos_prueba():
    generar_datos_perfectos().to_excel(os.path.join(DIR_ACTUAL, "datos_perfectos.xlsx"), index=False)
    generar_datos_con_errores().to_excel(os.path.join(DIR_ACTUAL, "datos_con_errores.xlsx"), index=False)


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
        pdf.multi_cell(0, 6, latin(f"Señores:\n{ips}\n\nReferencia: Notificacion de cobro prejudicial por concepto de servicios de salud prestados."))
        pdf.ln(6)
        pdf.multi_cell(0, 6, latin(f"La entidad beneficiaria {ips}, actuando bajo el respectivo Contrato de Mandato con GRUPO AXIS S.A.S., EXIGE formalmente el pago de las obligaciones economicas derivadas de la prestacion de servicios de salud. El incumplimiento facultara al acreedor para iniciar acciones judiciales mediante proceso ejecutivo."))
        pdf.ln(8)

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(10, 26, 63)
        pdf.cell(0, 7, latin("Detalle del Titulo Ejecutivo"), ln=1)
        pdf.ln(2)

        valor_total = datos_factura.get("VALOR_TOTAL", 0)
        valor_str = latin(f"$ {int(valor_total):,.0f} COP") if isinstance(valor_total, (int, float)) else latin(str(valor_total))
        detalles = [
            (latin("Numero de Factura:"), latin(str(datos_factura.get("NUMERO_FACTURA", "N/A")))),
            (latin("Fecha de Radicado:"), latin(str(datos_factura.get("FECHA_RADICADO", "N/A")))),
            (latin("Codigo CUPS:"), latin(str(datos_factura.get("CODIGO_CUPS", "N/A")))),
            (latin("Diagnostico:"), latin(str(datos_factura.get("DIAGNOSTICO", "N/A")))),
            (latin("NIT EPS:"), latin(str(eps))),
            (latin("Valor Total:"), valor_str),
        ]
        for etiqueta, valor in detalles:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 7, etiqueta, ln=1)
            pdf.set_x(pdf.l_margin + 5)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 7, valor, ln=1)
            pdf.ln(1)

        pdf.ln(10)
        pdf.multi_cell(0, 6, latin("Cordialmente,\nDepartamento de Recaudo y Cartera\nGRUPO AXIS S.A.S."))
        return pdf.output(dest="S").encode("latin-1")
    except Exception as e:
        st.error(f"Error al generar el PDF: {str(e)}")
        return None


def generar_certificado_auditoria(df, alertas, ips_nombre, fecha_inicio, fecha_fin):
    try:
        logo_path = os.path.join(DIR_ACTUAL, "logo_aqario.png")
        if not os.path.exists(logo_path):
            logo_path = None
        pdf = TituloPDF(format="Letter", logo_path=logo_path)
        pdf.usuario_impresion = "Sistema aQario"
        pdf.set_auto_page_break(auto=True, margin=45)
        pdf.add_page()
        pdf.set_margins(left=25, top=65, right=25)

        total_facturas = len(df)
        total_valor = f"$ {df['VALOR_TOTAL'].sum():,.0f} COP" if "VALOR_TOTAL" in df.columns else "N/A"
        total_errores = len(alertas)
        ahora = latin(datetime.now().strftime("%d/%m/%Y - %H:%M:%S"))

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 6, f"Fecha de expedicion: {ahora}", ln=1, align="R")
        pdf.ln(8)

        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(10, 26, 63)
        pdf.cell(0, 10, latin("CERTIFICADO DE AUDITORIA CONSOLIDADO"), ln=1, align="C")
        pdf.ln(4)

        pdf.set_draw_color(92, 160, 242)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(8)

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        certificacion = latin(
            f"GRUPO AXIS S.A.S. certifica que entre el {fecha_inicio} y el {fecha_fin} "
            f"se auditaron {total_facturas} facturas de la {ips_nombre}."
        )
        pdf.multi_cell(0, 6, certificacion)
        pdf.ln(4)
        pdf.multi_cell(0, 6, latin(f"Valor total auditado: {total_valor}"))
        pdf.ln(6)

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(10, 26, 63)
        pdf.cell(0, 7, latin("Hallazgos de Auditoria"), ln=1)
        pdf.ln(2)

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        if total_errores > 0:
            pdf.multi_cell(0, 6, latin(f"Se detectaron {total_errores} errores en codigos CUPS y validacion clinica:"))
            pdf.ln(2)
            for a in alertas[:20]:
                pdf.cell(0, 6, latin(f" - Fila {a['fila']}: {a['tipo']} (CUPS: {a['cups']})"), ln=1)
        else:
            pdf.multi_cell(0, 6, latin("Auditoria exitosa: 0 errores encontrados. Todos los datos cumplen los estandares de calidad."))
        pdf.ln(6)

        pdf.set_draw_color(92, 160, 242)
        pdf.set_line_width(1)
        pdf.rect(pdf.l_margin + 10, pdf.get_y(), pdf.w - pdf.r_margin - pdf.l_margin - 20, 15)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(10, 26, 63)
        y_pos = pdf.get_y() + 4
        pdf.set_xy(pdf.l_margin + 15, y_pos)
        pdf.cell(0, 7, latin("TITULO EJECUTIVO GENERADO"), ln=1, align="C")
        pdf.set_xy(pdf.l_margin + 15, pdf.get_y())
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 5, latin("Las facturas aprobadas cuentan con soporte legal para cobro prejuridico"), ln=1, align="C")

        pdf.ln(14)
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(0, 5, latin("Este certificado fue generado automaticamente por el sistema aQario de Grupo AXIS S.A.S.\nDocumento valido como constancia de auditoria de cartera."))

        return pdf.output(dest="S").encode("latin-1")
    except Exception as e:
        st.error(f"Error al generar certificado: {str(e)}")
        return None


def generar_certificado_diagnostico(df_riesgo, porcentaje, estado, ips_nombre):
    try:
        logo_path = os.path.join(DIR_ACTUAL, "logo_aqario.png")
        if not os.path.exists(logo_path):
            logo_path = None
        pdf = TituloPDF(format="Letter", logo_path=logo_path)
        pdf.usuario_impresion = "Sistema aQario"
        pdf.set_auto_page_break(auto=True, margin=45)
        pdf.add_page()
        pdf.set_margins(left=25, top=65, right=25)

        ahora = latin(datetime.now().strftime("%d/%m/%Y - %H:%M:%S"))
        total_cartera = df_riesgo["valor"].sum() if not df_riesgo.empty else 0

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 6, f"Fecha de expedicion: {ahora}", ln=1, align="R")
        pdf.ln(8)

        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(10, 26, 63)
        pdf.cell(0, 10, latin("CERTIFICADO DE ESTADO DE CARTERA"), ln=1, align="C")
        pdf.ln(4)

        pdf.set_draw_color(92, 160, 242)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(8)

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        certificacion = latin(
            f"Bajo el diagnostico tecnico de AXIS BPO, la cartera de {ips_nombre} tiene un "
            f"potencial de recuperacion del {porcentaje:.1f}%. El estado promedio es {estado}."
        )
        pdf.multi_cell(0, 6, certificacion)
        pdf.ln(6)

        pdf.multi_cell(0, 6, latin(f"Cartera total analizada: $ {total_cartera:,.0f} COP"))
        pdf.multi_cell(0, 6, latin(f"Facturas analizadas: {len(df_riesgo)}"))
        pdf.ln(6)

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(10, 26, 63)
        pdf.cell(0, 7, latin("Clasificacion de Riesgo"), ln=1)
        pdf.ln(2)

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        for riesgo, icono in [("Recuperable", "Verde (Bajo Riesgo)"), ("Arriesgado", "Amarillo (Riesgo Medio)"), ("Perdida Total", "Rojo (Riesgo Alto)")]:
            count = len(df_riesgo[df_riesgo["riesgo"] == riesgo]) if not df_riesgo.empty else 0
            val = df_riesgo[df_riesgo["riesgo"] == riesgo]["valor"].sum() if not df_riesgo.empty else 0
            pdf.cell(0, 6, latin(f"{icono} - {riesgo}: {count} facturas ($ {val:,.0f})"), ln=1)
        pdf.ln(8)

        pdf.set_draw_color(92, 160, 242)
        pdf.set_line_width(0.8)
        pdf.rect(pdf.l_margin + 10, pdf.get_y(), pdf.w - pdf.r_margin - pdf.l_margin - 20, 18)
        pdf.set_xy(pdf.l_margin + 15, pdf.get_y() + 4)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 5, latin("Nuestro equipo de gestion humana ejecutara las acciones necesarias para el rescate de estos fondos.\nGRUPO AXIS S.A.S. - Departamento de Recaudo y Cartera"))

        return pdf.output(dest="S").encode("latin-1")
    except Exception as e:
        st.error(f"Error al generar certificado: {str(e)}")
        return None


CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }

    .stApp { background-color: #FFFFFF !important; }

    .main-header { color: #0A1A3F; font-size: 2.5rem; font-weight: 700; letter-spacing: -0.5px; margin-bottom: 0.25rem; }
    .main-subheader { color: #5CA0F2; font-size: 1rem; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 1.5rem; }
    .description-text { color: #1C3D73; font-size: 0.95rem; line-height: 1.7; max-width: 720px; }

    .section-title { color: #0A1A3F; font-size: 1.25rem; font-weight: 600; margin-top: 2rem; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 2px solid #5CA0F2; }

    .upload-container { background-color: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 12px; padding: 2rem; box-shadow: 0 1px 3px rgba(10, 26, 63, 0.08); }

    .action-button-container { background-color: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 12px; padding: 1.5rem; text-align: center; box-shadow: 0 2px 8px rgba(10, 26, 63, 0.06); }

    .footer { margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid #E5E7EB; color: #9CA3AF; font-size: 0.8rem; text-align: center; }
    hr.divider { border: none; height: 1px; background: linear-gradient(to right, transparent, #5CA0F2, transparent); margin: 2rem 0; }

    .risk-green { background-color: #ECFDF5; border-left: 4px solid #10B981; padding: 12px 16px; border-radius: 8px; margin: 8px 0; }
    .risk-yellow { background-color: #FFFBEB; border-left: 4px solid #F59E0B; padding: 12px 16px; border-radius: 8px; margin: 8px 0; }
    .risk-red { background-color: #FEF2F2; border-left: 4px solid #EF4444; padding: 12px 16px; border-radius: 8px; margin: 8px 0; }

    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { background-color: #FFFFFF; border-radius: 8px; padding: 12px 24px; border: 1px solid #E5E7EB; color: #1C3D73; font-weight: 500; }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] { background-color: #0A1A3F; color: #FFFFFF; border-color: #0A1A3F; }

    .stMetric { background-color: #FFFFFF; border-radius: 8px; padding: 1rem; }

    div[data-testid="stExpander"] { background-color: transparent; }
    [data-testid="stExpander"] .streamlit-expanderHeader { background-color: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; color: #0A1A3F !important; font-weight: 600; }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

st.markdown('''
<style>
    [data-testid="stSidebar"] { background-color: #0A1A3F !important; }
    [data-testid="stSidebar"] *, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
        color: #FFFFFF !important; font-weight: 600 !important;
    }
    .stMain p, .stMain label, .stMain h1, .stMain h2, .stMain h3, .stMain span { color: #0A1A3F !important; }
    input { color: #000000 !important; }
    [data-testid="stSidebar"] img { margin-top: -20px; margin-bottom: 20px; }
    div[data-testid="stMarkdownContainer"] p, label, span { color: #0A1A3F !important; font-weight: bold !important; }
    .stError, .stWarning, .stInfo, .stSuccess { color: #0A1A3F !important; }
    div[data-testid="stAlert"] { color: #0A1A3F !important; }
    button[kind="primary"] {
        background-color: #1C3D73 !important; color: #FFFFFF !important; border-radius: 10px !important;
        font-size: 16px !important; font-weight: 600 !important; padding: 12px 24px !important; border: none !important;
    }
    button[kind="primary"]:hover {
        background-color: #0A1A3F !important; color: #FFFFFF !important;
        box-shadow: 0 4px 12px rgba(10, 26, 63, 0.3) !important;
    }
    th { background-color: #0A1A3F !important; color: #FFFFFF !important; }
    td { color: #0A1A3F !important; }
    .dataframe { border: 1px solid #E5E7EB !important; }
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
if "ips_seleccionada" not in st.session_state:
    st.session_state.ips_seleccionada = "Todas las IPS"
if "df_riesgo" not in st.session_state:
    st.session_state.df_riesgo = None
if "pagina_actual" not in st.session_state:
    st.session_state.pagina_actual = 1
if "fecha_auditoria_inicio" not in st.session_state:
    st.session_state.fecha_auditoria_inicio = None
ROWS_POR_PAGINA = 100


def agregar_historial(nombre_archivo, tipo):
    entrada = {"archivo": nombre_archivo, "tipo": tipo, "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "usuario": st.session_state.user}
    st.session_state.historial.insert(0, entrada)
    if len(st.session_state.historial) > 50:
        st.session_state.historial = st.session_state.historial[:50]


def render_login():
    col_c1, col_c2, col_c3 = st.columns([1, 1.2, 1])
    with col_c2:
        try:
            st.image("logo_aqario.png", width=160)
        except Exception:
            st.markdown('<div style="text-align:center; font-size:2.5rem; font-weight:700; color:#0A1A3F; margin-bottom:1rem;">aQario</div>', unsafe_allow_html=True)
        st.markdown('<p style="text-align:center; color:#5CA0F2; font-size:0.75rem; font-weight:600; letter-spacing:2px; text-transform:uppercase; margin-top:-0.75rem; margin-bottom:2rem;">Sistema de Auditoria y Recuperacion de Cartera</p>', unsafe_allow_html=True)
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
        st.markdown("---")
        ips_options = ["Todas las IPS", "IPS SURA", "Clinica del Valle", "Hospital Central"]
        st.session_state.ips_seleccionada = st.selectbox("IPS Activa:", ips_options, index=ips_options.index(st.session_state.ips_seleccionada) if st.session_state.ips_seleccionada in ips_options else 0)
        if st.button("Cerrar Sesion", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.session_state.rol = None
            st.session_state.df_auditoria = None
            st.session_state.df_riesgo = None
            st.session_state.alertas_detectadas = []
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        if st.session_state.rol == "Master":
            with st.expander("Herramientas de Desarrollo", expanded=False):
                if st.button("Generar Archivos de Prueba", use_container_width=True):
                    generar_archivos_prueba()
                    st.sidebar.success("Archivos generados correctamente.")


def render_paginated_df(df, key_prefix="data", max_rows=ROWS_POR_PAGINA):
    total_rows = len(df)
    if total_rows <= max_rows:
        st.dataframe(df, use_container_width=True, hide_index=True)
        return
    total_paginas = (total_rows + max_rows - 1) // max_rows
    col_p1, col_p2, col_p3 = st.columns([1, 2, 1])
    with col_p2:
        pagina = st.number_input(
            f"Pagina (1-{total_paginas})",
            min_value=1,
            max_value=total_paginas,
            value=st.session_state.get(f"pagina_{key_prefix}", 1),
            key=f"page_input_{key_prefix}",
        )
        st.session_state[f"pagina_{key_prefix}"] = pagina
    inicio = (pagina - 1) * max_rows
    fin = inicio + max_rows
    st.dataframe(df.iloc[inicio:fin], use_container_width=True, hide_index=True)
    st.caption(f"Mostrando {inicio + 1}-{min(fin, total_rows)} de {total_rows:,} registros")


def render_auditoria_tab():
    st.markdown('<p class="section-title" style="margin-top: 0.5rem;">Cargar Archivo de Facturacion o RIPS</p>', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="upload-container">', unsafe_allow_html=True)
        uploaded_file = st.file_uploader(label="Seleccione un archivo", type=["xlsx", "csv"], key="auditoria_uploader")
        st.markdown('</div>', unsafe_allow_html=True)

    if uploaded_file is not None:
        st.session_state.uploaded_file_name = uploaded_file.name
        st.success(f"Archivo cargado: **{uploaded_file.name}**")
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
        st.session_state.df_auditoria = df
        st.session_state.fecha_auditoria_inicio = datetime.now().strftime("%d/%m/%Y")

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
            for col in encontradas if encontradas else ["Ninguna"]:
                st.success(col) if encontradas else st.info(col)
        with col_check2:
            st.markdown("**Columnas Faltantes**")
            if faltantes:
                for col in faltantes:
                    st.error(col)
            else:
                st.success("Todas las columnas criticas presentes")
        st.markdown('</div>', unsafe_allow_html=True)

    if faltantes:
        st.warning(f"**Archivo no apto.** Faltan {len(faltantes)} campo(s) critico(s): {', '.join(faltantes)}.")
        return

    st.success("**Estructura valida.** Archivo apto para generar titulos ejecutivos seguros.")

    alertas = validar_cruce_clinico(df)
    st.session_state.alertas_detectadas = alertas

    st.markdown('<p class="section-title">Motor de Validacion - Cruce Clinico</p>', unsafe_allow_html=True)
    if alertas:
        st.error("ERROR DE IPS DETECTADO: Incoherencia Sexo-Procedimiento. Riesgo de Glosa Alto.")
        st.dataframe(pd.DataFrame(alertas), use_container_width=True, hide_index=True)
    elif "SEXO" in df.columns:
        st.success("Cruce clinico completado. Sin incoherencias.")
    else:
        st.info("Columna 'SEXO' no presente. Cruce clinico no aplica.")

    if not faltantes:
        df["VALOR_TOTAL"] = pd.to_numeric(df["VALOR_TOTAL"], errors="coerce").fillna(0).astype(int)

        st.divider()
        st.markdown('<h3 style="color: #1C3D73; font-size: 1.5rem; font-weight: 600; margin-bottom: 1.25rem;">Modulo de Analisis de Recuperacion</h3>', unsafe_allow_html=True)

        df_riesgo = calcular_riesgo_cartera(df, alertas)
        st.session_state.df_riesgo = df_riesgo
        porcentaje, estado = calcular_porcentaje_recuperacion(df_riesgo)

        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        with col_r1:
            st.metric("Total Cartera", f"$ {df['VALOR_TOTAL'].sum():,.0f}")
        with col_r2:
            st.metric("% Recuperacion Estimado", f"{porcentaje:.1f}%")
        with col_r3:
            verde = len(df_riesgo[df_riesgo["riesgo"] == "Recuperable"])
            st.metric("Recuperables", verde)
        with col_r4:
            rojo = len(df_riesgo[df_riesgo["riesgo"] == "Perdida Total"])
            st.metric("Perdida Total", rojo)

        st.markdown("### Clasificacion por Riesgo")
        for riesgo, css_class in [("Recuperable", "risk-green"), ("Arriesgado", "risk-yellow"), ("Perdida Total", "risk-red")]:
            sub = df_riesgo[df_riesgo["riesgo"] == riesgo]
            if not sub.empty:
                st.markdown(f'<div class="{css_class}"><b>{riesgo}</b>: {len(sub)} facturas | $ {sub["valor"].sum():,.0f}</div>', unsafe_allow_html=True)

        st.markdown('<p class="section-title">Certificado de Estado de Cartera</p>', unsafe_allow_html=True)
        st.info("Descargue el certificado con el potencial de recuperacion de su cartera.")
        if st.button("Generar Certificado de Estado", type="primary", use_container_width=True):
            pdf_bytes = generar_certificado_diagnostico(df_riesgo, porcentaje, estado, st.session_state.ips_seleccionada)
            if pdf_bytes:
                st.download_button(label="Descargar Certificado PDF", data=pdf_bytes, file_name="Certificado_Estado_Cartera.pdf", mime="application/pdf", type="primary", use_container_width=True)

        st.markdown('<p class="section-title">Certificado de Auditoria Consolidado</p>', unsafe_allow_html=True)
        col_cert1, col_cert2 = st.columns(2)
        with col_cert1:
            fecha_ini = st.date_input("Fecha Inicio", value=datetime(2026, 1, 1))
        with col_cert2:
            fecha_fin = st.date_input("Fecha Fin", value=datetime(2026, 5, 1))
        if st.button("Generar Certificado de Auditoria AXIS", type="primary", use_container_width=True):
            pdf_bytes = generar_certificado_auditoria(df, alertas, st.session_state.ips_seleccionada, fecha_ini.strftime("%d/%m/%Y"), fecha_fin.strftime("%d/%m/%Y"))
            if pdf_bytes:
                for _, fila in df.iterrows():
                    guardar_db({"ips": st.session_state.ips_seleccionada, "eps": str(fila.get("NIT_EPS", "")), "no_factura": str(fila.get("NUMERO_FACTURA", "")), "valor": str(fila.get("VALOR_TOTAL", 0)), "errores": str(len(alertas)), "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "estado": "Auditada", "usuario": st.session_state.user})
                st.download_button(label="Descargar Certificado AXIS PDF", data=pdf_bytes, file_name="Certificado_Auditoria_AXIS.pdf", mime="application/pdf", type="primary", use_container_width=True)

        render_paginated_df(df, key_prefix="auditoria_main")


def render_fabrica_pdf_tab():
    df = st.session_state.df_auditoria
    if df is None:
        st.info("Cargue un archivo en la pestana de Auditoria.")
        return
    df, encontradas, faltantes = validar_estructura(df)
    if faltantes:
        st.warning("El archivo no tiene todas las columnas criticas.")
        return
    df["VALOR_TOTAL"] = pd.to_numeric(df["VALOR_TOTAL"], errors="coerce").fillna(0).astype(int)

    st.markdown('<p class="section-title" style="margin-top: 0.5rem;">Generar Titulo Individual</p>', unsafe_allow_html=True)
    factura_seleccionada = st.selectbox("Seleccione una factura:", df["NUMERO_FACTURA"].tolist(), key="pdf_selector")
    if factura_seleccionada:
        fila = df[df["NUMERO_FACTURA"] == factura_seleccionada].iloc[0]
        pdf_bytes = generar_titulo_pdf(datos_factura=fila.to_dict(), eps=str(fila["NIT_EPS"]), ips="IPS Beneficiaria", usuario=st.session_state.user)
        if pdf_bytes:
            guardar_db({"ips": st.session_state.ips_seleccionada, "eps": str(fila["NIT_EPS"]), "no_factura": factura_seleccionada, "valor": str(fila["VALOR_TOTAL"]), "errores": "0", "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "estado": "Titulo Generado", "usuario": st.session_state.user})
            col_d1, col_d2 = st.columns([3, 1])
            with col_d1:
                st.download_button(label="Descargar Titulo PDF", data=pdf_bytes, file_name=f"Titulo_{factura_seleccionada}.pdf", mime="application/pdf", type="primary", use_container_width=True)
            with col_d2:
                config_email = cargar_config_email()
                if config_email.get("enabled"):
                    email_destino = st.text_input("Email destinatario", key="email_destino_individual")
                    if st.button("Enviar por Correo", use_container_width=True):
                        if email_destino:
                            asunto = f"Titulo Ejecutivo - Factura {factura_seleccionada}"
                            cuerpo = f"Estimado(a),\n\nAdjunto se remite el titulo ejecutivo correspondiente a la factura {factura_seleccionada}.\n\nCordialmente,\nDepartamento de Cartera - GRUPO AXIS S.A.S."
                            ok, msg = enviar_titulo_email(email_destino, asunto, cuerpo, pdf_bytes, f"Titulo_{factura_seleccionada}.pdf", config_email)
                            if ok:
                                st.success(msg)
                            else:
                                st.error(msg)
                        else:
                            st.warning("Ingrese un correo destinatario")

    st.divider()
    st.markdown('<p class="section-title">Consolidado Masivo por EPS</p>', unsafe_allow_html=True)
    eps_unique = df["NIT_EPS"].unique().tolist()
    eps_labels = [f"{resolver_nombre_eps(e)} ({e})" for e in eps_unique]
    eps_selected_label = st.selectbox("EPS Deudora:", eps_labels, key="consolidado_eps")
    eps_idx = eps_labels.index(eps_selected_label)
    eps_seleccionada = eps_unique[eps_idx]
    if eps_seleccionada:
        df_eps = df[df["NIT_EPS"] == eps_seleccionada]
        st.markdown(f"**{len(df_eps)} facturas** de **{resolver_nombre_eps(eps_seleccionada)}** | Total: **$ {df_eps['VALOR_TOTAL'].sum():,.0f}**")
        if st.button("Generar Consolidado", type="primary", use_container_width=True):
            pdfs_generados = []
            for _, f in df_eps.iterrows():
                pdf_bytes = generar_titulo_pdf(datos_factura=f.to_dict(), eps=str(eps_seleccionada), ips="IPS Beneficiaria", usuario=st.session_state.user)
                if pdf_bytes:
                    pdfs_generados.append((str(f["NUMERO_FACTURA"]), pdf_bytes))
                guardar_db({"ips": st.session_state.ips_seleccionada, "eps": resolver_nombre_eps(eps_seleccionada), "no_factura": str(f["NUMERO_FACTURA"]), "valor": str(f["VALOR_TOTAL"]), "errores": "0", "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "estado": "Consolidado", "usuario": st.session_state.user})
            st.success(f"Consolidado generado: {len(pdfs_generados)} titulos.")
            config_email = cargar_config_email()
            if config_email.get("enabled") and pdfs_generados:
                st.markdown("**Enviar consolidado por correo**")
                col_e1, col_e2 = st.columns([2, 1])
                with col_e1:
                    email_destino = st.text_input("Email destinatario", key="email_destino_consolidado")
                with col_e2:
                    if st.button("Enviar por Correo", use_container_width=True):
                        if email_destino:
                            asunto = f"Consolidado Titulos Ejecutivos - {resolver_nombre_eps(eps_seleccionada)}"
                            cuerpo = f"Estimado(a),\n\nAdjunto se remiten {len(pdfs_generados)} titulos ejecutivos correspondientes a la EPS {resolver_nombre_eps(eps_seleccionada)}.\n\nCordialmente,\nDepartamento de Cartera - GRUPO AXIS S.A.S."
                            ok, msg = enviar_titulo_email(email_destino, asunto, cuerpo, pdfs_generados[0][1], f"Titulo_{pdfs_generados[0][0]}.pdf", config_email)
                            if ok:
                                st.success(f"Primer titulo enviado. Se enviaran {len(pdfs_generados)} titulos en total.")
                            else:
                                st.error(msg)
                        else:
                            st.warning("Ingrese un correo destinatario")


def render_informes_tab():
    df = st.session_state.df_auditoria
    alertas = st.session_state.alertas_detectadas
    if df is None:
        st.info("Cargue un archivo primero.")
        return
    st.markdown('<p class="section-title" style="margin-top: 0.5rem;">Informe de Hallazgos</p>', unsafe_allow_html=True)
    ips_nombre = st.text_input("Nombre de la IPS", value=st.session_state.ips_seleccionada)
    periodo = st.selectbox("Periodo", ["Mensual", "Semanal", "Trimestral"])
    if st.button("Generar Informe", type="primary", use_container_width=True):
        df_alertas = pd.DataFrame(alertas) if alertas else pd.DataFrame(columns=["fila", "cups", "sexo", "tipo"])
        pdf_bytes = generar_informe_hallazgos(df_alertas, ips_nombre, periodo, st.session_state.user)
        if pdf_bytes:
            guardar_db({"ips": ips_nombre, "eps": "N/A", "no_factura": f"{len(alertas)} errores", "valor": "N/A", "errores": str(len(alertas)), "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "estado": "Informe Generado", "usuario": st.session_state.user})
            st.success(f"Informe generado: {len(alertas)} errores en periodo {periodo.lower()}.")
            st.download_button(label="Descargar Informe", data=pdf_bytes, file_name=f"Informe_{periodo}.pdf", mime="application/pdf", type="primary", use_container_width=True)


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
        pdf.cell(0, 6, f"Fecha: {ahora}", ln=1, align="R")
        pdf.ln(8)

        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(10, 26, 63)
        pdf.cell(0, 8, latin(f"INFORME DE HALLAZGOS - {periodo.upper()}"), ln=1, align="C")
        pdf.ln(4)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, latin(f"IPS: {ips_nombre}"), ln=1)
        pdf.ln(6)

        pdf.set_draw_color(92, 160, 242)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(8)

        pdf.multi_cell(0, 6, latin(f"Señores {ips_nombre}: Hemos detectado {total_errores} errores de digitacion este periodo ({periodo}). Observaciones: Mejorar la codificacion SOAT en el servicio de urgencias."))
        pdf.ln(8)

        if total_errores > 0:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(10, 26, 63)
            pdf.cell(0, 7, latin("Errores Detectados"), ln=1)
            pdf.ln(2)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(0, 0, 0)
            for _, a in df_alertas.iterrows():
                pdf.cell(0, 6, latin(f"- Fila {a.get('fila', '')}: {a.get('tipo', '')} | CUPS: {a.get('cups', '')}"), ln=1)

        pdf.ln(8)
        pdf.multi_cell(0, 6, latin("Informe generado por sistema aQario - Grupo AXIS S.A.S."))
        return pdf.output(dest="S").encode("latin-1")
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None


def render_gestion_usuarios():
    st.markdown('<p class="section-title" style="margin-top: 0.5rem;">Gestion de Usuarios</p>', unsafe_allow_html=True)
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown('<div class="upload-container">', unsafe_allow_html=True)
        st.markdown("**Crear Usuario**")
        with st.form("new_user_form"):
            new_user = st.text_input("Usuario", placeholder="ej: gestor_nuevo")
            new_pass = st.text_input("Contraseña", type="password")
            new_rol = st.selectbox("Perfil", ["Master", "Gestor", "Cliente IPS"])
            new_nombre = st.text_input("Nombre", placeholder="Juan Perez")
            new_eps = st.text_input("EPS Asignada", placeholder="Opcional")
            if st.form_submit_button("Crear", use_container_width=True, type="primary"):
                if len(new_pass) < 4:
                    st.error("Minimo 4 caracteres")
                elif not new_user:
                    st.error("Usuario obligatorio")
                else:
                    ok, msg = crear_usuario(new_user, new_pass, new_rol, new_nombre, new_eps if new_eps else None)
                    if ok:
                        st.session_state.usuarios = cargar_usuarios()
                        st.success(msg)
                    else:
                        st.error(msg)
        st.markdown('</div>', unsafe_allow_html=True)
    with col_g2:
        st.markdown('<div class="upload-container">', unsafe_allow_html=True)
        st.markdown("**Usuarios Registrados**")
        usuarios = st.session_state.usuarios
        df_users = pd.DataFrame([{"Usuario": u, "Rol": d["rol"], "Nombre": d["nombre"], "EPS": d.get("eps_asignada", "-")} for u, d in usuarios.items()])
        st.dataframe(df_users, use_container_width=True, hide_index=True)
        usuarios_eliminar = [u for u in usuarios if u != "admin"]
        if usuarios_eliminar:
            user_del = st.selectbox("Eliminar usuario:", usuarios_eliminar)
            if st.button("Eliminar", use_container_width=True):
                ok, msg = eliminar_usuario(user_del)
                if ok:
                    st.session_state.usuarios = cargar_usuarios()
                    st.success(msg)
                else:
                    st.error(msg)
        st.markdown('</div>', unsafe_allow_html=True)


def render_configuracion_tab():
    st.markdown('<p class="section-title" style="margin-top: 0.5rem;">Base de Datos de Recuperacion</p>', unsafe_allow_html=True)
    df_db = cargar_db()
    if not df_db.empty:
        ips_filter = ["Todas"] + df_db["ips"].unique().tolist()
        filtro = st.selectbox("Filtrar por IPS:", ips_filter)
        if filtro != "Todas":
            df_db = df_db[df_db["ips"] == filtro]
        render_paginated_df(df_db, key_prefix="db_records")
    else:
        st.info("No hay registros aun.")

    st.markdown('<p class="section-title">Historial de Manuales</p>', unsafe_allow_html=True)
    if st.session_state.historial:
        st.dataframe(pd.DataFrame(st.session_state.historial), use_container_width=True, hide_index=True)
    else:
        st.info("Sin historial de cargas.")

    st.markdown('<p class="section-title">Logo Institucional</p>', unsafe_allow_html=True)
    uploaded_logo = st.file_uploader("Cargar Logo (.png)", type=["png"], key="logo_uploader")
    if uploaded_logo:
        with open(os.path.join(DIR_ACTUAL, "logo_aqario.png"), "wb") as f:
            f.write(uploaded_logo.getbuffer())
        st.success("Logo actualizado.")
    else:
        logo_path = os.path.join(DIR_ACTUAL, "logo_aqario.png")
        if os.path.exists(logo_path):
            st.image(logo_path, width=180)
        else:
            st.warning("Sin logo configurado.")

    st.markdown('<p class="section-title">Configuracion de Correo Electronico</p>', unsafe_allow_html=True)
    config = cargar_config_email()
    with st.container():
        st.markdown('<div class="upload-container">', unsafe_allow_html=True)
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            email_user = st.text_input("Correo Emisor", value=config.get("email", ""), placeholder="cartera@grupoaxis.com.co")
            email_pass = st.text_input("Contrasena de Aplicacion", type="password", value=config.get("password", ""), placeholder="Contraseña de aplicacion")
        with col_e2:
            smtp_server = st.text_input("Servidor SMTP", value=config.get("smtp_server", "smtp.gmail.com"))
            smtp_port = st.number_input("Puerto SMTP", value=config.get("smtp_port", 587), min_value=1, max_value=65535)
        email_enabled = st.checkbox("Habilitar envio automatico de titulos", value=config.get("enabled", False))
        if st.button("Guardar Configuracion de Correo", use_container_width=True, type="primary"):
            nuevo_config = {"smtp_server": smtp_server, "smtp_port": smtp_port, "email": email_user, "password": email_pass, "enabled": email_enabled}
            guardar_config_email(nuevo_config)
            st.success("Configuracion guardada. " + ("Envio automatico activado." if email_enabled else "Envio automatico desactivado."))
        st.markdown('</div>', unsafe_allow_html=True)


def render_portal_ips():
    st.markdown('<h1 class="main-header">Portal de IPS - Grupo AXIS</h1>', unsafe_allow_html=True)
    df = st.session_state.df_auditoria
    if df is None:
        st.info("No hay datos. Contacte al administrador.")
        return
    df, _, faltantes = validar_estructura(df)
    if not faltantes:
        df["VALOR_TOTAL"] = pd.to_numeric(df["VALOR_TOTAL"], errors="coerce").fillna(0).astype(int)
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("Total Titulos", f"{len(df):,}")
        with col_m2:
            st.metric("Proyeccion Liquidez", f"$ {df['VALOR_TOTAL'].sum():,.0f}", delta="Activos en cartera")
        with col_m3:
            st.metric("Promedio", f"$ {df['VALOR_TOTAL'].mean():,.0f}")
        df_display = df[["NUMERO_FACTURA", "NIT_EPS", "VALOR_TOTAL"]].copy()
        df_display["EPS"] = df_display["NIT_EPS"].apply(resolver_nombre_eps)
        df_display = df_display[["NUMERO_FACTURA", "EPS", "VALOR_TOTAL"]]
        df_display["ESTADO"] = "En Proceso"
        df_display["VALOR_TOTAL"] = df_display["VALOR_TOTAL"].apply(lambda x: f"$ {x:,.0f}")
        render_paginated_df(df_display, key_prefix="portal_ips")


def render_app():
    render_sidebar()
    if st.session_state.rol == "Cliente IPS":
        render_portal_ips()
    elif st.session_state.rol == "Master":
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["AUDITORIA", "TITULOS PDF", "INFORMES", "GESTION USUARIOS", "CONFIGURACION"])
        with tab1: render_auditoria_tab()
        with tab2: render_fabrica_pdf_tab()
        with tab3: render_informes_tab()
        with tab4: render_gestion_usuarios()
        with tab5: render_configuracion_tab()
    else:
        tab1, tab2, tab3 = st.tabs(["AUDITORIA", "TITULOS PDF", "INFORMES"])
        with tab1: render_auditoria_tab()
        with tab2: render_fabrica_pdf_tab()
        with tab3: render_informes_tab()


if not st.session_state.logged_in:
    render_login()
else:
    st.markdown('<p class="main-subheader">Sistema de Auditoria y Recuperacion de Cartera</p>', unsafe_allow_html=True)
    st.markdown('<h1 class="main-header">aQario</h1>', unsafe_allow_html=True)
    st.markdown('<p class="description-text">Plataforma interna para la auditoria, analisis y recuperacion de cartera del sector salud.</p>', unsafe_allow_html=True)
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    render_app()
    st.markdown('<p class="footer">&copy; 2026 Grupo AXIS S.A.S. | 902021366-2 | www.grupoaxis.com.co</p>', unsafe_allow_html=True)
