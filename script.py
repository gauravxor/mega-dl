from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from pathlib import Path
import os
import time
import requests
import psutil
import re
import subprocess
import logging.config

from dotenv import load_dotenv

load_dotenv()
from config import LOGGER_CONFIG

logging.config.dictConfig(LOGGER_CONFIG)
logger = logging.getLogger(__name__)


class MegaDl:

    def __init__(self):
        self.megasync_process_name = "MEGAsync.exe"
        self.megasync_process = self.find_megasync_process()
        self.megasync_quota_exceeded = False
        self.megasync_log_file = "C:\\Users\\gaurav\\AppData\\Local\\Mega Limited\\MEGAsync\\logs\MEGAsync.log"

        driver_opt = Options()
        driver_opt.add_argument("--headless")
        driver_opt.add_argument("--disable-gpu")

        self.chrome_driver = webdriver.Chrome(
            service=webdriver.ChromeService(executable_path=os.getenv('WEBDRIVER_PATH')),
            options=driver_opt
        )

        self.logout_button_selector = "input.ask3"
        self.username_field_id = "username"
        self.password_field_id = "password"
        self.login_button_selector = "button.btnlink1"

        self.isp_portal_url = os.getenv("ISP_URL")
        self.load_isp_portal()
        self.logged_in = self.is_logged_in()
        self.ip_log_file = Path(__file__).parent / "ip_addrs.txt"
        self.retry_delay_seconds = 5

        if not self.ip_log_file.exists():
            self.ip_log_file.touch()

    def fetch_public_ip(self):
        if not self.logged_in:
            logger.warning("Cannot fetch public IP: Not connected to the internet or ISP login failed.")
            return None

        try:
            ip_response = requests.get("https://api.ipify.org?format=text", timeout=5)
            logger.info("Successfully fetched public IP.")
            return ip_response.text.strip()
        except requests.RequestException as e:
            logger.error(f"Error fetching public IP: {e}")
            return None

    def load_isp_portal(self):
        try:
            logger.info(f"Loading ISP portal: {self.isp_portal_url}")
            self.chrome_driver.get(self.isp_portal_url)
            logger.info("ISP portal loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load ISP portal at {self.isp_portal_url}: {e}")

    def logout(self):
        try:
            logger.info("Attempting to log out of ISP portal...")

            logout_button = self.chrome_driver.find_element(By.CSS_SELECTOR, self.logout_button_selector)
            logger.debug("Logout button located. Clicking now...")

            logout_button.click()

            logger.debug("Waiting for logout to complete...")
            WebDriverWait(self.chrome_driver, 10).until(
                EC.invisibility_of_element_located((By.CSS_SELECTOR, self.logout_button_selector))
            )

            self.logged_in = False
            logger.info("Logged out successfully.")
        except Exception as e:
            logger.error(f"Logout failed: {e}", exc_info=True)

    def login(self):
        try:
            logger.info("Attempting to log in to ISP portal...")

            username = os.getenv("ISP_USERNAME")
            password = os.getenv("ISP_PASSWORD")

            if not username or not password:
                logger.error("ISP_USERNAME or ISP_PASSWORD environment variables are not set.")
                return

            username_input = self.chrome_driver.find_element(By.ID, self.username_field_id)
            logger.debug("Username input field located.")

            password_input = self.chrome_driver.find_element(By.ID, self.password_field_id)
            logger.debug("Password input field located.")

            login_button = self.chrome_driver.find_element(By.CSS_SELECTOR, self.login_button_selector)
            logger.debug("Login button located.")

            logger.debug("Entering credentials...")
            username_input.send_keys(username)
            password_input.send_keys(password)

            logger.debug("Clicking the login button...")
            login_button.click()

            logger.debug("Waiting for login to complete...")
            WebDriverWait(self.chrome_driver, 10).until(
                EC.invisibility_of_element_located((By.CSS_SELECTOR, self.login_button_selector))
            )

            self.logged_in = True
            logger.info("Logged in successfully.")

        except Exception as e:
            logger.error(f"Login failed: {e}", exc_info=True)

    def is_logged_in(self):
        try:
            self.chrome_driver.find_element(By.CSS_SELECTOR, self.logout_button_selector)
            logger.info("User is currently logged in (logout button found).")
            return True
        except NoSuchElementException:
            logger.info("User is not logged in (logout button not found).")
            return False

    def get_logged_ip_addresses(self):
        ip_addresses = []
        try:
            with self.ip_log_file.open('r') as file:
                ip_addresses = [line.strip() for line in file if line.strip()]
        except Exception as e:
            logger.error(f"Failed to read IP addresses from log file: {e}", exc_info=True)

        return ip_addresses

    def append_ip_to_log(self, public_ip=None):
        if public_ip is None:
            logger.warning("No public IP provided — skipping log entry.")
            return

        try:
            with self.ip_log_file.open('a') as file:
                file.write(f"{public_ip}\n")
            logger.debug(f"Logged public IP: {public_ip}")
        except Exception as e:
            logger.error(f"Failed to log IP address '{public_ip}': {e}", exc_info=True)

    def has_ip_rotated(self):
        current_ip = self.fetch_public_ip()
        if not current_ip:
            logger.warning("Cannot determine current IP — skipping rotation check.")
            return False

        logged_ips = self.get_logged_ip_addresses()

        if not logged_ips:
            logger.info("No IPs logged previously — logging current IP.")
            self.append_ip_to_log(current_ip)
            return False

        if current_ip not in logged_ips:
            logger.info(f"Detected IP rotation: new IP {current_ip}")
            self.append_ip_to_log(current_ip)
            return True

        logger.debug("IP has not changed.")
        return False

    def rotate_ip(self):
        max_retry_delay = 300  # maximum backoff time
        max_attempts = 10
        attempts = 0

        while True:
            if self.has_ip_rotated():
                logger.info("Public IP successfully rotated.")
                self.retry_delay_seconds = 5  # reset kardo backoff time ko
                return True

            logger.info("IP not rotated. Logging out and retrying...")

            self.logout()

            logger.info(f"Waiting for {self.retry_delay_seconds} seconds before retrying login...")
            time.sleep(self.retry_delay_seconds)

            self.login()
            if not self.logged_in:
                logger.warning("Login failed. Retrying after delay...")

            self.retry_delay_seconds = min(self.retry_delay_seconds * 2, max_retry_delay)

            attempts += 1
            if attempts >= max_attempts:
                logger.error("Max IP rotation attempts reached. Aborting.")
                return False

    def find_megasync_process(self):
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] == self.megasync_process_name:
                    logger.debug(f"Found MEGAsync process: PID {proc.pid}")
                    return proc
            logger.info("MEGAsync process not found.")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            logger.error(f"Error while searching for MEGAsync process: {e}", exc_info=True)

        return None

    def stop_megasync(self):
        if not self.megasync_process:
            logger.warning("No MEGAsync process reference available.")
            return

        try:
            pid = self.megasync_process.pid
            logger.info(f"Attempting to terminate MEGAsync process (PID: {pid})...")
            self.megasync_process.terminate()

            try:
                self.megasync_process.wait(timeout=5)
                logger.info(f"MEGAsync process {pid} terminated successfully.")
            except psutil.TimeoutExpired:
                logger.warning(f"MEGAsync process {pid} did not terminate in time. Attempting to kill...")
                self.megasync_process.kill()
                self.megasync_process.wait(timeout=3)
                logger.info(f"MEGAsync process {pid} forcefully killed.")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            logger.error(f"Failed to stop MEGAsync process: {e}", exc_info=True)

    def start_megasync(self):
        try:
            exe_path = os.path.expandvars(r"%LocalAppData%\MEGAsync\MEGAsync.exe")

            if not os.path.exists(exe_path):
                logger.error(f"MEGAsync executable not found at {exe_path}")
                return

            proc = subprocess.Popen([exe_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.megasync_process = psutil.Process(proc.pid)
            logger.info(f"MEGAsync started successfully from {exe_path} (PID: {proc.pid})")

        except Exception as e:
            logger.error(f"Failed to start MEGAsync: {e}", exc_info=True)

    def update_transfer_quota(self, log_line):
        quota_exceeded_pattern = re.compile(r"Transfer over quota ui message shown", re.IGNORECASE)

        if quota_exceeded_pattern.search(log_line):
            if not self.megasync_quota_exceeded:
                logger.info("Detected MEGAsync transfer quota exceeded.")
                self.megasync_quota_exceeded = True
            else:
                logger.debug("Quota exceeded message seen again; already marked.")

    def monitor_log(self):
        last_size = 0

        try:
            logger.info("Flushing existing MEGAsync log file...")
            with open(self.megasync_log_file, 'w'):
                pass

            logger.info("Starting MEGAsync and monitoring its log file...")
            self.start_megasync()

            with open(self.megasync_log_file, 'r') as f:
                f.seek(0, os.SEEK_END)

                while True:
                    current_size = os.path.getsize(self.megasync_log_file)

                    if current_size < last_size:
                        logger.info("Log file appears to have been rotated. Resetting file pointer to beginning.")
                        f.seek(0)
                    last_size = current_size

                    line = f.readline()
                    if not line:
                        time.sleep(0.5)
                        continue

                    self.update_transfer_quota(line)

                    if self.megasync_quota_exceeded:
                        logger.info("Transfer quota exceeded — stopping log monitor.")
                        return

        except Exception as e:
            logger.error(f"Error while monitoring MEGAsync log: {e}", exc_info=True)
        finally:
            logger.info("Log monitoring has stopped.")


if __name__ == "__main__":
    mega_dl = MegaDl()

    if mega_dl.megasync_process:
        logger.info("MEGAsync is already running — attempting to stop it...")
        mega_dl.stop_megasync()
        logger.info("MEGAsync process terminated.")
        time.sleep(10)

    logger.info("Rotating IP before starting MEGAsync...")
    if not mega_dl.logged_in:
        logger.info("Logging in before rotating IPs.")
        mega_dl.login()

    mega_dl.rotate_ip()

    while True:
        try:
            logger.info("********** Monitoring MEGAsync Logs **********")
            mega_dl.monitor_log()

            logger.info("Quota exceeded — stopping MEGAsync...")
            mega_dl.stop_megasync()

            logger.info("Attempting to rotate public IP again...")
            mega_dl.rotate_ip()

            mega_dl.megasync_quota_exceeded = False  # reset quota flag for agla cycle

        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
            exit(0)