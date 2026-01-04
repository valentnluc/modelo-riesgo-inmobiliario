
import numpy as np
from scipy.stats import skewnorm
from scipy.integrate import simpson
from scipy.optimize import fmin

VENTAS_PRESETS = {
    "pozo_clasica": {
        "descripcion": "Ventas lentas al inicio, aceleran hacia posesión (Moda=50%, Alpha=2.5)",
        "moda_pct": 0.50, # Was 18 / 36
        "alpha": 2.5,
        "scale_pct": 0.22, # Was 8 / 36
    },
    "preventa_fuerte": {
        "descripcion": "Alta absorción temprana (Moda=30%, Alpha=1.2)",
        "moda_pct": 0.30, # Was 10 / 36
        "alpha": 1.2,
        "scale_pct": 0.17, # Was 6 / 36
    },
    "post_obra": {
        "descripcion": "Ventas mayormente terminada la obra (Moda=70%, Alpha=3.5)",
        "moda_pct": 0.70, # Was 26 / 36
        "alpha": 3.5,
        "scale_pct": 0.28, # Was 10 / 36
    },
}

COSTOS_PRESETS = {
    "s_estandar": {
        "descripcion": "Curva S estándar, ejecución equilibrada (Moda=55%, Scale=25%)",
        "moda_pct": 0.55, # Was 20 / 36
        "alpha": -0.5,
        "scale_pct": 0.25, # Was 9 / 36
    },
    "inicio_pesado": {
        "descripcion": "Gasto fuerte al inicio (Estructura/Acopios) (Moda=45%)",
        "moda_pct": 0.45, # Was 16 / 36
        "alpha": -2.0,
        "scale_pct": 0.22, # Was 8 / 36
    },
    "cola_larga": {
        "descripcion": "Cierre lento y terminaciones largas (Moda=65%)",
        "moda_pct": 0.65, # Was 24 / 36
        "alpha": 1.5,
        "scale_pct": 0.30, # Was 11 / 36
    },
}

TIERRA_PRESETS = {
    "canje_30": {
        "descripcion": "Canje del 30% del proyecto (No genera flujo de efectivo saliente)",
        "tipo": "canje",
        "canje_pct_m2": 0.30,
    },
    "contado": {
        "descripcion": "Pago 100% al inicio (Mes 0)",
        "tipo": "pago",
        "pagos": [
            {"mes": 0, "pct": 1.0},
        ],
    },
    "cuotas": {
        "descripcion": "Anticipo 30% + Pago Mes 12 (30%) + Pago Mes 24 (40%)",
        "tipo": "pago",
        "pagos": [
            {"mes": 0,  "pct": 0.30},
            {"mes": 12, "pct": 0.30},
            {"mes": 24, "pct": 0.40},
        ],
    },
}


def calcular_loc(target_mode: float, alpha: float, scale: float) -> float:
    m0 = fmin(lambda x: -skewnorm.pdf(x, alpha, loc=0, scale=1), 0.0, disp=False)[0]
    return target_mode - (scale * m0)


def generar_curva_ventas(parametros: dict, meses=(0, 36), n_puntos: int = 500):
    inicio, fin = meses
    duracion = fin - inicio
    if duracion <= 0:
        return np.linspace(inicio, fin, n_puntos), np.zeros(n_puntos)
        
    x = np.linspace(inicio, fin, n_puntos)
    
    # Handle both relative (new) and absolute (legacy/custom) params
    if 'moda_pct' in parametros:
        mode = inicio + (parametros['moda_pct'] * duracion)
        scale = parametros.get('scale_pct', 0.25) * duracion
    else:
        # Fallback or manual override
        mode = parametros.get('moda', inicio + duracion/2)
        scale = parametros.get('scale', duracion/4)

    alpha = parametros.get('alpha', 0)
    total_val = parametros.get('area_n', 1.0)

    # Ensure scale is not zero or negative
    scale = max(0.1, scale)

    loc = calcular_loc(mode, alpha, scale)
    y_base = skewnorm.pdf(x, alpha, loc=loc, scale=scale)
    
    area = simpson(y_base, x)
    if area <= 1e-9:
        return x, np.zeros_like(x)
        
    y = y_base * (total_val / area)
    
    return x, y


def generar_curva_ventas_acumulada(parametros: dict, meses=(0, 36), n_puntos: int = 500):
    inicio, fin = meses
    duracion = fin - inicio
    if duracion <= 0:
        return np.linspace(inicio, fin, n_puntos), np.zeros(n_puntos)

    x = np.linspace(inicio, fin, n_puntos)
    
    if 'moda_pct' in parametros:
        mode = inicio + (parametros['moda_pct'] * duracion)
        scale = parametros.get('scale_pct', 0.25) * duracion
    else:
        mode = parametros.get('moda', inicio + duracion/2)
        scale = parametros.get('scale', duracion/4)

    # Sanity checks
    scale = max(0.1, scale)
    
    alpha = parametros.get('alpha', 0)
    total_val = parametros.get('area_n', 1.0)
    
    loc = calcular_loc(mode, alpha, scale)
    
    y_cdf = skewnorm.cdf(x, alpha, loc=loc, scale=scale)
    
    # Normalize to ensure we reach exactly total_val
    max_cdf = y_cdf[-1]
    
    # Corregir offset para arrancar en 0
    min_cdf = y_cdf[0]
    
    if (max_cdf - min_cdf) <= 1e-9:
        return x, np.zeros_like(x)
        
    # Scale (0 to 1) over the viewed window
    y_scaled = ((y_cdf - min_cdf) / (max_cdf - min_cdf)) * total_val
    
    # Normalizamos el rango visible de 0 a total_val.
    # Esto fuerza que la curva arranque en 0 al inicio del proyecto.
    
    return x, y_scaled


def generar_curva_inversion(parametros: dict, meses=(0, 36), n_puntos: int = 500):
    p_copy = parametros.copy()
    p_copy['area_n'] = parametros.get('limite_n', 1.0)
    
    return generar_curva_ventas_acumulada(p_copy, meses, n_puntos)


def crear_cronograma_tierra(parametros_tierra: dict, rango_meses: tuple) -> np.ndarray:
    n_meses = int(rango_meses[1]) + 1
    cronograma = np.zeros(n_meses)
    
    total_value = parametros_tierra.get('valor_total', 0)
    
    if parametros_tierra.get('tipo') == 'canje':
        return cronograma
        
    pagos = parametros_tierra.get('pagos', [])
    for p in pagos:
        m = int(p['mes'])
        if 0 <= m < n_meses:
            cronograma[m] += total_value * p['pct']
            
    return cronograma
