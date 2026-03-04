"""
Motor de simulación híbrido (Determinístico y Monte Carlo).
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional, Union
from tqdm import tqdm

from cashflow import construir_flujo_caja
from metrics import calcular_van, calcular_tir
from constants import DEFAULT_ANNUAL_RATE
from presets import generar_curva_ventas_acumulada, generar_curva_inversion


def simular(
    n_iteraciones: int,
    parametros_ventas: dict,
    parametros_costos: dict,
    parametros_tierra: dict,
    meses: Tuple[int, int] = (0, 36),
    meses_obra: Optional[Tuple[int, int]] = None,
    tasa_descuento: float = DEFAULT_ANNUAL_RATE,
    variacion_ventas: float = 0.0,
    variacion_costos: float = 0.0,
    semilla: Optional[int] = None,
    mostrar_progreso: bool = False,
    retornar_curvas: bool = False,
    max_curvas: int = 200
) -> Union[pd.DataFrame, Tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Simula N escenarios variando ventas y costos.
    """
    # Fast-path para modo determinístico (1 iteración sin varianza)
    if n_iteraciones == 1 and variacion_ventas == 0 and variacion_costos == 0:
        df = construir_flujo_caja(parametros_ventas, parametros_costos, parametros_tierra, meses, meses_obra)
        metrics = {
            'sim_id': 0,
            'VAN': calcular_van(df, tasa_descuento),
            'TIR': calcular_tir(df),
            'Total_Ventas': parametros_ventas.get('area_n', pd.NA),
            'Total_Costo': parametros_costos.get('limite_n', pd.NA)
        }
        df_res = pd.DataFrame([metrics])
        if retornar_curvas:
            df['sim_id'] = 0
            return df_res, df
        return df_res

    # PRE-CALCULO: Curvas normalizadas para evitar llamar a scipy.stats en el loop
    
    # 1. Ventas Normalizada (Total=1.0)
    # Creamos copia con area_n=1.0 para normalizar
    params_ventas_norm = {**parametros_ventas, 'area_n': 1.0}
    eje_x, ventas_acum_norm = generar_curva_ventas_acumulada(
        parametros=params_ventas_norm,
        meses=meses
    )
    ventas_norm_mensual = np.diff(ventas_acum_norm, prepend=0.0)
    
    # 2. Costos Normalizada (Total=1.0)
    periodo_obra = meses_obra if meses_obra else meses
    params_costos_norm = {**parametros_costos, 'limite_n': 1.0}
    
    x_obra, obra_acum_norm = generar_curva_inversion(
        parametros=params_costos_norm,
        meses=periodo_obra
    )
    # Interpolar al eje X principal y calcular mensual
    obra_norm_mensual = np.zeros_like(eje_x, dtype=float)
    obra_mensual_local = np.diff(obra_acum_norm, prepend=0.0)
    
    for ix_local, mes_val in enumerate(x_obra):
        if mes_val in eje_x:
            idx_global = np.where(eje_x == mes_val)[0][0]
            obra_norm_mensual[idx_global] = obra_mensual_local[ix_local]
    
    # 3. Tierra (Fijo)
    # Instanciar dummy para extraer tierra. Ya no usa pandas gracias al cambio, devuelve dataframe pero extraemos:
    df_dummy = construir_flujo_caja({**parametros_ventas, 'area_n': 0}, {**parametros_costos, 'limite_n': 0}, parametros_tierra, meses, meses_obra)
    tierra_mensual = df_dummy['Egresos_Tierra'].values
    
    # Loop Monte Carlo
    
    rng = np.random.default_rng(semilla)
    ventas_base = parametros_ventas.get('area_n', 1000)
    costos_base = parametros_costos.get('limite_n', 1000)
    
    resultados = []
    curvas = []
    
    rango = range(n_iteraciones)
    if mostrar_progreso:
        rango = tqdm(rango, desc="Simulando", unit="sim")
    
    for i in rango:
        # Variar montos totales
        v_sim = max(0.0, rng.normal(ventas_base, ventas_base * variacion_ventas)) if variacion_ventas > 0 else ventas_base
        c_sim = max(0.0, rng.normal(costos_base, costos_base * variacion_costos)) if variacion_costos > 0 else costos_base
        
        # Flujos base matemáticos (pura aritmética de NumPy)
        ventas_arr = ventas_norm_mensual * v_sim
        obra_arr = obra_norm_mensual * c_sim
        flujo_neto_arr = ventas_arr - obra_arr - tierra_mensual
        
        # Métricas directas a matrices
        datos_metrics = (flujo_neto_arr, eje_x)
        van_val = calcular_van(datos_metrics, tasa_descuento)
        tir_val = calcular_tir(datos_metrics) # Ya no hay limite de a<100, NumPy rinde bien
        
        resultados.append({
            'sim_id': i,
            'VAN': van_val,
            'TIR': tir_val,
            'Total_Ventas': v_sim,
            'Total_Costo': c_sim
        })
        
        if retornar_curvas and i < max_curvas:
            curvas.append(pd.DataFrame({
                'Mes': eje_x,
                'Ventas': ventas_arr,
                'Egresos_Obra': obra_arr,
                'Egresos_Tierra': tierra_mensual,
                'Flujo_Neto': flujo_neto_arr,
                'Cash_Acumulado': np.cumsum(flujo_neto_arr),
                'sim_id': i
            }))
    
    df_resultados = pd.DataFrame(resultados)
    
    if retornar_curvas:
        df_curvas = pd.concat(curvas) if curvas else pd.DataFrame()
        return df_resultados, df_curvas
    
    return df_resultados
