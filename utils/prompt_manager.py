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

def edit_prompt(prompt_id, text, description):
    """Update existing prompt"""
    supabase = init_supabase()
    return supabase.table("prompts").update({
        "text": text,
        "description": description
    }).eq("id", prompt_id).execute()

def show_prompt_management():
    """Display prompt management UI"""
    require_auth()
    st.header("📝 Prompt Management")
    
    # Add new prompt
    with st.form("add_prompt"):
        description = st.text_input("Prompt Title/Description")
        prompt_text = st.text_area("Prompt Text", height=200)
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
            with st.expander(f"📝 {prompt['description']}", expanded=False):
                # Show created date
                st.caption(f"Created: {prompt['created_at'].split('T')[0]}")
                
                # Editable fields
                new_description = st.text_input("Title", value=prompt["description"], key=f"desc_{prompt['id']}")
                new_text = st.text_area("Text", value=prompt["text"], height=400, key=f"text_{prompt['id']}")
                
                # Action buttons in columns
                col1, col2, col3 = st.columns([1,1,4])
                with col1:
                    if st.button("Save", key=f"save_{prompt['id']}", type="primary", use_container_width=True):
                        if not new_description or not new_text:
                            st.error("Both fields are required")
                        else:
                            edit_prompt(prompt["id"], new_text, new_description)
                            st.success("Updated!")
                            st.rerun()
                with col2:
                    if st.button("Delete", key=f"del_{prompt['id']}", type="secondary", use_container_width=True):
                        delete_prompt(prompt["id"])
                        st.success("Deleted!")
                        st.rerun()
    