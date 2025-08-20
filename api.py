import os
import logging
from typing import List, Optional
from contextlib import asynccontextmanager
import traceback
import time 
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field, validator
import uvicorn

from tool import run_agent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pydantic models for request/response
class LegalQuery(BaseModel):
    query: str = Field(..., min_length=10, max_length=5000, description="The legal query from the user")
    
    @validator('query')
    def validate_query(cls, v):
        if not v.strip():
            raise ValueError('Query cannot be empty or just whitespace')
        return v.strip()

class UserAnswers(BaseModel):
    initial_query: str = Field(..., min_length=10, max_length=5000)
    answers: str = Field(..., min_length=10, max_length=10000, description="User's answers to the probing questions")
    
    @validator('initial_query', 'answers')
    def validate_fields(cls, v):
        if not v.strip():
            raise ValueError('Field cannot be empty or just whitespace')
        return v.strip()

class QuestionResponse(BaseModel):
    questions: List[str] = Field(..., description="List of probing questions")
    message: str = Field(..., description="Instructions for the user")

class ReportResponse(BaseModel):
    report: str = Field(..., description="The generated legal report")
    timestamp: str = Field(..., description="When the report was generated")

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    request_id: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str

# Environment validation
def validate_environment():
    """Validate required environment variables"""
    required_vars = ["GOOGLE_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        raise RuntimeError(f"Missing required environment variables: {missing_vars}")
    
    logger.info("All required environment variables are present")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up Legal Consultation API...")
    try:
        validate_environment()
        logger.info("Environment validation successful")
        yield
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down Legal Consultation API...")

# Initialize FastAPI app
app = FastAPI(
    title="Legal Consultation API",
    description="AI-powered legal consultation service specializing in Indian law",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this based on your needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Generate request ID
    request_id = f"{int(start_time)}-{hash(str(request.url)) % 10000}"
    request.state.request_id = request_id
    
    logger.info(f"Request {request_id}: {request.method} {request.url}")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logger.info(f"Request {request_id} completed in {process_time:.3f}s with status {response.status_code}")
    
    return response

# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error="Invalid input",
            detail=str(exc),
            request_id=getattr(request.state, 'request_id', None)
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail="An unexpected error occurred. Please try again later.",
            request_id=getattr(request.state, 'request_id', None)
        ).dict()
    )

# Health check endpoint
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        environment=os.getenv("ENVIRONMENT", "production")
    )

# Root endpoint
@app.get("/", tags=["Root"])
async def read_root():
    """Root endpoint with API information"""
    return {
        "message": "Legal Consultation API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

# Main endpoints
@app.post("/ask-question", response_model=QuestionResponse, tags=["Legal Consultation"])
async def ask_legal_question(query: LegalQuery, background_tasks: BackgroundTasks):
    """
    Submit a legal query and receive probing questions to gather more details.
    
    This endpoint takes an initial legal query and returns a set of specific questions
    designed to gather the necessary information for providing accurate legal guidance
    based on Indian law.
    """
    try:
        logger.info(f"Processing legal query: {query.query[:100]}...")
        
        # Run the agent to get questions
        messages = run_agent(query.query)
        
        # Extract questions from the messages
        questions = []
        instructions = ""
        
        for msg in messages:
            content = msg.content
            if content.startswith("Question"):
                # Extract the question part after "Question X: "
                question_text = content.split(": ", 1)[1] if ": " in content else content
                questions.append(question_text)
            elif "Please answer the questions" in content:
                instructions = content
        
        if not questions:
            raise HTTPException(status_code=500, detail="Failed to generate questions")
        
        # Log successful processing
        background_tasks.add_task(
            logger.info, 
            f"Successfully generated {len(questions)} questions for query"
        )
        
        return QuestionResponse(
            questions=questions,
            message=instructions or "Please answer the questions above to the best of your ability. I will generate a report once I have your answers."
        )
        
    except Exception as e:
        logger.error(f"Error processing legal query: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to process legal query: {str(e)}")

@app.post("/generate-report", response_model=ReportResponse, tags=["Legal Consultation"])
async def generate_legal_report(answers: UserAnswers, background_tasks: BackgroundTasks):
    """
    Generate a comprehensive legal report based on the initial query and user's answers.
    
    This endpoint takes the initial legal query and the user's detailed answers to 
    generate a structured legal report with analysis, applicable laws, and recommendations
    based on Indian legal framework.
    """
    try:
        logger.info(f"Generating report for query: {answers.initial_query[:100]}...")
        
        # Run the agent with answers to get the report
        messages = run_agent(answers.initial_query, answers.answers)
        
        # Extract the report from messages
        report_content = ""
        for msg in messages:
            if msg.content and len(msg.content) > 100:  # Assuming report is substantial
                report_content = msg.content
                break
        
        if not report_content:
            raise HTTPException(status_code=500, detail="Failed to generate report")
        
        # Log successful processing
        background_tasks.add_task(
            logger.info, 
            f"Successfully generated legal report of {len(report_content)} characters"
        )
        
        from datetime import datetime
        return ReportResponse(
            report=report_content,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error generating legal report: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to generate legal report: {str(e)}")

@app.get("/api/info", tags=["API Information"])
async def api_info():
    """Get API information and available endpoints"""
    return {
        "name": "Legal Consultation API",
        "version": "1.0.0",
        "description": "AI-powered legal consultation service specializing in Indian law",
        "endpoints": {
            "POST /ask-question": "Submit a legal query and get probing questions",
            "POST /generate-report": "Generate a legal report based on answers",
            "GET /health": "Health check endpoint",
            "GET /api/info": "API information"
        },
        "supported_legal_system": "Indian Law",
        "features": [
            "AI-powered legal analysis",
            "Structured questioning system",
            "Comprehensive legal reports",
            "Indian legal framework specialization"
        ]
    }


if __name__ == "__main__":
    # This is for development only
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8080)),
        reload=False,
        log_level="info"
    )