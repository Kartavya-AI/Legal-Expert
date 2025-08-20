import streamlit as st
from tool import run_agent
from dotenv import load_dotenv
import os

st.set_page_config(
    page_title="Legal Expert Agent 🧑‍⚖️",
    page_icon="🧑‍⚖️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

load_dotenv()
if not os.getenv("GOOGLE_API_KEY"):
    st.error("🚨 GOOGLE_API_KEY environment variable is not set! Please create a .env file with your key from Google AI Studio.")
    st.stop()

st.markdown("""
<style>
    .stApp {
        background-color: #121212; /* Black background */
        color: #ffffff; /* White text */
    }
    .st-emotion-cache-1y4p8pa {
        max-width: 1000px; /* Centered container */
    }
    h1, p {
        color: #ffffff; /* Ensure headers and paragraphs are white */
    }
    .st-header {
        text-align: center;
        padding-bottom: 20px;
    }
    .st-chat-message {
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        color: #ffffff; /* White text for chat messages */
    }
    .st-chat-message-user {
        background-color: #004d80; /* Darker blue for user messages */
    }
    .st-chat-message-assistant {
        background-color: #2b2b2b; /* Dark gray for assistant messages */
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        border: 1px solid #0068c9;
        background-color: #007bff;
        color: white;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #0056b3;
        color: white;
    }
    .stDownloadButton>button {
        background-color: #28a745;
        color: white;
        border: none;
        width: 100%;
    }
    .stDownloadButton>button:hover {
        background-color: #218838;
        color: white;
    }
    .stTextArea textarea {
        border-radius: 8px;
        background-color: #333333; /* Dark background for text area */
        color: #ffffff; /* White text for text area */
    }
    .stSpinner > div > div {
        border-top-color: #007bff;
    }
    .stAlert {
        color: #000000; /* Black text for alerts to contrast with their background */
    }
</style>
""", unsafe_allow_html=True)


if "messages" not in st.session_state:
    st.session_state.messages = []
if "step" not in st.session_state:
    st.session_state.step = "initial_query"
if "initial_query" not in st.session_state:
    st.session_state.initial_query = ""
if "final_report" not in st.session_state:
    st.session_state.final_report = ""


st.markdown("<h1 style='text-align: center; color: #ffffff;'>Legal Expert Agent 🧑‍⚖️</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Powered by Google Gemini</p>", unsafe_allow_html=True)
st.markdown("---")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if st.session_state.step == "initial_query":
    user_query = st.chat_input("What is your legal question? (e.g., 'Is it legal to use movie clips in my video?')")
    if user_query:
        st.session_state.initial_query = user_query
        st.session_state.messages.append({"role": "user", "content": user_query})
        
        with st.chat_message("assistant"):
            with st.spinner("Analyzing your query and preparing questions..."):
                response_messages = run_agent(initial_query=user_query)
                full_response = ""
                for msg in response_messages:
                    if "Please answer the questions" not in msg.content:
                        full_response += f"- {msg.content.replace('Question 1: ', '').replace('Question 2: ', '').replace('Question 3: ', '').replace('Question 4: ', '')}\n"
                
                st.markdown("To provide you with the best advice, I need a bit more information. Please answer the following questions:")
                st.markdown(full_response)
                
                st.session_state.messages.append({"role": "assistant", "content": "To provide you with the best advice, I need a bit more information. Please answer the following questions:\n" + full_response})

        st.session_state.step = "awaiting_answers"
        st.rerun()

elif st.session_state.step == "awaiting_answers":
    user_answers = st.text_area("Your Detailed Answers", height=250, placeholder="Provide your answers to the questions above here...")
    
    if st.button("Generate Report"):
        if not user_answers.strip():
            st.warning("Please provide your answers before generating the report.")
        else:
            st.session_state.messages.append({"role": "user", "content": user_answers})
            
            with st.chat_message("assistant"):
                with st.spinner("Compiling your information and generating the final report with Gemini... This may take a moment."):
                    report_messages = run_agent(initial_query=st.session_state.initial_query, user_answers=user_answers)
                    final_report = report_messages[-1].content
                    st.session_state.final_report = final_report
                    
                    st.markdown("### Your Legal Report")
                    st.markdown(final_report)
                    st.session_state.messages.append({"role": "assistant", "content": "### Your Legal Report\n" + final_report})
            
            st.session_state.step = "report_generated"
            st.rerun()

elif st.session_state.step == "report_generated":
    st.success("Report generated successfully!")
    
    st.download_button(
        label="📥 Download Report as .txt",
        data=st.session_state.final_report,
        file_name="legal_report.txt",
        mime="text/plain"
    )

    st.markdown("---")
    if st.button("Start New Consultation"):
        st.session_state.messages = []
        st.session_state.step = "initial_query"
        st.session_state.initial_query = ""
        st.session_state.final_report = ""
        st.rerun()

st.markdown("---")
st.warning("**Disclaimer:** This is an AI-powered agent and does not provide legally binding advice. Always consult with a qualified human lawyer for critical matters.", icon="⚠️")
