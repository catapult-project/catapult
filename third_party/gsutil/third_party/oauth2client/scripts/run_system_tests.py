import json
import os

import httplib2
from oauth2client import client
from oauth2client import service_account


JSON_KEY_PATH = os.getenv('OAUTH2CLIENT_TEST_JSON_KEY_PATH')
P12_KEY_PATH = os.getenv('OAUTH2CLIENT_TEST_P12_KEY_PATH')
P12_KEY_EMAIL = os.getenv('OAUTH2CLIENT_TEST_P12_KEY_EMAIL')
USER_KEY_PATH = os.getenv('OAUTH2CLIENT_TEST_USER_KEY_PATH')
USER_KEY_EMAIL = os.getenv('OAUTH2CLIENT_TEST_USER_KEY_EMAIL')

SCOPE = ('https://www.googleapis.com/auth/plus.login',
         'https://www.googleapis.com/auth/plus.me',
         'https://www.googleapis.com/auth/userinfo.email',
         'https://www.googleapis.com/auth/userinfo.profile')
USER_INFO = 'https://www.googleapis.com/oauth2/v2/userinfo'


def _require_environ():
    if (JSON_KEY_PATH is None or P12_KEY_PATH is None or
        P12_KEY_EMAIL is None or USER_KEY_PATH is None or
        USER_KEY_EMAIL is None):
        raise EnvironmentError('Expected environment variables to be set:',
                               'OAUTH2CLIENT_TEST_JSON_KEY_PATH',
                               'OAUTH2CLIENT_TEST_P12_KEY_PATH',
                               'OAUTH2CLIENT_TEST_P12_KEY_EMAIL',
                               'OAUTH2CLIENT_TEST_USER_KEY_PATH',
                               'OAUTH2CLIENT_TEST_USER_KEY_EMAIL')

    if not os.path.isfile(JSON_KEY_PATH):
        raise EnvironmentError(JSON_KEY_PATH, 'is not a file')
    if not os.path.isfile(P12_KEY_PATH):
        raise EnvironmentError(P12_KEY_PATH, 'is not a file')
    if not os.path.isfile(USER_KEY_PATH):
        raise EnvironmentError(USER_KEY_PATH, 'is not a file')


def _check_user_info(credentials, expected_email):
    http = credentials.authorize(httplib2.Http())
    response, content = http.request(USER_INFO)
    if response.status != 200:
        raise ValueError('Expected 200 response.')

    content = content.decode('utf-8')
    payload = json.loads(content)
    if payload['email'] != expected_email:
        raise ValueError('User info email does not match credentials.')


def run_json():
    with open(JSON_KEY_PATH, 'r') as file_object:
        client_credentials = json.load(file_object)

    credentials = service_account._ServiceAccountCredentials(
        service_account_id=client_credentials['client_id'],
        service_account_email=client_credentials['client_email'],
        private_key_id=client_credentials['private_key_id'],
        private_key_pkcs8_text=client_credentials['private_key'],
        scopes=SCOPE,
    )

    _check_user_info(credentials, client_credentials['client_email'])


def run_p12():
    with open(P12_KEY_PATH, 'rb') as file_object:
        private_key_contents = file_object.read()

    credentials = client.SignedJwtAssertionCredentials(
        service_account_name=P12_KEY_EMAIL,
        private_key=private_key_contents,
        scope=SCOPE,
    )

    _check_user_info(credentials, P12_KEY_EMAIL)


def run_user_json():
    with open(USER_KEY_PATH, 'r') as file_object:
        client_credentials = json.load(file_object)

    credentials = client.GoogleCredentials(
        access_token=None,
        client_id=client_credentials['client_id'],
        client_secret=client_credentials['client_secret'],
        refresh_token=client_credentials['refresh_token'],
        token_expiry=None,
        token_uri=client.GOOGLE_TOKEN_URI,
        user_agent='Python client library',
    )

    _check_user_info(credentials, USER_KEY_EMAIL)


def main():
    _require_environ()
    run_json()
    run_p12()
    run_user_json()


if __name__ == '__main__':
    main()
