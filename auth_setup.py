import os
import base64
import time
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these SCOPES, delete the file token.json.
SCOPES = ['https://mail.google.com/']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'


def authenticate_gmail():
    """
    Authenticates with Gmail API, either by loading existing credentials
    or by initiating a new OAuth 2.0 flow.
    Saves new or refreshed credentials to token.json.
    """
    creds = None
    # Check if token.json exists and load credentials from it
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    # If no credentials or credentials are invalid/expired, refresh or initiate new flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh token if expired
            creds.refresh(Request())
        else:
            # Initiate new OAuth 2.0 flow for authorization
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the updated credentials to token.json
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return creds

def get_service():
    """
    Authenticates and builds the Gmail API service.
    """
    creds = authenticate_gmail()
    # Build the Gmail service client
    service = build('gmail', 'v1', credentials=creds)
    return service

def get_latest_email(service, user_id='me'):
    """
    Retrieves the latest unread email from the user's inbox.
    Args:
        service: The authenticated Gmail API service object.
        user_id: The user's Gmail ID, typically 'me' for the authenticated user.
    Returns:
        The latest message object, or None if no unread messages are found.
    """
    # List unread messages in the INBOX, limit to 1 result
    results = service.users().messages().list(userId=user_id, labelIds=['INBOX'], q='is:unread', maxResults=1).execute()
    messages = results.get('messages', [])
    
    if not messages:
        return None
    
    # Get the ID of the latest message
    msg_id = messages[0]['id']
    # Retrieve the full message details
    msg = service.users().messages().get(userId=user_id, id=msg_id, format='full').execute()
    return msg

def send_reply(service, original_msg, reply_text, user_id='me'):
    """
    Sends a reply to an original email, maintaining the thread.
    Args:
        service: The authenticated Gmail API service object.
        original_msg: The full message object of the email to which to reply.
        reply_text: The content of the reply message.
        user_id: The user's Gmail ID, typically 'me'.
    Returns:
        The sent message object.
    """
    # Extract headers from the original message payload
    # Pylance might infer 'Unknown' for headers, but we'll handle values carefully.
    headers: dict[str, str] = {h['name']: h['value'] for h in original_msg['payload']['headers']}

    # Safely get header values, providing default empty strings to satisfy type checkers
    # and prevent NoneType errors if headers are missing.
    to = headers.get('From', '') # Original error line 51 resolved by providing default ''
    subject = headers.get('Subject', '(no subject)')
    message_id = headers.get('Message-ID', '') # Original error line 54 resolved by providing default ''
    
    thread_id = original_msg['threadId']

    # Create the MIMEText object for the reply
    reply = MIMEText(reply_text)
    reply['To'] = to
    reply['Subject'] = 'Re: ' + subject
    reply['In-Reply-To'] = message_id
    reply['References'] = message_id # Original error line 53 implicitly resolved by message_id fix
    
    # Encode the message into a URL-safe base64 string
    raw = base64.urlsafe_b64encode(reply.as_bytes()).decode()
    
    # Prepare the message body for sending
    body = {'raw': raw, 'threadId': thread_id}
    
    # Send the reply message
    sent = service.users().messages().send(userId=user_id, body=body).execute()
    return sent

def delete_email(service, msg_id, user_id='me'):
    """
    Deletes a specified email message.
    Args:
        service: The authenticated Gmail API service object.
        msg_id: The ID of the message to delete.
        user_id: The user's Gmail ID, typically 'me'.
    """
    service.users().messages().delete(userId=user_id, id=msg_id).execute()

def main():
    """
    Main function to authenticate, check for latest unread email,
    send a reply, and delete the original email.
    """
    print('Authenticating and connecting to Gmail...')
    service = get_service()
    print('Checking for new emails...')
    
    # Get the latest unread email
    msg = get_latest_email(service)
    
    if not msg:
        print('No unread emails found. Please send an email to yourself and rerun this script.')
        return
    
    # Identify the sender of the processed email
    sender = next((h['value'] for h in msg['payload']['headers'] if h['name'] == 'From'), 'Unknown Sender')
    print('Processing email from:', sender)
    
    reply_text = 'Aura received your message and this is an automated confirmation reply.'
    
    # Send the automated reply
    send_reply(service, msg, reply_text)
    print('Reply sent. Deleting original email...')
    
    # Delete the original email
    delete_email(service, msg['id'])
    print('Original email deleted. Phase 0 complete.')

if __name__ == '__main__':
    main()
