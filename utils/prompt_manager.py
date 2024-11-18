import streamlit as st
from utils.supabase_client import init_supabase, require_auth

def add_prompt(text, category=None):
    """Add new prompt"""
    supabase = init_supabase()
    return supabase.table("prompts").insert({
        "text": text,
        "category": category,
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
        prompt_text = st.text_area("New Prompt")
        category = st.text_input("Category (optional)")
        submitted = st.form_submit_button("Add Prompt")
        
        if submitted and prompt_text:
            add_prompt(prompt_text, category)
            st.success("Prompt added!")
            st.rerun()
    
    # List existing prompts
    prompts = get_prompts()
    
    if prompts.data:
        for prompt in prompts.data:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.text(prompt["text"])
            with col2:
                st.text(prompt["category"] or "")
            with col3:
                if st.button("Delete", key=f"del_{prompt['id']}"):
                    delete_prompt(prompt["id"])
                    st.rerun() 