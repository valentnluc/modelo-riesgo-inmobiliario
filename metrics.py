"""
Métricas financieras (VAN, TIR, Déficit, Break-even).
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional, Union
from scipy.optimize import brentq

def calcular_van(datos: Union[pd.DataFrame, Tuple[np.ndarray, np.ndarray]], tasa_anual: float) -> float:
    """
    Calcula el Valor Actual Neto (VAN).
    VAN = Σ (flujo_t / (1 + r)^t)
    Puede recibir un DataFrame o una tupla de arreglos (flujos, meses).
    """
    # Convertir tasa anual a mensual
    tasa_mensual = (1 + tasa_anual) ** (1/12) - 1
    
    if isinstance(datos, pd.DataFrame):
        flujos = datos['Flujo_Neto'].values
        meses = datos['Mes'].values
    else:
        flujos, meses = datos
        
    # Factor de descuento para cada mes
    factores = (1 + tasa_mensual) ** meses
    
    # Suma de flujos descontados
    return float(np.sum(flujos / factores))


def calcular_tir(datos: Union[pd.DataFrame, Tuple[np.ndarray, np.ndarray]]) -> Optional[float]:
    """
    Calcula la Tasa Interna de Retorno (TIR).
    Retorna la tasa que hace VAN=0, o None si no converge.
    Puede recibir un DataFrame o una tupla de arreglos (flujos, meses).
    """
    if isinstance(datos, pd.DataFrame):
        flujos = datos['Flujo_Neto'].values
        meses = datos['Mes'].values
    else:
        flujos, meses = datos
        
    # Fast-fail: verificar si hay cambio de signo en los flujos
    # Si todos los flujos son negativos o todos positivos, no hay TIR
    if not (np.any(flujos > 0) and np.any(flujos < 0)):
        return None
    
    # Fast-fail: si la suma total es muy negativa, no hay TIR realista
    suma_total = np.sum(flujos)
    if suma_total < -np.sum(np.abs(flujos)) * 0.5:
        return None
    
    def van_a_tasa(r):
        """VAN para una tasa dada."""
        if r <= -1:
            return float('inf')
        tasa_mensual = (1 + r) ** (1/12) - 1
        if tasa_mensual <= -1:
            return float('inf')
        try:
            resultado = np.sum(flujos / ((1 + tasa_mensual) ** meses))
            if not np.isfinite(resultado):
                return float('inf')
            return resultado
        except:
            return float('inf')
    
    try:
        van_0 = van_a_tasa(0.0)
        
        # Si VAN(0) no es finito, no hay TIR
        if not np.isfinite(van_0):
            return None
        
        # Buscar límites donde VAN cambia de signo
        low = -0.5
        high = 5.0  # Reducido de 10 para mayor velocidad
        
        # Búsqueda rápida de límites
        van_low = van_a_tasa(low)
        van_high = van_a_tasa(high)
        
        # Ajustar límites si es necesario
        if not np.isfinite(van_low):
            low = -0.3
            van_low = van_a_tasa(low)
        
        if not np.isfinite(van_low):
            low = 0.0
            van_low = van_0
        
        # Verificar que hay cruce de cero
        if van_low * van_high >= 0:
            # Intentar un rango más amplio
            for test_high in [10.0, 20.0]:
                van_high = van_a_tasa(test_high)
                if np.isfinite(van_high) and van_low * van_high < 0:
                    high = test_high
                    break
            else:
                return None
        
        return float(brentq(van_a_tasa, low, high, maxiter=50))  # Reducido maxiter
        
    except Exception:
        return None


def calcular_max_deficit(datos: Union[pd.DataFrame, Tuple[np.ndarray, np.ndarray]]) -> Tuple[float, Optional[float]]:
    """
    Encuentra el punto de máxima exposición financiera (valle del cash acumulado).
    Returns: (monto_déficit, mes)
    Puede recibir un DataFrame o una tupla de arreglos (cash_acumulado, meses).
    """
    if isinstance(datos, pd.DataFrame):
        acumulado = datos['Cash_Acumulado'].values
        meses = datos['Mes'].values
    else:
        acumulado, meses = datos
        
    minimo = float(np.min(acumulado))
    
    if minimo >= 0:
        return 0.0, None
    
    # Encontrar en qué mes ocurre el mínimo
    idx_minimo = int(np.argmin(acumulado))
    mes_minimo = float(meses[idx_minimo])
    
    # El déficit es el valor absoluto del mínimo
    return float(-minimo), mes_minimo


def calcular_break_even(datos: Union[pd.DataFrame, Tuple[np.ndarray, np.ndarray]]) -> Optional[float]:
    """
    Primer mes con saldo acumulado positivo.
    Puede recibir un DataFrame o una tupla de arreglos (cash_acumulado, meses).
    """
    if isinstance(datos, pd.DataFrame):
        acumulado = datos['Cash_Acumulado'].values
        meses = datos['Mes'].values
    else:
        acumulado, meses = datos
        
    positivos = acumulado > 0
    
    if np.any(positivos):
        idx_first_positive = np.argmax(positivos)
        return float(meses[idx_first_positive])
    
    return None
