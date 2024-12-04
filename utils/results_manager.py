import streamlit as st
import json
from utils.supabase_client import init_supabase, require_auth
import re
from typing import Dict, Any
import plotly.express as px
import plotly.figure_factory as ff
import pandas as pd
import numpy as np

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
        clean_json = clean_json_string(result['analysis'])
        parsed = json.loads(clean_json)
        
        # Find all numeric values in the parsed result that end with level/rating
        score_components = []
        for key, value in parsed.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    if (k.lower().endswith(('level', 'rating', 'score')) and 
                        isinstance(v, (int, float))):
                        score_components.append(v)
        
        # Calculate overall score (0-1000)
        valid_scores = [s for s in score_components if s > 0]
        parsed['overall_score'] = round((sum(valid_scores) / len(valid_scores)) * 100) if valid_scores else 0
        
        return parsed
        
    except json.JSONDecodeError as e:
        st.error(f"Failed to parse JSON: {str(e)}")
        return {'error': 'Invalid JSON format'}

def display_json_field(key: str, value: Any, level: int = 0):
    """Recursively display JSON fields with proper formatting"""
    indent = "  " * level
    
    if isinstance(value, dict):
        # Handle dictionary with level + description pattern
        if 'level' in value and 'description' in value:
            st.markdown(f"{indent}**{key}:** {value['level']} - {value['description']}")
            return
            
        # Handle boolean fields with checkmarks
        if any(k.startswith('is') for k in value.keys()):
            bool_fields = [f"{k}: {'✅' if v else '❌'}" for k, v in value.items() if k.startswith('is')]
            other_fields = {k: v for k, v in value.items() if not k.startswith('is') and k not in ['level', 'description']}
            
            if bool_fields:
                st.markdown(f"{indent}**{key}:** {', '.join(bool_fields)}")
            if other_fields:
                for k, v in other_fields.items():
                    display_json_field(k, v, level + 1)
            return
            
        # Handle version fields
        if 'version' in value:
            st.markdown(f"{indent}**{key}:** {value['version']}")
            return
            
        # Default dictionary handling
        st.markdown(f"{indent}**{key}:**")
        for k, v in value.items():
            if k not in ['level', 'description', 'version']:
                display_json_field(k, v, level + 1)
    else:
        if not key.lower().endswith(('level', 'version')):
            st.markdown(f"{indent}**{key}:** {value}")

def flatten_metrics(parsed_result: dict, prefix='') -> dict:
    """Recursively flatten nested metrics that contain numeric values"""
    flat = {}
    for key, value in parsed_result.items():
        if isinstance(value, dict):
            # If dict has a 'level' key, use that value
            if 'level' in value:
                flat[key] = value['level']
            # Otherwise recurse with prefix
            else:
                flat.update(flatten_metrics(value, f"{prefix}{key}_"))
        elif isinstance(value, (int, float)):
            flat[f"{prefix}{key}"] = value
    return flat

def camel_to_title(name: str) -> str:
    """Convert camelCase to Title Case with spaces"""
    # Add space before capital letters and handle consecutive capitals
    spaced = ''.join(' ' + c if c.isupper() and i > 0 and not name[i-1].isupper() 
                     else c for i, c in enumerate(name))
    # Handle special cases like 'ID' or 'URL'
    words = spaced.strip().split()
    titled_words = []
    for word in words:
        if word.isupper() and len(word) <= 3:  # Keep abbreviations uppercase
            titled_words.append(word)
        else:
            titled_words.append(word.title())
    return ' '.join(titled_words)

