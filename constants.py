"""Constantes globales, configuración por defecto y helpers de formato."""

# SIMULACIÓN

DEFAULT_ANNUAL_RATE = 0.10       # Tasa de descuento por defecto (10%)
DEFAULT_N_POINTS = 500           # Puntos para discretización de curvas
DEFAULT_PROJECT_MONTHS = 36      # Duración típica de un proyecto
IRR_GUESS_BOUNDS = (-0.99, 10.0) # Límites para búsqueda de TIR


# COLORES / TEMA

COLORS = {
    # Colores principales
    'primary': '#ff4b4b',      # Rojo Streamlit
    'secondary': '#0068c9',    # Azul
    'tertiary': '#83c9ff',     # Azul claro
    'quaternary': '#29b09d',   # Verde teal
    
    # Grises para UI
    'text': '#262730',
    'text_light': '#808495',
    'text_muted': '#808495',    # Alias - para compatibilidad viz.py
    'border': '#e6e6e6',
    'background': '#ffffff',
    'background_alt': '#f0f2f6',
    
    # Alias
    'brand': '#0068c9',        # Alias - para compatibilidad viz.py (Blue)
}

# Alias para gráficos de flujos
COLOR_INCOME = COLORS['secondary']      # Azul - ingresos
COLOR_EXPENSE = COLORS['primary']       # Rojo - egresos
COLOR_NET = COLORS['text']              # Negro - flujo neto
COLOR_ACCUM = COLORS['quaternary']      # Teal - acumulado


# CONFIG GRÁFICOS

CHART_CONFIG = {
    'font': 'sans-serif',
    'title_font_size': 14,
    'subtitle_font_size': 11,
    'axis_label_font_size': 10,
    'axis_title_font_size': 11,
    'legend_font_size': 10,
}

CHART_WIDTH = 700
CHART_HEIGHT_MAIN = 350
CHART_HEIGHT_SMALL = 280


# FORMATO

def format_currency(value: float) -> str:
    """Formato corto: $1.5M, $250K."""
    abs_val = abs(value)
    sign = '-' if value < 0 else ''
    
    if abs_val >= 1_000_000:
        return f"{sign}${abs_val/1_000_000:.1f}M"
    elif abs_val >= 1_000:
        return f"{sign}${abs_val/1_000:.0f}K"
    else:
        return f"{sign}${abs_val:.0f}"


def format_percent(value: float) -> str:
    """Formato porcentaje: 15.0%."""
    if value is None:
        return "N/A"
    return f"{value*100:.1f}%"
