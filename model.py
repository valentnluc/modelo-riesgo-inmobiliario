"""Lógica del modelo y cálculos financieros."""

from typing import Optional, Tuple, Dict, Any
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from tqdm import tqdm

from presets import (
    generate_sales_curve,
    generate_sales_cumulative,
    generate_investment_curve,
    create_land_schedule
)


def build_monthly_cashflow(
    sales_params: dict,
    cost_params: dict,
    land_params: dict,
    months: Tuple[int, int] = (0, 36),
    n_points: int = 500,
) -> pd.DataFrame:
    
    x_v, y_v_acum = generate_sales_cumulative(sales_params, months, n_points)
    ventas_step = np.diff(y_v_acum, prepend=0.0)
    
    x_i, y_i_acum = generate_investment_curve(cost_params, months, n_points)
    
    if not np.allclose(x_v, x_i):
        y_i_acum = np.interp(x_v, x_i, y_i_acum)
    
    x = x_v
    inv_obra_step = np.diff(y_i_acum, prepend=0.0)

    land_schedule = create_land_schedule(land_params, months)
    land_acum = np.cumsum(land_schedule)
    months_int = np.arange(len(land_schedule))
    land_acum_interp = np.interp(x, months_int, land_acum)
    land_step = np.diff(land_acum_interp, prepend=0.0)

    total_egresos = inv_obra_step + land_step
    flujo_neto = ventas_step - total_egresos
    cash_acum = np.cumsum(flujo_neto)

    df = pd.DataFrame({
        'Mes': x,
        'Flujo_Neto': flujo_neto,
        'Cash_Acumulado': cash_acum,
        'Ventas': ventas_step,
        'Egresos_Obra': inv_obra_step,
        'Egresos_Tierra': land_step
    })
    return df


def van(df: pd.DataFrame, annual_rate: float) -> float:
    monthly_rate = (1 + annual_rate) ** (1 / 12) - 1
    cash = df['Flujo_Neto'].values
    t = df['Mes'].values
    discounts = (1 + monthly_rate) ** t
    return float(np.sum(cash / discounts))


def tir(df: pd.DataFrame, guess_bounds: Tuple[float, float] = (-0.99, 10.0)) -> Optional[float]:
    cash = df['Flujo_Neto'].values
    t = df['Mes'].values

    def npv_annual(r):
        monthly = (1 + r) ** (1 / 12) - 1
        disc = (1 + monthly) ** t
        return np.sum(cash / disc)

    a, b = guess_bounds
    try:
        return float(brentq(lambda r: npv_annual(r), a, b, maxiter=500))
    except Exception:
        return None


def max_drawdown(df: pd.DataFrame) -> Tuple[float, Optional[float]]:
    cum = df['Cash_Acumulado'].values
    min_val = float(np.min(cum))
    idx = int(np.argmin(cum))
    need = float(-min_val) if min_val < 0 else 0.0
    return need, float(df['Mes'].iloc[idx]) if need > 0 else None


def break_even_month(df: pd.DataFrame) -> Optional[float]:
    mask = df['Cash_Acumulado'] >= 0
    if mask.any():
        return float(df.loc[mask, 'Mes'].iloc[0])
    return None


def run_deterministic(
    sales_params: dict,
    cost_params: dict,
    land_params: dict,
    months: Tuple[int, int] = (0, 36),
    annual_rate: float = 0.10,
    n_points: int = 500,
) -> Tuple[pd.DataFrame, dict]:
    
    df = build_monthly_cashflow(sales_params, cost_params, land_params, months, n_points)
    
    need, need_m = max_drawdown(df)
    
    metrics = {
        'VAN': van(df, annual_rate),
        'TIR': tir(df),
        'BreakEvenMonth': break_even_month(df),
        'MaxFinancingNeed': need,
        'MaxFinancingMonth': need_m
    }
    return df, metrics


def run_montecarlo(
    n_sims: int,
    base_sales_params: dict,
    base_cost_params: dict,
    base_land_params: dict,
    months: Tuple[int, int] = (0, 36),
    annual_rate: float = 0.10,
    n_points: int = 500,
    sales_cv: float = 0.15,
    cost_cv: float = 0.15,
    seed: Optional[int] = None,
    use_progress: bool = False
) -> pd.DataFrame:
    
    rng = np.random.default_rng(seed)
    results = []
    
    area_base = base_sales_params.get('area_n', 1000)
    inv_base = base_cost_params.get('limite_n', 1000)
    
    iterator = range(n_sims)
    if use_progress:
        iterator = tqdm(iterator, desc="Simulando Escenarios", unit="sim")

    for i in iterator:
        area_s = max(0.0, rng.normal(area_base, area_base * sales_cv))
        s_alpha = rng.normal(base_sales_params.get('alpha', 0), 0.5)
        s_scale = max(0.1, rng.normal(base_sales_params.get('scale', 1), 1.0))
        
        sim_sales = {**base_sales_params, 'area_n': area_s, 'alpha': s_alpha, 'scale': s_scale}

        inv_s = max(0.0, rng.normal(inv_base, inv_base * cost_cv))
        c_alpha = rng.normal(base_cost_params.get('alpha', 0), 0.5)
        c_scale = max(0.1, rng.normal(base_cost_params.get('scale', 1), 1.0))
        
        sim_cost = {**base_cost_params, 'limite_n': inv_s, 'alpha': c_alpha, 'scale': c_scale}

        df = build_monthly_cashflow(sim_sales, sim_cost, base_land_params, months, n_points)
        
        results.append({
            'sim_id': i,
            'VAN': van(df, annual_rate),
            'TIR': tir(df),
            'Total_Ventas': area_s,
            'Total_Costo': inv_s
        })
        
    return pd.DataFrame(results)
