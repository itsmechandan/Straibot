# app_v1.py - The Main Streamlit Application

# Import necessary libraries
import streamlit as st
import httpx
import os
import certifi
from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub
from langchain.prompts import PromptTemplate
from langchain_community.callbacks import StreamlitCallbackHandler
from langchain_community.agent_toolkits import PowerBIToolkit
from langchain_community.utilities.powerbi import PowerBIDataset
from azure.identity import DefaultAzureCredential
from azure.core.credentials import TokenCredential
import time
import os
import requests
import ssl
import urllib3
import jwt
import hashlib

# --- Import Dynamic Configuration ---
from dataset_config import DATASET_CONFIGS, CORE_TEMPLATE

# --- SSL Patch (Keep this section intact) ---
# ... (SSL patch code remains the same) ...
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
original_request = requests.Session.request
def unsafe_request(self, method, url, *args, **kwargs):
    if "api.powerbi.com" in url:
        kwargs["verify"] = False
    return original_request(self, method, url, *args, **kwargs)
requests.Session.request = unsafe_request
PowerBIDataset.model_rebuild()
try:
    _create_unverified_https_context = ssl._create_unverified_https_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

TOKEN = "1234567890" # Used for your app authentication
def hashparameters(timestamp, token):
    hasher = hashlib.sha256()
    hasher.update(f"{timestamp}{token}".encode('utf-8'))
    return hasher.hexdigest()

# --- Streamlit Setup & Minimalist Styling (Initial) ---
st.set_page_config(page_title="Straibot", page_icon="🤖", layout="wide")

