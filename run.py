import imaplib
import email
from email.header import decode_header
import os
import re
import requests
import zipfile
import time
import glob
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from google.cloud import storage

# Email login credentials
username = 'brian@nmdemocrats.org'
app_password = os.environ.get('GMAIL_PASS')

# Connect to Gmail's IMAP server
mail = imaplib.IMAP4_SSL('imap.gmail.com')
mail.login(username, app_password)

# Select the mailbox you want to search (e.g., inbox)
mail.select('inbox')

# Search for emails containing the specific phrase in the body
status, messages = mail.search(None, 'BODY "Below is a link to the daily absentee voting list."')

# Get the list of email IDs
email_ids = messages[0].split()

# If emails are found, process the latest one
if email_ids:
    latest_email_id = email_ids[-1]  # Get the most recent email
    print(f"Found {len(email_ids)} emails matching the search.")
else:
    print("No emails found with the given phrase.")
    exit()

print(latest_email_id)

# Fetch the email content using the latest email ID
status, msg_data = mail.fetch(latest_email_id, '(RFC822)')

# Parse the email content
for response_part in msg_data:
    if isinstance(response_part, tuple):
        msg = email.message_from_bytes(response_part[1])

        # Check if the email is multipart (i.e., contains text and HTML)
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    # Decode and extract the email body
                    email_body = part.get_payload(decode=True).decode()
        else:
            # If it's not multipart, it's likely plain text
            email_body = msg.get_payload(decode=True).decode()

# Adjusted regular expression to stop at space, new line, or HTML tag
link_match = re.search(r'(https://[^\s<]+)', email_body)
if link_match:
    absentee_voting_link = link_match.group(1)
    print(f"Found link: {absentee_voting_link}")
else:
    print("No link found in the email.")
    exit()

# Download and unzip the Chrome headless shell
chrome_zip_url = 'https://storage.googleapis.com/demsnmsp-uploads/chrome-headless-shell-linux64.zip'
download_path = '/tmp/chrome-headless-shell-linux64.zip'
extract_path = '/tmp/chrome-headless-shell'

# Download the zip file from GCP
response = requests.get(chrome_zip_url)
with open(download_path, 'wb') as file:
    file.write(response.content)

# Unzip the file
with zipfile.ZipFile(download_path, 'r') as zip_ref:
    zip_ref.extractall(extract_path)

# Make the chrome-headless-shell executable
os.chmod(os.path.join(extract_path, 'chrome-headless-shell'), 0o755)

# Set up Chrome options
download_dir = r"/tmp/chrome-downloads"  # Temporary download path for CSV files
os.makedirs(download_dir, exist_ok=True)

chrome_options = Options()
chrome_options.binary_location = os.path.join(extract_path, 'chrome-headless-shell')  # Path to Chrome headless shell
chrome_options.add_experimental_option("prefs", {
    "download.default_directory": download_dir,  # Specify your download directory
    "download.prompt_for_download": False,       # Disable the download prompt
    "download.directory_upgrade": True,          # Allow the directory to be upgraded
    "safebrowsing.enabled": True                  # Enable safe browsing
})

# Set up the service for ChromeDriver
service = Service(os.path.join(extract_path, 'chrome-headless-shell'))  # Use the path to the headless shell

# Set up the browser with the specified options
driver = webdriver.Chrome(service=service, options=chrome_options)

# Open the link from the email
driver.get(absentee_voting_link)

# Give the page some time to load
time.sleep(3)

# Find the email input field
email_input = driver.find_element(By.NAME, "ctl00$MainContent$txtEmail")  # Use the correct name
email_input.send_keys("brian@nmdemocrats.org")
email_input.send_keys(Keys.RETURN)

# Wait for the file to download
downloaded_file_path = os.path.join(download_dir, "*.csv")  # Adjust this if needed
while True:
    time.sleep(1)  # Check every second
    files = glob.glob(downloaded_file_path)  # Get all CSV files in the download directory
    if files:
        # Check if any of the files are still downloading
        if not any(file.endswith('.crdownload') for file in files):
            break  # Exit the loop if no .crdownload files are found

# Close the browser
driver.quit()

# Initialize a storage client (uses default credentials from the environment)
client = storage.Client()

# Specify the bucket name and the destination path
bucket_name = 'demsnmsp-avev'
destination_folder = 'inbox/20241105_general/statewide/'

# Function to find the most recent file in the directory
def get_most_recent_file(folder_path):
    """Returns the most recent file in the specified folder."""
    list_of_files = glob.glob(os.path.join(folder_path, '*'))  # Get all files in the folder
    if not list_of_files:
        print("No files found in the directory.")
        return None
    most_recent_file = max(list_of_files, key=os.path.getmtime)  # Find the file with the latest modification time
    return most_recent_file

# Function to upload the file to GCP
def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the specified bucket."""
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)

    print(f"File {source_file_name} uploaded to {destination_blob_name}.")

# Get the most recent file from the download directory
most_recent_file = get_most_recent_file(download_dir)

# If a file is found, upload it
if most_recent_file:
    # Extract the filename to use in the destination path
    file_name = os.path.basename(most_recent_file)
    destination_blob_name = f"{destination_folder}{file_name}"

    # Upload the most recent file to GCP
    upload_blob(bucket_name, most_recent_file, destination_blob_name)
