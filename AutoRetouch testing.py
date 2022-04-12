import json
import http.client
import webbrowser
from time import sleep, time
import os


class Config:
    def __init__(self, file):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                config_json = json.load(f)
        except FileNotFoundError:
            self.file = file
            self.user_name = None
            self.client_id = 'V8EkfbxtBi93cAySTVWAecEum4d6pt4J'
            self.access_token = None
            self.access_expiry = None
            self.refresh_token = None
        else:
            self.file = file
            self.user_name = config_json['user_name']
            self.client_id = config_json['client_id']
            self.access_token = config_json['access_token']
            self.access_expiry = config_json['access_expiry']
            self.refresh_token = config_json['refresh_token']

    def save(self):
        config_json = {'user_name': self.user_name,
                       'client_id': self.client_id,
                       'access_token': self.access_token,
                       'access_expiry': self.access_expiry,
                       'refresh_token': self.refresh_token}
        with open(self.file, 'w', encoding='utf-8') as f:
            json.dump(config_json, f, ensure_ascii=False, indent=4)


def get_device_code(config):
    conn = http.client.HTTPSConnection('auth.autoretouch.com')
    payload = (f'client_id={config.client_id}'
               '&scope=offline_access'
               '&audience=https://api.autoretouch.com')
    headers = {'User-Agent': config.user_name,
               'Content-Type': 'application/x-www-form-urlencoded'}
    conn.request('POST', '/oauth/device/code', payload, headers)

    res = conn.getresponse()
    if any([res.status == 200,
            res.status == 201]):
        return json.loads(res.read())
    else:
        raise RuntimeError('Error getting device code response.')
    
def get_access_tokens(config, response):
    print(f'Confirm the user code {response["user_code"]} in your browser...')
    sleep(2)
    try:
        webbrowser.open(response['verification_uri_complete'])
    except:
        raise RuntimeError('Failed to open web browser')

    seconds_waited = 0
    while seconds_waited < response['expires_in']:
        conn = http.client.HTTPSConnection('auth.autoretouch.com')
        payload = ('grant_type=urn:ietf:params:oauth:grant-type:device_code'
                   f'&device_code={response["device_code"]}'
                   f'&client_id={config.client_id}')
        headers = {'User-Agent': config.user_name,
                   'Content-Type': 'application/x-www-form-urlencoded'}
        conn.request('POST', '/oauth/token', payload, headers)
        
        res = conn.getresponse()
        if any([res.status == 200,
                res.status == 201]):
            auth_response = json.loads(res.read())
            config.access_token = auth_response['access_token']
            config.access_expiry = int(time() + auth_response['expires_in'])
            config.refresh_token = auth_response['refresh_token']
            return

        seconds_waited += response['interval']
        sleep(response['interval'])

    raise RuntimeError(f'Device Code not confirmed after {seconds_waited} '
                       'seconds.')

def refresh_access_token(config):
    conn = http.client.HTTPSConnection('auth.autoretouch.com')
    payload = ('grant_type=refresh_token'
               f'&refresh_token={config.refresh_token}'
               f'&client_id={config.client_id}')
    headers = {'User-Agent': config.user_name,
               'Content-Type': 'application/x-www-form-urlencoded'}
    conn.request('POST', '/oauth/token', payload, headers)
    
    res = conn.getresponse()
    if any([res.status == 200,
            res.status == 201]):
        response = json.loads(res.read())
        config.access_token = response['access_token']
        config.access_expiry = int(time() + response['expires_in'])
    else:
        raise RuntimeError('Error refreshing access code.')
    
def authorise_device(config):
    if config.access_token == None:
        print('Performing first-time setup.')
        config.user_name = os.environ['COMPUTERNAME']
        device_code_response = get_device_code(config)
        get_access_tokens(config, device_code_response)
        config.save()
        print('Setup complete.\n')
    elif config.access_expiry - 120 < time():
        refresh_access_token(config)
        config.save()

def main():
    # Load config data.
    config = Config('config.json')
    authorise_device(config)
    

if __name__ == '__main__':
    main()

'''

Send Client ID > Recieve Device code > [Refresh Token if past expiry]
> Recieve Access Token
Store Access Token as environment variable or in config.xml.

Get workflow list > if desired workflow gone, ask user for workflow
name. If it exists, save as default in config.xml.

Image upload > Recieve image hash.

Create a workflow execution with previously uploaded image.

Workflow execution status.

Download workflow execution result image.

Place in folder like in autocrop.



'''


'''

What's the difference between a workflow and a workflow execution?
What's a batch?

'''
