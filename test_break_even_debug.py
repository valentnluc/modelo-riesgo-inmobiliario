import modelo_riesgo_inmobiliario
import streamlit_app as app
import model
import pandas as pd
print("sim_ids:", app.df_curvas['sim_id'].unique()[:5])
df_0 = app.df_curvas[app.df_curvas['sim_id'] == 0]
print("Rows in df_sim_0:", len(df_0))
print("First 5 accum:", df_0['Cash_Acumulado'].head().values)
mask = df_0['Cash_Acumulado'] >= 0
print("Mask any?", mask.any())
if mask.any():
    print("Break even month:", df_0.loc[mask, 'Mes'].iloc[0])
