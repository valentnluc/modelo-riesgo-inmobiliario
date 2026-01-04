"""Generación de flujos de caja mensuales."""

import numpy as np
import pandas as pd
from typing import Tuple, Optional

from presets import generar_curva_ventas_acumulada, generar_curva_inversion
from constants import DEFAULT_N_POINTS


def construir_flujo_caja(
    parametros_ventas: dict,
    parametros_costos: dict,
    parametros_tierra: dict,
    meses: Tuple[int, int] = (0, 36),
    meses_obra: Optional[Tuple[int, int]] = None,
    n_puntos: int = DEFAULT_N_POINTS,
) -> pd.DataFrame:
    """
    Construye el flujo de caja.
    
    1. Curva de ventas
    2. Curva de egresos (obra)
    3. Cronograma tierra
    4. Neto = Ventas - Obra - Tierra
    """
    # 1. Generar curva de ventas
    x, ventas_acum = generar_curva_ventas_acumulada(
        parametros=parametros_ventas,
        meses=meses,
        n_puntos=n_puntos
    )
    ventas_mensuales = np.diff(ventas_acum, prepend=0.0)
    
    # 2. Generar curva de costos de obra
    periodo_obra = meses_obra if meses_obra else meses
    _, obra_acum = generar_curva_inversion(
        parametros=parametros_costos,
        meses=periodo_obra,
        n_puntos=n_puntos
    )
    # Interpolar al eje X de ventas si es necesario
    x_obra = np.linspace(periodo_obra[0], periodo_obra[1], n_puntos)
    obra_acum_interp = np.interp(x, x_obra, obra_acum)
    obra_mensual = np.diff(obra_acum_interp, prepend=0.0)
    
    # 3. Generar cronograma de tierra
    tierra_mensual = _crear_cronograma_tierra(parametros_tierra, meses, x, n_puntos)
    
    # 4. Calcular flujo neto
    flujo_neto = ventas_mensuales - obra_mensual - tierra_mensual
    
    # 5. Calcular cash acumulado
    cash_acumulado = np.cumsum(flujo_neto)
    
    return pd.DataFrame({
        'Mes': x,
        'Ventas': ventas_mensuales,
        'Egresos_Obra': obra_mensual,
        'Egresos_Tierra': tierra_mensual,
        'Flujo_Neto': flujo_neto,
        'Cash_Acumulado': cash_acumulado
    })


def calcular_flujo_rapido(
    ventas_norm: np.ndarray,
    obra_norm: np.ndarray,
    tierra_mensual: np.ndarray,
    total_ventas: float,
    total_obra: float,
    eje_x: np.ndarray
) -> pd.DataFrame:
    """Optimización: usa curvas normalizadas pre-calculadas para escalar totales."""
    # Escalar curvas
    ventas = ventas_norm * total_ventas
    obra = obra_norm * total_obra
    
    # Calcular netos
    flujo_neto = ventas - obra - tierra_mensual
    cash_acumulado = np.cumsum(flujo_neto)
    
    return pd.DataFrame({
        'Mes': eje_x,
        'Ventas': ventas,
        'Egresos_Obra': obra,
        'Egresos_Tierra': tierra_mensual,
        'Flujo_Neto': flujo_neto,
        'Cash_Acumulado': cash_acumulado
    })


def _crear_cronograma_tierra(parametros_tierra: dict, meses: Tuple[int, int], 
                             x: np.ndarray, n_puntos: int) -> np.ndarray:
    """
    Crea el cronograma de pagos de tierra.
    
    Soporta:
        - tipo='canje': No hay pagos en efectivo
        - tipo='pago': Lista de pagos con mes y porcentaje
    """
    n_meses = int(meses[1]) + 1
    cronograma = np.zeros(n_meses)
    
    valor_total = parametros_tierra.get('valor_total', 0)
    
    # Si es canje, no hay pagos
    if parametros_tierra.get('tipo') == 'canje':
        return np.zeros(len(x))
    
    # Procesar pagos
    pagos = parametros_tierra.get('pagos', [])
    for pago in pagos:
        mes = int(pago['mes'])
        if 0 <= mes < n_meses:
            cronograma[mes] += valor_total * pago['pct']
    
    # Interpolar al eje X
    tierra_acum = np.cumsum(cronograma)
    meses_int = np.arange(n_meses)
    tierra_interp = np.interp(x, meses_int, tierra_acum)
    
    return np.diff(tierra_interp, prepend=0.0)
