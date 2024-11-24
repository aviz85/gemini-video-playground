import streamlit as st
import json
from utils.supabase_client import init_supabase, require_auth
import re
from typing import Dict, Any

def clean_json_string(raw_json: str) -> str:
    """Clean JSON string from Gemini output"""
    # Extract JSON content between triple backticks
    json_match = re.search(r'```json\n(.*?)\n```', raw_json, re.DOTALL)
    if json_match:
        return json_match.group(1)
    return raw_json

def parse_analysis_result(result: Dict[str, Any]) -> Dict:
    """Parse and beautify analysis result"""
    if not result or 'analysis' not in result:
        return {}
        
    try:
        # Clean the JSON string
        clean_json = clean_json_string(result['analysis'])
        
        # Parse the cleaned JSON
        parsed = json.loads(clean_json)
        
        # Format specific fields for better display
        if 'videoQuality' in parsed:
            parsed['videoQuality'] = {
                'rating': parsed['videoQuality']['visual'],
                'details': parsed['videoQuality']['description']
            }
            
        if 'categories' in parsed:
            parsed['categories'] = parsed['categories']['selections']
            
        if 'toxicity' in parsed:
            parsed['toxicity'] = {
                'acceptable': parsed['toxicity']['isAcceptable'],
                'level': parsed['toxicity']['level'],
                'notes': parsed['toxicity']['reason'] or 'None'
            }
            
        return parsed
        
    except json.JSONDecodeError as e:
        st.error(f"Failed to parse JSON: {str(e)}")
        return {'error': 'Invalid JSON format'}

def show_batch_results():
    """Show analysis results"""
    require_auth()
    st.header("📊 Analysis Results")

    # Get all batches for user
    supabase = init_supabase()
    batches = supabase.table("analysis_batches") \
        .select("*") \
        .eq("created_by", st.session_state.user.id) \
        .order("created_at", desc=True) \
        .execute()

    if not batches.data:
        st.info("No analysis batches found")
        return

    # Select batch
    batch_options = {
        f"Batch {b['id'][:8]} ({b['total_videos']} videos, {b['status']})": b['id'] 
        for b in batches.data
    }
    selected_batch = st.selectbox(
        "Select Batch", 
        options=list(batch_options.keys())
    )
    batch_id = batch_options[selected_batch]

    # Create tabs for stats and individual results
    tab1, tab2 = st.tabs(["📈 Batch Statistics", "🔍 Individual Results"])

    with tab1:
        show_batch_statistics(batch_id)

    with tab2:
        show_individual_results(batch_id)

def show_batch_statistics(batch_id):
    """Show statistics for selected batch"""
    supabase = init_supabase()
    
    # Get all tasks for batch
    tasks = supabase.table("analysis_tasks") \
        .select("*, videos(*), prompts(*)") \
        .eq("batch_id", batch_id) \
        .execute()

    if not tasks.data:
        st.warning("No tasks found for this batch")
        return

    # Calculate statistics
    total_tasks = len(tasks.data)
    completed_tasks = sum(1 for t in tasks.data if t['status'] == 'completed')
    failed_tasks = sum(1 for t in tasks.data if t['status'] == 'failed')
    pending_tasks = sum(1 for t in tasks.data if t['status'] == 'pending')

    # Display statistics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Tasks", total_tasks)
    with col2:
        st.metric("Completed", completed_tasks)
    with col3:
        st.metric("Failed", failed_tasks)
    with col4:
        st.metric("Pending", pending_tasks)

    # Show completion percentage
    if total_tasks > 0:
        progress = completed_tasks / total_tasks
        st.progress(progress)
        st.caption(f"{progress:.1%} Complete")

def show_individual_results(batch_id):
    # Initialize session state for JSON toggles if not exists
    if 'json_toggles' not in st.session_state:
        st.session_state.json_toggles = {}

    supabase = init_supabase()
    tasks = supabase.table("analysis_tasks") \
        .select("*, videos(id, thumbnail_path, source_url, metadata)") \
        .eq("batch_id", batch_id) \
        .execute()

    if not tasks.data:
        st.warning("No tasks found for this batch")
        return

    # Filter options
    status_filter = st.multiselect(
        "Filter by Status",
        options=["completed", "failed", "pending"],
        default=["completed"]
    )

    filtered_tasks = [t for t in tasks.data if t['status'] in status_filter]

    for task in filtered_tasks:
        st.divider()
        
        # Get video details
        video = task['videos']
        title = video.get('metadata', {}).get('title', video['id'])
        
        # Create columns for thumbnail and details
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader(title)
            
            # Display video player if source_url exists, otherwise show thumbnail
            if video['source_url']:
                st.video(video['source_url'])
            elif video['thumbnail_path']:
                try:
                    thumbnail_url = supabase.storage.from_('videos').get_public_url(video['thumbnail_path'])
                    st.image(thumbnail_url, use_container_width=True)
                except Exception as e:
                    st.error(f"Failed to load thumbnail: {str(e)}")
            
            st.write("**Status:**", task['status'])
            if task['status'] == 'failed':
                st.error(f"Error: {task.get('error', 'Unknown error')}")

        with col2:
            if task['result']:
                try:
                    parsed_result = parse_analysis_result(task['result'])
                    
                    # Display metrics and other info...
                    
                    # Toggle button for JSON
                    toggle_key = f"json_{task['id']}"
                    if toggle_key not in st.session_state.json_toggles:
                        st.session_state.json_toggles[toggle_key] = False
                        
                    if st.button(
                        "Hide Raw JSON" if st.session_state.json_toggles[toggle_key] else "Show Raw JSON", 
                        key=f"toggle_{task['id']}"
                    ):
                        st.session_state.json_toggles[toggle_key] = not st.session_state.json_toggles[toggle_key]
                    
                    if st.session_state.json_toggles[toggle_key]:
                        st.code(json.dumps(parsed_result, indent=2), language="json")
                        
                except Exception as e:
                    st.error(f"Failed to parse result: {str(e)}")
                    st.code(str(task['result']))