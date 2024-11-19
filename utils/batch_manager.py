import streamlit as st
from utils.supabase_client import init_supabase, require_auth
from utils.videos import get_video_groups, get_group_videos, get_thumbnail_url
from utils.prompt_manager import get_prompts
import google.generativeai as genai

def create_batch():
    """Create and manage batch analysis"""
    require_auth()
    st.header("🔄 Create Batch Analysis")

    # Get video groups
    groups = get_video_groups()
    if not groups.data:
        st.warning("Create a video group first")
        return

    # Get prompts
    prompts = get_prompts()
    if not prompts.data:
        st.warning("Create prompts first")
        return

    # Select group
    group_options = {g["name"]: g["id"] for g in groups.data}
    selected_group = st.selectbox("Select Video Group", options=list(group_options.keys()))
    group_id = group_options[selected_group]

    # Get videos in group
    videos = get_group_videos(group_id)
    if not videos.data:
        st.warning("Add videos to the selected group first")
        return

    # Display videos with thumbnails
    st.subheader("Videos in Group")
    cols = st.columns(4)
    selected_videos = []

    for idx, video in enumerate(videos.data):
        with cols[idx % 4]:
            if video["thumbnail_path"]:
                thumb_url = get_thumbnail_url(video["thumbnail_path"])
                st.image(thumb_url, use_column_width=True)
            
            selected = st.checkbox("Select", key=f"vid_{video['id']}")
            if selected:
                selected_videos.append(video)

    # Select prompts
    st.subheader("Select Prompts")
    selected_prompts = []
    for prompt in prompts.data:
        if st.checkbox(prompt["description"], key=f"prompt_{prompt['id']}"):
            selected_prompts.append(prompt)

    # Model selection
    model_name = st.selectbox(
        "Select Model", 
        options=st.session_state.available_models
    )

    # Create batch
    if st.button("Create Batch", disabled=not (selected_videos and selected_prompts)):
        create_analysis_batch(selected_videos, selected_prompts, model_name)

def create_analysis_batch(videos, prompts, model_name):
    """Create a new analysis batch"""
    supabase = init_supabase()
    
    with st.status("Creating batch...") as status:
        try:
            # Create batch record
            batch = supabase.table("analysis_batches").insert({
                "model": model_name,
                "status": "pending",
                "created_by": st.session_state.user.id
            }).execute()
            
            batch_id = batch.data[0]["id"]
            
            # Create analysis tasks
            for video in videos:
                for prompt in prompts:
                    supabase.table("analysis_tasks").insert({
                        "batch_id": batch_id,
                        "video_id": video["id"],
                        "prompt_id": prompt["id"],
                        "status": "pending"
                    }).execute()
            
            status.update(label="✅ Batch created successfully!", state="complete")
            
        except Exception as e:
            status.update(label=f"❌ Error creating batch: {str(e)}", state="error")