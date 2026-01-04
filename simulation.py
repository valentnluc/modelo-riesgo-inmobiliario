"""
Motor de simulación híbrido (Determinístico y Monte Carlo).
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional, Union
from tqdm import tqdm

from cashflow import construir_flujo_caja, calcular_flujo_rapido
from metrics import calcular_van, calcular_tir
from constants import DEFAULT_ANNUAL_RATE, DEFAULT_N_POINTS
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
        meses=meses,
        n_puntos=DEFAULT_N_POINTS
    )
    ventas_norm_mensual = np.diff(ventas_acum_norm, prepend=0.0)
    
    # 2. Costos Normalizada (Total=1.0)
    periodo_obra = meses_obra if meses_obra else meses
    params_costos_norm = {**parametros_costos, 'limite_n': 1.0}
    
    _, obra_acum_norm = generar_curva_inversion(
        parametros=params_costos_norm,
        meses=periodo_obra,
        n_puntos=DEFAULT_N_POINTS
    )
    # Interpolar al eje X principal
    x_obra = np.linspace(periodo_obra[0], periodo_obra[1], DEFAULT_N_POINTS)
    obra_acum_interp = np.interp(eje_x, x_obra, obra_acum_norm)
    obra_norm_mensual = np.diff(obra_acum_interp, prepend=0.0)
    
    # 3. Tierra (Fijo)
    # FIXME: Instanciar dummy para extraer tierra es sub-optimo pero simple.
    dummy_params_v = {**parametros_ventas, 'area_n': 0}
    dummy_params_c = {**parametros_costos, 'limite_n': 0}
    df_dummy = construir_flujo_caja(dummy_params_v, dummy_params_c, parametros_tierra, meses, meses_obra)
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
        if variacion_ventas > 0:
            v_sim = max(0.0, rng.normal(ventas_base, ventas_base * variacion_ventas))
        else:
            v_sim = ventas_base
            
        if variacion_costos > 0:
            c_sim = max(0.0, rng.normal(costos_base, costos_base * variacion_costos))
        else:
            c_sim = costos_base
        
        # Calcular usando curvas pre-calculadas (Vectorizado = Rápido)
        df = calcular_flujo_rapido(
            ventas_norm_mensual, 
            obra_norm_mensual, 
            tierra_mensual, 
            v_sim, 
            c_sim, 
            eje_x
        )
        
        # Métricas
        tir_valor = calcular_tir(df) if i < 100 else None
        
        resultados.append({
            'sim_id': i,
            'VAN': calcular_van(df, tasa_descuento),
            'TIR': tir_valor,
            'Total_Ventas': v_sim,
            'Total_Costo': c_sim
        })
        
        if retornar_curvas and i < max_curvas:
            df_curva = df.copy()
            df_curva['sim_id'] = i
            curvas.append(df_curva)
    
    df_resultados = pd.DataFrame(resultados)
    
    if retornar_curvas:
        df_curvas = pd.concat(curvas) if curvas else pd.DataFrame()
        return df_resultados, df_curvas
    
    return df_resultados
