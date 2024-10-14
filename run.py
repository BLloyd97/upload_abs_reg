import imaplib
import email
from email.header import decode_header
import os
import re
import requests
import tempfile
import glob
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

# Create a temporary directory (works in a virtual environment like Linux or cloud platforms)
download_dir = tempfile.mkdtemp()  # Creates a unique temporary directory
csv_file_path = os.path.join(download_dir, "absentee_voting.csv")

# Download the CSV file from the absentee voting link and save to the temporary directory
csv_response = requests.get(absentee_voting_link)

with open(csv_file_path, 'wb') as file:
    file.write(csv_response.content)

print(f"Downloaded file saved to: {csv_file_path}")

# Initialize a storage client (uses default credentials from the environment)
client = storage.Client()

# Specify the bucket name (no folder needed)
bucket_name = 'demsnmsp-uploads'

# Function to upload the file to GCP
def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the specified bucket."""
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)

    print(f"File {source_file_name} uploaded to {destination_blob_name}.")

# Extract the filename
file_name = os.path.basename(csv_file_path)

# Upload the CSV file to GCP (directly into the bucket, no folder)
upload_blob(bucket_name, csv_file_path, file_name)

# Optionally, remove the temporary directory after uploading the file
# This helps clean up after the process completes
os.remove(csv_file_path)
os.rmdir(download_dir)
