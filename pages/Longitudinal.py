import os
import streamlit as st
import pandas as pd
import hmac


def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        secret_password = os.getenv("PASSWORD")
        if hmac.compare_digest(st.session_state["password"], secret_password):
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


# Cache the data after loading for performance. If we ever have more real time data,
# we should change this to a session state variable.
@st.cache_data(show_spinner="Loading data...")
def load_and_autofill_data() -> pd.DataFrame:
    """loads the data

    Returns:
        pd.DataFrame: loaded arrow dataframe
    """
    # Load dataset
    data = pd.read_excel("PRODRSOMDashboardDat_DATA_2024-06-04_1845.xlsx")

    # Convert 'tss' to numeric, forcing non-numeric values to NaN
    data['tss'] = pd.to_numeric(data['tss'], errors='coerce')
    # Propagate values for sex_dashboard, graft_dashboard2, and prior_aclr so they are consistent throughout the record id
    data = autofill(data, ['sex_dashboard', 'graft_dashboard2', 'prior_aclr'])
    return data


def autofill(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Function to fill missing values for each record id

    Args:
        df (pd.DataFrame): arrow dataset
        columns (list[str]): list of columns to autofill

    Returns:
        pd.DataFrame: autofilled dataframe
    """
    for column in columns:
        df[column] = df.groupby('record_id')[column].ffill().bfill()
    return df


data = load_and_autofill_data()


def filter_count(df: pd.DataFrame, cols: list[str], variables: list[str]) -> tuple[dict[str, int], pd.DataFrame]:
    """Function applies filters and counts non-blank records for each variable

    Args:
        df (pd.DataFrame): arrow dataframe
        cols (list[str]): list of columns to filter
        variables (list[str]): list of columns to display counts for

    Returns:
        tuple[dict[str, int], pd.DataFrame]: tuple of dictionary of non-blank counts
                                             and the filtered dataframe 
    """
    filtered_df = df.copy()
    # Check if we should only look at record_ids with long-term outcomes
    if only_long_term_outcomes:
        filtered_df = filtered_df.groupby('record_id').filter(
            lambda grp: grp['long_term_outcomes_complete'].notna().sum() >= 1)
    for column, values in cols.items():  # Iterates through each filter
        if column in ['age', 'tss']:
            filtered_df = filtered_df[filtered_df[column].between(
                values[0], values[1])]
        elif values:  # Only apply filter if values are not empty
            filtered_df = filtered_df[filtered_df[column].isin(values)]

    # Count non-blank records for each variable
    non_blank_counts = {
        var: filtered_df[var].notna().sum() for var in variables}

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
# Make the timepoints one more than right bound so that we
# are effectively flooring everything when organizing longitudinal
# columns. Ex: 7.5 months tss becomes
timepoints = {
    "3-4 months": (3, 5),
    "5-7 months": (5, 8),
    "8-12 months": (8, 13),
    "13-24 months": (13, 25)
}


def longitudinal_filter(data: pd.DataFrame, timepoints: dict[str, tuple[int, int]], variables: list[str]) -> dict[str, dict[str, int]]:
    """Function for longitudinal filter and count

    Args:
        data (pd.DataFrame): arrow dataframe
        timepoints (dict[str, tuple[int, int]]): timepoints for longitudinal filter in months
        variables (list[str]): list of columns to display counts

    Returns:
        dict[str, dict[str, int]]: dictionary of variables and their longitudinal counts
    """
    longitudinal_counts = {var: {tp: 0 for tp in timepoints}
                           for var in variables}

    for tp_label, tp_range in timepoints.items():
        tp_data = data[(data['tss'] >= tp_range[0]) &
                       (data['tss'] < tp_range[1])]
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
        selected_values = st.multiselect(
            f"Select value/s for '{column}' (**Leave blank to select all**)", options)
        # Converting yes/no to 1/0
        selected_values = [1 if v == "Yes" else 0 for v in selected_values]
        if selected_values:  # Only add to cols if not empty
            cols['prior_aclr'] = selected_values  # Correct column name
    elif column == "Participant Sex":
        selected_values = st.multiselect(
            f"Select value/s for '{column}' (**Leave blank to select all**)", options)
        if selected_values:  # Only add to cols if not empty
            cols['sex_dashboard'] = selected_values  # Correct column name
    elif column == "Graft Type":
        selected_values = st.multiselect(
            f"Select value/s for '{column}' (**Leave blank to select all**)", options)
        if selected_values:  # Only add to cols if not empty
            cols['graft_dashboard2'] = selected_values  # Correct column name

# Add age range slider
age_min = int(data['age'].min())  # Min age in dataset
# Max age in dataset. Add 1 because int takes floor of float
age_max = int(data['age'].max() + 1)
age_range = st.slider("Select age range (**Leave blank to select all**)", min_value=age_min,
                      # Slider widget with integer step
                      max_value=age_max, value=(age_min, age_max), step=1)
cols['age'] = age_range

# Add tss range slider
tss_min = int(data['tss'].min())  # Min tss in dataset
# Max tss in dataset. Add 1 because int takes floor of float
tss_max = int(data['tss'].max() + 1)
tss_range = st.slider("Select time since surgery range (in months) (**Leave blank to select all**)",
                      min_value=tss_min, max_value=tss_max, value=(tss_min, tss_max), step=1)
cols['tss'] = tss_range

# Add long-term outcomes checkbox
only_long_term_outcomes = st.checkbox(
    "Include Only Results with a Long-Term Outcome", value=False)

# Call the function
if st.button("Apply Filters"):
    result_counts, filtered_data = filter_count(
        df=data, cols=cols, variables=variables)
    longitudinal_counts = longitudinal_filter(
        filtered_data, timepoints, variables)

    # Display results in a table format
    st.write("Counts of Non-Blank Records for Variables by Timepoint:")
    longitudinal_df = pd.DataFrame(longitudinal_counts).T
    st.dataframe(longitudinal_df)
