
import os
import sys
from typing import Any, Dict
import pandas as pd
from presets import VENTAS_PRESETS, COSTOS_PRESETS, TIERRA_PRESETS
import model
import viz

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_input(prompt: str, default: Any = None, cast_type: type = str) -> Any:
    if default is not None:
        user_input = input(f"{prompt} [{default}]: ")
    else:
        user_input = input(f"{prompt}: ")
        
    if not user_input.strip():
        return default
    
    try:
        return cast_type(user_input)
    except ValueError:
        print(f"Error: Entrada inválida. Se esperaba {cast_type.__name__}.")
        return get_input(prompt, default, cast_type)

def select_preset_or_custom(category_name: str, presets_dict: Dict) -> Dict:
    print(f"\n--- Configuración de {category_name} (Forma de Curva) ---")
    print("Opciones disponibles:")
    keys = list(presets_dict.keys())
    for i, key in enumerate(keys):
        print(f"{i+1}. {key} - {presets_dict[key]['descripcion']}")
    print(f"{len(keys)+1}. Custom (Definir manualmente)")
    
    choice = get_input("Seleccione opción", 1, int)
    
    if 1 <= choice <= len(keys):
        key = keys[choice-1]
        print(f"Seleccionado: {key}")
        return presets_dict[key].copy()
    else:
        print(f"Modo Custom para {category_name}...")
        params = {}
        if category_name == 'Tierra':
            tipo = get_input("Tipo (pago/canje)", "pago")
            params['tipo'] = tipo
            if tipo == 'canje':
                params['canje_pct_m2'] = get_input("Porcentaje de Canje (0.0-1.0)", 0.30, float)
            else:
                pct_anticipo = get_input("Porcentaje Anticipo (0.0-1.0)", 0.30, float)
                num_cuotas = get_input("Cantidad de Cuotas", 12, int)
                inicio_cuotas = get_input("Mes inicio cuotas", 1, int)
                
                pagos = [{"mes": 0, "pct": pct_anticipo}]
                remainder = 1.0 - pct_anticipo
                if num_cuotas > 0 and remainder > 0:
                    pct_cuota = remainder / num_cuotas
                    for i in range(num_cuotas):
                        pagos.append({"mes": inicio_cuotas + i, "pct": pct_cuota})
                params['pagos'] = pagos
        else:
            params['moda'] = get_input("Moda (Mes pico)", 20, float)
            params['alpha'] = get_input("Alpha (Asimetría)", 0.0, float)
            params['scale'] = get_input("Scale (Dispersión)", 5.0, float)
            
        return params

