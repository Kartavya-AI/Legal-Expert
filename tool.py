import os
from typing import TypedDict, Annotated, List
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY environment variable not set.")

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key, temperature=0)

class InterviewState(TypedDict):
    messages: Annotated[List[BaseMessage], lambda x, y: x + y]
    turn: int

class QueryDetails(BaseModel):
    probing_questions: List[str] = Field(
        description="A list of 3-4 detailed, probing questions to deeply understand the user's legal issue within the context of Indian law."
    )

class Report(BaseModel):
    report_text: str = Field(
        description="A comprehensive, well-structured report addressing the user's legal query based on the conversation, with specific reference to Indian legal provisions."
    )

question_generator = llm.with_structured_output(QueryDetails)
report_generator = llm.with_structured_output(Report)

def start_node(state: InterviewState):
    initial_query = state['messages'][-1].content
    
    prompt = f"""
    You are an expert legal consultant AI specializing in the **Indian legal framework**. 
    A user has a query regarding a legal matter in India. Your task is to generate 3-4 highly specific, probing questions to gather the necessary details. 
    These questions must be framed to elicit information relevant to Indian laws, such as:
    - The specific state or territory in India where the issue occurred (as laws can vary).
    - The nature of the parties involved (e.g., individuals, companies, government bodies).
    - Key dates and a timeline of events.
    - The existence of any written agreements, contracts, or official documents.

    User's query: "{initial_query}"

    Generate questions that will help you provide a detailed analysis based on relevant Indian Acts (e.g., Indian Penal Code, Contract Act, 1872, Information Technology Act, 2000, etc.).
    """
    
    questions_structured = question_generator.invoke(prompt)
    question_messages = [HumanMessage(content=f"Question {i+1}: {q}") for i, q in enumerate(questions_structured.probing_questions)]
    system_message = HumanMessage(content="Please answer the questions above to the best of your ability. I will generate a report once I have your answers.")
    
    return {"messages": question_messages + [system_message], "turn": 1}

def report_node(state: InterviewState):
    conversation_history = "\n".join([f"{msg.type}: {msg.content}" for msg in state['messages']])
    
    prompt = f"""
    You are a Legal Expert AI specializing in **Indian Law**. You have gathered information from a user.
    Your task is to generate a comprehensive, well-documented report based on the entire conversation. The report must be structured with the following sections:
    
    1.  **Summary of Facts:** Briefly outline the user's situation based on the information provided.
    2.  **Applicable Indian Legal Provisions:** Identify and cite relevant Acts and sections of Indian law (e.g., Section 420 of the Indian Penal Code, 1860; Section 17 of the Indian Contract Act, 1872).
    3.  **Legal Analysis:** Analyze the situation in the context of the identified laws. Explain how the law applies to the user's facts and discuss potential legal arguments.
    4.  **Preliminary Opinion & Next Steps:** Provide a preliminary opinion on the matter. Suggest practical next steps the user could consider, such as mediation, sending a legal notice, or consulting with a lawyer registered with the Bar Council of India.
    5.  **Disclaimer:** Conclude with a clear disclaimer that this report is for informational purposes only and does not constitute legal advice from a licensed advocate.

    Conversation History:
    ---
    {conversation_history}
    ---

    Generate the final, structured report.
    """
    
    report_structured = report_generator.invoke(prompt)
    report_message = HumanMessage(content=report_structured.report_text)
    
    return {"messages": [report_message]}


workflow = StateGraph(InterviewState)

workflow.add_node("start_interview", start_node)
workflow.add_node("generate_report", report_node)
workflow.set_entry_point("start_interview")
workflow.add_edge("start_interview", "generate_report")
workflow.add_edge("generate_report", END)

legal_agent = workflow.compile()

def run_agent(initial_query: str, user_answers: str = ""):
    if not user_answers:
        inputs = {"messages": [HumanMessage(content=initial_query)], "turn": 0}
        result = legal_agent.invoke(inputs)
        return result['messages']
    else:
        full_context = f"Initial Query: {initial_query}\n\nUser's Answers:\n{user_answers}"
        inputs = {"messages": [HumanMessage(content=full_context)], "turn": 2}
        result = legal_agent.invoke(inputs)
        return result['messages']
