import streamlit as st

# Set the page config to open to the hello page by default
st.set_page_config(
    page_title="Home",
    page_icon="👋",
)


st.title("Welcome to the ARROW Data Counter")
st.write("Use the menu on the left to select a page.")

st.sidebar.success("Select a page above.")
