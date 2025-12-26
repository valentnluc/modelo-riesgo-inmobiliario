
import numpy as np
from scipy.stats import skewnorm
from scipy.integrate import simpson
from scipy.optimize import fmin

VENTAS_PRESETS = {
    "pozo_clasica": {
        "descripcion": "Ventas lentas al inicio, aceleran hacia posesión (Moda=18, Alpha=2.5)",
        "moda": 18,
        "alpha": 2.5,
        "scale": 8,
    },
    "preventa_fuerte": {
        "descripcion": "Alta absorción temprana (Moda=10, Alpha=1.2)",
        "moda": 10,
        "alpha": 1.2,
        "scale": 6,
    },
    "post_obra": {
        "descripcion": "Ventas mayormente terminada la obra (Moda=26, Alpha=3.5)",
        "moda": 26,
        "alpha": 3.5,
        "scale": 10,
    },
}

COSTOS_PRESETS = {
    "s_estandar": {
        "descripcion": "Curva S estándar, ejecución equilibrada (Moda=20)",
        "moda": 20,
        "alpha": -0.5,
        "scale": 9,
    },
    "inicio_pesado": {
        "descripcion": "Gasto fuerte al inicio (Estructura/Acopios) (Moda=16)",
        "moda": 16,
        "alpha": -2.0,
        "scale": 8,
    },
    "cola_larga": {
        "descripcion": "Cierre lento y terminaciones largas (Moda=24)",
        "moda": 24,
        "alpha": 1.5,
        "scale": 11,
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


def generate_sales_curve(params: dict, months=(0, 36), n_points: int = 500):
    x = np.linspace(months[0], months[1], n_points)
    
    mode = params.get('moda', months[1]/2)
    alpha = params.get('alpha', 0)
    scale = params.get('scale', months[1]/4)
    total_val = params.get('area_n', 1.0)

    loc = calcular_loc(mode, alpha, scale)
    y_base = skewnorm.pdf(x, alpha, loc=loc, scale=scale)
    
    area = simpson(y_base, x)
    if area <= 1e-9:
        return x, np.zeros_like(x)
        
    y = y_base * (total_val / area)
    
    return x, y


def generate_sales_cumulative(params: dict, months=(0, 36), n_points: int = 500):
    x = np.linspace(months[0], months[1], n_points)
    
    mode = params.get('moda', months[1]/2)
    alpha = params.get('alpha', 0)
    scale = params.get('scale', months[1]/4)
    total_val = params.get('area_n', 1.0)
    
    loc = calcular_loc(mode, alpha, scale)
    
    y_cdf = skewnorm.cdf(x, alpha, loc=loc, scale=scale)
    
    max_cdf = y_cdf[-1]
    if max_cdf <= 1e-9:
        return x, np.zeros_like(x)
        
    y_scaled = (y_cdf / max_cdf) * total_val
    return x, y_scaled


def generate_investment_curve(params: dict, months=(0, 36), n_points: int = 500):
    p_copy = params.copy()
    p_copy['area_n'] = params.get('limite_n', 1.0)
    
    return generate_sales_cumulative(p_copy, months, n_points)


def create_land_schedule(land_params: dict, months_range: tuple) -> np.ndarray:
    n_months = int(months_range[1]) + 1
    schedule = np.zeros(n_months)
    
    total_value = land_params.get('valor_total', 0)
    
    if land_params.get('tipo') == 'canje':
        return schedule
        
    pagos = land_params.get('pagos', [])
    for p in pagos:
        m = int(p['mes'])
        if 0 <= m < n_months:
            schedule[m] += total_value * p['pct']
            
    return schedule
