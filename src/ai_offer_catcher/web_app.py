import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()
DB_DSN = os.getenv("AI_OFFER_DB_DSN", "postgresql://bytedance@localhost:5432/ai_offer_catcher")

# Setup page configuration
st.set_page_config(
    page_title="八股杀手 - AI 面经提取系统",
    page_icon="🔪",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .post-card {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
        background-color: #f9f9f9;
        color: #333;
    }
    .post-title {
        font-size: 18px;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 8px;
    }
    .post-meta {
        font-size: 12px;
        color: #666;
        margin-bottom: 12px;
    }
    .post-content {
        font-size: 14px;
        line-height: 1.6;
        white-space: pre-wrap;
    }
    .question-highlight {
        background-color: #ffe0b2;
        padding: 2px 4px;
        border-radius: 4px;
        font-weight: 500;
    }
    /* Dark mode support */
    @media (prefers-color-scheme: dark) {
        .post-card {
            background-color: #2b2b2b;
            border-color: #444;
            color: #ddd;
        }
        .post-title {
            color: #4fc3f7;
        }
        .post-meta {
            color: #aaa;
        }
        .question-highlight {
            background-color: #5c4015;
            color: #ffb74d;
        }
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_engine():
    return create_engine(DB_DSN)

@st.cache_data(ttl=60)
def load_top_questions(question_type=None, limit=100):
    engine = get_engine()
    
    query = """
    SELECT 
        id, 
        canonical_text as "问题描述", 
        question_type as "分类", 
        unique_post_count as "出现次数 (不同帖子)", 
        companies as "提及公司", 
        roles as "提及岗位"
    FROM canonical_question_stats
    """
    
    if question_type and question_type != "全部":
        query += f" WHERE question_type = '{question_type}'"
        
    query += f" ORDER BY unique_post_count DESC LIMIT {limit}"
    
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df

@st.cache_data
def get_question_types():
    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql("SELECT DISTINCT question_type FROM canonical_questions", conn)
    types = df['question_type'].tolist()
    return ["全部"] + [t for t in types if t]

def load_posts_for_question(canonical_id):
    engine = get_engine()
    query = f"""
    SELECT 
        rp.source_note_id,
        rp.title,
        rp.content,
        rp.author_nickname,
        rp.published_at,
        rp.note_url,
        eq.raw_text as extracted_question,
        pql.company_name,
        pql.role_name,
        pql.interview_stage
    FROM post_question_links pql
    JOIN raw_posts rp ON pql.raw_post_id = rp.id
    JOIN extracted_questions eq ON pql.extracted_question_id = eq.id
    WHERE pql.canonical_question_id = {canonical_id}
    ORDER BY rp.published_at DESC
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    return df

def highlight_text(text, highlight):
    if not text or not highlight:
        return text
    
    # Try to find the exact match or close match
    try:
        # Simple string replacement for HTML rendering
        pattern = re.compile(re.escape(highlight), re.IGNORECASE)
        return pattern.sub(lambda m: f'<span class="question-highlight">{m.group(0)}</span>', text)
    except:
        return text

# Main UI
st.title("🔪 八股杀手 - 全网面经热点提取与溯源")
st.markdown("自动收集小红书面经，使用大模型抽取真实面试题，语义聚类排行。")

# Sidebar for filtering
st.sidebar.header("🔍 筛选条件")
q_types = get_question_types()
selected_type = st.sidebar.selectbox("选择题目类型", q_types)
top_n = st.sidebar.slider("显示前 N 个热点", min_value=10, max_value=500, value=50)

st.sidebar.markdown("---")
st.sidebar.info("""
### 关于分类
- **knowledge_qa**: 基础八股/概念
- **project_drilldown**: 项目深挖/场景题
- **leetcode_algo**: 算法/手撕代码
- **ml_llm_coding**: 大模型/机器学习微调
- **agent_rag_tool**: Agent/RAG相关结构
""")

# Load and display top questions
df_questions = load_top_questions(selected_type, top_n)

if df_questions.empty:
    st.info("当前数据库中还没有解析好的面经数据。请先在终端运行抓取和提取流水线。")
else:
    # Display metrics
    total_q = len(df_questions)
    total_posts = df_questions['出现次数 (不同帖子)'].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("已提取的独立问题", total_q)
    col2.metric("涉及的面经总次数", total_posts)
    
    st.subheader("🔥 面试题热度排行榜")
    
    # We use a dataframe with a special selection behavior
    # For now, let's use a simple radio/select box to pick a question to trace
    
    # Format companies and roles for display
    display_df = df_questions.copy()
    display_df['提及公司'] = display_df['提及公司'].apply(lambda x: ', '.join(x) if isinstance(x, list) and x else '-')
    display_df['提及岗位'] = display_df['提及岗位'].apply(lambda x: ', '.join(x) if isinstance(x, list) and x else '-')
    
    st.dataframe(
        display_df[['问题描述', '分类', '出现次数 (不同帖子)', '提及公司', '提及岗位']], 
        use_container_width=True,
        hide_index=True
    )
    
    st.markdown("---")
    st.subheader("🕵️‍♂️ 面经溯源分析")
    
    # Create a nice selectbox for choosing which question to trace
    options = [f"[{row['出现次数 (不同帖子)']}次] {row['问题描述']}" for _, row in df_questions.iterrows()]
    selected_option = st.selectbox("选择一个问题，查看包含该问题的小红书原贴：", options)
    
    if selected_option:
        # Find the ID of the selected question
        idx = options.index(selected_option)
        selected_id = df_questions.iloc[idx]['id']
        selected_q_text = df_questions.iloc[idx]['问题描述']
        
        st.write(f"**正在溯源问题：** `{selected_q_text}`")
        
        posts_df = load_posts_for_question(selected_id)
        
        if posts_df.empty:
            st.warning("未找到关联帖子，可能是数据库关联有误。")
        else:
            st.success(f"找到了 {len(posts_df)} 篇包含该问题的小红书面经！")
            
            for _, post in posts_df.iterrows():
                # Format dates and tags
                date_str = post['published_at'].strftime('%Y-%m-%d %H:%M') if pd.notnull(post['published_at']) else "未知时间"
                
                # Tags for company and role
                tags = []
                if post['company_name']: tags.append(f"🏢 {post['company_name']}")
                if post['role_name']: tags.append(f"💼 {post['role_name']}")
                if post['interview_stage']: tags.append(f"🎯 {post['interview_stage']}")
                tags_html = " ".join(f"<span style='background:#e0e0e0; color:#333; padding:2px 6px; border-radius:4px; font-size:12px; margin-right:8px;'>{t}</span>" for t in tags)
                
                # Highlight the extracted question in the main content
                extracted_q = post['extracted_question']
                content_html = post['content'] or ""
                
                # Render post card
                st.markdown(f"""
                <div class="post-card">
                    <div class="post-title">📝 {post['title'] or '无标题帖子'}</div>
                    <div class="post-meta">
                        👤 作者: {post['author_nickname'] or '匿名'} &nbsp;&nbsp;|&nbsp;&nbsp; 
                        📅 发布于: {date_str} &nbsp;&nbsp;|&nbsp;&nbsp;
                        🔗 小红书 ID: {post['source_note_id']}
                    </div>
                    <div style="margin-bottom: 12px;">
                        {tags_html}
                    </div>
                    <div style="margin-bottom: 8px; padding-left: 8px; border-left: 3px solid #ff9800; color: #ff9800; font-size: 13px;">
                        <b>大模型抽取的原话:</b> {extracted_q}
                    </div>
                    <div class="post-content">{content_html}</div>
                </div>
                """, unsafe_allow_html=True)
