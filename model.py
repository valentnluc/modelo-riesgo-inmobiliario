"""
Módulo principal: Configuración y Fachada.

Define la configuración central del proyecto (ProjectConfig) y expone
las funciones de alto nivel para ejecutar simulaciones.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Tuple, Dict, Any, Optional

from cashflow import construir_flujo_caja
from metrics import calcular_van, calcular_tir, calcular_max_deficit, calcular_break_even
from simulation import simular
from constants import DEFAULT_ANNUAL_RATE

@dataclass
class ProjectConfig:
    """
    Configuración central del proyecto.
    Convierte inputs de negocio (m2, FOT) a parámetros de simulación.
    """
    # Inputs Proyecto
    m2_terreno: float
    fot: float
    efficiency: float = 0.80
    
    # Inputs Cronograma
    duracion_proy: int = 36
    inicio_obra: int = 0
    duracion_obra: int = 30
    
    # Inputs Ventas
    precio_promedio: float = 1800.0  # USD/m2
    # Presets o parámetros manuales de curva
    ventas_preset: Optional[Dict] = None 
    ventas_custom: Optional[Dict] = None

    # Inputs Costos
    costo_m2: float = 950.0 # USD/m2
    costos_preset: Optional[Dict] = None
    costos_custom: Optional[Dict] = None
    
    # Inputs Tierra
    tierra_preset: Optional[Dict] = None # diccionario con 'tipo' y datos
    tierra_valor: float = 350000.0
    canje_pct: float = 0.0 # 0.0 a 1.0

    @property
    def m2_construidos(self) -> float:
        return self.m2_terreno * self.fot

    @property
    def m2_vendibles(self) -> float:
        return self.m2_construidos * self.efficiency

    @property
    def ventas_brutas_totales(self) -> float:
        return self.m2_vendibles * self.precio_promedio

    @property
    def costo_obra_total(self) -> float:
        return self.m2_construidos * self.costo_m2

    @property
    def meses_totales(self) -> Tuple[int, int]:
        return (0, self.duracion_proy)

    @property
    def meses_obra(self) -> Tuple[int, int]:
        return (self.inicio_obra, self.inicio_obra + self.duracion_obra)

    def generar_parametros_simulacion(self) -> Tuple[Dict, Dict, Dict]:
        # TODO: Mover lógica de validación de presets a un metodo separado si crece.
        # Retorna: (params_ventas, params_costos, params_tierra) para el motor.
        # 1. Ventas
        # Ajustamos el total por el canje si aplica
        ventas_netas = self.ventas_brutas_totales * (1.0 - self.canje_pct)
        
        if self.ventas_preset:
            p_ventas = self.ventas_preset.copy()
            p_ventas['area_n'] = ventas_netas
        elif self.ventas_custom:
            p_ventas = self.ventas_custom.copy()
            p_ventas['area_n'] = ventas_netas
        else:
            # Fallback
            p_ventas = {'area_n': ventas_netas}

        # 2. Costos
        total_capex = self.costo_obra_total
        
        if self.costos_preset:
            p_costos = self.costos_preset.copy()
            p_costos['limite_n'] = total_capex
        elif self.costos_custom:
            p_costos = self.costos_custom.copy()
            p_costos['limite_n'] = total_capex
            
            # Ajuste de moda relativa a absoluta si viene del UI "custom"
            # En UI custom, la moda es relativa al inicio de obra
            # Si el custom viene con 'moda_pct', no hacemos nada
            # Si viene 'moda' absoluta, asumimos que ya está ajustada o es inputs raw
            # Para mantener compatibilidad con UI actual que pasa 'moda' relativa a inicio:
            if 'moda' in p_costos and 'moda_pct' not in p_costos:
                 # Check if this looks like relative offset (small number) or absolute month
                 # Logic de UI actual: 'moda': inicio_obra + curve_p['moda']
                 pass
        else:
            p_costos = {'limite_n': total_capex}

        # 3. Tierra
        p_tierra = {}
        if self.canje_pct > 0:
             p_tierra = {'tipo': 'canje', 'canje_pct_m2': self.canje_pct}
        elif self.tierra_preset:
             p_tierra = self.tierra_preset.copy()
             p_tierra['valor_total'] = self.tierra_valor
        
        return p_ventas, p_costos, p_tierra

def ejecutar_deterministico(
    parametros_ventas: dict,
    parametros_costos: dict,
    parametros_tierra: dict,
    meses_totales: Tuple[int, int],
    meses_obra: Tuple[int, int],
    tasa_anual: float = DEFAULT_ANNUAL_RATE
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """Correr un escenario determinístico único."""
    # Construir flujo
    df = construir_flujo_caja(
        parametros_ventas, 
        parametros_costos, 
        parametros_tierra, 
        meses_totales, 
        meses_obra
    )
    
    # Calcular métricas
    van = calcular_van(df, tasa_anual)
    tir = calcular_tir(df)
    deficit, mes_deficit = calcular_max_deficit(df)
    break_even = calcular_break_even(df)
    
    metricas = {
        'VAN': van,
        'TIR': tir,
        'MaxFinancingNeed': deficit,
        'MaxFinancingMonth': mes_deficit,
        'BreakEvenMonth': break_even
    }
    
    return df, metricas


def ejecutar_montecarlo(
    n_iteraciones: int,
    parametros_ventas: dict,
    parametros_costos: dict,
    parametros_tierra: dict,
    meses_totales: Tuple[int, int],
    meses_obra: Tuple[int, int],
    tasa_descuento: float = DEFAULT_ANNUAL_RATE,
    variacion_ventas: float = 0.0,
    variacion_costos: float = 0.0,
    semilla: Optional[int] = None,
    retornar_curvas: bool = True,
    max_curvas: int = 200
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Wrapper para lanzar la simulación Monte Carlo."""
    return simular(
        n_iteraciones=n_iteraciones,
        parametros_ventas=parametros_ventas,
        parametros_costos=parametros_costos,
        parametros_tierra=parametros_tierra,
        meses=meses_totales,
        meses_obra=meses_obra,
        tasa_descuento=tasa_descuento,
        variacion_ventas=variacion_ventas,
        variacion_costos=variacion_costos,
        semilla=semilla,
        retornar_curvas=retornar_curvas,
        max_curvas=max_curvas,
        mostrar_progreso=True
    )


