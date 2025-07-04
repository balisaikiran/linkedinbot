from __future__ import annotations

import json
import csv
import logging
import os
import random
import re
import time
from datetime import datetime, timedelta
import getpass
from pathlib import Path

import pandas as pd
import pyautogui
import yaml
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from selenium.webdriver.chrome.service import Service as ChromeService
import webdriver_manager.chrome as ChromeDriverManager
ChromeDriverManager = ChromeDriverManager.ChromeDriverManager

# Import Gemini agent for AI-powered form filling
try:
    from gemini_agent import GeminiAgent
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logging.warning("Gemini agent not available. Install google-generativeai package to enable AI-powered form filling.")


log = logging.getLogger(__name__)


def setupLogger() -> None:
    dt: str = datetime.strftime(datetime.now(), "%m_%d_%y %H_%M_%S ")

    if not os.path.isdir('./logs'):
        os.mkdir('./logs')

    # TODO need to check if there is a log dir available or not
    logging.basicConfig(filename=('./logs/' + str(dt) + 'applyJobs.log'), filemode='w',
                        format='%(asctime)s::%(name)s::%(levelname)s::%(message)s', datefmt='./logs/%d-%b-%y %H:%M:%S')
    log.setLevel(logging.DEBUG)
    c_handler = logging.StreamHandler()
    c_handler.setLevel(logging.DEBUG)
    c_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%H:%M:%S')
    c_handler.setFormatter(c_format)
    log.addHandler(c_handler)