def show_batch_results():
    """Show analysis results"""
    require_auth()
    st.header("📊 Analysis Results")

    # Get all batches for user with related data
    supabase = init_supabase()
    batches = supabase.table("analysis_batches") \
        .select("""
            *,
            video_groups!analysis_batches_group_id_fkey(name, is_red),
            prompts(description)
        """) \
        .eq("created_by", st.session_state.user.id) \
        .order("created_at", desc=True) \
        .execute()

    if not batches.data:
        st.info("No analysis batches found")
        return

    # Select batch with enhanced info - update access to video_groups
    batch_options = {
        f"Batch {b['id'][:8]} - "
        f"{b['video_groups']['name'] if b.get('video_groups') else 'No Group'} - "
        f"{b['prompts'][0]['description'] if b.get('prompts') else 'No Prompt'} "
        f"({b.get('total_videos', 0)} videos, {b.get('status', 'unknown')})": b['id']
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
    """Show statistics for batch with dynamic metrics"""
    import plotly.express as px
    import pandas as pd
    
    supabase = init_supabase()
    tasks = supabase.table("analysis_tasks") \
        .select("*, videos(*), prompts(*)") \
        .eq("batch_id", batch_id) \
        .execute()

    if not tasks.data:
        st.warning("No tasks found for this batch")
        return

    # Extract all metrics from completed tasks
    metrics_data = []
    for task in tasks.data:
        if task['status'] == 'completed' and task.get('result'):
            parsed = parse_analysis_result(task['result'])
            if parsed:
                # Flatten nested dictionaries
                flat_metrics = {'video_id': task['video_id']}
                
                # Add original score from video metadata
                if task['videos'].get('metadata', {}).get('score'):
                    flat_metrics['original_score'] = task['videos']['metadata']['score']
                
                # Add other metrics
                for key, value in parsed.items():
                    if isinstance(value, dict) and 'level' in value:
                        flat_metrics[key] = value['level']
                    else:
                        flat_metrics[key] = value
                metrics_data.append(flat_metrics)

    if not metrics_data:
        st.warning("No completed analysis data available")
        return

    df = pd.DataFrame(metrics_data)
    
    # Identify numerical columns (metrics)
    numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns

    # Create tabs for different visualization categories
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Distributions", "📈 Trends", "🔄 Correlations", "📊 Rankings"])

    with tab1:
        st.subheader("Score Distributions")
        
        # Distribution plots with multiple visualization options
        for col in numeric_cols:
            col1, col2 = st.columns(2)
            
            with col1:
                # Histogram with box plot
                fig = px.histogram(
                    df, x=col,
                    title=f"{col} Distribution",
                    nbins=20,
                    marginal="box"
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Violin plot
                fig = px.violin(
                    df, y=col,
                    title=f"{col} Violin Plot",
                    box=True,
                    points="all"
                )
                st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("Score Trends")
        
        # Line plots showing trends across videos
        for col in numeric_cols:
            fig = px.line(
                df.sort_values(col),
                y=col,
                title=f"{col} Trend Across Videos",
                markers=True
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Add percentile analysis
            percentiles = df[col].quantile([0.25, 0.5, 0.75])
            col1, col2, col3 = st.columns(3)
            col1.metric("25th Percentile", f"{percentiles[0.25]:.2f}")
            col2.metric("Median", f"{percentiles[0.5]:.2f}")
            col3.metric("75th Percentile", f"{percentiles[0.75]:.2f}")

    with tab3:
        st.subheader("Correlations Between Metrics")
        
        # Correlation heatmap
        corr = df[numeric_cols].corr()
        fig = px.imshow(
            corr,
            title="Correlation Matrix",
            color_continuous_scale='RdBu_r',
            aspect='auto',
            labels=dict(color="Correlation")
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Scatter matrix for selected metrics
        if len(numeric_cols) > 1:
            fig = px.scatter_matrix(
                df[numeric_cols],
                title="Scatter Plot Matrix",
                dimensions=numeric_cols
            )
            st.plotly_chart(fig, use_container_width=True)

    with tab4:
        st.subheader("Metric Rankings and Comparisons")
        
        # Bar charts showing ranking of videos by each metric
        for col in numeric_cols:
            fig = px.bar(
                df.sort_values(col, ascending=False),
                y=col,
                title=f"Videos Ranked by {col}",
                labels={col: "Score", "index": "Video Rank"}
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Show summary statistics
            stats = df[col].describe()
            cols = st.columns(4)
            cols[0].metric("Mean", f"{stats['mean']:.2f}")
            cols[1].metric("Std Dev", f"{stats['std']:.2f}")
            cols[2].metric("Min", f"{stats['min']:.2f}")
            cols[3].metric("Max", f"{stats['max']:.2f}")

    # Add overall insights
    st.subheader("📝 Key Insights")
    
    # Show highest and lowest scoring videos for each metric
    for col in numeric_cols:
        with st.expander(f"Top/Bottom Videos by {col}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write("Top 3 Videos:")
                st.dataframe(df.nlargest(3, col)[['video_id', col]])
            with col2:
                st.write("Bottom 3 Videos:")
                st.dataframe(df.nsmallest(3, col)[['video_id', col]])

    # Only show original vs overall score comparison if original scores exist
    if 'original_score' in df.columns:
        st.subheader("🎯 Original vs Overall Score Analysis")
        
        # Get all metrics from the first complete analysis to build columns
        sample_metrics = next((
            flatten_metrics(parse_analysis_result(task['result']))
            for task in tasks.data
            if task['status'] == 'completed' and task.get('result')
        ), {})
        
        # Update metrics_data to include all flattened metrics
        metrics_data = []
        for task in tasks.data:
            if task['status'] == 'completed' and task.get('result'):
                parsed = parse_analysis_result(task['result'])
                if parsed:
                    flat_metrics = {'video_id': task['video_id']}
                    if task['videos'].get('metadata', {}).get('score'):
                        flat_metrics['original_score'] = task['videos']['metadata']['score']
                    flat_metrics.update(flatten_metrics(parsed))
                    metrics_data.append(flat_metrics)

        df = pd.DataFrame(metrics_data)
        
        # Get all numeric columns except 'original_score' and 'video_id'
        score_columns = [col for col in df.select_dtypes(include=['int64', 'float64']).columns 
                        if col not in ['original_score', 'video_id']]
        
        # Create checkboxes for each score type in a grid layout
        num_cols = 4
        num_rows = (len(score_columns) + num_cols - 1) // num_cols
        
        for row in range(num_rows):
            cols = st.columns(num_cols)
            for col in range(num_cols):
                idx = row * num_cols + col
                if idx < len(score_columns):
                    score = score_columns[idx]
                    # Format display name
                    display_name = camel_to_title(score)
                    cols[col].checkbox(
                        display_name, 
                        key=f"cb_{score}",
                        value=(score == 'overall_score')
                    )
        
        # Get selected scores
        active_scores = [score for score in score_columns 
                        if st.session_state.get(f"cb_{score}")]
        
        if active_scores:
            # Create scatter plot with multiple traces
            fig = px.scatter(
                df.melt(
                    id_vars=['original_score'],
                    value_vars=active_scores,
                    var_name='Score Type',
                    value_name='Score'
                ),
                x='Score',
                y='original_score',
                color='Score Type',
                trendline="ols",
                title="Original Score vs Selected Scores Correlation",
                labels={
                    'original_score': 'Original Score',
                    'Score': 'Selected Scores',
                    'Score Type': 'Score Type'
                }
            )
            
            # Update traces to use formatted names in legend
            fig.for_each_trace(lambda t: t.update(
                name=camel_to_title(t.name) if t.name in active_scores 
                else t.name.replace('_', ' ').title()
            ))
            
            # Update layout for better readability
            fig.update_layout(
                height=600,
                legend=dict(
                    yanchor="top",
                    y=0.99,
                    xanchor="left",
                    x=0.01
                )
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Show correlations for active scores
            correlations = {score: df['original_score'].corr(df[score]) 
                          for score in active_scores}
            
            # Display correlations in a grid
            corr_cols = st.columns(min(4, len(correlations)))
            for i, (score, corr) in enumerate(correlations.items()):
                with corr_cols[i % 4]:
                    display_name = camel_to_title(score)
                    st.metric(f"{display_name}", f"{corr:.3f}")

def show_individual_results(batch_id):
    # Add sort state management
    if 'sort_field' not in st.session_state:
        st.session_state.sort_field = None
    if 'sort_direction' not in st.session_state:
        st.session_state.sort_direction = 'desc'

    # Initialize session state for JSON toggles if not exists
    if 'json_toggles' not in st.session_state:
        st.session_state.json_toggles = {}
    if 'table_settings' not in st.session_state:
        st.session_state.table_settings = {
            'sort_by': None,
            'sort_ascending': True,
            'filters': {},
            'visible_columns': ['title', 'status', 'overall_score']
        }

    # Get batch info including group details
    supabase = init_supabase()
    batch = supabase.table("analysis_batches") \
        .select("""
            *,
            video_groups!analysis_batches_group_id_fkey(*)
        """) \
        .eq("id", batch_id) \
        .single() \
        .execute()
    
    is_red = batch.data['video_groups']['is_red'] if batch.data.get('video_groups') else False

    tasks = supabase.table("analysis_tasks") \
        .select("*, videos(id, thumbnail_path, source_url, metadata, is_red)") \
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

    # Pagination
    items_per_page = 20
    total_pages = max(1, len(filtered_tasks) // items_per_page + (1 if len(filtered_tasks) % items_per_page else 0))
    
    col1, col2, col3 = st.columns([2, 4, 2])
    with col2:
        current_page = st.selectbox('Page', range(1, total_pages + 1), 0)
    
    start_idx = (current_page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, len(filtered_tasks))
    
    # Sort tasks if sort field is set
    if st.session_state.sort_field:
        filtered_tasks.sort(
            key=lambda t: (
                parse_analysis_result(t['result']).get(st.session_state.sort_field, {})
                .get('level', 0) if isinstance(parse_analysis_result(t['result'])
                .get(st.session_state.sort_field), dict)
                else parse_analysis_result(t['result']).get(st.session_state.sort_field, 0)
            ) if t['result'] else 0,
            reverse=st.session_state.sort_direction == 'desc'
        )

    # Display page info
    st.write(f"Showing {start_idx + 1}-{end_idx} of {len(filtered_tasks)} results")

    # Only process tasks for current page
    page_tasks = filtered_tasks[start_idx:end_idx]

    # At top of show_individual_results
    sort_icons = {
        'asc': '↑',
        'desc': '↓',
        None: '↕'  # Default icon showing it's sortable
    }

    for task in page_tasks:
        st.divider()
        
        video = task['videos']
        title = video.get('metadata', {}).get('title', video['id'])
        # Get is_red from the task/video
        is_red = task.get('is_red', False) or video.get('is_red', False)
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader(title)
            
            # Modified video display logic
            if video['source_url']:
                if is_red:
                    st.markdown(f"[🔗 Open Video]({video['source_url']})")
                else:
                    st.video(video['source_url'])
            elif video['thumbnail_path'] and not is_red:
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
                    
                    # Add toggle for raw JSON
                    toggle_key = f"json_toggle_{task['id']}"
                    if toggle_key not in st.session_state:
                        st.session_state[toggle_key] = False
                    
                    show_raw = st.toggle('Show Raw JSON', key=toggle_key)
                    
                    if show_raw:
                        # Get the raw analysis string and beautify it
                        raw_analysis = task['result']['analysis']
                        # Remove JSON code block markers if present
                        clean_raw = clean_json_string(raw_analysis)
                        try:
                            # Parse and re-stringify with indentation
                            parsed_raw = json.loads(clean_raw)
                            beautified_raw = json.dumps(parsed_raw, indent=2)
                            st.code(beautified_raw, language='json')
                        except json.JSONDecodeError:
                            # If parsing fails, show original raw text
                            st.code(raw_analysis)
                    
                    # Find metrics to display
                    metrics_to_show = []
                    
                    # Add original score from videos table if it exists
                    if video.get('metadata', {}).get('score'):
                        metrics_to_show.append(("Original Score", video['metadata']['score']))
                    
                    # Always show overall score next
                    metrics_to_show.append(("Overall Score", parsed_result.get('overall_score', 'N/A')))
                    
                    # Find other metrics by looking for rating/level fields
                    for key, value in parsed_result.items():
                        if isinstance(value, dict):
                            for k, v in value.items():
                                if k.lower() in ('rating', 'level', 'score'):
                                    display_name = ''.join(' ' + c if c.isupper() else c for c in key).title()
                                    metrics_to_show.append((display_name, v))
                    
                    # Display metrics in columns
                    num_metrics = len(metrics_to_show)
                    metrics = st.columns(num_metrics)
                    
                    for i, (name, value) in enumerate(metrics_to_show):
                        with metrics[i]:
                            field_key = next((k for k, v in parsed_result.items() 
                                            if isinstance(v, dict) and 'level' in v 
                                            and v['level'] == value), 'overall_score')
                            
                            # Get current sort icon
                            current_icon = sort_icons[st.session_state.sort_direction] if st.session_state.sort_field == field_key else sort_icons[None]
                            
                            # Sort button first
                            if st.button(current_icon, key=f"sort_{task['id']}_{field_key}_{name.lower().replace(' ', '_')}"):
                                if st.session_state.sort_field == field_key:
                                    st.session_state.sort_direction = 'asc' if st.session_state.sort_direction == 'desc' else 'desc'
                                else:
                                    st.session_state.sort_field = field_key
                                    st.session_state.sort_direction = 'desc'
                                st.rerun()
                            
                            # Then name and value
                            st.markdown(f"""<p style='text-align: center; 
                                                      margin-bottom: 0; 
                                                      min-height: 40px;  /* קבע גובה מינימלי */
                                                      display: flex; 
                                                      align-items: center; 
                                                      justify-content: center;'>{name}</p>""", 
                                        unsafe_allow_html=True)
                            st.markdown(f"<h2 style='text-align: center; margin: 0;'>{value}</h2>", unsafe_allow_html=True)
                            
                    # Generic display of all fields
                    st.markdown("### Analysis Details")
                    excluded_fields = {'overall_score', 'videoQuality', 'audioQuality', 
                                     'authenticity', 'motivation'}  # Fields already shown in metrics
                    
                    for key, value in parsed_result.items():
                        if key not in excluded_fields:
                            display_json_field(key, value)
                            
                except Exception as e:
                    st.error(f"Failed to parse result: {str(e)}")
                    st.code(str(task['result']))

    st.markdown("""
        <style>
        .stButton button {
            padding: 0px 8px;
            font-size: 14px;
            background: transparent;
            border: none;
            display: block;
            margin: 0 auto;
        }
        .stButton button:hover {
            background: #f0f0f0;
            border: none;
        }
        .metric-title {
            text-align: center;
            margin-bottom: 0;
            min-height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        </style>
    """, unsafe_allow_html=True)