def ejecutar_analisis_sensibilidad(
    parametros_ventas: dict,
    parametros_costos: dict,
    parametros_tierra: dict,
    meses_totales: Tuple[int, int],
    meses_obra: Tuple[int, int],
    tasa_anual: float,
    pasos: int = 5
) -> pd.DataFrame:
    """Matriz de sensibilidad Precio vs Costo (+/- 20% en pasos n)."""
    # Rango +/- 20%
    variaciones = np.linspace(-0.20, 0.20, pasos)
    
    resultados = []
    
    base_ventas = parametros_ventas.get('area_n', 1000)
    base_costos = parametros_costos.get('limite_n', 1000)
    
    for var_v in variaciones:
        for var_c in variaciones:
            # Ajustar params
            p_ventas = parametros_ventas.copy()
            p_ventas['area_n'] = base_ventas * (1 + var_v)
            
            p_costos = parametros_costos.copy()
            p_costos['limite_n'] = base_costos * (1 + var_c)
            
            # Ejecutar modelo
            df = construir_flujo_caja(
                p_ventas, p_costos, parametros_tierra, 
                meses_totales, meses_obra
            )
            
            van = calcular_van(df, tasa_anual)
            tir = calcular_tir(df)
            
            resultados.append({
                'Variacion_Precio': var_v,
                'Variacion_Costo': var_c,
                'VAN': van,
                'TIR': tir
            })
            
    return pd.DataFrame(resultados)
