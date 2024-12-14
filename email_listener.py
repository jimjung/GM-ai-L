import os.path
import threading
import time
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

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
                        email_data = {
                            "From": self.get_header(msg, 'From'),
                            "Subject": self.get_header(msg, 'Subject'),
                            "Snippet": msg.get('snippet'),
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
