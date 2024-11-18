import os
import time
from pathlib import Path
import streamlit as st
import google.generativeai as genai
from supabase import create_client

# Initialize Supabase client
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

# Page configuration
st.set_page_config(
    page_title="Gemini Video Analysis",
    page_icon="🎥",
    layout="wide"
)

def init_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None

def verify_api_key():
    """Verify Gemini API key"""
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        models = genai.list_models()
        st.session_state.available_models = [
            m.name for m in models 
            if "generateContent" in m.supported_generation_methods
        ]
        return True
    except Exception as e:
        st.error(f"❌ API key verification failed: {str(e)}")
        return False

def login_form():
    """Display login form"""
    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            try:
                response = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                st.session_state.authenticated = True
                st.session_state.user = response.user
                st.session_state.session = response.session
                st.rerun()
            except Exception as e:
                st.error(f"Login failed: {str(e)}")

def signup_form():
    """Display signup form"""
    with st.form("signup"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Sign Up")
        
        if submitted:
            if password != confirm_password:
                st.error("Passwords don't match")
                return
            try:
                response = supabase.auth.sign_up({
                    "email": email,
                    "password": password
                })
                st.success("Signup successful! Please check your email to verify your account.")
            except Exception as e:
                st.error(f"Signup failed: {str(e)}")

def show_auth_page():
    """Display authentication page"""
    st.title("🎥 Gemini Video Analysis")
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        login_form()
    with tab2:
        signup_form()

def manage_prompts():
    """Prompt management panel"""
    st.header("📝 Prompt Management")
    
    # Add new prompt
    with st.form("add_prompt"):
        prompt_text = st.text_area("New Prompt")
        category = st.text_input("Category (optional)")
        submitted = st.form_submit_button("Add Prompt")
        
        if submitted and prompt_text:
            supabase.table("prompts").insert({
                "text": prompt_text,
                "category": category,
                "created_by": st.session_state.user.id
            }).execute()
            st.success("Prompt added!")
            st.rerun()
    
    # List existing prompts
    prompts = supabase.table("prompts").select("*").eq("created_by", st.session_state.user.id).execute()
    
    if prompts.data:
        for prompt in prompts.data:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.text(prompt["text"])
            with col2:
                st.text(prompt["category"] or "")
            with col3:
                if st.button("Delete", key=f"del_{prompt['id']}"):
                    supabase.table("prompts").delete().eq("id", prompt["id"]).execute()
                    st.rerun()

def manage_video_groups():
    """Video groups management panel"""
    st.header("📁 Video Groups")
    
    # Add new group
    with st.form("add_group"):
        group_name = st.text_input("Group Name")
        description = st.text_area("Description")
        submitted = st.form_submit_button("Create Group")
        
        if submitted and group_name:
            supabase.table("video_groups").insert({
                "name": group_name,
                "description": description,
                "created_by": st.session_state.user.id
            }).execute()
            st.success("Group created!")
            st.rerun()
    
    # List groups
    groups = supabase.table("video_groups").select("*").eq("created_by", st.session_state.user.id).execute()
    
    if groups.data:
        for group in groups.data:
            with st.expander(group["name"]):
                st.write(group["description"])
                
                # Upload videos to group
                uploaded_files = st.file_uploader(
                    "Upload Videos", 
                    type=["mp4", "mov", "avi"],
                    accept_multiple_files=True,
                    key=f"upload_{group['id']}"
                )
                
                if uploaded_files:
                    for video in uploaded_files:
                        # Save video file
                        file_path = f"videos/{video.name}"
                        with open(file_path, "wb") as f:
                            f.write(video.getbuffer())
                            
                        # Add to database
                        supabase.table("videos").insert({
                            "name": video.name,
                            "file_path": file_path,
                            "mime_type": video.type,
                            "group_id": group["id"],
                            "created_by": st.session_state.user.id
                        }).execute()
                
                # List videos in group
                videos = supabase.table("videos").select("*").eq("group_id", group["id"]).execute()
                if videos.data:
                    st.write("Videos in group:")
                    for video in videos.data:
                        st.write(f"- {video['name']}")

def create_batch():
    """Batch analysis creation panel"""
    st.header("🔄 Create Analysis Batch")
    
    # Get user's groups
    groups = supabase.table("video_groups").select("*").eq("created_by", st.session_state.user.id).execute()
    
    if not groups.data:
        st.warning("Create a video group first!")
        return
        
    # Get user's prompts
    prompts = supabase.table("prompts").select("*").eq("created_by", st.session_state.user.id).execute()
    
    if not prompts.data:
        st.warning("Create some prompts first!")
        return
    
    # Create batch form
    with st.form("create_batch"):
        batch_name = st.text_input("Batch Name")
        selected_group = st.selectbox("Select Video Group", options=groups.data, format_func=lambda x: x["name"])
        selected_prompt = st.selectbox("Select Prompt", options=prompts.data, format_func=lambda x: x["text"])
        selected_model = st.selectbox("Select Model", options=st.session_state.available_models)
        
        submitted = st.form_submit_button("Create Batch")
        
        if submitted and batch_name:
            # Create batch
            batch = supabase.table("analysis_batches").insert({
                "name": batch_name,
                "group_id": selected_group["id"],
                "prompt_id": selected_prompt["id"],
                "model_name": selected_model,
                "created_by": st.session_state.user.id
            }).execute()
            
            # Create analysis entries for each video
            videos = supabase.table("videos").select("*").eq("group_id", selected_group["id"]).execute()
            
            for video in videos.data:
                supabase.table("video_analysis").insert({
                    "video_id": video["id"],
                    "batch_id": batch.data[0]["id"],
                    "prompt_id": selected_prompt["id"],
                    "model_name": selected_model,
                    "created_by": st.session_state.user.id
                }).execute()
            
            st.success("Batch created!")
            st.rerun()

def view_results():
    """Results viewer panel"""
    st.header("📊 Analysis Results")
    
    # Get batches
    batches = supabase.table("analysis_batches").select("*").eq("created_by", st.session_state.user.id).execute()
    
    if batches.data:
        for batch in batches.data:
            with st.expander(f"Batch: {batch['name']}"):
                # Get analyses for this batch
                analyses = supabase.table("video_analysis").select(
                    "*, videos(name), prompts(text)"
                ).eq("batch_id", batch["id"]).execute()
                
                if analyses.data:
                    # Create dataframe for display
                    import pandas as pd
                    df = pd.DataFrame([{
                        "Video": a["videos"]["name"],
                        "Prompt": a["prompts"]["text"],
                        "Status": a["status"],
                        "Analysis": a["analysis"] or "",
                        "Error": a["error"] or ""
                    } for a in analyses.data])
                    
                    st.dataframe(
                        df,
                        column_config={
                            "Video": st.column_config.TextColumn("Video"),
                            "Analysis": st.column_config.TextColumn("Analysis", width="large"),
                            "Error": st.column_config.TextColumn("Error", width="medium")
                        }
                    )

def main():
    """Main application"""
    init_session_state()
    
    if not verify_api_key():
        st.stop()
    
    if not st.session_state.authenticated:
        show_auth_page()
        return
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["Prompt Management", "Video Groups", "Create Batch", "View Results"]
    )
    
    # Logout button
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()
    
    # Page routing
    if page == "Prompt Management":
        manage_prompts()
    elif page == "Video Groups":
        manage_video_groups()
    elif page == "Create Batch":
        create_batch()
    elif page == "View Results":
        view_results()

if __name__ == "__main__":
    main() 