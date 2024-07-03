import streamlit as st
import pandas as pd
import hmac

# Password function
def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # deletes password 
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    # Ask user for password
    st.text_input(
        "Password", type="password", on_change=password_entered, key="password"
    )
    if "password_correct" in st.session_state:
        st.error("😕 Password incorrect")
    return False

if not check_password():
    st.stop()  # Do not continue if password is wrong

# Streamlit title and subtitle
st.title("ARROW Data Counter with Longitudinal Filter")  # Title
st.write("This app will count non-blank record counts for variables given specified criteria, including longitudinal filtering.")

# Load dataset
data = pd.read_excel("PRODRSOMDashboardDat_DATA_2024-06-04_1845.xlsx")

# Convert 'tss' to numeric, forcing non-numeric values to NaN
data['tss'] = pd.to_numeric(data['tss'], errors='coerce')

# Function to fill missing values for each record id
def autofill(df, columns):
    for column in columns:
        df[column] = df.groupby('record_id')[column].ffill().bfill()
    return df

# Propagate values for sex_dashboard, graft_dashboard2, and prior_aclr so they are consistent throughout the record id
data = autofill(data, ['sex_dashboard', 'graft_dashboard2', 'prior_aclr'])

# Function applies filters and counts non-blank records for each variable
def filter_count(df, cols, variables):
    filtered_df = df.copy()
    for column, values in cols.items():  # Iterates through each filter
        if column in ['age', 'tss']:
            filtered_df = filtered_df[filtered_df[column].between(values[0], values[1])]
        elif values:  # Only apply filter if values are not empty
            filtered_df = filtered_df[filtered_df[column].isin(values)]

    # Count non-blank records for each variable
    non_blank_counts = {var: filtered_df[var].notna().sum() for var in variables} 
        
    return non_blank_counts, filtered_df

# Define variables to count non-blank records
variables = [
    "insurance_dashboard_use", "ikdc", "pedi_ikdc", "marx", "pedi_fabs", "koos_pain", 
    "koos_sx", "koos_adl", "koos_sport", "koos_qol", "acl_rsi", "tsk", "rsi_score", 
    "rsi_emo", "rsi_con", "sh_lsi", "th_lsi", "ch_lsi", "lsi_ext_mvic_90", 
    "lsi_ext_mvic_60", "lsi_flex_mvic_60", "lsi_ext_isok_60", "lsi_flex_isok_60", 
    "lsi_ext_isok_90", "lsi_flex_isok_90", "lsi_ext_isok_180", "lsi_flex_isok_180", 
    "rts", "reinjury"]

# Define timepoints for longitudinal filter in months
timepoints = {
    "3-4 months": (3, 4),
    "5-7 months": (5, 7),
    "8-12 months": (8, 12),
    "13-24 months": (13, 24)
}

# Function for longitudinal filter and count
def longitudinal_filter(data, timepoints, variables):
    longitudinal_counts = {var: {tp: 0 for tp in timepoints} for var in variables}
    
    for tp_label, tp_range in timepoints.items():
        tp_data = data[(data['tss'] >= tp_range[0]) & (data['tss'] <= tp_range[1])]
        for var in variables:
            longitudinal_counts[var][tp_label] = tp_data[var].notna().sum()
    
    return longitudinal_counts

# Ask for filter criteria
st.subheader("Enter criteria:")
cols = {}

# Filters with subgroups
filter_columns = {
    "Participant Sex": ["Female", "Male"],
    "Graft Type": ["Allograft", "BTB autograft", "HS autograft", "Other", "QT autograft"],
    "Prior ACL?": ["Yes", "No"]
}

# Make drop-down selections for each filter
for column, options in filter_columns.items():
    if column == "Prior ACL?":
        selected_values = st.multiselect(f"Select value/s for '{column}'", options) 
        selected_values = [1 if v == "Yes" else 0 for v in selected_values]  # Converting yes/no to 1/0
        if selected_values:  # Only add to cols if not empty
            cols['prior_aclr'] = selected_values  # Correct column name
    elif column == "Participant Sex":
        selected_values = st.multiselect(f"Select value/s for '{column}'", options)
        if selected_values:  # Only add to cols if not empty
            cols['sex_dashboard'] = selected_values  # Correct column name
    elif column == "Graft Type":
        selected_values = st.multiselect(f"Select value/s for '{column}'", options)
        if selected_values:  # Only add to cols if not empty
            cols['graft_dashboard2'] = selected_values  # Correct column name

# Add age range slider
age_min = int(data['age'].min())  # Min age in dataset
age_max = int(data['age'].max())  # Max age in dataset
age_range = st.slider("Select age range", min_value=age_min, max_value=age_max, value=(age_min, age_max), step=1)  # Slider widget with integer step
cols['age'] = age_range

# Add tss range slider
tss_min = int(data['tss'].min())  # Min tss in dataset
tss_max = int(data['tss'].max())  # Max tss in dataset
tss_range = st.slider("Select time since surgery range (in months)", min_value=tss_min, max_value=tss_max, value=(tss_min, tss_max), step=1)
cols['tss'] = tss_range

# Call the function 
if st.button("Apply Filters"): 
    result_counts, filtered_data = filter_count(df=data, cols=cols, variables=variables)
    longitudinal_counts = longitudinal_filter(filtered_data, timepoints, variables)
    
    # Display results in a table format
    st.write("Counts of Non-Blank Records for Variables by Timepoint:")
    longitudinal_df = pd.DataFrame(longitudinal_counts).T
    st.dataframe(longitudinal_df)
