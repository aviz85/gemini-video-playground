import streamlit as st
from supabase import create_client

def init_supabase():
    """Initialize Supabase client"""
    if 'supabase' not in st.session_state:
        client = create_client(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_KEY"]
        )
        st.session_state.supabase = client
    return st.session_state.supabase

def get_user():
    """Get current user from session"""
    return st.session_state.get('user', None)

def require_auth():
    """Require authentication to access page"""
    if 'authenticated' not in st.session_state or not st.session_state.authenticated:
        st.warning("Please log in to access this page")
        st.stop() 