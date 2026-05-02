import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)

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


def generar_fecha(base, max_dias=180):
    delta = np.random.randint(0, max_dias)
    return (base - timedelta(days=delta)).strftime("%Y-%m-%d")


def generar_datos_perfectos(n=20):
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
    }
    return pd.DataFrame(data)


def generar_datos_con_errores(n=20):
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


if __name__ == "__main__":
    df_perfectos = generar_datos_perfectos()
    df_perfectos.to_excel("datos_perfectos.xlsx", index=False)
    print("datos_perfectos.xlsx creado con exito.")

    df_errores = generar_datos_con_errores()
    df_errores.to_excel("datos_con_errores.xlsx", index=False)
    print("datos_con_errores.xlsx creado con exito.")
