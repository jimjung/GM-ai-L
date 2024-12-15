import threading
import time
import base64
from datetime import datetime
import os

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from pdfminer.high_level import extract_text
from io import BytesIO

# If modifying these scopes, delete the token.json file
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


class GmailReader(threading.Thread):
    def __init__(self, callback=None):
        threading.Thread.__init__(self)
        self.creds = None
        self.service = None
        self.callback = callback  # Function to process emails
        self.running = True  # Control the thread's execution
        self.processed_ids = set()  # Track processed emails

    def authenticate(self):
        # Load credentials from token.json or initiate new authorization flow
        if os.path.exists('token.json'):
            self.creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                self.creds = flow.run_local_server(port=0)
            # Save the credentials for future use
            with open('token.json', 'w') as token:
                token.write(self.creds.to_json())

    def run(self):
        self.authenticate()
        self.service = build('gmail', 'v1', credentials=self.creds)

        while self.running:
            self.fetch_new_emails()
            time.sleep(10)  # Wait 10 seconds before checking again

    def fetch_new_emails(self):
        try:
            # Get the user's messages
            results = self.service.users().messages().list(userId='me', maxResults=10).execute()
            messages = results.get('messages', [])

            if not messages:
                print("No new emails.")
            else:
                for message in messages:
                    if message['id'] not in self.processed_ids:
                        self.processed_ids.add(message['id'])
                        msg = self.service.users().messages().get(userId='me', id=message['id']).execute()

                        # Extract email details
                        timestamp_ms = int(msg.get('internalDate', 0))  # Get timestamp in milliseconds
                        email_body = self.get_email_body(msg)
                        parsed_attachments = self.parse_attachments(msg)  # Parse attachments
                        email_data = {
                            "From": self.get_header(msg, 'From'),
                            "Subject": self.get_header(msg, 'Subject'),
                            "Body": email_body,
                            "Timestamp": datetime.fromtimestamp(timestamp_ms / 1000.0).strftime('%Y-%m-%d %H:%M:%S'),
                            "ParsedAttachments": parsed_attachments,
                        }
                        print(f"New Email Received:\n{email_data}\n{'=' * 50}")

                        # Process the email using the callback function, if provided
                        if self.callback:
                            self.callback(email_data)

        except Exception as e:
            print(f"Error fetching emails: {e}")

    @staticmethod
    def get_header(msg, header_name):
        headers = msg['payload']['headers']
        for header in headers:
            if header['name'] == header_name:
                return header['value']
        return None

    @staticmethod
    def get_email_body(msg):
        """
        Extract the full email body from the message.
        Handles plain text and HTML content.
        """
        try:
            parts = msg['payload'].get('parts', [])
            body = None

            if not parts:  # If no 'parts', it's a single-part message
                body = msg['payload']['body'].get('data')
            else:  # Multi-part message
                for part in parts:
                    if part['mimeType'] == 'text/plain':  # Prefer plain text
                        body = part['body'].get('data')
                        break
                    elif part['mimeType'] == 'text/html':  # Fallback to HTML
                        body = part['body'].get('data')

            if body:
                # Decode the base64url-encoded body content
                decoded_body = base64.urlsafe_b64decode(body).decode('utf-8')
                # Replace carriage returns with newlines for better readability
                return decoded_body.replace("\r\n", "\n").strip()
            else:
                return "No body content available."

        except Exception as e:
            return f"Error extracting email body: {e}"

    def parse_attachments(self, msg):
        """
        Extract and parse attachments from the email message.
        Returns the parsed content of attachments.
        """
        parsed_attachments = []
        parts = msg['payload'].get('parts', [])
        for part in parts:
            if part.get('filename'):  # Check if the part has a filename (i.e., it's an attachment)
                attachment_id = part['body'].get('attachmentId')
                if attachment_id:
                    attachment = self.service.users().messages().attachments().get(
                        userId='me', messageId=msg['id'], id=attachment_id).execute()
                    data = attachment.get('data')

                    if data:
                        file_data = base64.urlsafe_b64decode(data)
                        # Parse PDFs with pdfminer
                        if part['mimeType'] == 'application/pdf':
                            try:
                                pdf_text = extract_text(BytesIO(file_data))
                                parsed_attachments.append({
                                    "filename": part['filename'],
                                    "content": pdf_text.strip()
                                })
                            except Exception as e:
                                parsed_attachments.append({
                                    "filename": part['filename'],
                                    "error": f"Error parsing PDF: {e}"
                                })
                        else:
                            parsed_attachments.append({
                                "filename": part['filename'],
                                "content": f"Unsupported file type: {part['mimeType']}"
                            })
        return parsed_attachments

    def stop(self):
        self.running = False


def process_email(email_data):
    """
    Callback function to process emails.
    Replace this with your email parsing logic.
    """
    print("Processing email:")
    print(email_data)
    # Add your parsing logic here, e.g., save to a database or analyze the content


def main():
    # Start GmailReader in a separate thread
    reader = GmailReader(callback=process_email)
    reader.start()

    print("Email listener started. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)  # Keep the main thread alive
    except KeyboardInterrupt:
        print("\nStopping email listener...")
        reader.stop()
        reader.join()


if __name__ == '__main__':
    main()
