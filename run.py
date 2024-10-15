import imaplib
import email
from email.header import decode_header
import re
import os
import tempfile
import asyncio
import time
from pyppeteer import launch
from google.cloud import storage

async def main():
    # Email login credentials
    username = 'brian@nmdemocrats.org'
    app_password = os.getenv('GMAIL_PASS')

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
        latest_email_id = email_ids[-1]
        print(f"Found {len(email_ids)} emails matching the search.")
    else:
        print("No emails found with the given phrase.")
        exit()

    print(f"Processing email ID: {latest_email_id}")

    # Fetch the email content using the latest email ID
    status, msg_data = mail.fetch(latest_email_id, '(RFC822)')

    # Parse the email content
    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        email_body = part.get_payload(decode=True).decode()
            else:
                email_body = msg.get_payload(decode=True).decode()

    link_match = re.search(r'(https://[^\s<]+)', email_body)
    if link_match:
        absentee_voting_link = link_match.group(1)
        print(f"Found link: {absentee_voting_link}")
    else:
        print("No link found in the email.")
        exit()

    # Create a temporary directory for downloads
    temp_dir = tempfile.mkdtemp()
    print(f"Using temporary directory: {temp_dir}")

    # Set up Pyppeteer browser
    browser = await launch(headless=True)
    page = await browser.newPage()

    # Set download behavior
    await page._client.send('Page.setDownloadBehavior', {
        'behavior': 'allow',
        'downloadPath': temp_dir,
    })

    # Navigate to the absentee voting link
    await page.goto(absentee_voting_link)

    # Wait for the email input box to appear
    email_input_locator = 'input[name="ctl00$MainContent$txtEmail"]'
    await page.waitForSelector(email_input_locator)

    # Enter email address
    await page.type(email_input_locator, 'brian@nmdemocrats.org')

    # Submit the form
    await page.click('input[type="submit"]')

    # Wait for a moment to ensure submission is processed
    await page.waitForTimeout(5000)

    # Check for file download
    downloaded_file_path = ""
    timeout = 120  # Timeout after 120 seconds
    start_time = time.time()

    while time.time() - start_time < timeout:
        files = os.listdir(temp_dir)
        for file in files:
            if file.endswith(".csv"):
                downloaded_file_path = os.path.join(temp_dir, file)
                break
        if downloaded_file_path:
            break
        await asyncio.sleep(2)  # Wait before checking again

    if not downloaded_file_path:
        print("File did not download within the timeout period.")
        await browser.close()
        exit()

    # Upload to Google Cloud Storage
    bucket_name = 'demsnmsp-uploads'
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    # Upload the file to GCP
    blob = bucket.blob(os.path.basename(downloaded_file_path))
    blob.upload_from_filename(downloaded_file_path)
    print("File uploaded to GCP successfully.")

    # Close the browser
    await browser.close()

# Run the main function
asyncio.run(main())
