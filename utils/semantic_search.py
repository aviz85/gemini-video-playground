import streamlit as st
import cohere
import numpy as np
import faiss
from utils.supabase_client import init_supabase, require_auth
import ast

def show_semantic_search():
    """Semantic search interface"""
    require_auth()
    st.header("🔍 Semantic Search")
    
    # Check for missing embeddings
    with st.spinner("Checking for missing embeddings..."):
        missing_embeddings = generate_embeddings_for_all()
    
    if missing_embeddings:
        st.info("Some videos were missing embeddings. They have been generated.")
    
    # Warning about summary requirement
    st.warning("""
        ⚠️ This feature requires videos to have been analyzed with a summary.
        Videos without analysis results will not be included in the search.
    """)
    
    # Initialize Cohere client
    try:
        co = cohere.Client(st.secrets["COHERE_API_KEY"])
    except Exception as e:
        st.error(f"Failed to initialize Cohere client: {str(e)}")
        return
    
    # Get videos with summaries from analysis_tasks
    supabase = init_supabase()
    
    # Get all embeddings for FAISS
    embeddings = []
    summaries = []
    video_data = []
    
    # Get all analysis tasks with embeddings
    analysis_results = (
        supabase.table("analysis_tasks")
        .select("id, video_id, summary, summary_embedding")
        .not_.is_("summary_embedding", "null")
        .execute()
    )
    
    for analysis in analysis_results.data:
        if analysis.get('summary_embedding'):
            # Convert string embedding to float array using ast.literal_eval
            embedding_str = analysis['summary_embedding']
            try:
                embedding_list = ast.literal_eval(embedding_str)
                embeddings.append(embedding_list)
                summaries.append(analysis['summary'])
                video_data.append(analysis)
            except:
                continue
    
    # Debug query results
    st.write("Total results:", len(analysis_results.data))
    st.write("Raw data:", analysis_results.data)
    
    # Then continue with the original filter
    videos_with_summaries = [
        analysis for analysis in analysis_results.data 
        if analysis.get('summary')
    ]
    st.write("Filtered results:", len(videos_with_summaries))
    
    if not videos_with_summaries:
        st.info("No videos with summaries found. Run video analysis first to use semantic search.")
        return
    
    # Search interface
    with st.form("semantic_search"):
        query = st.text_input("Search Query")
        initial_results = st.slider("Initial Results", min_value=10, max_value=100, value=30)
        final_results = st.slider("Final Results (after reranking)", min_value=1, max_value=initial_results, value=min(10, initial_results))
        search_button = st.form_submit_button("Search")
        
        if search_button and query:
            with st.spinner("Searching..."):
                try:
                    # Get embeddings for videos without them
                    videos_to_embed = [
                        v for v in videos_with_summaries 
                        if not v.get('summary_embedding')
                    ]
                    
                    if videos_to_embed:
                        st.info(f"Generating embeddings for {len(videos_to_embed)} videos...")
                        
                        # Generate embeddings in batches
                        batch_size = 96  # Cohere's recommended batch size
                        for i in range(0, len(videos_to_embed), batch_size):
                            batch = videos_to_embed[i:i + batch_size]
                            summaries = [v['summary'] for v in batch]
                            
                            # Generate embeddings
                            embeddings = co.embed(
                                texts=summaries,
                                model='embed-multilingual-v3.0',
                                input_type='search_document'
                            ).embeddings
                            
                            # Update videos with embeddings
                            for video, embedding in zip(batch, embeddings):
                                supabase.table("videos").update({
                                    'summary_embedding': embedding
                                }).eq('id', video['id']).execute()
                    
                    # Get all embeddings for FAISS
                    embeddings = []
                    summaries = []
                    video_data = []
                    
                    for video in videos_with_summaries:
                        if video.get('summary_embedding'):
                            embeddings.append(video['summary_embedding'])
                            summaries.append(video['summary'])
                            video_data.append(video)
                    
                    if not embeddings:
                        st.error("No embeddings available for search.")
                        return
                    
                    # Create FAISS index
                    embeddings_array = np.array(embeddings).astype('float32')
                    dimension = len(embeddings[0])
                    index = faiss.IndexFlatL2(dimension)
                    index.add(embeddings_array)
                    
                    # Generate query embedding
                    query_embedding = co.embed(
                        texts=[query],
                        model='embed-multilingual-v3.0',
                        input_type='search_query'
                    ).embeddings[0].tolist()
                    
                    # FAISS search
                    D, I = index.search(np.array([query_embedding], dtype=np.float32), initial_results)
                    
                    # Get initial results
                    initial_results_data = [
                        {
                            'summary': summaries[i],
                            'video': video_data[i],
                            'distance': D[0][idx]
                        }
                        for idx, i in enumerate(I[0])
                    ]
                    
                    # Rerank with Cohere
                    rerank_results = co.rerank(
                        model="rerank-v3.5",
                        query=query,
                        documents=[r['summary'] for r in initial_results_data],
                        top_n=final_results
                    )
                    
                    # Display results
                    st.subheader("Search Results")
                    for result in rerank_results.results:
                        video = initial_results_data[result.index]['video']
                        with st.expander(f"Score: {result.relevance_score:.2f} - {video.get('title', 'Untitled')}"):
                            if video.get('result'):
                                st.json(video['result'])
                            if video.get('thumbnail_path'):
                                st.image(
                                    supabase.storage.from_("videos")
                                    .get_public_url(video['thumbnail_path'])
                                )
                        
                except Exception as e:
                    st.error(f"Search failed: {str(e)}")

def create_match_videos_function():
    """Create PostgreSQL function for vector similarity search - Not used with FAISS"""
    pass  # Function no longer needed as we're using FAISS

def generate_embeddings_for_all():
    """Generate embeddings for all summaries that don't have them"""
    supabase = init_supabase()
    co = cohere.Client(st.secrets["COHERE_API_KEY"])
    
    # Get all records without embeddings
    results = (
        supabase.table("analysis_tasks")
        .select("id, summary")
        .neq("summary", None)
        .is_("summary_embedding", None)
        .execute()
    )
    
    if not results.data:
        return False
    
    # Generate embeddings in batches
    batch_size = 96
    for i in range(0, len(results.data), batch_size):
        batch = results.data[i:i + batch_size]
        summaries = [r['summary'] for r in batch]
        
        embeddings = co.embed(
            texts=summaries,
            model='embed-multilingual-v3.0',
            input_type='search_document'
        ).embeddings
        
        # Update analysis_tasks table
        for record, embedding in zip(batch, embeddings):
            supabase.table("analysis_tasks").update({
                'summary_embedding': embedding
            }).eq('id', record['id']).execute()
    
    return True