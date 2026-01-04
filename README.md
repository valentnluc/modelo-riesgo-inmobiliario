# Modelo de Riesgo Financiero Inmobiliario 🏢 📊

**Simulación de Monte Carlo Avanzada y Dashboard Interactivo para Análisis de Inversión Inmobiliaria.**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-App-red)
![Altair](https://img.shields.io/badge/Visualization-Altair-orange)
![Language](https://img.shields.io/badge/Language-Spanish-yellow)

Una herramienta interactiva diseñada para ir más allá de las planillas de Excel estáticas, ofreciendo una **evaluación probabilística** de proyectos inmobiliarios. Simula miles de escenarios de mercado (Precio de Venta, Ritmo de Absorción, Costos de Construcción) para cuantificar el riesgo y optimizar la toma de decisiones.

---

## 🚀 Características Principales

### 1. Dashboard Financiero Interactivo
Una experiencia de usuario (UX) diseñada con estética "Financial Times":
*   **Flujos Operativos**: Ingresos Mensuales (Azul) vs Egresos (Rojo) con indicadores de Flujo Neto.
*   **Saldo Estratégico**: Curva de Cash Flow Acumulado con marcadores de **Exposición de Capital**.
*   **Visualización de Riesgo**:
    *   **Fan Charts**: Intervalos de confianza del 90% (P05-P95) para flujos de caja.
    *   **Histogramas**: Distribución de VAN y TIR con marcadores P05/P95.
    *   **Matriz de Burbujas**: Análisis de sensibilidad visualizando el impacto de variaciones en Precio vs Costo sobre la rentabilidad.

### 2. Motor de Simulación Monte Carlo
*   **Modelado Estocástico**: Simula miles de escenarios variando drivers clave (Velocidad de Venta, Volatilidad de Precios, Inflación de Costos).
*   **Rendimiento Vectorizado**: Construido con `numpy` y `pandas` para cálculo de alta velocidad.
*   **Cuantificación de Riesgo**: Calcula Probabilidad de Pérdida, Valor en Riesgo (VaR) y dispersión máxima.

### 3. Estructuración Flexible de Negocyios
*   **Adquisición de Tierra**: Contado, Cuotas o Canje (Swap por metros).
*   **Curvas de Ventas**: Distribuciones Estándar (Beta), Preventa Agresiva o Ventas al Final.
*   **Curvas de Costos**: Distribución en Curva-S (Sigmoide) para el flujo de obra.

---

## 🛠️ Instalación y Uso

1.  **Clonar el repositorio**:
    ```bash
    git clone https://github.com/tu-usuario/modelo-riesgo-inmobiliario.git
    cd modelo-riesgo-inmobiliario
    ```

2.  **Instalar dependencias**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Ejecutar el Dashboard**:
    ```bash
    streamlit run streamlit_app.py
    ```

4.  **Explorar**:
    *   Ajusta los parámetros en la **Barra Lateral**.
    *   Activa **"Activar Monte Carlo"** para ver los gráficos probabilísticos (Fan Charts).
    *   Analiza las burbujas en **"Análisis de Sensibilidad"** para encontrar el punto de quiebre del proyecto.

---

## 📂 Estructura del Proyecto

*   `streamlit_app.py`: Punto de entrada de la aplicación (UI y Layout).
*   `model.py`: Fachada lógica financiera.
*   `simulation.py`: Motor de Monte Carlo (Vectorizado).
*   `cashflow.py`: Constructor de flujo de caja determinístico.
*   `metrics.py`: Fórmulas financieras (VAN, TIR, Break-even).
*   `presets.py`: Lógica de generación de curvas (Skew-Normal) y Presets de parámetros.
*   `viz.py`: Lógica de generación de gráficos Altair (Histogramas, Flujos, Burbujas).
*   `styles/`: CSS personalizado para el tema oscuro "Core Infra".

> **Nota**: Todo el código base ha sido estandarizado a **Español** para coincidir con el contexto de negocio local (`parametros_ventas`, `tasa_anual`, etc.).

---

## 📈 Metodología

Este modelo transforma inputs estáticos (ej. "Vender a $2000/m²") en distribuciones probabilísticas ("Vender a $2000/m² ± 15%"). Calcula el **Valor Actual Neto (VAN)** y la **Tasa Interna de Retorno (TIR)** para cada escenario, generando un perfil de riesgo que ayuda a los inversores a responder:

> *"¿Cuál es la probabilidad de perder dinero en este negocio?"*

---

**Licencia**: MIT
