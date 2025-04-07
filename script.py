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
import time
from dotenv import load_dotenv
from pathlib import Path

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
    IP_LOG_FILE = None
    RETRY_BACKOFF = None

    def __init__(self):
        driver_options = Options()
        driver_options.add_argument("--headless")
        driver_options.add_argument("--disable-gpu")

        self.DRIVER = webdriver.Chrome(
            service=webdriver.ChromeService(executable_path=os.getenv('WEBDRIVER_PATH')),
            options=driver_options
        )
        self.ISP_URL = os.getenv('ISP_URL')

        self.DRIVER.get(self.ISP_URL)
        self.load_isp_site()
        self.LOGGED_IN = self.is_loggedin()
        self.IP_LOG_FILE = Path(__file__).parent / 'ip_addrs.txt'
        if not self.IP_LOG_FILE.exists():
            self.IP_LOG_FILE.touch()

        self.RETRY_BACKOFF = 5

    def load_isp_site(self):
        self.DRIVER.get(self.ISP_URL)

    def logout(self):
        try:
            logger.info('Attempting to logout...')
            self.load_isp_site()
            logout_element = self.DRIVER.find_element(By.CSS_SELECTOR, "input.ask3")
            logger.debug('Found the logout button')

            logout_element.click()
            logger.debug('Clicked the logout button, waiting for the action to complete...')

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
            logger.debug('Found the username input field')

            password_element = self.DRIVER.find_element(By.ID, "password")
            logger.debug('Found the password input field')

            login_button_element = self.DRIVER.find_element(By.CSS_SELECTOR, "button.btnlink1")
            logger.debug('Found the login button')

            logger.debug('Populating credentials...')
            username_element.send_keys(os.getenv('ISP_USERNAME'))
            password_element.send_keys(os.getenv('ISP_PASSWORD'))

            logger.debug('Clicked the login button...waiting for the action to complete...')
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

    def get_old_ip_addrs(self):
        ip_list = []
        try:
            with self.IP_LOG_FILE.open('r') as file:
                ip_list = [line.strip() for line in file if line.strip()]
        except Exception as e:
            logger.error(f'Failed to get the list of old ip addresses. {str(e)}', exc_info=True)
        finally:
            return ip_list

    def log_ip(self, public_ip=None):

        if public_ip is None:
            return

        try:
            with self.IP_LOG_FILE.open('a') as file:
                file.write(f"{public_ip}\n")
        except Exception as e:
            logger.error(f'Error logging IP - {public_ip}. Error - {str(e)}', exc_info=True)

    def is_ip_rotated(self):
        public_ip = self.get_public_ip()
        old_ip_adds = self.get_old_ip_addrs()

        if len(old_ip_adds) == 0:
            self.log_ip(public_ip)
            return False

        if public_ip not in old_ip_adds:
            self.log_ip(public_ip)
            return True

        return False

    def rotate_ip(self):
        if not self.LOGGED_IN:
            logger.info('Logging into ISP portal...')
            self.login()

        while True:
            if self.is_ip_rotated():
                logger.info('Rotated the public IP')
                return True
            else:
                logger.info('Logging out, because ISP did not provide new IP')
                self.logout()
                logger.info(f'Waiting for {self.RETRY_BACKOFF} seconds before logging in again...')
                time.sleep(self.RETRY_BACKOFF)
                self.login()
                self.RETRY_BACKOFF *= 2


isp = ISP()
isp.rotate_ip()