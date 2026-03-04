"""Generación de flujos de caja mensuales."""

import numpy as np
import pandas as pd
from typing import Tuple, Optional

from presets import generar_curva_ventas_acumulada, generar_curva_inversion


def construir_flujo_caja(
    parametros_ventas: dict,
    parametros_costos: dict,
    parametros_tierra: dict,
    meses: Tuple[int, int] = (0, 36),
    meses_obra: Optional[Tuple[int, int]] = None,
) -> pd.DataFrame:
    """
    Construye el flujo de caja utilizando matemática discreta de meses enteros.
    """
    # 1. Generar curva de ventas
    x, ventas_acum = generar_curva_ventas_acumulada(
        parametros=parametros_ventas,
        meses=meses
    )
    ventas_mensuales = np.diff(ventas_acum, prepend=0.0)
    
    # 2. Generar curva de costos de obra
    periodo_obra = meses_obra if meses_obra else meses
    x_obra, obra_acum = generar_curva_inversion(
        parametros=parametros_costos,
        meses=periodo_obra
    )
    
    obra_mensual = np.zeros_like(x, dtype=float)
    obra_mensual_local = np.diff(obra_acum, prepend=0.0)
    
    # Mapear los flujos de obra (que pueden tener distinto inicio/fin) al eje x principal
    for ix_local, mes_val in enumerate(x_obra):
        if mes_val in x:
            idx_global = np.where(x == mes_val)[0][0]
            obra_mensual[idx_global] = obra_mensual_local[ix_local]
            
    # 3. Generar cronograma de tierra
    tierra_mensual = _crear_cronograma_tierra(parametros_tierra, meses, x)
    
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


def _crear_cronograma_tierra(parametros_tierra: dict, meses: Tuple[int, int], x: np.ndarray) -> np.ndarray:
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
    
    tierra_mensual = np.zeros(len(x))
    
    # Asignar a los meses correspondientes en x
    for m in range(n_meses):
        if m in x:
            idx = np.where(x == m)[0][0]
            tierra_mensual[idx] = cronograma[m]
            
    return tierra_mensual
