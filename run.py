#Configured only for jupiter. This worked. 

import imaplib
import email
from email.header import decode_header
import re
import requests
import os
import glob
from google.cloud import storage
import tempfile


# Email login credentials
username = 'brian@nmdemocrats.org'
app_password = 'oivb bzqb rtcx bbpz'  # Use your app-specific password

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

# Step 2: Submitting your email to the absentee voting link using requests

# Data to be sent (the email address field)
data = {
    'ctl00$MainContent$txtEmail': 'brian@nmdemocrats.org'
}

# Simulate the form submission to start the download
session = requests.Session()  # Use a session to persist cookies if needed
response = session.post(absentee_voting_link, data=data)

# Check if the request was successful and find the file to download
if response.status_code == 200:
    print("Successfully submitted the email.")
    # You can check the response headers to see if the file is being downloaded
    if 'Content-Disposition' in response.headers:
        # Extract the filename from the headers
        file_name = response.headers.get('Content-Disposition').split('filename=')[-1].strip('""')
        download_dir = tempfile.gettempdir()  # Use the system's temporary directory


        # Save the file
        file_path = os.path.join(download_dir, file_name)
        with open(file_path, 'wb') as file:
            file.write(response.content)
        print(f"File saved as {file_name}.")
else:
    print("Failed to submit the form or download the file.")

# Step 3: Upload the file to Google Cloud Storage

# # Path to your service account key JSON file
# service_account_key_path = r"C:\Users\brian\Documents\JSON_key_google_service_account\BigQuery_creds.json" # Update this with your path

# # Initialize a storage client with the service account key
# client = storage.Client.from_service_account_json(service_account_key_path)

# # Specify the bucket name and the destination path
# bucket_name = 'demsnmsp-avev'
# destination_folder = 'inbox/20241105_general/statewide/'

# # Path to the folder where your CSV files are saved
# csv_folder_path = r"C:\Users\brian\Documents\dpnm\AVEV\2024g"

# # Function to find the most recent file in the directory
# def get_most_recent_file(folder_path):
#     """Returns the most recent file in the specified folder."""
#     list_of_files = glob.glob(os.path.join(folder_path, '*'))  # Get all files in the folder
#     if not list_of_files:
#         print("No files found in the directory.")
#         return None
#     most_recent_file = max(list_of_files, key=os.path.getmtime)  # Find the file with the latest modification time
#     return most_recent_file

# # Function to upload the file to GCP
# def upload_blob(bucket_name, source_file_name, destination_blob_name):
#     """Uploads a file to the specified bucket."""
#     bucket = client.bucket(bucket_name)
#     blob = bucket.blob(destination_blob_name)
#     blob.upload_from_filename(source_file_name)

#     print(f"File {source_file_name} uploaded to {destination_blob_name}.")

# # Get the most recent file from the folder
# most_recent_file = get_most_recent_file(csv_folder_path)

# # If a file is found, upload it
# if most_recent_file:
#     # Extract the filename to use in the destination path
#     file_name = os.path.basename(most_recent_file)
#     destination_blob_name = f"{destination_folder}{file_name}"

#     # Upload the most recent file to GCP
#     upload_blob(bucket_name, most_recent_file, destination_blob_name)

import os
import glob
from google.cloud import storage

# Path to your service account key JSON file
service_account_key_path = r"C:\Users\brian\Documents\JSON_key_google_service_account\BigQuery_creds.json"  # Update this with your path

# Initialize a storage client with the service account key
client = storage.Client.from_service_account_json(service_account_key_path)

# Specify the bucket name (no folder)
bucket_name = 'demsnmsp-uploads'

# Path to the folder where your CSV files are saved
csv_folder_path = tempfile.gettempdir()  # Use the system's temporary directory


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

# Get the most recent file from the folder
most_recent_file = get_most_recent_file(csv_folder_path)

# If a file is found, upload it
if most_recent_file:
    # Extract the filename to use in the destination path
    file_name = os.path.basename(most_recent_file)
    destination_blob_name = file_name  # Upload directly to the bucket, no folder

    # Upload the most recent file to GCP
    upload_blob(bucket_name, most_recent_file, destination_blob_name)