# Custom CSS for a cleaner, minimalist look and to hide Streamlit elements
st.markdown("""
<style>
    /* ... (CSS styles remain the same) ... */
    /* Main container settings */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 0rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    /* Hide the default Streamlit header/footer/menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Styling for Key Insights box */
    .stAlert {
        border-left: 6px solid #1f77b4; /* Blue bar on the left */
        background-color: #f0f8ff; /* Light background */
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 4px 8px 0 rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# Main Title
st.title("Straibot: AI Analytics Assistant 🤖")

PowerBIDataset.model_rebuild()

# --- Auth Flow (Your existing logic) ---
if 'user_payload' not in st.session_state:
    st.session_state.user_payload = None

token = st.query_params.get("token")
timestamp = st.query_params.get("timestamp")

if not st.session_state.user_payload and token:
    payload = token==hashparameters(timestamp, TOKEN)
    if payload and timestamp and (time.time() - int(timestamp) < 360000): 
        st.session_state.user_payload = payload
    else:
        st.error("❌ Invalid or expired token.")
elif not st.session_state.user_payload:
    st.warning("🔒 Authentication required. Waiting for token from host application...")

# --- Secrets, LLM, Agent, and Main Application Logic (Protected by Auth Check) ---
if st.session_state.user_payload:
    
    # --- 1. Load Secrets ---
    try:
        tenant_id = st.secrets["POWERBI_TENANT_ID"]
        client_id = st.secrets["POWERBI_CLIENT_ID"]
        client_secret = st.secrets["POWERBI_CLIENT_SECRET"]
        openai_api_key = st.secrets["OPEN_API_KEY"]

        os.environ["AZURE_TENANT_ID"] = tenant_id
        os.environ["AZURE_CLIENT_ID"] = client_id
        os.environ["AZURE_CLIENT_SECRET"] = client_secret
        os.environ["OPENAI_API_KEY"] = openai_api_key
    except KeyError as e:
        st.error(f"Missing secret: {e}. Please add it to your Streamlit secrets.")
        st.stop()

    # --- 2. Dataset Selection ---
    dataset_keys = list(DATASET_CONFIGS.keys())
    
    # Allow user to switch datasets via the sidebar
    selected_dataset_key = st.sidebar.selectbox(
        "Select Active Dataset", 
        dataset_keys, 
        index=dataset_keys.index("Incident_Tracker") # Default to Incident Tracker
    )
    
    # Load the configuration dynamically
    CONFIG = DATASET_CONFIGS[selected_dataset_key]
    
    # Set dynamic variables
    DATASET_ID = CONFIG["dataset_id"]
    TABLE_NAMES = CONFIG["table_names"]
    FAQS = CONFIG["faqs"]
    KEY_INSIGHTS_QUERY = CONFIG["key_insights_query"]
    LLM_PERSONA = CONFIG["llm_persona"]
    SCHEMA_CONTEXT = CONFIG["schema_context"] # <-- NEW: Load schema context
    
    # --- 3. Mock User Setup & Chat Initialization ---
    USER_NAME = "Mr. Jain"

    if "messages" not in st.session_state:
        initial_message = f"Hello {USER_NAME}! I am Straibot, your Power BI Assistant for **{LLM_PERSONA}**. How can I help you?"
        st.session_state.messages = [{"role": "assistant", "content": initial_message}]

    # --- 4. Agent and Toolkit Setup ---
    llm = ChatOpenAI(
        openai_api_base="https://llmfoundry.straive.com/openai/v1/",
        openai_api_key=f'{openai_api_key}:my-test-project',
        model="gpt-4o-mini",
        streaming=True,
        temperature=0.2 
    )
    credential = DefaultAzureCredential()
    toolkit = PowerBIToolkit(
        powerbi=PowerBIDataset(
            dataset_id=DATASET_ID, 
            table_names=TABLE_NAMES, 
            credential=credential,
        ),
        llm=llm,
    )
    
    # --- 5. Prompt Template Creation (Injecting Schema Context) ---
    # We first create the PromptTemplate, then use .partial() to inject the dynamic context.
    base_prompt = PromptTemplate.from_template(CORE_TEMPLATE)
    
    # Use partial to inject the dynamic schema context into the template
    prompt = base_prompt.partial(schema_context=SCHEMA_CONTEXT)
    
    # --- 6. Create the Agent Executor ---
    agent_executor = AgentExecutor(
        agent=create_react_agent(
            llm=llm,
            tools=toolkit.get_tools(),
            prompt=prompt, # Use the context-injected prompt
        ),
        tools=toolkit.get_tools(),
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=25, 
        max_execution_time=180 
    )

    # --- 7. Helper Function for FAQs ---
    def set_chat_input(prompt):
        st.session_state.chat_input = prompt

    # --- 8. Key Insights Generation Function ---
    def generate_key_insights(agent_executor, chat_history):
        # Pass the dynamic query from the config file
        analysis_query = KEY_INSIGHTS_QUERY 
        try:
            st_callback = StreamlitCallbackHandler(st.empty())
            with st.spinner(f"Generating Key Insights for {LLM_PERSONA}..."):
                response = agent_executor.invoke(
                    {"input": analysis_query, "chat_history": chat_history},
                    {"callbacks": [st_callback]}
                )
            return response.get("output", "Could not generate key insights.")
        except Exception as e:
            return f"Error generating insights for {LLM_PERSONA}: {e}"

    # --- 9. Layout: Main Application Structure ---
    col_left, col_right = st.columns([1, 2])

    # -----------------------------------------------------------
    # --- LEFT COLUMN: FAQs ---
    # -----------------------------------------------------------
    with col_left:
        st.markdown("### Frequently Asked Questions:")
        for faq_question in FAQS:
            st.button(faq_question, use_container_width=True, on_click=set_chat_input, args=[faq_question])
        
        st.markdown("<br>", unsafe_allow_html=True)

    # -----------------------------------------------------------
    # --- RIGHT COLUMN: Key Insights & Chat ---
    # -----------------------------------------------------------
    with col_right:
        # 1. Key Insights Section
        st.markdown(f"### Key Insights ({selected_dataset_key})")
        
        insights_key = f"key_insights_{selected_dataset_key}" 
        if insights_key not in st.session_state:
            st.session_state[insights_key] = generate_key_insights(
                agent_executor, st.session_state.messages
            )
        
        st.info(st.session_state[insights_key])
        
        st.markdown("---")
        
        # 2. Chatbot Section
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        user_prompt = st.chat_input("Type what you want to find...", key="chat_input")

        # --- Handle User Input and Agent Response ---
        if user_prompt:
            st.session_state.messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)

            with st.chat_message("assistant"):
                st_callback = StreamlitCallbackHandler(st.container())
                
                response = agent_executor.invoke(
                    {"input": user_prompt, "chat_history": st.session_state.messages},
                    {"callbacks": [st_callback]}
                )
                output = response.get("output", "Sorry, I encountered an error.")
                st.markdown(output)
            
            st.session_state.messages.append({"role": "assistant", "content": output})