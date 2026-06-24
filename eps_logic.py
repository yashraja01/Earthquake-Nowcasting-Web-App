import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import scipy.stats as st
from scipy.stats import linregress
from scipy.stats import rv_continuous
from openpyxl import load_workbook

def run_eps_analysis(earthquake_df, cities_df, r_value, m_sigma, m_lambda):
    
    class ExponentiatedExponential(rv_continuous):
        def _pdf(self, x, alpha, lambd):
            # PDF: f(x) = α * λ * e^(-λx) * (1 - e^(-λx))^(α-1), x > 0
            return alpha * lambd * np.exp(-lambd*x) * (1 - np.exp(-lambd*x))**(alpha-1) * (x > 0)

        def _cdf(self, x, alpha, lambd):
            # CDF: F(x) = (1 - e^(-λx))^α
            return (1 - np.exp(-lambd*x))**alpha * (x > 0)

    expon_exp = ExponentiatedExponential(name="exponexp")

    class ExponentiatedWeibull(rv_continuous):
        def _pdf(self, x, a, c, lam):
            return (a * c / lam) * (x/lam)**(c-1) * np.exp(-(x/lam)**c) * \
               (1 - np.exp(-(x/lam)**c))**(a-1) * (x > 0)

        def _cdf(self, x, a, c, lam):
            return (1 - np.exp(-(x/lam)**c))**a * (x > 0)

    # Create distribution object
    expon_weibull = ExponentiatedWeibull(name="exponweibull")

    #end of defining distributions--------------------------------------------------
    # A.GENERATING PLOTS

    # Plot 1
    df = earthquake_df

    # Keep valid magnitudes
    df = df.dropna(subset=["Mw"]).copy()
    df["Mw"] = pd.to_numeric(df["Mw"], errors="coerce")
    df = df.dropna(subset=["Mw"])

    # Round Mw to nearest 0.1
    df["Mw_round"] = df["Mw"].round(1)

    m_min = m_sigma
    m_max = float(np.floor(df["Mw_round"].max() * 10) / 10.0)
    mag_grid = np.round(np.arange(m_min, m_max + 0.001, 0.1), 1)

    counts = df["Mw_round"].value_counts().reindex(mag_grid, fill_value=0).sort_index()
    cdf = counts.cumsum()
    total = int(counts.sum())
    n_ge = total - (cdf - counts)
    log10_n = np.where(n_ge > 0, np.log10(n_ge), np.nan)

    result = pd.DataFrame({
        "Magnitude": mag_grid,
        "count": counts.values,
        "cumulative_count": cdf.values,
        "N(>=M)": n_ge.values,
        "log10(N)": log10_n
    })

    #Drop NaNs for regression
    fit_data = result.dropna(subset=["log10(N)"])
    slope, intercept, r_coeff, p_value, std_err = linregress(fit_data["Magnitude"], fit_data["log10(N)"])
    a_value = intercept
    b_value = -slope

    #print(f" fit: log10(N) = {a_value:.3f} - {b_value:.3f} * M")
    #print(f"R-squared = {r_coeff**2:.4f}")

    # Plot
    """ 
    plt.figure(figsize=(8, 6))
    plt.scatter(result["Magnitude"], result["log10(N)"], s=40, alpha=0.7, label="Observed data")
    x_vals = np.linspace(result["Magnitude"].min(), result["Magnitude"].max(), 100)
    y_vals = intercept + slope * x_vals
    plt.plot(x_vals, y_vals, color="red", linewidth=2, label=f"Fit: log10(N) = {a_value:.2f} - {b_value:.2f}M")
    plt.xlabel("Magnitude (Mw)")
    plt.ylabel("log10(N)")
    plt.title("Frequency-Magnitude Distribution")
    plt.grid(True)
    plt.legend()
    plt.show() 
    """

    fig1, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(result["Magnitude"], result["log10(N)"], s=40, alpha=0.7, label="Observed data")
    x_vals = np.linspace(result["Magnitude"].min(), result["Magnitude"].max(), 100)
    y_vals = intercept + slope * x_vals

    ax.plot(x_vals, y_vals, color="red", linewidth=2, label=f"Fit: log10(N) = {a_value:.2f} - {b_value:.2f}M")
    ax.set_xlabel("Magnitude (Mw)")
    ax.set_ylabel("log10(N)")
    ax.set_title("Frequency-Magnitude Distribution")
    ax.grid(True)
    ax.legend()
    ###############################################
    #1. MERGE DATA (Replaces writing to Excel at column 6)
    # Instead of saving to disk to merge, we concatenate in memory.
    # axis=1 means "put them side-by-side" (columns)
    # This creates a unified dataframe with original data + result data
    full_df = pd.concat([earthquake_df, result], axis=1)

    #2. CALCULATE NEW COLUMNS (No change needed, just use full_df)
    
    # 1) Small? column: 1 if Mw < M_lambda, else 0
    full_df["Small?"] = (full_df["Mw"] < m_lambda).astype(int)

    # 2) Large? column: 1 if Mw >= M_lambda, else 0
    full_df["Large?"] = (full_df["Mw"] >= m_lambda).astype(int)

    # 3) Cumulative small earthquakes (Logic remains the same)
    cumulative_counts = []
    count = 0
    
    # We iterate over the columns in memory
    for small, large in zip(full_df["Small?"], full_df["Large?"]):
        if large == 1:
            count = 0
            cumulative_counts.append(count)
        else:
            if small == 1:
                count += 1
            cumulative_counts.append(count)

    full_df["CumulativeSmall"] = cumulative_counts

    #3.CYCLE PEAK LOGIC
    values = full_df["CumulativeSmall"].tolist()
    full_df["Cycle_peak"] = np.nan # Initialize with NaN

    for i in range(1, len(values)):
        # Detect reset (when value goes to 0 or 1 after being higher)
        if values[i] in (0, 1) and values[i-1] > values[i]:
            full_df.loc[i-1, "Cycle_peak"] = values[i-1]  # mark the peak row

    # Plot 2
    
    #PREPARE DATA FOR PLOT 2
    # Ensure the dataframe being used (e.g., full_df) has the Date column in datetime format
    # Note: 'full_df' is the dataframe you created in the previous step by merging result columns
    full_df['Date'] = pd.to_datetime(full_df['Date'])
    full_df['year'] = full_df['Date'].dt.year

    # Filter year range (1970-2030)
    # We create a temporary view for plotting so we don't lose data in the main export
    plot_df = full_df[(full_df['year'] >= 1970) & (full_df['year'] <= 2030)]

    # Split magnitudes
    df_big = plot_df[plot_df['Mw'] >= m_lambda]
    df_small = plot_df[plot_df['Mw'] < m_lambda]

    # --- GENERATE PLOT 2 ---
    fig2, ax2 = plt.subplots(figsize=(12, 6))

    # Scatter for small magnitudes
    # Note: Using ax2.scatter
    ax2.scatter(df_small['year'], df_small['Mw'], s=5, color='navy', label='Mw < M_lambda')

    # Scatter for big magnitudes
    ax2.scatter(df_big['year'], df_big['Mw'], s=40, edgecolors='black', color='yellow', label='Mw ≥ M_lambda')

    # Axis limits
    # Note: Using ax2.set_xlim / set_ylim
    ax2.set_xlim(1970, 2030)
    ax2.set_ylim(3, 8)

    # Ticks
    # Note: Using ax2.set_xticks / set_yticks
    ax2.set_xticks(range(1970, 2031, 10))
    ax2.set_yticks(range(3, 9, 1))

    # Grid and Labels
    ax2.grid(which='major', linestyle='--', alpha=0.7)
    ax2.set_xlabel("Time (Years)")
    ax2.set_ylabel("Magnitude")
    ax2.set_title("Earthquake Magnitudes Over Time (1970–2030)")
    
    # Optional: Add a legend since we have two groups
    ax2.legend()

    # Remember: Do NOT use plt.show(). This 'fig2' will be returned at the end.
    
    # Plot 3

    # --- PREPARE DATA FOR PLOT 3 ---
    # 1. Filter Data
    # We create a specific dataframe for this plot to handle the DropNA 
    # without affecting the main 'full_df' export.
    plot_df_3 = full_df.dropna(subset=['Cycle_peak']).copy()

    # 2. Create Bins and Labels
    bins = range(0, 1901, 100)
    # Labels: "1-100", "101-200", ... "1801-1900"
    labels = [f'{i+1}-{i+100}' for i in range(0, 1900, 100)]

    # 3. Categorize the data
    plot_df_3['Range'] = pd.cut(plot_df_3['Cycle_peak'], bins=bins, labels=labels, include_lowest=True)

    # 4. Calculate Frequency
    frequency_data = plot_df_3['Range'].value_counts().sort_index()

    # --- GENERATE PLOT 3 ---
    fig3, ax3 = plt.subplots(figsize=(10, 6))

    # 5. Plot the Bar Graph on ax3
    bars = ax3.bar(frequency_data.index.astype(str), frequency_data.values, color='skyblue', edgecolor='black')

    # Add labels and title using set_
    ax3.set_title('Natural Time Frequency Distribution', fontsize=14)
    ax3.set_xlabel('Natural Time Counts', fontsize=12)
    ax3.set_ylabel('Number of Earthquakes', fontsize=12)

    # --- FIX HERE: Adjust x-axis tick labels ---
    # axis='x': apply only to x-axis
    # labelsize=8: reduce font size (default is usually 10 or 12)
    # rotation=45: angle the text so it doesn't overlap
    ax3.tick_params(axis='x', labelsize=8, rotation=45)
    
    # Plot 4
    
    # --- PREPARE DATA FOR PLOT 4 ---

    full_df['Cycle_peak'] = pd.to_numeric(full_df['Cycle_peak'], errors='coerce')
    # 1. Clean and Sort Data from the in-memory dataframe
    data_for_fit = full_df['Cycle_peak'].dropna().sort_values()

    # Define the distributions you want to test
    # Note: We are using 'st' for scipy.stats here as requested
    DISTRIBUTIONS = {
        "Weibull": st.weibull_min,
        "Gamma": st.gamma,
        "Lognormal": st.lognorm,
        "Exponential": st.expon
    }

    # --- GENERATE PLOT 4 ---
    fig4, ax4 = plt.subplots(figsize=(12, 8))

    # 2. Plot Empirical Data (ECDF)
    n = len(data_for_fit)
    x_emp = np.sort(data_for_fit)
    y_emp = np.arange(1, n + 1) / n
    
    # Use ax4.step
    ax4.step(x_emp, y_emp, label='Empirical Data (ECDF)', color='black', linewidth=2, where='post')

    # Create x-range for smooth theoretical lines
    x_space = np.linspace(data_for_fit.min(), data_for_fit.max(), 500)

    # List to store statistical results (replaces print statements)
    results_list = []

    # 3. Loop through distributions
    for name, dist in DISTRIBUTIONS.items():
        try:
            # Fit distribution (floc=0 fixes location to 0)
            params = dist.fit(data_for_fit, floc=0)

            # Compute Statistics
            loglik = np.sum(dist.logpdf(data_for_fit, *params))
            k = len(params)
            aic = 2*k - 2*loglik
            ks_stat, ks_pval = st.kstest(data_for_fit, dist.cdf, args=params)

            # Calculate fitted CDF for plotting
            cdf_fitted = dist.cdf(x_space, *params)

            # Plot on ax4
            ax4.plot(x_space, cdf_fitted, label=f'{name} (AIC: {aic:.0f})', alpha=0.7, linestyle='--')

            # Append results to list (for the Table)
            results_list.append({
                "Distribution": name,
                "AIC": aic,
                "KS Stat": ks_stat
            })

        except Exception as e:
            # In a web app, maybe just pass, or log to console
            # print(f"Could not fit {name}: {e}")
            pass

    # 4. Finalize Plot Aesthetics
    ax4.set_title('ECDF vs Fitted Theoretical Distributions', fontsize=16)
    ax4.set_xlabel('Natural Times', fontsize=12)
    ax4.set_ylabel('Cumulative Probability', fontsize=12)
    ax4.legend(title="Distributions", loc='best')
    ax4.grid(True, alpha=0.3)
    ax4.set_xlim(left=0)
    ax4.set_ylim(0, 1.05)

    # 5. Create the Results DataFrame (This replaces your print table)
    dist_table = pd.DataFrame(results_list)
    if not dist_table.empty:
        # Sort by AIC (lowest is best)
        dist_table = dist_table.sort_values(by="AIC")
        best_dist_name = dist_table.iloc[0]['Distribution']
        
        # Add "Best Fit" text box to the plot
        ax4.text(0.05, 0.95, f"Best Fit: {best_dist_name}",
                 transform=ax4.transAxes, fontsize=12,
                 bbox=dict(facecolor='white', alpha=0.8))

    fig4.tight_layout()
    

    # --- B. DATA PROCESSING ---
    # (Do your calculations here using earthquake_df and cities_df)
    # ... code ...

    # Let's assume you created two result DataFrames:
    '''
    # Candidate distributions with parameter names
    DISTRIBUTIONS = {
        "Exponential": (st.expon, ["loc", "scale"]),
        "Gamma": (st.gamma, ["a", "loc", "scale"]),
        "LogNormal": (st.lognorm, ["s", "loc", "scale"]),
        "Weibull": (st.weibull_min, ["c", "loc", "scale"]),
        "Inverse-Gaussian": (st.invgauss, ["mu", "loc", "scale"]),
        "Inverse-Weibull": (st.invweibull, ["c", "loc", "scale"]),
        "Exponentiated Exponential": (expon_exp, ["alpha", "lambda"]),
        "Exponentiated Weibull": (expon_weibull, ["a", "c", "lambda"])
    }

    def fit_distributions(data):
        results = []
        n = len(data)

        for name, (dist, param_names) in DISTRIBUTIONS.items():
            try:
                # Fit distribution using MLE
                params = dist.fit(data, floc=0)

                # Compute log-likelihood
                loglik = np.sum(dist.logpdf(data, *params))

                # Number of parameters
                k = len(params)

                # AIC = 2k - 2ln(L)
                aic = 2*k - 2*loglik

                # Kolmogorov–Smirnov test
                ks_stat, ks_pval = st.kstest(data, dist.cdf, args=params)

                # Pack parameter estimates nicely
                param_dict = {p: round(val, 4) for p, val in zip(param_names, params)}

                results.append({
                    "Distribution": name,
                    "Parameters": ", ".join(param_names),
                    "MLE Estimates": param_dict,
                    "AIC": round(aic, 2),
                    "KS Statistic": round(ks_stat, 4),
                    "KS p-value": round(ks_pval, 4)
                })

            except Exception as e:
                print(f"Could not fit {name}: {e}")

        # Put into DataFrame and sort by AIC
        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values("AIC").reset_index(drop=True)

        return results_df
    # Step A: Extract ONLY the column you need
    target_data = full_df['Cycle_peak']
    
    # Step B: Clean it (Force numeric, remove NaNs)
    target_data = pd.to_numeric(target_data, errors='coerce').dropna()
    dist_table=fit_distributions(target_data)
    '''

    # --- 1. Define Distributions ---
    DISTRIBUTIONS = {
        "Exponential": (st.expon, ["loc", "scale"]),
        "Gamma": (st.gamma, ["a", "loc", "scale"]),
        "LogNormal": (st.lognorm, ["s", "loc", "scale"]),
        "Weibull": (st.weibull_min, ["c", "loc", "scale"]),
        "Inverse-Gaussian": (st.invgauss, ["mu", "loc", "scale"]),
        "Inverse-Weibull": (st.invweibull, ["c", "loc", "scale"]),
        # Note: Ensure custom functions like expon_exp are defined if you use them
        # "Exponentiated Exponential": (expon_exp, ["alpha", "lambda"]),
        # "Exponentiated Weibull": (expon_weibull, ["a", "c", "lambda"])
    }

    # --- 2. Define Fitting Function (Updated to return Best Model) ---
    def fit_distributions(data):
        results = []
        n = len(data)
        
        # Variables to track the winner
        best_aic = float('inf')
        best_model_func = None
        best_model_params = None

        for name, (dist, param_names) in DISTRIBUTIONS.items():
            try:
                # Fit distribution using MLE
                params = dist.fit(data, floc=0)

                # Compute log-likelihood
                loglik = np.sum(dist.logpdf(data, *params))

                # Number of parameters
                k = len(params)

                # AIC = 2k - 2ln(L)
                aic = 2*k - 2*loglik

                # Kolmogorov–Smirnov test
                ks_stat, ks_pval = st.kstest(data, dist.cdf, args=params)
                
                # --- NEW: Check if this is the best fit so far ---
                if aic < best_aic:
                    best_aic = aic
                    best_model_func = dist
                    best_model_params = params

                # Pack parameter estimates nicely
                param_dict = {}
                for i, p_name in enumerate(param_names):
                    if i < len(params):
                        param_dict[p_name] = round(params[i], 4)

                results.append({
                    "Distribution": name,
                    "Parameters": ", ".join(param_names),
                    "MLE Estimates": str(param_dict),
                    "AIC": round(aic, 2),
                    "KS Statistic": round(ks_stat, 4)
                })

            except Exception as e:
                # print(f"Could not fit {name}: {e}")
                pass

        # Put into DataFrame and sort by AIC
        results_df = pd.DataFrame(results)
        if not results_df.empty:
            results_df = results_df.sort_values("AIC").reset_index(drop=True)

        # RETURN 3 ITEMS: The Table, The Best Function, The Best Params
        return results_df, best_model_func, best_model_params

    # --- 3. Call the function and UNPACK the results ---
    
    # Step A: Extract ONLY the column you need
    target_data = full_df['Cycle_peak']
    
    # Step B: Clean it (Force numeric, remove NaNs)
    target_data = pd.to_numeric(target_data, errors='coerce').dropna()
    
    # Step C: Call function and get the Best Model for later use
    dist_table, best_dist, best_params = fit_distributions(target_data)


    #####################################################
    
    #CALCULATE EPS SCORES FOR CITIES

    # 1. AGGRESSIVE DATA CLEANING (Ensure types are correct)
    full_df['Mw'] = pd.to_numeric(full_df['Mw'], errors='coerce')
    full_df['Date'] = pd.to_datetime(full_df['Date'], errors='coerce')

    # Robust Datetime Combination
    try:
        full_df['Datetime'] = pd.to_datetime(
            full_df['Date'].astype(str) + ' ' + full_df['Time'].astype(str), 
            errors='coerce'
        )
    except:
        full_df['Datetime'] = full_df['Date']

    # Safety Check: If r_value was overwritten by regression, reset it
    if r_value < 0: 
        r_value = 150

    summary_data = []

    # 2. Iterate through the User's Cities
    if not cities_df.empty:
        for index, row in cities_df.iterrows():
            city_name = row.get('City', 'Unknown')
            city_lat = row.get('Latitude', 0)
            city_lon = row.get('Longitude', 0)
            
            # A. Calculate Distance
            dist_col = f"{city_name} (km)"
            full_df[dist_col] = np.sqrt(
                (full_df['Latitude'] - city_lat)**2 + 
                (full_df['Longitude'] - city_lon)**2
            ) * 101.5

            # B. Filter Logic
            mask_nearby = full_df[dist_col] <= r_value
            mask_major = full_df['Mw'] >= m_lambda
            valid_quakes = full_df[mask_nearby & mask_major]

            if not valid_quakes.empty:
                # Get latest major earthquake
                latest_quake = valid_quakes.sort_values(by='Datetime', ascending=False).iloc[0]
                latest_datetime = latest_quake['Datetime']

                # C. Count Small Quakes
                mask_time = full_df['Datetime'] > latest_datetime
                mask_dist = full_df[dist_col] <= r_value
                mask_mag = full_df['Mw'] < m_lambda
                
                # This is the "n" (Count)
                current_count = len(full_df[mask_time & mask_dist & mask_mag])

                # --- D. NEW: CALCULATE EPS (CDF VALUE) ---
                # We use the Best Model found in the previous step
                eps_cdf_value = 0.0
                if best_dist is not None and best_params is not None:
                    try:
                        # CDF(x) gives the probability
                        eps_cdf_value = best_dist.cdf(current_count, *best_params)
                    except Exception as e:
                        print(f"CDF Calc Error for {city_name}: {e}")
                        eps_cdf_value = 0.0

                # Populate Dictionary
                city_result = {
                    'City': city_name,
                    'Latitude': city_lat,
                    'Longitude': city_lon,
                    # Empty placeholders for formatting if needed
                    'EQ Date': latest_quake['Date'],
                    'EQ Time': latest_quake['Time'],
                    'EQ Latitude': latest_quake['Latitude'],
                    'EQ Longitude': latest_quake['Longitude'],
                    'Depth': latest_quake['Depth'],
                    'Mw': latest_quake['Mw'],
                    'Distance (km)': round(latest_quake[dist_col], 2),
                    'Small Event Count': current_count,
                    'EPS Score': round(eps_cdf_value, 4) # <--- FINAL CDF VALUE
                }
            else:
                # Default values if no major quake
                city_result = {
                    'City': city_name,
                    'Latitude': city_lat,
                    'Longitude': city_lon,
                    'EQ Date': None, 'EQ Time': None,
                    'EQ Latitude': None, 'EQ Longitude': None,
                    'Depth': None, 'Mw': None,
                    'Distance (km)': None,
                    'Small Event Count': 0,
                    'EPS Score': 0.0
                }

            summary_data.append(city_result)

    # 3. Create the Summary DataFrame
    eps_out = pd.DataFrame(summary_data)
    
    

    '''
    # --- CALCULATE EPS SCORES FOR CITIES ---

    # 1. PRE-PROCESSING: Ensure Data Types are correct before looping
    # Force Mw to numeric
    full_df['Mw'] = pd.to_numeric(full_df['Mw'], errors='coerce')
    
    # Create a robust Datetime column (Date + Time) for accurate sorting
    # This handles cases where Time might be in different formats
    try:
        full_df['Datetime'] = pd.to_datetime(
            full_df['Date'].astype(str) + ' ' + full_df['Time'].astype(str), 
            errors='coerce'
        )
    except:
        # Fallback if Time column has issues
        full_df['Datetime'] = pd.to_datetime(full_df['Date'], errors='coerce')

    summary_data = []

    # 2. Loop through the cities entered by the user on the website
    if not cities_df.empty:
        for index, row in cities_df.iterrows():
            city_name = row['City']
            city_lat = row['Latitude']
            city_lon = row['Longitude']
            
            # A. Calculate Distance for this city
            distance_col = f"{city_name} (km)"
            full_df[distance_col] = np.sqrt(
                (full_df['Latitude'] - city_lat)**2 + 
                (full_df['Longitude'] - city_lon)**2
            ) * 101.5

            # B. Filter Logic: Within Radius AND Mw >= 6
            # Note: We use r_value (from user input) instead of hardcoded 150
            mask_nearby = full_df[distance_col] <= r_value
            mask_major = full_df['Mw'] >= 6.0
            
            valid_quakes = full_df[mask_nearby & mask_major]

            if not valid_quakes.empty:
                # Get latest (most recent) major earthquake
                latest_quake = valid_quakes.sort_values(by='Datetime', ascending=False).iloc[0]
                latest_datetime = latest_quake['Datetime']

                # C. Build the Dictionary (EXACTLY as you requested)
                latest_info = {
                    'City': city_name,
                    'Latitude': city_lat,
                    'Longitude': city_lon,
                    '': '',   # Placeholder 1
                    ' ': '',  # Placeholder 2
                    '  ': '', # Placeholder 3
                    'EQ Date': latest_quake['Date'],
                    'EQ Time': latest_quake['Time'],
                    'EQ Latitude': latest_quake['Latitude'],
                    'EQ Longitude': latest_quake['Longitude'],
                    'Depth': latest_quake['Depth'],
                    'Mw': latest_quake['Mw'],
                    'Distance (km)': round(latest_quake[distance_col], 2),
                }

                # D. Count Small Quakes (Mw < 6) AFTER the major quake
                small_quakes_after = full_df[
                    (full_df['Datetime'] > latest_datetime) & 
                    (full_df[distance_col] <= r_value) & 
                    (full_df['Mw'] < 6.0)
                ]

                latest_info['Small Event Count'] = len(small_quakes_after)

            else:
                # No major earthquake found - Empty Structure
                latest_info = {
                    'City': city_name,
                    'Latitude': city_lat,
                    'Longitude': city_lon,
                    '': '',
                    ' ': '',
                    '  ': '',
                    'EQ Date': None,
                    'EQ Time': None,
                    'EQ Latitude': None,
                    'EQ Longitude': None,
                    'Depth': None,
                    'Mw': None,
                    'Distance (km)': None,
                    'Small Event Count': 0
                }

            # Append to list
            summary_data.append(latest_info)

    # 3. Create the final DataFrame
    eps_out = pd.DataFrame(summary_data)
    '''

    # --- CALCULATE EPS SCORES FOR CITIES ---
    '''
    print("\n--- DEBUGGING STARTED ---")
    
    # 1. INSPECT THE CITIES DATAFRAME
    print(f"Cities Data Received: {type(cities_df)}")
    print(f"Number of rows in Cities DF: {len(cities_df)}")
    print("Cities Head:\n", cities_df.head()) # This will show us the actual table content

    # 2. AGGRESSIVE DATA CLEANING
    full_df['Mw'] = pd.to_numeric(full_df['Mw'], errors='coerce')
    full_df['Date'] = pd.to_datetime(full_df['Date'], errors='coerce')

    # 3. ROBUST DATETIME COMBINATION
    try:
        full_df['Datetime'] = pd.to_datetime(
            full_df['Date'].astype(str) + ' ' + full_df['Time'].astype(str), 
            errors='coerce'
        )
    except:
        full_df['Datetime'] = full_df['Date']

    full_df = full_df.dropna(subset=['Datetime'])

    summary_data = []

    # 4. FORCE THE LOOP (Deep Inspection Mode)
    print(f"\n--- DEEP INSPECTION FOR EARTHQUAKE DATA ---")
    print(f"Total rows in Earthquake File: {len(full_df)}")
    
    # Check if we have ANY major quakes in the whole file
    global_major_count = len(full_df[full_df['Mw'] >= 6.0])
    print(f"Total Quakes with Mw >= 6.0 in ENTIRE file: {global_major_count}")
    
    # Check column names (to ensure we aren't missing 'Latitude' vs 'lat')
    print(f"Earthquake File Columns: {list(full_df.columns)}")

    for index, row in cities_df.iterrows():
        city_name = row.get('City', 'Unknown City')
        city_lat = row.get('Latitude', 0)
        city_lon = row.get('Longitude', 0)
        
        print(f"\nProcessing City: {city_name}")
        
        # A. Calculate Distance
        distance_col = f"{city_name} (km)"
        
        # Force coordinates to numeric just in case
        full_df['Latitude'] = pd.to_numeric(full_df['Latitude'], errors='coerce')
        full_df['Longitude'] = pd.to_numeric(full_df['Longitude'], errors='coerce')

        full_df[distance_col] = np.sqrt(
            (full_df['Latitude'] - city_lat)**2 + 
            (full_df['Longitude'] - city_lon)**2
        ) * 101.5

        # --- CRITICAL DEBUG INFO ---
        # 1. What is the CLOSEST earthquake to this city?
        min_dist = full_df[distance_col].min()
        print(f"  > Closest earthquake found: {min_dist:.2f} km")
        print(f"  > Radius limit user selected: {r_value} km")
        
        # 2. Filter Logic
        mask_nearby = full_df[distance_col] <= r_value
        mask_major = full_df['Mw'] >= 6.0
        
        nearby_count = len(full_df[mask_nearby])
        valid_quakes = full_df[mask_nearby & mask_major]
        
        print(f"  > Events within Radius: {nearby_count}")
        print(f"  > Major Events (Mw>=6) within Radius: {len(valid_quakes)}")

        if not valid_quakes.empty:
            latest_quake = valid_quakes.sort_values(by='Datetime', ascending=False).iloc[0]
            latest_datetime = latest_quake['Datetime']
            
            # C. Count Small Quakes
            mask_time = full_df['Datetime'] > latest_datetime
            mask_dist = full_df[distance_col] <= r_value
            mask_mag = full_df['Mw'] < 6.0
            
            count = len(full_df[mask_time & mask_dist & mask_mag])
            
            print(f"  > SUCCESS: Major Quake at {latest_datetime}. Small quakes after: {count}")

            latest_info = {
                'City': city_name,
                'Latitude': city_lat,
                'Longitude': city_lon,
                '': '', ' ': '', '  ': '',
                'EQ Date': latest_quake['Date'],
                'EQ Time': latest_quake['Time'],
                'EQ Latitude': latest_quake['Latitude'],
                'EQ Longitude': latest_quake['Longitude'],
                'Depth': latest_quake['Depth'],
                'Mw': latest_quake['Mw'],
                'Distance (km)': round(latest_quake[distance_col], 2),
                'Small Event Count': count 
            }
        else:
            print("  > FAILURE: No major quake found meeting criteria.")
            latest_info = {
                'City': city_name,
                'Latitude': city_lat,
                'Longitude': city_lon,
                '': '', ' ': '', '  ': '',
                'EQ Date': None, 'EQ Time': None,
                'EQ Latitude': None, 'EQ Longitude': None,
                'Depth': None, 'Mw': None,
                'Distance (km)': None,
                'Small Event Count': 0
            }

        summary_data.append(latest_info)

    eps_out = pd.DataFrame(summary_data)
    print("--- DEBUGGING FINISHED ---")

    return fig1, fig2, fig3, fig4, dist_table, eps_out, full_df
    '''


    #C.RETURN EVERYTHING
    return fig1, fig2, fig3, fig4, dist_table, eps_out, full_df
