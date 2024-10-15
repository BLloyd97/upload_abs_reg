import imaplib
import email
import re
import time
import tempfile
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from google.cloud import storage  # Import the Google Cloud Storage library

# Email login credentials
username = 'brian@nmdemocrats.org'
app_password = os.getenv('GMAIL_PASS')  # Change this to os.getenv('GMAIL_PASS') if using environmental variable

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
    exit()  # Exit if no emails found

print(f"Processing email ID: {latest_email_id}")

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
                    email_body = part.get_payload(decode=True).decode()
        else:
            email_body = msg.get_payload(decode=True).decode()

# Adjusted regular expression to stop at space, new line, or HTML tag
link_match = re.search(r'(https://[^\s<]+)', email_body)
if link_match:
    absentee_voting_link = link_match.group(1)
    print(f"Found link: {absentee_voting_link}")
else:
    print("No link found in the email.")
    exit()  # Exit if no link found

# Step 2: Use Selenium to follow the absentee voting link and submit your email
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))  # Ensure the correct ChromeDriver is used
driver.get(absentee_voting_link)

# Wait for the page to load completely
time.sleep(5)  # Adjust sleep time as necessary for your internet speed

# Find the email input box and submit the email address
email_input = driver.find_element(By.NAME, "ctl00$MainContent$txtEmail")
email_input.send_keys('brian@nmdemocrats.org')  # Enter your email address

# Submit the form
email_input.submit()  # Or find the submit button and click it

# Optional: Wait for a moment to ensure the submission is processed
time.sleep(5)

# Create a temporary directory for downloads
with tempfile.TemporaryDirectory() as temp_dir:
    print(f"Temporary download directory created at: {temp_dir}")

    # Check for the file download
    downloaded_file_path = ""
    timeout = 120  # Timeout after 60 seconds
    start_time = time.time()

    while time.time() - start_time < timeout:
        # Look for downloaded files in the temporary directory
        files = os.listdir(temp_dir)
        for file in files:
            if file.endswith(".csv"):  # Check for the expected file type (adjust if needed)
                downloaded_file_path = os.path.join(temp_dir, file)
                print(f"File downloaded: {downloaded_file_path}")
                break
        if downloaded_file_path:
            break
        time.sleep(2)  # Wait before checking again

    if not downloaded_file_path:
        print("File did not download within the timeout period.")
        driver.quit()
        exit()

    # Upload to Google Cloud Storage
    bucket_name = 'demsnmsp-uploads'  # Your GCP bucket name
    client = storage.Client()  # Create a GCP storage client
    bucket = client.bucket(bucket_name)

    # Upload the file to GCP
    blob = bucket.blob(os.path.basename(downloaded_file_path))  # Name the file as you want it in GCP
    blob.upload_from_filename(downloaded_file_path)
    print("File uploaded to GCP successfully.")

# Close the browser
driver.quit()
