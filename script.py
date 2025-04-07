import logging.config
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
import requests
import os
import logging
from dotenv import load_dotenv

load_dotenv()
from config import LOGGER_CONFIG

logging.config.dictConfig(LOGGER_CONFIG)
logger = logging.getLogger(__name__)


class IP:

    @staticmethod
    def get_public_ip():
        logger.info('Fetching the public IP')
        try:
            response = requests.get("https://api.ipify.org?format=text", timeout=5)
            logger.info(f'Fetched public IP = {response.text}')
            return response.text
        except requests.RequestException:
            logger.error("Failed to fetch public IP:", exc_info=True)
            return None


class ISP(IP):
    ISP_URL = None
    DRIVER = None
    LOGGED_IN = False

    def __init__(self):
        driver_options = Options()
        # driver_options.add_argument("--headless")
        driver_options.add_argument("--disable-gpu")

        self.DRIVER = webdriver.Chrome(
            service=webdriver.ChromeService(executable_path=os.getenv('WEBDRIVER_PATH')),
            options=driver_options
        )
        self.ISP_URL = os.getenv('ISP_URL')

        self.DRIVER.get(self.ISP_URL)
        self.load_isp_site()
        self.LOGGED_IN = self.is_loggedin()

    def load_isp_site(self):
        self.DRIVER.get(self.ISP_URL)

    def logout(self):
        try:
            logger.info('Attempting to logout...')
            self.load_isp_site()
            logout_element = self.DRIVER.find_element(By.CSS_SELECTOR, "input.ask3")
            logger.info('Found the logout button')

            logout_element.click()
            logger.info('Clicked the logout button, waiting for the action to complete...')

            WebDriverWait(self.DRIVER, 10).until(
                EC.invisibility_of_element_located((By.CSS_SELECTOR, "input.ask3"))
            )
            logger.info('Logged out successfully...')
            self.LOGGED_IN = False
        except Exception as e:
            logger.error(f'Failed to logout. {str(e)}', exc_info=True)

    def login(self):
        try:
            logger.info('Attempting to login...')

            self.load_isp_site()
            username_element = self.DRIVER.find_element(By.ID, "username")
            logger.info('Found the username input field')

            password_element = self.DRIVER.find_element(By.ID, "password")
            logger.info('Found the password input field')

            login_button_element = self.DRIVER.find_element(By.CSS_SELECTOR, "button.btnlink1")
            logger.info('Found the login button')

            logger.info('Populating credentials...')
            username_element.send_keys(os.getenv('ISP_USERNAME'))
            password_element.send_keys(os.getenv('ISP_PASSWORD'))

            logger.info('Clicked the login button...waiting for the action to complete...')
            login_button_element.click()
            WebDriverWait(self.DRIVER, 10).until(
                EC.invisibility_of_element_located((By.CSS_SELECTOR, "button.btnlink1"))
            )

            logger.info('Logged in successfully...')
            self.LOGGED_IN = True
        except Exception as e:
            logger.error(f'Failed to login. {str(e)}', exc_info=True)

    def is_loggedin(self):
        logger.info('Checking authentication status')
        try:
            self.DRIVER.find_element(By.CSS_SELECTOR, "input.ask3")
            logger.info('Logout button found...User is logged in')
            return True
        except NoSuchElementException:
            logger.info('Unable to find logout button...User not logged in')
            return False

    def rotate_ip(self):
        pass


isp = ISP()

while True:
    if isp.LOGGED_IN:
        isp.logout()
    else:
        isp.login()

    inp = input("Press 'c' to continue, anything else to exit.")
    if inp.lower() != 'c':
        break