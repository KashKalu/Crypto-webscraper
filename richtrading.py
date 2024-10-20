from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
import pandas as pd
from datetime import datetime
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Google Sheets Configuration
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '1kP_ypv8JZyImVmQOx4asWESbOoZ0cfdyaqwGt_S543w'
SHEET_NAME = 'Sheet3'

# Load Google Sheets API credentials
creds = ServiceAccountCredentials.from_json_keyfile_name('rich-trading-credentials.json', SCOPES)
client = gspread.authorize(creds)

# Open the Google Sheet
sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)

# Telegram Bot Configuration
BOT_TOKEN = '##########:AAFxbmMMVJiVF9DRaNryzBINd8j0vzLku9Y'
GROUP_CHAT_ID = '-1002324536427'  # Replace with your group's chat ID

# Function to load user agents from a file
def load_user_agents(file_path):
    """Load user agents from a specified text file"""
    try:
        with open(file_path, 'r') as file:
            user_agents = [line.strip() for line in file.readlines()]
        return user_agents
    except Exception as e:
        print(f"Error loading user agents: {e}")
        return []

# Load user agents
user_agents = load_user_agents('agents.txt')

# Function to send Telegram message
def send_telegram_message(price_difference, current_price):
    """Send a price alert to the Telegram group"""
    try:
        formatted_price_difference = f"{price_difference:.4f}"
        formatted_current_price = f"{current_price:.4f}"
        message_text = f"Price Alert: The price changed by {formatted_price_difference}. Current Price: {formatted_current_price}"

        send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': GROUP_CHAT_ID,
            'text': message_text
        }

        response = requests.post(send_url, data=payload)
        if response.status_code == 200:
            print("Price alert sent to Telegram group successfully.")
        else:
            print(f"Failed to send alert. Status code: {response.status_code}, Response: {response.text}")
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

# Function to get the crypto price
def get_crypto_price(url):
    """Uses Selenium to get the crypto price from the provided URL."""
    try:
        chrome_options = webdriver.ChromeOptions()
        user_agent = random.choice(user_agents)
        chrome_options.add_argument(f"user-agent={user_agent}")

        # Add headless option
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")  # Applicable to Windows OS
        chrome_options.add_argument("--no-sandbox")    # Bypass OS security model
        chrome_options.add_argument("--window-size=1920x1080")  # Set a window size

        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)

        WebDriverWait(driver, 3).until(
            EC.visibility_of_element_located((By.XPATH,
                                              "/html/body/uni-app/uni-page/uni-page-wrapper/uni-page-body/uni-view/uni-view[1]/uni-view/uni-view[3]/uni-shadow-root/uni-view/uni-view/uni-view/uni-shadow-root[2]/uni-view/uni-view/uni-view/uni-navigator[14]/uni-view[3]/uni-view"))
        )

        price_element = driver.find_element(By.XPATH,
                                            "/html/body/uni-app/uni-page/uni-page-wrapper/uni-page-body/uni-view/uni-view[1]/uni-view/uni-view[3]/uni-shadow-root/uni-view/uni-view/uni-view/uni-shadow-root[2]/uni-view/uni-view/uni-view/uni-navigator[14]/uni-view[3]/uni-view")
        price_text = price_element.text.strip()
        price = float(price_text)

        driver.quit()
        return price, user_agent

    except Exception as e:
        print(f"Error retrieving crypto price: {e}")
        driver.quit()
        return None, None

# Function to save data to Google Sheets
def save_to_google_sheets(data):
    sheet.append_row(data)

# Function to calculate price volatility and yield
def calculate_volatility_and_yield(last_price, current_price, multiplier=200):
    if last_price is None:
        return None, None

    price_volatility = abs(((current_price - last_price) / last_price) * 100)
    yield_percentage = price_volatility * multiplier
    return price_volatility, yield_percentage

def monitor_price_until_threshold():
    url = "https://wap.coxobtc.com"
    csv_file = "crypto_prices.csv"
    price_data = []
    last_price = None
    consecutive_alerts = 0
    failure_count = 0

    # Session and cooldown duration
    session_duration = 45 * 60
    cooldown_duration = 15 * 60
    start_time = time.time()

    try:
        while True:
            current_time = time.time()
            elapsed_time = current_time - start_time

            if elapsed_time < session_duration:
                current_price, used_user_agent = get_crypto_price(url)

                if current_price is not None:
                    failure_count = 0
                    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    price_difference = None
                    price_volatility = None
                    yield_percentage = None

                    if last_price is not None:
                        price_difference = current_price - last_price
                        price_volatility, yield_percentage = calculate_volatility_and_yield(last_price, current_price)

                    row_data = [current_time_str, current_price, price_difference, price_volatility, yield_percentage]
                    save_to_google_sheets(row_data)
                    price_data.append({
                        'time': current_time_str, 'price': current_price,
                        'price_difference': price_difference, 'price_volatility': price_volatility,
                        'yield_percentage': yield_percentage
                    })

                    df = pd.DataFrame(price_data)
                    df.to_csv(csv_file, index=False)

                    if price_difference is not None and abs(price_difference) >= 0.044:
                        send_telegram_message(round(price_difference, 4), round(current_price, 4))
                        consecutive_alerts += 1
                        print(f"Alert sent! Consecutive Alerts: {consecutive_alerts}")
                    else:
                        consecutive_alerts = 0

                    if consecutive_alerts >= 3:
                        print("Three consecutive alerts sent. Stopping monitoring.")
                        break

                    last_price = current_price
                else:
                    failure_count += 1
                    print("Failed to retrieve price. Failure count:", failure_count)

                    if failure_count >= 5:
                        print("Exceeded maximum failure attempts. Stopping monitoring.")
                        break

                time.sleep(random.uniform(50, 70))

            else:
                print("Cooldown period starting...")
                time.sleep(cooldown_duration)
                print("Cooldown period ended. Resuming price monitoring...")
                start_time = time.time()

    finally:
        print("Monitoring stopped.")

# Start monitoring
monitor_price_until_threshold()
