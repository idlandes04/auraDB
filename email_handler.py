# Handles all Gmail API interactions
import base64
from googleapiclient.errors import HttpError
from auth_setup import get_service

def get_latest_email_body():
    """
    Fetches the body of the latest unread email.
    Returns the email body as a string, or None if no unread email is found.
    """
    try:
        service = get_service()
        # List unread messages in the INBOX, limit to 1 result
        results = service.users().messages().list(userId='me', labelIds=['INBOX'], q='is:unread', maxResults=1).execute()
        messages = results.get('messages', [])

        if not messages:
            print('No unread emails found.')
            return None

        msg_id = messages[0]['id']
        msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()

        # Extract sender and subject for context
        headers = {h['name']: h['value'] for h in msg['payload']['headers']}
        sender = headers.get('From', 'Unknown Sender')
        subject = headers.get('Subject', '(no subject)')
        print(f"Processing email from: {sender}\nSubject: {subject}")

        # Extract body (plain text preferred)
        body = ""
        if 'parts' in msg['payload']:
            for part in msg['payload']['parts']:
                if part.get('mimeType') == 'text/plain':
                    data = part['body'].get('data')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8')
                        break
        # Fallback if no plain text part is found
        if not body:
            data = msg['payload']['body'].get('data')
            if data:
                body = base64.urlsafe_b64decode(data).decode('utf-8')

        # Mark as read so it isn't processed again
        service.users().messages().modify(userId='me', id=msg_id, body={'removeLabelIds': ['UNREAD']}).execute()
        print("Email marked as read.")

        return body.strip()

    except HttpError as error:
        print(f'Gmail API error: {error}')
        return None
    except Exception as e:
        print(f'Error fetching email: {e}')
        return None