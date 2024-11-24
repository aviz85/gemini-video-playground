import streamlit as st
from utils.supabase_client import init_supabase, require_auth
from utils.videos import get_video_groups, get_group_videos
from utils.prompt_manager import get_prompts
import google.generativeai as genai
from datetime import datetime

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

    # Create two columns
    col1, col2 = st.columns(2)

    with col1:
        # Select group
        group_options = {g["name"]: g["id"] for g in groups.data}
        selected_group = st.selectbox("Select Video Group", options=list(group_options.keys()))
        group_id = group_options[selected_group]

        # Get videos count in group
        videos = get_group_videos(group_id)
        if not videos.data:
            st.warning("Add videos to the selected group first")
            return

        st.info(f"Selected group contains {len(videos.data)} videos")

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
        if st.button("Create Batch", disabled=not selected_prompts):
            batch_id = create_analysis_batch(videos.data, selected_prompts, model_name)
            if batch_id:
                st.session_state.last_batch_id = batch_id  # Store batch_id for processing

    with col2:
        st.subheader("Process Batch")
        if 'last_batch_id' in st.session_state:
            if st.button("Process Latest Batch"):
                process_batch_tasks(st.session_state.last_batch_id)
        
        # Show all pending batches
        supabase = init_supabase()
        pending_batches = supabase.table("analysis_batches") \
            .select("*") \
            .eq("status", "pending") \
            .eq("created_by", st.session_state.user.id) \
            .execute()

        if pending_batches.data:
            st.subheader("Or Process Pending Batch")
            batch_options = {
                f"Batch {b['id'][:8]} ({b['total_videos']} videos)": b['id'] 
                for b in pending_batches.data
            }
            selected_batch = st.selectbox(
                "Select Pending Batch", 
                options=list(batch_options.keys()),
                key="pending_batch_select"
            )
            if st.button("Process Selected Batch"):
                process_batch_tasks(batch_options[selected_batch])
        else:
            st.info("No pending batches available")

def create_analysis_batch(videos, prompts, model_name):
    """Create a new analysis batch"""
    supabase = init_supabase()
    
    with st.status("Creating batch...") as status:
        try:
            total_videos = len(videos)
            
            # Create batch record
            batch_response = supabase.table("analysis_batches").insert({
                "model_name": model_name,
                "status": "pending",
                "progress": 0,
                "total_videos": total_videos,
                "created_by": st.session_state.user.id
            }).execute()
            
            if not batch_response.data:
                raise Exception("Failed to create batch record")
            
            batch_id = batch_response.data[0]["id"]
            status.write(f"Created batch ID: {batch_id}")
            
            # Create analysis tasks
            total_tasks = total_videos * len(prompts)
            status.write(f"Creating {total_tasks} analysis tasks...")
            tasks_created = 0
            
            for video in videos:
                for prompt in prompts:
                    # Debug info
                    st.write(f"Debug - Creating task with:")
                    st.write({
                        "batch_id": batch_id,
                        "video_id": video["id"],
                        "prompt_id": prompt["id"]
                    })
                    
                    try:
                        task_response = supabase.table("analysis_tasks").insert({
                            "batch_id": batch_id,
                            "video_id": video["id"],
                            "prompt_id": prompt["id"],
                            "status": "pending",
                            "created_by": st.session_state.user.id  # Add this if required
                        }).execute()
                        
                        tasks_created += 1
                        status.write(f"Created {tasks_created}/{total_tasks} tasks")
                    except Exception as task_error:
                        st.error(f"Task creation error: {str(task_error)}")
                        # Continue with next task instead of failing completely
                        continue
            
            if tasks_created == total_tasks:
                status.update(label=f"✅ Batch created with {tasks_created} tasks!", state="complete")
            else:
                status.update(label=f"⚠️ Batch created with {tasks_created}/{total_tasks} tasks", state="error")
            
            return batch_id  # Return batch_id for processing
            
        except Exception as e:
            st.error(f"Detailed error: {str(e)}")
            status.update(label=f"❌ Error creating batch: {str(e)}", state="error")
            # Print full error details for debugging
            import traceback
            st.error(traceback.format_exc())
            return None

