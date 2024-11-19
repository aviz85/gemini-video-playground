import streamlit as st
from utils.supabase_client import init_supabase, require_auth

def add_prompt(text, description):
    """Add new prompt"""
    supabase = init_supabase()
    return supabase.table("prompts").insert({
        "text": text,
        "description": description,
        "created_by": st.session_state.user.id
    }).execute()

def get_prompts():
    """Get user's prompts"""
    supabase = init_supabase()
    return supabase.table("prompts").select("*").eq(
        "created_by", st.session_state.user.id
    ).execute()

def delete_prompt(prompt_id):
    """Delete prompt"""
    supabase = init_supabase()
    return supabase.table("prompts").delete().eq("id", prompt_id).execute()

def show_prompt_management():
    """Display prompt management UI"""
    require_auth()
    st.header("📝 Prompt Management")
    
    # Add new prompt
    with st.form("add_prompt"):
        description = st.text_input("Prompt Title/Description")
        prompt_text = st.text_area("Prompt Text", height=100)
        col1, col2 = st.columns([4,1])
        with col2:
            submitted = st.form_submit_button("Add Prompt", use_container_width=True)
        
        if submitted:
            if not description or not prompt_text:
                st.error("Both fields are required")
            else:
                add_prompt(prompt_text, description)
                st.success("Prompt added!")
                st.rerun()
    
    # List existing prompts
    prompts = get_prompts()
    
    if prompts.data:
        for prompt in prompts.data:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.text(prompt["description"])
            with col2:
                created_at = prompt["created_at"].split("T")[0]  # Show only date
                st.text(created_at)
            with col3:
                if st.button("Delete", key=f"del_{prompt['id']}"):
                    delete_prompt(prompt["id"])
                    st.rerun() 