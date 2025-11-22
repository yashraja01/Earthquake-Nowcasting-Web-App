import streamlit as st
import pandas as pd
from eps_logic import run_eps_analysis # Import your function

# Page Config
st.set_page_config(page_title="EPS Score Analyzer", layout="wide")

st.title("Earthquake EPS Score Analyzer")
st.markdown("---")

# ==========================================
# SECTION 1: INPUTS
# ==========================================
col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Upload Data")
    # Input: Earthquake Data (Excel)
    uploaded_file = st.file_uploader("Upload Earthquake Data (Excel)", type=['xlsx', 'xls'])
    
    st.subheader("2. Analysis Parameters")
    # Input: R Value
    r_value = st.number_input("Enter Radius (R) in km", min_value=1, value=250)

    # value=0.0 ensures they are treated as floats (decimals)
    m_sigma = st.number_input("Enter M_sigma (min)", value=0.0, step=0.1, format="%.2f")
    m_lambda = st.number_input("Enter M_lambda (big earthquake)", value=0.0, step=0.1, format="%.2f")

with col2:
    st.subheader("3. Enter Cities & Coordinates")
    st.info("You can add rows or copy-paste from Excel.")
    
    # Input: Cities Grid
    # We create a template DataFrame for the user to fill in
    default_data = pd.DataFrame(
        [{"City": "New Delhi", "Latitude": 28.6139, "Longitude": 77.2090}],
    )
    
    # This creates an editable table
    cities_input = st.data_editor(
        default_data,
        num_rows="dynamic", # Allows user to add/delete rows
        width="stretch"   
    )

# ==========================================
# SECTION 2: EXECUTION
# ==========================================
st.markdown("---")
run_btn = st.button("Run Analysis", type="primary", use_container_width=True)

if run_btn:
    if uploaded_file is not None and not cities_input.empty:
        try:
            with st.spinner("Processing data and generating plots..."):
                # Load the Excel file
                earthquake_df = pd.read_excel(uploaded_file)
                
                # Call your python script
                # We unpack the 6 returns we defined in eps_logic.py
                fig1, fig2, fig3, fig4, dist_table, eps_out, full_df = run_eps_analysis(
                    earthquake_df, 
                    cities_input, 
                    r_value,
                    m_sigma,
                    m_lambda
                )

            # ==========================================
            # SECTION 3: OUTPUTS
            # ==========================================
            st.success("Analysis Complete!")

            # --- Display Plots (2x2 Grid) ---
            st.subheader("Visualizations")
            p_col1, p_col2 = st.columns(2)
            
            with p_col1:
                st.pyplot(fig1)
                st.pyplot(fig3)
                
            with p_col2:
                st.pyplot(fig2)
                st.pyplot(fig4)

            st.markdown("---")

            # --- Display Tables ---
            t_col1, t_col2 = st.columns(2)

            with t_col1:
                st.subheader("Best Fit Distribution")
                st.dataframe(dist_table, use_container_width=True)

            with t_col2:
                st.subheader("Final EPS Scores")
                st.dataframe(eps_out, use_container_width=True)
                
                # Add download button for the final scores
                csv = eps_out.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "Download EPS Scores",
                    csv,
                    "final_eps_scores.csv",
                    "text/csv"
                )


            # Now, if you want the user to DOWNLOAD this processed file:
            st.subheader("Download Processed Data")

            import io
            buffer = io.BytesIO()

            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                # You can write the main processed data
                full_df.to_excel(writer, sheet_name='Processed_Data', index=False)
                # You can also add the other tables if you want all in one file
                dist_table.to_excel(writer, sheet_name='Distribution_Fit', index=False)
                eps_out.to_excel(writer, sheet_name='EPS_Scores', index=False)

            # Create the download button
            st.download_button(
                label="Download Full Analysis Excel",
                data=buffer.getvalue(),
                file_name="Earthquake_Analysis_Complete.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"An error occurred during calculation: {e}")
    else:
        st.warning("Please upload the Excel file and ensure at least one city is entered.")

    