def process_batch():
    """Process and manage batch analysis"""
    require_auth()
    st.header("🔄 Process Batch Analysis")

    # Get pending batches
    supabase = init_supabase()
    batches = supabase.table("analysis_batches") \
        .select("*") \
        .eq("status", "pending") \
        .eq("created_by", st.session_state.user.id) \
        .execute()

    if not batches.data:
        st.info("No pending batches found")
        return

    # Select batch to process
    batch_options = {f"Batch {b['id'][:8]} ({b['total_videos']} videos)": b['id'] 
                    for b in batches.data}
    selected_batch = st.selectbox("Select Batch", options=list(batch_options.keys()))
    batch_id = batch_options[selected_batch]

    if st.button("Process Batch"):
        process_batch_tasks(batch_id)

def process_batch_tasks(batch_id):
    """Process all tasks in a batch"""
    # Configure Gemini API
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
    supabase = init_supabase()
    
    # Get batch info
    batch = supabase.table("analysis_batches") \
        .select("*") \
        .eq("id", batch_id) \
        .single() \
        .execute()

    if not batch.data:
        st.error("Batch not found")
        return

    # Get all tasks
    tasks = supabase.table("analysis_tasks") \
        .select("*, videos(*), prompts(*)") \
        .eq("batch_id", batch_id) \
        .eq("status", "pending") \
        .execute()

    if not tasks.data:
        st.error("No pending tasks found for this batch")
        return

    total_tasks = len(tasks.data)
    
    with st.status("Processing batch...") as status:
        progress_text = st.empty()
        progress_bar = st.progress(0)
        tasks_completed = 0
        
        try:
            # Initialize the model once
            model = genai.GenerativeModel(
                model_name=batch.data['model_name'],
                generation_config={
                    "temperature": 0.4,
                    "top_p": 0.8,
                    "top_k": 40,
                    "max_output_tokens": 2048,
                }
            )
            
            for index, task in enumerate(tasks.data):
                current = index + 1
                progress = (current / total_tasks) * 100
                
                # Update progress
                progress_text.write(f"Processing task {current}/{total_tasks}")
                progress_bar.progress(int(progress))
                
                try:
                    # Get video file from Gemini
                    video_file = genai.get_file(task['videos']['gemini_file_id'])
                    
                    # Get prompt text
                    prompt_text = task['prompts']['text']
                    
                    # Analyze video
                    status.write(f"🎥 Analyzing video {task['videos']['id']}")
                    response = model.generate_content([video_file, prompt_text])
                    result = response.text
                    
                    # Update task with result
                    supabase.table("analysis_tasks").update({
                        "status": "completed",
                        "result": {"analysis": result},
                        "completed_at": datetime.utcnow().isoformat()
                    }).eq("id", task["id"]).execute()
                    
                    tasks_completed += 1
                    
                    # Update batch progress
                    supabase.table("analysis_batches").update({
                        "progress": tasks_completed,
                        "status": "processing" if tasks_completed < total_tasks else "completed",
                        "completed_at": datetime.utcnow().isoformat() if tasks_completed == total_tasks else None
                    }).eq("id", batch_id).execute()
                    
                except Exception as e:
                    st.error(f"Task failed: {str(e)}")
                    # Update task with error
                    supabase.table("analysis_tasks").update({
                        "status": "failed",
                        "error": str(e),
                        "completed_at": datetime.utcnow().isoformat()
                    }).eq("id", task["id"]).execute()
                    continue
            
            if tasks_completed > 0:
                status.update(label=f"✅ Processed {tasks_completed} tasks!", state="complete")
            else:
                status.update(label="❌ No tasks were processed successfully", state="error")
            
        except Exception as e:
            st.error(f"Batch processing failed: {str(e)}")
            import traceback
            st.error(traceback.format_exc())