class EasyApplyBot:
    setupLogger()
    # MAX_SEARCH_TIME is 10 hours by default, feel free to modify it
    MAX_SEARCH_TIME = 60 * 60

    def __init__(self,
                 username,
                 password,
                 phone_number,
                 # profile_path,
                 salary,
                 rate,
                 uploads={},
                 filename='output.csv',
                 blacklist=[],
                 blackListTitles=[],
                 experience_level=[],
                 gemini_api_key=None,
                 use_gemini_agent=True,
                 user_data_file="user_data.yaml",
                 auto_apply=True,
                 min_match_score=70
                 ) -> None:

        log.info("Welcome to Easy Apply Bot")
        dirpath: str = os.getcwd()
        log.info("current directory is : " + dirpath)
        log.info("Please wait while we prepare the bot for you")
        if experience_level:
            experience_levels = {
                1: "Entry level",
                2: "Associate",
                3: "Mid-Senior level",
                4: "Director",
                5: "Executive",
                6: "Internship"
            }
            applied_levels = [experience_levels[level] for level in experience_level]
            log.info("Applying for experience level roles: " + ", ".join(applied_levels))
        else:
            log.info("Applying for all experience levels")
        
        # Initialize Gemini agent if available and enabled
        self.use_gemini_agent = use_gemini_agent and GEMINI_AVAILABLE
        self.gemini_agent = None
        if self.use_gemini_agent:
            try:
                self.gemini_agent = GeminiAgent(api_key=gemini_api_key, user_data_path=user_data_file)
                if self.gemini_agent.is_enabled():
                    log.info("Gemini AI agent initialized successfully for intelligent form filling")
                else:
                    log.warning("Gemini AI agent initialization failed. Falling back to standard form filling.")
                    self.use_gemini_agent = False
            except Exception as e:
                log.error(f"Error initializing Gemini agent: {str(e)}")
                self.use_gemini_agent = False
        
        # Auto-apply settings
        self.auto_apply = auto_apply
        self.min_match_score = min_match_score

        self.uploads = uploads
        self.salary = salary
        self.rate = rate
        # self.profile_path = profile_path
        past_ids: list | None = self.get_appliedIDs(filename)
        self.appliedJobIDs: list = past_ids if past_ids != None else []
        self.filename: str = filename
        self.options = self.browser_options()
        self.browser = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=self.options)
        self.wait = WebDriverWait(self.browser, 30)
        self.blacklist = blacklist
        self.blackListTitles = blackListTitles
        self.start_linkedin(username, password)
        self.phone_number = phone_number
        self.experience_level = experience_level
        
        # Recovery mechanism to prevent stopping in between
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        
        # Initialize answers dictionary and QA file
        self.answers = {}
        self.qa_file = 'qa.csv'
        if not os.path.exists(self.qa_file):
            with open(self.qa_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Question", "Answer"])
                log.info(f"Created new QA file: {self.qa_file}")
        else:
            # Load existing QA pairs
            try:
                qa_data = pd.read_csv(self.qa_file, encoding='utf-8')
                self.answers = dict(zip(qa_data["Question"], qa_data["Answer"]))
                log.info(f"Loaded {len(self.answers)} QA pairs from {self.qa_file}")
            except Exception as e:
                log.error(f"Error loading QA file: {str(e)}")
                self.answers = {}


        self.locator = {
            "next": (By.CSS_SELECTOR, "button[aria-label='Continue to next step']"),
            "review": (By.CSS_SELECTOR, "button[aria-label='Review your application']"),
            "submit": (By.CSS_SELECTOR, "button[aria-label='Submit application']"),
            "error": (By.CLASS_NAME, "artdeco-inline-feedback__message"),
            "upload_resume": (By.XPATH, "//*[contains(@id, 'jobs-document-upload-file-input-upload-resume')]"),
            "upload_cv": (By.XPATH, "//*[contains(@id, 'jobs-document-upload-file-input-upload-cover-letter')]"),
            "follow": (By.CSS_SELECTOR, "label[for='follow-company-checkbox']"),
            "upload": (By.NAME, "file"),
            "search": (By.CLASS_NAME, "jobs-search-results-list"),
            "links": ("xpath", '//div[@data-job-id]'),
            "fields": (By.CLASS_NAME, "jobs-easy-apply-form-section__grouping"),
            "radio_select": (By.CSS_SELECTOR, "input[type='radio']"), #need to append [value={}].format(answer)
            "multi_select": (By.XPATH, "//*[contains(@id, 'text-entity-list-form-component')]"),
            "text_select": (By.CLASS_NAME, "artdeco-text-input--input"),
            "2fa_oneClick": (By.ID, 'reset-password-submit-button'),
            "easy_apply_button": (By.XPATH, '//button[contains(@class, "jobs-apply-button")]')

        }

        #initialize questions and answers file
        self.qa_file = Path("qa.csv")
        self.answers = {}

        #if qa file does not exist, create it
        if self.qa_file.is_file():
            df = pd.read_csv(self.qa_file)
            for index, row in df.iterrows():
                self.answers[row['Question']] = row['Answer']
        #if qa file does exist, load it
        else:
            df = pd.DataFrame(columns=["Question", "Answer"])
            df.to_csv(self.qa_file, index=False, encoding='utf-8')


    def get_appliedIDs(self, filename) -> list | None:
        try:
            df = pd.read_csv(filename,
                             header=None,
                             names=['timestamp', 'jobID', 'job', 'company', 'attempted', 'result'],
                             lineterminator='\n',
                             encoding='utf-8')

            df['timestamp'] = pd.to_datetime(df['timestamp'], format="%Y-%m-%d %H:%M:%S")
            df = df[df['timestamp'] > (datetime.now() - timedelta(days=2))]
            jobIDs: list = list(df.jobID)
            log.info(f"{len(jobIDs)} jobIDs found")
            return jobIDs
        except Exception as e:
            log.info(str(e) + "   jobIDs could not be loaded from CSV {}".format(filename))
            return None

    def browser_options(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument('--no-sandbox')
        options.add_argument("--disable-extensions")
        #options.add_argument(r'--remote-debugging-port=9222')
        #options.add_argument(r'--profile-directory=Person 1')

        # Disable webdriver flags or you will be easily detectable
        options.add_argument("--disable-blink-features")
        options.add_argument("--disable-blink-features=AutomationControlled")

        # Load user profile
        #options.add_argument(r"--user-data-dir={}".format(self.profile_path))
        return options

    def start_linkedin(self, username, password) -> None:
        log.info("Logging in.....Please wait :)  ")
        self.browser.get("https://www.linkedin.com/login?trk=guest_homepage-basic_nav-header-signin")
        try:
            user_field = self.browser.find_element("id","username")
            pw_field = self.browser.find_element("id","password")
            # Updated login button selector to be more reliable
            login_button = self.browser.find_element("xpath", "//button[@type='submit']")
            user_field.send_keys(username)
            user_field.send_keys(Keys.TAB)
            time.sleep(2)
            pw_field.send_keys(password)
            time.sleep(2)
            login_button.click()
            time.sleep(15)
            # if self.is_present(self.locator["2fa_oneClick"]):
            #     oneclick_auth = self.browser.find_element(by='id', value='reset-password-submit-button')
            #     if oneclick_auth is not None:
            #         log.info("additional authentication required, sleep for 15 seconds so you can do that")
            #         time.sleep(15)
            # else:
            #     time.sleep()
        except TimeoutException:
            log.info("TimeoutException! Username/password field or login button not found")

    def fill_data(self) -> None:
        self.browser.set_window_size(1, 1)
        self.browser.set_window_position(2000, 2000)

    def start_apply(self, positions, locations) -> None:
        start: float = time.time()
        self.fill_data()
        self.positions = positions
        self.locations = locations
        combos: list = []
        while len(combos) < len(positions) * len(locations):
            position = positions[random.randint(0, len(positions) - 1)]
            location = locations[random.randint(0, len(locations) - 1)]
            combo: tuple = (position, location)
            if combo not in combos:
                combos.append(combo)
                log.info(f"Applying to {position}: {location}")
                location = "&location=" + location
                self.applications_loop(position, location)
            if len(combos) > 500:
                break

    # self.finish_apply() --> this does seem to cause more harm than good, since it closes the browser which we usually don't want, other conditions will stop the loop and just break out

    def applications_loop(self, position, location):

        count_application = 0
        count_job = 0
        jobs_per_page = 0
        start_time: float = time.time()

        log.info("Looking for jobs.. Please wait..")

        self.browser.set_window_position(1, 1)
        self.browser.maximize_window()
        self.browser, _ = self.next_jobs_page(position, location, jobs_per_page, experience_level=self.experience_level)
        log.info("Looking for jobs.. Please wait..")

        while time.time() - start_time < self.MAX_SEARCH_TIME:
            try:
                log.info(f"{(self.MAX_SEARCH_TIME - (time.time() - start_time)) // 60} minutes left in this search")

                # sleep to make sure everything loads, add random to make us look human.
                randoTime: float = random.uniform(1.5, 2.9)
                log.debug(f"Sleeping for {round(randoTime, 1)}")
                #time.sleep(randoTime)
                self.load_page(sleep=0.5)

                # LinkedIn displays the search results in a scrollable <div> on the left side, we have to scroll to its bottom

                # scroll to bottom

                if self.is_present(self.locator["search"]):
                    scrollresults = self.get_elements("search")
                    #     self.browser.find_element(By.CLASS_NAME,
                    #     "jobs-search-results-list"
                    # )
                    # Selenium only detects visible elements; if we scroll to the bottom too fast, only 8-9 results will be loaded into IDs list
                    for i in range(300, 3000, 100):
                        self.browser.execute_script("arguments[0].scrollTo(0, {})".format(i), scrollresults[0])
                    scrollresults = self.get_elements("search")
                    #time.sleep(1)

                # get job links, (the following are actually the job card objects)
                if self.is_present(self.locator["links"]):
                    links = self.get_elements("links")
                # links = self.browser.find_elements("xpath",
                #     '//div[@data-job-id]'
                # )

                    jobIDs = {} #{Job id: processed_status}
                
                    # children selector is the container of the job cards on the left
                    for link in links:
                            if 'Applied' not in link.text: #checking if applied already
                                if link.text not in self.blacklist: #checking if blacklisted
                                    jobID = link.get_attribute("data-job-id")
                                    if jobID == "search":
                                        log.debug("Job ID not found, search keyword found instead? {}".format(link.text))
                                        continue
                                    else:
                                        jobIDs[jobID] = "To be processed"
                    if len(jobIDs) > 0:
                        self.apply_loop(jobIDs)
                    self.browser, jobs_per_page = self.next_jobs_page(position,
                                                                      location,
                                                                      jobs_per_page, 
                                                                      experience_level=self.experience_level)
                else:
                    self.browser, jobs_per_page = self.next_jobs_page(position,
                                                                      location,
                                                                      jobs_per_page, 
                                                                      experience_level=self.experience_level)


            except Exception as e:
                print(e)
    def apply_loop(self, jobIDs):
        for jobID in jobIDs:
            if jobIDs[jobID] == "To be processed":
                applied = self.apply_to_job(jobID)
                if applied:
                    log.info(f"Applied to {jobID}")
                else:
                    log.info(f"Failed to apply to {jobID}")
                jobIDs[jobID] == applied

    def apply_to_job(self, jobID):
        # Implement retry mechanism to prevent stopping in between
        for retry in range(self.max_retries):
            try:
                return self._apply_to_job_internal(jobID)
            except Exception as e:
                log.error(f"Error applying to job {jobID}: {str(e)}")
                if retry < self.max_retries - 1:
                    log.info(f"Retrying in {self.retry_delay} seconds... (Attempt {retry + 1}/{self.max_retries})")
                    time.sleep(self.retry_delay)
                else:
                    log.error(f"Failed to apply to job {jobID} after {self.max_retries} attempts.")
                    self.write_to_file(None, jobID, f"Error: {str(e)}", False)
                    return False
    
    def _apply_to_job_internal(self, jobID):
        # #self.avoid_lock() # annoying

        # get job page
        self.get_job_page(jobID)

        # let page load
        time.sleep(1)

        # get easy apply button
        button = self.get_easy_apply_button()

        # Check if we should apply using Gemini agent
        should_apply = True
        reason = ""
        job_description = ""
        
        if self.use_gemini_agent and self.gemini_agent and self.gemini_agent.is_enabled() and not self.auto_apply:
            try:
                # Get job description
                try:
                    job_description_element = self.browser.find_element(By.CLASS_NAME, "jobs-description")
                    if job_description_element:
                        job_description = job_description_element.text
                except:
                    pass
                
                # Ask Gemini if we should apply
                if job_description:
                    should_apply, reason = self.gemini_agent.should_apply(job_description)
                    log.info(f"Gemini recommendation - Apply: {should_apply}, Reason: {reason}")
            except Exception as e:
                log.error(f"Error getting Gemini recommendation: {str(e)}")

        # word filter to skip positions not wanted
        if button is not False:
            if any(word in self.browser.title for word in self.blackListTitles):
                log.info('skipping this application, a blacklisted keyword was found in the job position')
                string_easy = "* Contains blacklisted keyword"
                result = False
            elif not should_apply:
                log.info(f'Skipping this application based on Gemini recommendation: {reason}')
                string_easy = "* Skipped based on AI recommendation"
                result = False
            else:
                string_easy = "* has Easy Apply Button"
                log.info("Clicking the EASY apply button")
                button.click()
                clicked = True
                time.sleep(1)
                self.fill_out_fields()
                result: bool = self.send_resume()
                if result:
                    string_easy = "*Applied: Sent Resume"
                else:
                    string_easy = "*Did not apply: Failed to send Resume"
        elif "You applied on" in self.browser.page_source:
            log.info("You have already applied to this position.")
            string_easy = "* Already Applied"
            result = False
        else:
            log.info("The Easy apply button does not exist.")
            string_easy = "* Doesn't have Easy Apply Button"
            result = False

        # position_number: str = str(count_job + jobs_per_page)
        log.info(f"\nPosition {jobID}:\n {self.browser.title} \n {string_easy} \n")

        self.write_to_file(button, jobID, self.browser.title, result)
        return result

    def write_to_file(self, button, jobID, browserTitle, result) -> None:
        def re_extract(text, pattern):
            target = re.search(pattern, text)
            if target:
                target = target.group(1)
            return target

        timestamp: str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        attempted: bool = False if button == False else True
        job = re_extract(browserTitle.split(' | ')[0], r"\(?\d?\)?\s?(\w.*)")
        company = re_extract(browserTitle.split(' | ')[1], r"(\w.*)")

        toWrite: list = [timestamp, jobID, job, company, attempted, result]
        with open(self.filename, 'a+') as f:
            writer = csv.writer(f)
            writer.writerow(toWrite)

    def get_job_page(self, jobID):

        job: str = 'https://www.linkedin.com/jobs/view/' + str(jobID)
        self.browser.get(job)
        self.job_page = self.load_page(sleep=0.5)
        return self.job_page

    def get_easy_apply_button(self):
        EasyApplyButton = False
        try:
            buttons = self.get_elements("easy_apply_button")
            # buttons = self.browser.find_elements("xpath",
            #     '//button[contains(@class, "jobs-apply-button")]'
            # )
            for button in buttons:
                if "Easy Apply" in button.text:
                    EasyApplyButton = button
                    self.wait.until(EC.element_to_be_clickable(EasyApplyButton))
                else:
                    log.debug("Easy Apply button not found")
            
        except Exception as e: 
            print("Exception:",e)
            log.debug("Easy Apply button not found")


        return EasyApplyButton

    def fill_out_fields(self):
        fields = self.browser.find_elements(By.CLASS_NAME, "jobs-easy-apply-form-section__grouping")
        for field in fields:

            if "Mobile phone number" in field.text:
                field_input = field.find_element(By.TAG_NAME, "input")
                field_input.clear()
                field_input.send_keys(self.phone_number)


        return


    def get_elements(self, type) -> list:
        elements = []
        element = self.locator[type]
        if self.is_present(element):
            elements = self.browser.find_elements(element[0], element[1])
        return elements

    def is_present(self, locator):
        return len(self.browser.find_elements(locator[0],
                                              locator[1])) > 0

    def send_resume(self) -> bool:
        def is_present(button_locator) -> bool:
            return len(self.browser.find_elements(button_locator[0],
                                                  button_locator[1])) > 0

        try:
            # Define locators
            next_locator = (By.CSS_SELECTOR, "button[aria-label='Continue to next step']")
            review_locator = (By.CSS_SELECTOR, "button[aria-label='Review your application']")
            submit_locator = (By.CSS_SELECTOR, "button[aria-label='Submit application']")
            error_locator = (By.CLASS_NAME, "artdeco-inline-feedback__message")
            upload_resume_locator = (By.XPATH, '//span[text()="Upload resume"]')
            upload_cv_locator = (By.XPATH, '//span[text()="Upload cover letter"]')
            follow_locator = (By.CSS_SELECTOR, "label[for='follow-company-checkbox']")
            
            # Get job description for context if available
            job_description = ""
            try:
                job_description_element = self.browser.find_element(By.CLASS_NAME, "jobs-description")
                if job_description_element:
                    job_description = job_description_element.text
            except Exception:
                pass

            submitted = False
            loop = 0
            max_loops = 5  # Increased from 2 to handle more complex applications
            
            while loop < max_loops:
                loop += 1
                log.info(f"Application step {loop} of {max_loops}")
                time.sleep(1.5)  # Slightly longer wait to ensure page loads
                
                # Process any questions that might be present
                try:
                    if len(self.browser.find_elements(By.CLASS_NAME, "jobs-easy-apply-form-section__grouping")) > 0:
                        log.info("Found questions to answer")
                        self.process_questions()
                except Exception as e:
                    log.error(f"Error processing questions: {str(e)}")
                
                # Upload resume if needed
                if is_present(upload_resume_locator):
                    try:
                        # Try multiple possible resume upload selectors
                        resume_selectors = [
                            "//*[contains(@id, 'jobs-document-upload-file-input-upload-resume')]",
                            "//input[contains(@name, 'resume')]",
                            "//input[@type='file' and contains(@id, 'resume')]"
                        ]
                        
                        resume_locator = None
                        for selector in resume_selectors:
                            try:
                                resume_locator = self.browser.find_element(By.XPATH, selector)
                                if resume_locator:
                                    break
                            except:
                                continue
                        
                        if resume_locator and "Resume" in self.uploads:
                            resume = self.uploads["Resume"]
                            resume_locator.send_keys(resume)
                            log.info(f"Resume uploaded: {resume}")
                            time.sleep(1)  # Wait for upload to complete
                    except Exception as e:
                        log.error(f"Resume upload failed: {str(e)}")
                        if "Resume" in self.uploads:
                            log.debug(f"Resume path: {self.uploads['Resume']}")
                
                # Upload cover letter if needed
                if is_present(upload_cv_locator):
                    try:
                        # Try multiple possible cover letter upload selectors
                        cv_selectors = [
                            "//*[contains(@id, 'jobs-document-upload-file-input-upload-cover-letter')]",
                            "//input[contains(@name, 'cover')]",
                            "//input[@type='file' and contains(@id, 'cover')]"
                        ]
                        
                        cv_locator = None
                        for selector in cv_selectors:
                            try:
                                cv_locator = self.browser.find_element(By.XPATH, selector)
                                if cv_locator:
                                    break
                            except:
                                continue
                        
                        if cv_locator and "Cover Letter" in self.uploads:
                            cv = self.uploads["Cover Letter"]
                            cv_locator.send_keys(cv)
                            log.info(f"Cover letter uploaded: {cv}")
                            time.sleep(1)  # Wait for upload to complete
                    except Exception as e:
                        log.error(f"Cover letter upload failed: {str(e)}")
                        if "Cover Letter" in self.uploads:
                            log.debug(f"Cover letter path: {self.uploads['Cover Letter']}")
                
                # Handle follow checkbox
                if len(self.get_elements("follow")) > 0:
                    try:
                        elements = self.get_elements("follow")
                        for element in elements:
                            button = self.wait.until(EC.element_to_be_clickable(element))
                            button.click()
                            log.info("Clicked follow company checkbox")
                    except Exception as e:
                        log.error(f"Error clicking follow checkbox: {str(e)}")
                
                # Handle submit button
                if len(self.get_elements("submit")) > 0:
                    try:
                        elements = self.get_elements("submit")
                        for element in elements:
                            button = self.wait.until(EC.element_to_be_clickable(element))
                            button.click()
                            log.info("Application Submitted")
                            submitted = True
                            break
                        if submitted:
                            break
                    except Exception as e:
                        log.error(f"Error clicking submit button: {str(e)}")
                
                # Handle errors and questions
                elif len(self.get_elements("error")) > 0:
                    try:
                        elements = self.get_elements("error")
                        if "application was sent" in self.browser.page_source:
                            log.info("Application Submitted")
                            submitted = True
                            break
                        elif len(elements) > 0:
                            retry_count = 0
                            max_retries = 3
                            while len(elements) > 0 and retry_count < max_retries:
                                retry_count += 1
                                log.info(f"Found errors, attempting to fix (attempt {retry_count}/{max_retries})")
                                
                                # Get error messages
                                error_messages = [elem.text for elem in elements if elem.text]
                                log.info(f"Error messages: {error_messages}")
                                
                                # Process questions again with job description context
                                self.process_questions()
                                time.sleep(2)
                                
                                # Check if errors are resolved
                                elements = self.get_elements("error")
                                
                                if "application was sent" in self.browser.page_source:
                                    log.info("Application Submitted after fixing errors")
                                    submitted = True
                                    break
                                elif is_present(self.locator["easy_apply_button"]):
                                    log.info("Skipping application due to persistent errors")
                                    submitted = False
                                    break
                            
                            if submitted:
                                break
                            elif retry_count >= max_retries:
                                log.warning("Maximum retry attempts reached for error handling")
                                break
                            continue
                        else:
                            log.info("Application not submitted, unknown error")
                            time.sleep(2)
                    except Exception as e:
                        log.error(f"Error handling application errors: {str(e)}")
                
                # Handle next button
                elif len(self.get_elements("next")) > 0:
                    try:
                        elements = self.get_elements("next")
                        for element in elements:
                            button = self.wait.until(EC.element_to_be_clickable(element))
                            button.click()
                            log.info("Clicked next button")
                            time.sleep(1)  # Wait for next page to load
                            break
                    except Exception as e:
                        log.error(f"Error clicking next button: {str(e)}")
                
                # Handle review button
                elif len(self.get_elements("review")) > 0:
                    try:
                        elements = self.get_elements("review")
                        for element in elements:
                            button = self.wait.until(EC.element_to_be_clickable(element))
                            button.click()
                            log.info("Clicked review button")
                            time.sleep(1)  # Wait for review page to load
                            break
                    except Exception as e:
                        log.error(f"Error clicking review button: {str(e)}")
                
                # If no actionable elements found, try to process any questions
                else:
                    try:
                        # Check if there are any form fields to fill
                        if len(self.browser.find_elements(By.CLASS_NAME, "jobs-easy-apply-form-section__grouping")) > 0:
                            log.info("No buttons found but questions exist, processing questions")
                            self.process_questions()
                        else:
                            log.info("No actionable elements found, moving to next loop iteration")
                    except Exception as e:
                        log.error(f"Error in fallback question processing: {str(e)}")
                
                # Check if we've reached the end of the application process
                if "application was sent" in self.browser.page_source or "your application has been submitted" in self.browser.page_source.lower():
                    log.info("Application submitted successfully")
                    submitted = True
                    break

        except Exception as e:
            log.error(f"Error in send_resume: {str(e)}")
            log.error("Cannot apply to this job, but will continue with other applications")
        
        return submitted
    def process_questions(self):
        time.sleep(1)
        
        # Get job description for context if available
        job_description = ""
        try:
            job_description_element = self.browser.find_element(By.CLASS_NAME, "jobs-description")
            if job_description_element:
                job_description = job_description_element.text
        except Exception:
            pass
            
        # Get all form fields
        form = self.get_elements("fields") #self.browser.find_elements(By.CLASS_NAME, "jobs-easy-apply-form-section__grouping")
        
        if not form:
            log.warning("No form fields found")
            return
            
        for field in form:
            try:
                # Extract question text
                question = field.text.strip()
                if not question:
                    continue
                    
                # Get answer from Gemini or fallback
                answer = self.ans_question(question, job_description)
                if not answer:
                    log.warning(f"No answer found for question: {question}")
                    continue
                    
                log.info(f"Processing question: '{question}' with answer: '{answer}'")
                
                # Handle different input types
                
                # Radio buttons
                radio_buttons = field.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                if radio_buttons:
                    try:
                        # Try exact match first
                        for radio in radio_buttons:
                            radio_value = radio.get_attribute("value")
                            radio_label = radio.find_element(By.XPATH, "./following-sibling::label").text.strip()
                            
                            if answer.lower() in radio_value.lower() or answer.lower() in radio_label.lower():
                                self.browser.execute_script("arguments[0].click();", radio)
                                log.info(f"Selected radio button: {radio_label}")
                                break
                    except Exception as e:
                        log.error(f"Error with radio button: {str(e)}")
                
                # Dropdown/Select
                select_elements = field.find_elements(By.TAG_NAME, "select")
                if select_elements:
                    try:
                        for select_element in select_elements:
                            select = WebDriverWait(self.browser, 3).until(
                                EC.element_to_be_clickable((By.XPATH, f"//select[contains(@id, 'dropdown')]"))
                            )
                            select.click()
                            time.sleep(0.5)
                            options = select.find_elements(By.TAG_NAME, "option")
                            
                            for option in options:
                                option_text = option.text.strip().lower()
                                if answer.lower() in option_text or option_text in answer.lower():
                                    option.click()
                                    log.info(f"Selected dropdown option: {option_text}")
                                    break
                    except Exception as e:
                        log.error(f"Error with dropdown: {str(e)}")
                
                # Multi-select
                if self.is_present(self.locator["multi_select"]):
                    try:
                        input_field = field.find_element(self.locator["multi_select"])
                        input_field.clear()
                        input_field.send_keys(answer)
                        time.sleep(0.5)
                        # Try to select from dropdown if it appears
                        try:
                            dropdown_option = WebDriverWait(self.browser, 2).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, "li.search-result__option"))
                            )
                            dropdown_option.click()
                        except:
                            # If no dropdown appears, just leave the text as is
                            pass
                    except Exception as e:
                        log.error(f"Error with multi-select: {str(e)}")
                
                # Text box
                text_inputs = field.find_elements(By.CSS_SELECTOR, "input[type='text'], textarea")
                if text_inputs:
                    try:
                        for text_input in text_inputs:
                            if text_input.is_displayed() and text_input.is_enabled():
                                text_input.clear()
                                text_input.send_keys(answer)
                                log.info(f"Filled text input with: {answer}")
                                break
                    except Exception as e:
                        log.error(f"Error with text input: {str(e)}")
                
                # Checkbox
                checkboxes = field.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
                if checkboxes:
                    try:
                        for checkbox in checkboxes:
                            checkbox_label = checkbox.find_element(By.XPATH, "./following-sibling::label").text.strip()
                            if (answer.lower() == "yes" and "yes" in checkbox_label.lower()) or \
                               (answer.lower() in checkbox_label.lower()):
                                if not checkbox.is_selected():
                                    self.browser.execute_script("arguments[0].click();", checkbox)
                                    log.info(f"Checked checkbox: {checkbox_label}")
                    except Exception as e:
                        log.error(f"Error with checkbox: {str(e)}")
                
                # If no specific input type was found, try generic approach
                if not (radio_buttons or select_elements or self.is_present(self.locator["multi_select"]) or 
                        text_inputs or checkboxes):
                    try:
                        # Try to find any input element
                        inputs = field.find_elements(By.CSS_SELECTOR, "input, textarea, select")
                        if inputs:
                            for input_elem in inputs:
                                if input_elem.is_displayed() and input_elem.is_enabled():
                                    input_type = input_elem.get_attribute("type")
                                    if input_type in ["text", "textarea", None]:
                                        input_elem.clear()
                                        input_elem.send_keys(answer)
                                        log.info(f"Filled generic input with: {answer}")
                                    elif input_type == "radio":
                                        self.browser.execute_script("arguments[0].click();", input_elem)
                                        log.info("Clicked generic radio button")
                                    break
                    except Exception as e:
                        log.error(f"Error with generic input approach: {str(e)}")
            
            except Exception as e:
                log.error(f"Error processing question field: {str(e)}")
                continue

    def ans_question(self, question, job_description=None): #refactor this to an ans.yaml file
        answer = None
        question_lower = question.lower()
        
        # Try to use Gemini agent if available and enabled
        if hasattr(self, 'gemini_agent') and self.gemini_agent and self.use_gemini_agent:
            try:
                gemini_answer = self.gemini_agent.answer_question(question, job_description)
                if gemini_answer:
                    log.info(f"Gemini answered: '{question}' with '{gemini_answer}'")
                    return gemini_answer
            except Exception as e:
                log.error(f"Error using Gemini agent: {str(e)}")
                # Fall back to hardcoded answers
        
        # Check if we have a cached answer
        if question in self.answers:
            return self.answers[question]
            
        # Fallback to hardcoded answers
        if "how many" in question_lower:
            answer = "1"
        elif "experience" in question_lower:
            answer = "1"
        elif "sponsor" in question_lower:
            answer = "No"
        elif 'do you ' in question_lower:
            answer = "Yes"
        elif "have you " in question_lower:
            answer = "Yes"
        elif "US citizen" in question_lower or "authorized to work" in question_lower:
            answer = "Yes"
        elif "are you " in question_lower:
            answer = "Yes"
        elif "can you" in question_lower:
            answer = "Yes"
        elif "are you legally" in question_lower:
            answer = "Yes"
        elif "salary" in question_lower or "compensation" in question_lower:
            answer = self.salary
        elif "name" in question_lower:
            if hasattr(self, 'gemini_agent') and self.gemini_agent:
                try:
                    answer = self.gemini_agent.user_data.get('full_name', '')
                except:
                    pass
        elif "email" in question_lower:
            if hasattr(self, 'gemini_agent') and self.gemini_agent:
                try:
                    answer = self.gemini_agent.user_data.get('email', '')
                except:
                    pass
        elif "phone" in question_lower:
            answer = self.phone_number
        elif "gender" in question_lower:
            answer = "Male"
        elif "race" in question_lower:
            answer = "Wish not to answer"
        elif "lgbtq" in question_lower:
            answer = "Wish not to answer"
        elif "ethnicity" in question_lower:
            answer = "Wish not to answer"
        elif "nationality" in question_lower:
            answer = "Wish not to answer"
        elif "government" in question_lower:
            answer = "I do not wish to self-identify"
        else:
            log.info("Not able to answer question automatically. Using default 'Yes' answer")
            answer = "Yes"  # Default to Yes instead of waiting for user input to prevent stopping
        
        if not answer:
            log.info("No specific answer found, using default 'Yes'")
            answer = "Yes"  # Ensure we always have an answer
            
        log.info(f"Answering question: '{question}' with answer: '{answer}'")

        # Cache the answer for future use
        if question not in self.answers:
            self.answers[question] = answer
            # Append a new question-answer pair to the CSV file
            try:
                new_data = pd.DataFrame({"Question": [question], "Answer": [answer]})
                new_data.to_csv(self.qa_file, mode='a', header=False, index=False, encoding='utf-8')
                log.info(f"Appended to QA file: '{question}' with answer: '{answer}'.")
            except Exception as e:
                log.error(f"Error saving to QA file: {str(e)}")

        return answer

    def load_page(self, sleep=1):
        scroll_page = 0
        while scroll_page < 4000:
            self.browser.execute_script("window.scrollTo(0," + str(scroll_page) + " );")
            scroll_page += 500
            time.sleep(sleep)

        if sleep != 1:
            self.browser.execute_script("window.scrollTo(0,0);")
            time.sleep(sleep)

        page = BeautifulSoup(self.browser.page_source, "lxml")
        return page

    def avoid_lock(self) -> None:
        x, _ = pyautogui.position()
        pyautogui.moveTo(x + 200, pyautogui.position().y, duration=1.0)
        pyautogui.moveTo(x, pyautogui.position().y, duration=0.5)
        pyautogui.keyDown('ctrl')
        pyautogui.press('esc')
        pyautogui.keyUp('ctrl')
        time.sleep(0.5)
        pyautogui.press('esc')

    def next_jobs_page(self, position, location, jobs_per_page, experience_level=[]):
        # Construct the experience level part of the URL
        experience_level_str = ",".join(map(str, experience_level)) if experience_level else ""
        experience_level_param = f"&f_E={experience_level_str}" if experience_level_str else ""
        self.browser.get(
            # URL for jobs page
            "https://www.linkedin.com/jobs/search/?f_LF=f_AL&keywords=" +
            position + location + "&start=" + str(jobs_per_page) + experience_level_param)
        #self.avoid_lock()
        log.info("Loading next job page?")
        self.load_page()
        return (self.browser, jobs_per_page)

    # def finish_apply(self) -> None:
    #     self.browser.close()


