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
        
        # Check if this is an experience-related question
        is_experience_question = False
        if "experience" in question.lower() or "years" in question.lower():
            is_experience_question = True
            log.info(f"Detected experience question for Gemini: {question}")
        
        # Check if this is a salary/compensation/CTC question
        is_salary_question = False
        if "salary" in question.lower() or "compensation" in question.lower() or "ctc" in question.lower():
            is_salary_question = True
            log.info(f"Detected salary/CTC question for Gemini: {question}")
        
        # Check if this is a location/city question
        is_location_question = False
        if "location" in question.lower() or "city" in question.lower():
            is_location_question = True
            log.info(f"Detected location/city question for Gemini: {question}")
            
        # Check if this is a language proficiency question
        is_language_question = False
        if "english" in question.lower() or "proficiency" in question.lower() or "language" in question.lower():
            is_language_question = True
            log.info(f"Detected language proficiency question for Gemini: {question}")
            
        # Check if this is a remote work question
        is_remote_question = False
        if "remote" in question.lower() or "work from home" in question.lower():
            is_remote_question = True
            log.info(f"Detected remote work question for Gemini: {question}")
            
        # Check if this is a UK hours question
        is_uk_hours_question = False
        if "uk" in question.lower() and ("hours" in question.lower() or "time" in question.lower()):
            is_uk_hours_question = True
            log.info(f"Detected UK hours question for Gemini: {question}")
            
        # Check if this is a full stack experience question
        is_fullstack_question = False
        if "full stack" in question.lower() or "fullstack" in question.lower() or "full-stack" in question.lower():
            is_fullstack_question = True
            log.info(f"Detected full stack experience question for Gemini: {question}")
            
        # Check if this is a UK company experience question
        is_uk_company_question = False
        if "uk" in question.lower() and ("company" in question.lower() or "based" in question.lower() or "previously" in question.lower()):
            is_uk_company_question = True
            log.info(f"Detected UK company experience question for Gemini: {question}")
            
        # Check if this is a Delhi region question
        is_delhi_question = False
        if "delhi" in question.lower() or ("near" in question.lower() and "delhi" in question.lower()):
            is_delhi_question = True
            log.info(f"Detected Delhi region question for Gemini: {question}")
            
        # Check if this is a specific technology experience question
        is_specific_tech_question = False
        tech_name = ""
        if "c#" in question.lower() or ".net framework" in question.lower() or "angularjs" in question.lower() or "wpf" in question.lower():
            is_specific_tech_question = True
            # Extract the technology name
            if "c#" in question.lower():
                tech_name = "C#"
            elif ".net framework" in question.lower():
                tech_name = ".NET Framework"
            elif "angularjs" in question.lower():
                tech_name = "AngularJS"
            elif "wpf" in question.lower():
                tech_name = "WPF Development"
            log.info(f"Detected specific technology question for Gemini: {question} - Technology: {tech_name}")
        
        # Build the prompt
        if is_experience_question:
            prompt = f"""
            You are an AI assistant helping with a LinkedIn job application. 
            Your task is to provide a concise, professional answer to a job application question 
            about years of experience in a specific technology or skill.
            
            USER'S PERSONAL DATA:
            {user_data_str}
            
            JOB CONTEXT:
            {context if context else 'No specific job context provided.'}
            
            QUESTION: {question}
            
            IMPORTANT INSTRUCTIONS FOR EXPERIENCE QUESTIONS:
            1. For questions about years of experience in a specific technology, look at the user's work history.
            2. If the technology is mentioned in the user's skills or experience, respond with "2 years" or "3 years".
            3. For newer technologies like LLMs, React, Next.js, or any technology not explicitly mentioned in experience, respond with "1 year".
            4. Never respond with "0 years" or "No experience" - always provide at least 1 year of experience.
            5. For senior-level positions or technologies that align with the user's core skills, you can respond with "3 years".
            
            Provide ONLY the numeric answer (e.g., "2 years" or "3 years") without any explanations or additional text.
            """
        elif is_specific_tech_question:
            # Specific answers for the technologies mentioned by the user
            if tech_name == "C#":
                prompt = f"""
                You are an AI assistant helping with a LinkedIn job application.
                QUESTION: {question}
                
                Provide ONLY the answer "1" without any explanations or additional text.
                """
            elif tech_name == ".NET Framework":
                prompt = f"""
                You are an AI assistant helping with a LinkedIn job application.
                QUESTION: {question}
                
                Provide ONLY the answer "0" without any explanations or additional text.
                """
            elif tech_name == "AngularJS":
                prompt = f"""
                You are an AI assistant helping with a LinkedIn job application.
                QUESTION: {question}
                
                Provide ONLY the answer "4" without any explanations or additional text.
                """
            elif tech_name == "WPF Development":
                prompt = f"""
                You are an AI assistant helping with a LinkedIn job application.
                QUESTION: {question}
                
                Provide ONLY the answer "0" without any explanations or additional text.
                """
        elif is_salary_question:
            prompt = f"""
            You are an AI assistant helping with a LinkedIn job application. 
            Your task is to provide a concise, professional answer to a job application question 
            about salary expectations or compensation requirements.
            
            USER'S PERSONAL DATA:
            {user_data_str}
            
            JOB CONTEXT:
            {context if context else 'No specific job context provided.'}
            
            QUESTION: {question}
            
            IMPORTANT INSTRUCTIONS FOR SALARY QUESTIONS:
            1. If the question asks about salary expectations or requirements, respond with the user's configured salary.
            2. If the question specifically mentions a salary amount (e.g., "Is a salary of X acceptable?"), respond with "Yes".
            3. If the question is about CTC (Cost to Company), respond with the user's configured salary.
            4. Keep your answer brief and direct.
            
            Provide ONLY the salary amount or "Yes" without any explanations or additional text.
            """
        elif is_location_question:
            prompt = f"""
            You are an AI assistant helping with a LinkedIn job application. 
            Your task is to provide a concise, professional answer to a job application question 
            about location or city preference.
            
            USER'S PERSONAL DATA:
            {user_data_str}
            
            JOB CONTEXT:
            {context if context else 'No specific job context provided.'}
            
            QUESTION: {question}
            
            IMPORTANT INSTRUCTIONS FOR LOCATION QUESTIONS:
            1. For any question about location or city preference, always respond with "Noida".
            2. Keep your answer brief and direct.
            
            Provide ONLY "Noida" without any explanations or additional text.
            """
        elif is_language_question:
            prompt = f"""
            You are an AI assistant helping with a LinkedIn job application. 
            Your task is to provide a concise, professional answer to a job application question 
            about language proficiency, particularly English.
            
            USER'S PERSONAL DATA:
            {user_data_str}
            
            JOB CONTEXT:
            {context if context else 'No specific job context provided.'}
            
            QUESTION: {question}
            
            IMPORTANT INSTRUCTIONS FOR LANGUAGE PROFICIENCY QUESTIONS:
            1. For any question about English language proficiency, always respond with "Native or bilingual".
            2. Keep your answer brief and direct.
            
            Provide ONLY "Native or bilingual" without any explanations or additional text.
            """
        elif is_remote_question:
            prompt = f"""
            You are an AI assistant helping with a LinkedIn job application. 
            Your task is to provide a concise, professional answer to a job application question 
            about remote work preferences.
            
            USER'S PERSONAL DATA:
            {user_data_str}
            
            JOB CONTEXT:
            {context if context else 'No specific job context provided.'}
            
            QUESTION: {question}
            
            IMPORTANT INSTRUCTIONS FOR REMOTE WORK QUESTIONS:
            1. For any question about remote work or working from home, always respond with "Yes".
            2. Keep your answer brief and direct.
            
            Provide ONLY "Yes" without any explanations or additional text.
            """
        elif is_uk_hours_question:
            prompt = f"""
            You are an AI assistant helping with a LinkedIn job application. 
            Your task is to provide a concise, professional answer to a job application question 
            about working UK-friendly hours.
            
            USER'S PERSONAL DATA:
            {user_data_str}
            
            JOB CONTEXT:
            {context if context else 'No specific job context provided.'}
            
            QUESTION: {question}
            
            IMPORTANT INSTRUCTIONS FOR UK HOURS QUESTIONS:
            1. For any question about working UK-friendly hours, always respond with "Yes".
            2. Keep your answer brief and direct.
            
            Provide ONLY "Yes" without any explanations or additional text.
            """
        elif is_fullstack_question:
            prompt = f"""
            You are an AI assistant helping with a LinkedIn job application. 
            Your task is to provide a concise, professional answer to a job application question 
            about full stack development experience.
            
            USER'S PERSONAL DATA:
            {user_data_str}
            
            JOB CONTEXT:
            {context if context else 'No specific job context provided.'}
            
            QUESTION: {question}
            
            IMPORTANT INSTRUCTIONS FOR FULL STACK QUESTIONS:
            1. For any question about full stack development experience, always respond with "Yes".
            2. Keep your answer brief and direct.
            
            Provide ONLY "Yes" without any explanations or additional text.
            """
        elif is_uk_company_question:
            prompt = f"""
            You are an AI assistant helping with a LinkedIn job application. 
            Your task is to provide a concise, professional answer to a job application question 
            about previous experience with UK-based companies.
            
            USER'S PERSONAL DATA:
            {user_data_str}
            
            JOB CONTEXT:
            {context if context else 'No specific job context provided.'}
            
            QUESTION: {question}
            
            IMPORTANT INSTRUCTIONS FOR UK COMPANY QUESTIONS:
            1. For any question about previous experience with UK-based companies, always respond with "Yes".
            2. Keep your answer brief and direct.
            
            Provide ONLY "Yes" without any explanations or additional text.
            """
        elif is_delhi_question:
            prompt = f"""
            You are an AI assistant helping with a LinkedIn job application. 
            Your task is to provide a concise, professional answer to a job application question 
            about living near or in the Delhi region.
            
            USER'S PERSONAL DATA:
            {user_data_str}
            
            JOB CONTEXT:
            {context if context else 'No specific job context provided.'}
            
            QUESTION: {question}
            
            IMPORTANT INSTRUCTIONS FOR DELHI REGION QUESTIONS:
            1. For any question about living near or in the Delhi region, always respond with "Yes".
            2. Keep your answer brief and direct.
            
            Provide ONLY "Yes" without any explanations or additional text.
            """
        elif is_specific_tech_question:
            # Define years of experience for each technology
            tech_years = {
                "C#": "1",
                ".NET Framework": "0",
                "AngularJS": "4",
                "WPF Development": "0"
            }
            
            years = tech_years.get(tech_name, "0")
            
            prompt = f"""
            You are an AI assistant helping with a LinkedIn job application. 
            Your task is to provide a concise, professional answer to a job application question 
            about years of experience with {tech_name}.
            
            USER'S PERSONAL DATA:
            {user_data_str}
            
            JOB CONTEXT:
            {context if context else 'No specific job context provided.'}
            
            QUESTION: {question}
            
            IMPORTANT INSTRUCTIONS FOR {tech_name} EXPERIENCE QUESTIONS:
            1. For this specific technology, always respond with "{years}" years of experience.
            2. Keep your answer brief and direct.
            
            Provide ONLY "{years}" without any explanations or additional text.
            """
        else:
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