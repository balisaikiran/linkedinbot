import os
import yaml
import logging
import google.generativeai as genai
from pathlib import Path

log = logging.getLogger(__name__)

class GeminiAgent:
    """
    A class that uses Google's Gemini AI to help with form filling in the LinkedIn Easy Apply Bot.
    It processes job application questions and provides appropriate answers based on user data.
    """
    
    def __init__(self, api_key=None, user_data_path="user_data.yaml"):
        """
        Initialize the Gemini Agent with API key and user data.
        
        Args:
            api_key (str, optional): The Gemini API key. If not provided, will look for GEMINI_API_KEY env variable.
            user_data_path (str, optional): Path to the user data YAML file. Defaults to "user_data.yaml".
        """
        # Initialize Gemini API
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            log.warning("No Gemini API key provided. Please set GEMINI_API_KEY environment variable or provide it in config.yaml")
            self.enabled = False
            return
            
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            self.enabled = True
            log.info("Gemini AI agent initialized successfully")
        except Exception as e:
            log.error(f"Failed to initialize Gemini AI: {str(e)}")
            self.enabled = False
            return
        
        # Load user data
        try:
            user_data_file = Path(user_data_path)
            if user_data_file.exists():
                with open(user_data_file, 'r') as f:
                    self.user_data = yaml.safe_load(f)
                log.info("User data loaded successfully")
            else:
                log.warning(f"User data file not found at {user_data_path}")
                self.user_data = {}
        except Exception as e:
            log.error(f"Failed to load user data: {str(e)}")
            self.user_data = {}
    
    def is_enabled(self):
        """
        Check if the Gemini agent is enabled and ready to use.
        
        Returns:
            bool: True if the agent is enabled, False otherwise.
        """
        return self.enabled
    
    def answer_question(self, question, context=None):
        """
        Use Gemini AI to answer a job application question based on user data.
        
        Args:
            question (str): The job application question to answer.
            context (str, optional): Additional context about the job or application.
            
        Returns:
            str: The answer to the question.
        """
        if not self.enabled:
            log.warning("Gemini agent is not enabled. Returning default answer.")
            return "Not specified"
        
        try:
            # Create a prompt with the question and user data
            prompt = self._create_prompt(question, context)
            
            # Get response from Gemini
            response = self.model.generate_content(prompt)
            
            # Extract and return the answer
            answer = response.text.strip()
            log.info(f"Gemini answered question: '{question}' with: '{answer}'")
            return answer
        except Exception as e:
            log.error(f"Error getting answer from Gemini: {str(e)}")
            return "Not specified"
    
    def _create_prompt(self, question, context=None):
        """
        Create a prompt for Gemini based on the question and user data.
        
        Args:
            question (str): The job application question.
            context (str, optional): Additional context about the job.
            
        Returns:
            str: The formatted prompt for Gemini.
        """
        # Convert user data to a formatted string
        user_data_str = yaml.dump(self.user_data, default_flow_style=False)
        
        # Build the prompt
        prompt = f"""
        You are an AI assistant helping with a LinkedIn job application. 
        Your task is to provide a concise, professional answer to a job application question 
        based on the user's personal data. Keep answers brief and relevant.
        
        USER'S PERSONAL DATA:
        {user_data_str}
        
        JOB CONTEXT:
        {context if context else 'No specific job context provided.'}
        
        QUESTION: {question}
        
        Provide ONLY the answer without any explanations or additional text. 
        If the answer is a simple Yes/No, just respond with 'Yes' or 'No'.
        If the answer requires a specific format (like a number or date), use the appropriate format.
        If you don't have enough information to answer accurately, provide a reasonable professional response.
        """
        
        return prompt

    def process_job_description(self, job_description):
        """
        Process a job description to extract key information and prepare for application.
        
        Args:
            job_description (str): The full job description text.
            
        Returns:
            dict: A dictionary containing processed job information.
        """
        if not self.enabled:
            log.warning("Gemini agent is not enabled. Cannot process job description.")
            return {}
        
        try:
            prompt = f"""
            You are an AI assistant helping with a LinkedIn job application.
            Analyze the following job description and extract key information that would be useful for applying.
            
            JOB DESCRIPTION:
            {job_description}
            
            Extract and return ONLY a JSON object with the following fields:
            - job_title: The title of the job
            - company_name: The name of the company
            - required_skills: List of required skills mentioned
            - preferred_skills: List of preferred/nice-to-have skills
            - experience_level: Entry, Associate, Mid-Senior, Director, Executive, or Internship
            - job_type: Full-time, Part-time, Contract, etc.
            - remote: Whether the job is remote (true/false)
            - key_responsibilities: List of main job responsibilities
            
            If any field cannot be determined, set its value to null.
            """
            
            response = self.model.generate_content(prompt)
            
            # The response should be in JSON format, but we'll handle it as text
            # The application code will need to parse this JSON
            return response.text
        except Exception as e:
            log.error(f"Error processing job description with Gemini: {str(e)}")
            return {}

    def should_apply(self, job_description):
        """
        Determine if the user should apply to a job based on the job description and user data.
        
        Args:
            job_description (str): The full job description text.
            
        Returns:
            tuple: (bool, str) - Whether to apply and the reason.
        """
        if not self.enabled:
            log.warning("Gemini agent is not enabled. Defaulting to apply.")
            return True, "Gemini agent not enabled, defaulting to apply."
        
        try:
            # Convert user data to a formatted string
            user_data_str = yaml.dump(self.user_data, default_flow_style=False)
            
            prompt = f"""
            You are an AI assistant helping with a LinkedIn job application.
            Determine if the user should apply to this job based on their qualifications and the job requirements.
            
            USER'S PERSONAL DATA:
            {user_data_str}
            
            JOB DESCRIPTION:
            {job_description}
            
            Analyze the match between the user's qualifications and the job requirements.
            Return your response in the following format:
            APPLY: [Yes/No]
            REASON: [Brief explanation of your recommendation]
            MATCH_SCORE: [A number between 0-100 indicating how well the user matches the job]
            """
            
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Parse the response
            apply_line = next((line for line in response_text.split('\n') if line.startswith('APPLY:')), 'APPLY: Yes')
            reason_line = next((line for line in response_text.split('\n') if line.startswith('REASON:')), 'REASON: No specific reason provided.')
            
            should_apply = 'yes' in apply_line.lower()
            reason = reason_line.replace('REASON:', '').strip()
            
            return should_apply, reason
        except Exception as e:
            log.error(f"Error determining if should apply with Gemini: {str(e)}")
            return True, "Error occurred, defaulting to apply."