if __name__ == '__main__':

    with open("config.yaml", 'r') as stream:
        try:
            parameters = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise exc

    assert len(parameters['positions']) > 0
    assert len(parameters['locations']) > 0
    assert parameters['username'] is not None
    assert parameters['password'] is not None
    assert parameters['phone_number'] is not None

    if 'uploads' in parameters.keys() and type(parameters['uploads']) == list:
        raise Exception("uploads read from the config file appear to be in list format" +
                        " while should be dict. Try removing '-' from line containing" +
                        " filename & path")

    # Filter out sensitive information for logging
    log_safe_params = {k: parameters[k] for k in parameters.keys() 
                      if k not in ['username', 'password', 'gemini_api_key']}
    log.info(log_safe_params)

    output_filename: list = [f for f in parameters.get('output_filename', ['output.csv']) if f is not None]
    output_filename: list = output_filename[0] if len(output_filename) > 0 else 'output.csv'
    blacklist = parameters.get('blacklist', [])
    blackListTitles = parameters.get('blackListTitles', [])

    uploads = {} if parameters.get('uploads', {}) is None else parameters.get('uploads', {})
    for key in uploads.keys():
        assert uploads[key] is not None

    locations: list = [l for l in parameters['locations'] if l is not None]
    positions: list = [p for p in parameters['positions'] if p is not None]
    
    # Get Gemini API key from environment variable if not in config
    gemini_api_key = parameters.get('gemini_api_key')
    if gemini_api_key == "YOUR_GEMINI_API_KEY":
        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if gemini_api_key:
            log.info("Using Gemini API key from environment variable")
        else:
            log.warning("No Gemini API key provided in config or environment variable")
    
    # Get other Gemini and auto-apply settings
    use_gemini_agent = parameters.get('use_gemini_agent', True)
    user_data_file = parameters.get('user_data_file', "user_data.yaml")
    auto_apply = parameters.get('auto_apply', True)
    min_match_score = parameters.get('min_match_score', 70)

    try:
        bot = EasyApplyBot(parameters['username'],
                        parameters['password'],
                        parameters['phone_number'],
                        parameters['salary'],
                        parameters['rate'], 
                        uploads=uploads,
                        filename=output_filename,
                        blacklist=blacklist,
                        blackListTitles=blackListTitles,
                        experience_level=parameters.get('experience_level', []),
                        gemini_api_key=gemini_api_key,
                        use_gemini_agent=use_gemini_agent,
                        user_data_file=user_data_file,
                        auto_apply=auto_apply,
                        min_match_score=min_match_score
                        )
        bot.start_apply(positions, locations)
    except KeyboardInterrupt:
        log.info("Application interrupted by user. Exiting gracefully...")
    except Exception as e:
        log.error(f"An error occurred: {str(e)}")
        # Try to restart if possible
        log.info("Attempting to restart the application...")
        try:
            bot = EasyApplyBot(parameters['username'],
                            parameters['password'],
                            parameters['phone_number'],
                            parameters['salary'],
                            parameters['rate'], 
                            uploads=uploads,
                            filename=output_filename,
                            blacklist=blacklist,
                            blackListTitles=blackListTitles,
                            experience_level=parameters.get('experience_level', []),
                            gemini_api_key=gemini_api_key,
                            use_gemini_agent=use_gemini_agent,
                            user_data_file=user_data_file,
                            auto_apply=auto_apply,
                            min_match_score=min_match_score
                            )
            bot.start_apply(positions, locations)
        except Exception as e2:
            log.error(f"Failed to restart: {str(e2)}")
            log.error("Please restart the application manually.")


