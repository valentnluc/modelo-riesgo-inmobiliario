# Documentación del Proyecto: Modelo de Riesgo Inmobiliario

## 1. Visión General del Proyecto
Este proyecto implementa un **Motor de Simulación Inmobiliaria** diseñado para evaluar la viabilidad financiera y el riesgo de desarrollos inmobiliarios. Permite modelar flujos de fondos mensuales (Cashflow) considerando curvas de ventas y construcción no lineales.

El sistema ofrece dos modos de operación:
1.  **Análisis Determinístico**: Un escenario base único calculado con parámetros fijos.
2.  **Análisis Probabilístico (Monte Carlo)**: Simulación de múltiples escenarios variando precios, costos y tiempos para estimar la distribución de probabilidad de los retornos (VAN, TIR) y el riesgo de pérdida.

## 2. Guía de Uso

### Instalación

Requiere Python 3.8+ y las dependencias listadas.

```bash
pip install -r requirements.txt
```

### Ejecución

```bash
python app.py
```

Siga las instrucciones en consola para definir:
1.  **Terreno**: Superficie, FOT, Eficiencia.
2.  **Precios**: Valor de venta promedio y costo de construcción.
3.  **Curvas**: Seleccione el perfil de ventas y obra deseado.
4.  **Simulación**: Elija entre ejecución Única (Determinística) o Monte Carlo.

---

## 3. Estructura y Arquitectura del Código

El proyecto se organiza en cuatro módulos principales:

| Archivo | Responsabilidad Principal |
| :--- | :--- |
| **`app.py`** | **Interfaz de Usuario (CLI)**. Maneja la entrada de datos, orquesta la ejecución y llama a las funciones de guardado. |
| **`model.py`** | **Motor de Cálculo**. Contiene la lógica financiera (VAN, TIR), la generación del Cashflow mensual y el loop de Monte Carlo. |
| **`presets.py`** | **Definición de Curvas**. Librería de perfiles de ventas y costos (curvas S, campanas) basados en distribuciones estadísticas (*Skew Normal*). |
| **`viz.py`** | **Visualización**. Genera reportes gráficos interactivos en formato HTML utilizando la librería *Altair*. |

## 4. Análisis Detallado por Módulo

### 4.1. `model.py`: El Corazón Financiero

Este módulo transforma los parámetros del proyecto en un flujo de fondos temporal.

#### Funciones Clave:

*   **`build_monthly_cashflow(...)`**: 
    *   Es la función core. Sincroniza las curvas de ingresos y egresos en una línea de tiempo mensual común (default 0 a 36 meses).
    *   Computa:
        *   `Ventas`: Derivada de la curva acumulada de absorción.
        *   `Egresos_Obra`: Derivada de la curva S de inversión.
        *   `Egresos_Tierra`: Pagos del terreno según esquema (anticipo + cuotas) o canje.
        *   `Flujo_Neto`: Ventas - (Obra + Tierra).
        *   `Cash_Acumulado`: Saldo de caja acumulado en el tiempo.
*   **Indicadores Financieros**:
    *   `van(df, annual_rate)`: Valor Actual Neto descontado mensualmente.
    *   `tir(df)`: Tasa Interna de Retorno anualizada, calculada numéricamente (Brent method).
    *   `max_drawdown(df)`: Máxima exposición de capital (Maximum Financing Need) requerida antes de que el proyecto se autofinancie.
*   **`run_montecarlo(...)`**:
    *   Ejecuta `n` simulaciones.
    *   En cada iteración, perturba aleatoriamente:
        *   **Monto de Ventas** (Precio/Volumen).
        *   **Monto de Obra** (Costos).
        *   **Forma de las curvas** (parámetros `alpha` y `scale` de la distribución), simulando que la obra o las ventas pueden acelerarse o retrasarse aleatoriamente.

### 4.2. `presets.py`: Modelado de Curvas (S-Curves)

El proyecto utiliza la distribución **Skew Normal** (Normal Asimétrica) para modelar comportamientos no lineales realistas.

*   **Lógica**:
    *   Las ventas y los costos no son lineales.
    *   Se definen mediante `moda` (mes pico), `alpha` (asimetría - qué tan rápido sube/baja) y `scale` (dispersión - duración del ciclo).
    *   Función `generate_sales_cumulative`: Genera la **Curva S** (CDF - Función de Distribución Acumulada). Esta es la base para asegurar que la suma de los flujos mensuales iguale exactamente al total presupuestado (principio de conservación de masa).
    *   Función `generate_sales_curve`: Genera la curva de velocidad (PDF). Útil para visualizar el ritmo mensual.

*   **Presets Definidos**:
    *   *Ventas*: `preventa_fuerte` (pico temprano), `pozo_clasica` (pico medio), `post_obra` (pico tardío).
    *   *Costos*: `s_estandar`, `inicio_pesado` (acopio materiales), `cola_larga` (terminaciones lentas).

### 4.3. `viz.py`: Reportes

Genera dashboards HTML estáticos pero interactivos:
*   `reporte_cashflow.html`: Gráfico combinado de barras (ingresos/egresos mensuales) y línea (saldo acumulado).
*   `montecarlo_distribucion_*.html`: Histogramas de frecuencia para analizar el riesgo (ej. ¿Qué probabilidad hay de que el VAN sea negativo?).

## 5. Flujo de Datos

```mermaid
graph TD
    User[Usuario] -->|Inputs: m2, Precios, Presets| App[app.py]
    App -->|Params Estructurados| Model[model.py]
    Model -->|Solicita Curvas| Presets[presets.py]
    Presets -->|Arrays numpy (t, valor)| Model
    Model -->|DataFrame Cashflow| App
    App -->|DataFrame| Viz[viz.py]
    Viz -->|HTML Charts| Output[./output/]
    App -->|CSV| Output
```

## 6. Puntos Destacados de la Lógica

1.  **Interpolación Temporal**: Si las curvas de Ventas y Costos se generan con distinta resolución, el modelo interpola (`np.interp`) para alinearlas mes a mes, asegurando consistencia temporal.
2.  **Manejo de "Canje"**: El código distingue correctamente entre valor económico del terreno y flujo financiero. En un canje, el "costo" de la tierra es 0 en el flujo de caja, pero se reducen los "ingresos" (ventas efectivas) proporcionalmente.
3.  **Robustez Matemática**: El uso de CDFs (Acumuladas) en lugar de PDFs para calcular los montos mensuales evita errores de redondeo; la suma de los meses siempre coincide exactamente con el total inputado.
