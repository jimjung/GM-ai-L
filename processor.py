import openai
import supabase
from email_listener import GmailReader
from datetime import datetime
import json
import yaml

# Load API key from credentials.yaml
def load_from_yaml(key):
    with open("credentials.yaml", "r") as file:
        credentials = yaml.safe_load(file)
        return credentials.get(key)

# Set the OpenAI API key
openai.api_key = load_from_yaml("openai")
# Supabase setup
SUPABASE_URL = load_from_yaml("supabase_url")
SUPABASE_KEY = load_from_yaml("supabase_key")
supa_client = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)

def save_to_supabase(email_data, parsed_data):
    """Save parsed email content to Supabase."""
    try:
        # Format timestamp into ISO 8601 format for consistency
        timestamp = email_data.get("Timestamp")
        if timestamp:
            timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").isoformat()

        # Insert email data into Supabase
        response = supa_client.table("inbox").insert({
            "timestamp": timestamp,
            "address": email_data['From'],
            "subject": email_data['Subject'],
            "message": email_data['Body'],
            "category": parsed_data.get("category"),
            "priority": parsed_data.get("priority"),
            "customer_name": parsed_data.get("customer_name"),
            "action_required": parsed_data.get("action_required", False),
            "notes": parsed_data.get("notes")
        }).execute()
        
        if response.data:
            print("Email saved to Supabase successfully.")
        else:
            print("Failed to save email to Supabase:", response.error)
    except Exception as e:
        print(f"Error saving to Supabase: {e}")


def extract_important_content(email_text):
    """
    Use OpenAI API to parse important content from the email.
    Enforce a structured response to ensure consistency.
    """
    try:
        # Define the system message with explicit formatting instructions
        system_message = ("""
You are a data extraction assistant. Parse the following email text 
and provide the output in the following consistent JSON format: 
{
    "category": "string",
    "priority": "string",
    "customer_name": "string",
    "action_required": true/false,
    "notes": "string"
}. 
If any fields cannot be extracted, set their value to null. 
Note that priority must fall into the buckets of Low, Medium, High, Critical, and cannot be null.
Ensure the output is valid JSON.
""")

        # Send the prompt to OpenAI
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": email_text}
            ]
        )
        
        # Correctly access the message content
        msg = response.choices[0].message.content
        
        try:
            # Directly parse the JSON 
            parsed_data = json.loads(msg)
            
            # Validate required keys
            expected_keys = {"category", "priority", "customer_name", "action_required", "notes"}
            for key in expected_keys:
                if key not in parsed_data:
                    parsed_data[key] = None 

            return parsed_data
        except json.JSONDecodeError as parse_error:
            print(f"Error parsing AI response: {parse_error}")
            return {
                "category": None,
                "priority": None,
                "customer_name": None,
                "action_required": None,
                "notes": None,
            }

    except Exception as e:
        print(f"Error using OpenAI API: {e}")
        return {
            "category": None,
            "priority": None,
            "customer_name": None,
            "action_required": None,
            "notes": None,
        }



def filter_clients(email_data, client_list):
    """Check if the sender is in the client list."""
    sender = email_data['From']
    return any(client_email in sender for client_email in client_list)

def process_email(email_data):
    """Callback function to process emails."""
    # Define a list of client email addresses
    client_list = ["paulsfoodservice@gmail.com", "00mr.he@gmail.com", "benalonso69@gmail.com", "thomashackathon815@gmail.com"]

    if filter_clients(email_data, client_list):
        print("Processing email from a client:")
        print(email_data)

        # Extract detailed content using OpenAI API
        email_text = f"Subject: {email_data['Subject']}\Body: {email_data['Body']}"
        parsed_data = extract_important_content(email_text)

        # Save the processed content to Supabase
        save_to_supabase(email_data, parsed_data)

        print(f"Parsed data saved: {parsed_data}")
    else:
        print("Email not from a client, ignoring.")

def main():
    # Start GmailReader with the custom email processing callback
    reader = GmailReader(callback=process_email)
    reader.start()

    print("Email listener started. Press Ctrl+C to stop.")
    try:
        while True:
            pass  # Keep the main thread alive
    except KeyboardInterrupt:
        print("\nStopping email listener...")
        reader.stop()
        reader.join()

if __name__ == '__main__':
    main()