def main():
    clear_screen()
    print("=======================================================")
    print("   MOTOR DE SIMULACIÓN INMOBILIARIA (CLI v2)   ")
    print("=======================================================")
    
    print("\n[1] Definición del Terreno y Proyecto")
    
    m2_terreno = get_input("Superficie Terreno (m2)", 500.0, float)
    fot = get_input("FOT (Factor de Ocupación Total)", 2.5, float)
    
    sup_construible_total = m2_terreno * fot
    print(f" >> Superficie Construible Total estimada: {sup_construible_total:.1f} m2")
    
    efficiency = get_input("Eficiencia Vendible (% de sup. construible)", 0.85, float)
    sup_vendible = sup_construible_total * efficiency
    print(f" >> Superficie Vendible estimada: {sup_vendible:.1f} m2")

    months_end = get_input("Duración total de obra (meses)", 36, int)
    months = (0, months_end)
    annual_rate = get_input("Tasa de descuento anual (VAN)", 0.10, float)
    output_dir = get_input("Directorio de salida", "output")
    os.makedirs(output_dir, exist_ok=True)

    sales_params = select_preset_or_custom("Ventas", VENTAS_PRESETS)
    print("\n--- Valor del Producto ---")
    avg_price_m2 = get_input("Precio Promedio Venta (USD/m2)", 2500.0, float)
    total_sales = sup_vendible * avg_price_m2
    print(f" >> Ventas Totales Proyectadas: ${total_sales:,.2f}")
    sales_params['area_n'] = total_sales

    cost_params = select_preset_or_custom("Costos de Obra", COSTOS_PRESETS)
    print("\n--- Costo de Construcción ---")
    cost_m2 = get_input("Costo de Construcción (USD/m2 construible)", 1200.0, float)
    total_capex = sup_construible_total * cost_m2
    print(f" >> CAPEX Obra Total Proyectado: ${total_capex:,.2f}")
    cost_params['limite_n'] = total_capex

    land_params = select_preset_or_custom("Tierra", TIERRA_PRESETS)
    
    if land_params.get('tipo', 'pago') == 'canje':
         pct_canje = land_params.get('canje_pct_m2', 0.30)
         m2_canje = sup_vendible * pct_canje
         valor_tierra_implicito = m2_canje * avg_price_m2
         
         print(f" >> Ajustando Ventas por Canje ({pct_canje*100:.1f}%):")
         print(f"    - Ventas Brutas: ${total_sales:,.2f}")
         total_sales_cash = total_sales * (1.0 - pct_canje)
         print(f"    - Ventas Cash (Efectivas): ${total_sales_cash:,.2f}")
         sales_params['area_n'] = total_sales_cash
         land_params['valor_total'] = 0.0
         
    else:
        land_value = get_input("Incidencia / Valor Tierra Total (USD)", 500000.0, float)
        land_params['valor_total'] = land_value

    print("\n[5] Tipo de Simulación")
    print("1. Determinística")
    print("2. Probabilística (Monte Carlo)")
    sim_type = get_input("Opción", 1, int)

    if sim_type == 1:
        print("\nEjecutando Modelo Determinístico...")
        df, metrics = model.run_deterministic(
            sales_params, cost_params, land_params,
            months=months, annual_rate=annual_rate
        )
        
        print("\n--- RESULTADOS ---")
        print(f"VAN ({annual_rate*100}%): ${metrics['VAN']:,.2f}")
        tir_str = f"{metrics['TIR']*100:.2f}%" if metrics['TIR'] is not None else "N/A"
        print(f"TIR: {tir_str}")
        print(f"Margen sobre Ventas: {(metrics['VAN']/total_sales)*100:.1f}% (aprox)")
        
        df.to_csv(os.path.join(output_dir, "flujo_deterministico.csv"), index=False)
        viz.plot_cashflow_scenario(df, os.path.join(output_dir, "reporte_cashflow.html"))
        viz.generate_comparative_charts(output_dir, months, total_capex, land_params.get('valor_total', land_value if 'land_value' in locals() else 0))
        print(f"Resultados guardados en {output_dir}")

    else:
        print("\nConfiguración Monte Carlo")
        n_sims = get_input("Número de iteraciones", 2000, int)
        sales_cv = get_input("Volatilidad Precio/Ventas (CV)", 0.15, float)
        cost_cv = get_input("Volatilidad Costos Obra (CV)", 0.10, float)
        
        print("\nIniciando simulación...")
        df_mc = model.run_montecarlo(
            n_sims, sales_params, cost_params, land_params, 
            months=months, annual_rate=annual_rate,
            sales_cv=sales_cv, cost_cv=cost_cv,
            use_progress=True 
        )
        
        print("\n--- RESULTADOS MONTE CARLO ---")
        van_stats = df_mc['VAN'].describe(percentiles=[0.1, 0.5, 0.9])
        print(f"VAN Medio: ${van_stats['mean']:,.2f}")
        print(f"P10 (Pesimista): ${van_stats['10%']:,.2f}")
        print(f"P90 (Optimista): ${van_stats['90%']:,.2f}")
        
        prob_loss = (df_mc['VAN'] < 0).mean()
        print(f"Probabilidad de VAN < 0: {prob_loss*100:.1f}%")
        
        viz.plot_montecarlo_results(df_mc, output_dir)
        df_mc.to_csv(os.path.join(output_dir, "resultados_montecarlo.csv"), index=False)
        print(f"Resultados guardados en {output_dir}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
