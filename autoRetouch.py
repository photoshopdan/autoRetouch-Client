import os
import sys
import json
import http.client
import webbrowser
from time import sleep, time
from codecs import encode
import urllib.parse


class Config:
    def __init__(self, file):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                config_json = json.load(f)
        except FileNotFoundError:
            self.file = file
            self.user_name = None
            self.client_id = 'V8EkfbxtBi93cAySTVWAecEum4d6pt4J'
            self.organization_id = 'ad2b217b-d9d0-4cba-9123-2730860082bc'
            self.access_token = None
            self.access_expiry = None
            self.refresh_token = None
        else:
            self.file = file
            self.user_name = config_json['user_name']
            self.client_id = config_json['client_id']
            self.organization_id = config_json['organization_id']
            self.access_token = config_json['access_token']
            self.access_expiry = config_json['access_expiry']
            self.refresh_token = config_json['refresh_token']

    def save(self):
        config_json = {'user_name': self.user_name,
                       'client_id': self.client_id,
                       'organization_id': self.organization_id,
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
            config.access_expiry = int(time()
                                       + auth_response['expires_in']
                                       - 120)
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
        config.access_expiry = int(time()
                                   + response['expires_in']
                                   - 120)
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
    elif config.access_expiry < time():
        refresh_access_token(config)
        config.save()

def list_workflows(config):
    conn = http.client.HTTPSConnection('api.autoretouch.com')
    headers = {'User-Agent': config.user_name,
               'Authorization': f'Bearer {config.access_token}',
               'Content-Type': 'json'}
    conn.request('GET', '/v1/workflow', headers=headers)
    response = json.loads(conn.getresponse().read())

    return [(i['name'], i['id']) for i in response['entries']]

def choose_workflow(workflows):
    print('Please choose a workflow.\n')
    for w in workflows:
        print(f'{workflows.index(w) + 1}   {w[0]}')
    
    while True:
        choice = input('\nWorkflow number: ')
        try:
            choice = int(choice)
        except ValueError:
            print('\nInvalid input. Please try again.')
        else:
            if 0 < choice <= len(workflows):
                break
            else:
                print('\nInvalid input. Please try again.')

    return workflows[choice - 1][1]

def get_image_list(directories):
    images = []
    image_types = ('.jpg', '.jpeg', '.png')
    for d in directories:
        for root, dirs, files in os.walk(d):
            for file in files:
                _, ext = os.path.splitext(file)
                if ext.casefold() in image_types:
                    images.append(os.path.join(root, file))

    return images

def get_mimetype(file):
    _, ext = os.path.splitext(file)
    if ext.casefold() == '.png':
        return 'image/png'
    else:
        return 'image/jpeg'

def process_image(config, workflow, file):
    authorise_device(config)
    
    conn = http.client.HTTPSConnection('api.autoretouch.com')

    data = []
    boundary = 'wL36Yn8afVp8Ag7AmP8qZ0SA4n1v9T'
    data.append(encode('--' + boundary))
    data.append(encode('Content-Disposition: form-data; name=file; '
                       f'filename={os.path.basename(file)}'))
    data.append(encode(f'Content-Type: {get_mimetype(file)}'))
    data.append(encode(''))

    with open(file, 'rb') as f:
        data.append(f.read())

    data.append(encode('--' + boundary + '--'))
    data.append(encode(''))

    payload = b'\r\n'.join(data)
    headers = {'User-Agent': config.user_name,
               'Authorization': f'Bearer {config.access_token}',
               'Content-type': f'multipart/form-data; boundary={boundary}'}
    conn.request('POST',
                 ('/v1/workflow/execution/create'
                  f'?workflow={workflow}'
                  f'&organization={config.organization_id}'),
                 payload, headers)
    res = conn.getresponse()
    data = res.read()
    
    return data.decode('utf-8')

def get_execution_status(config, execution):
    authorise_device(config)
    
    conn = http.client.HTTPSConnection('api.autoretouch.com')
    headers = {'User-Agent': config.user_name,
               'Authorization': f'Bearer {config.access_token}',
               'Content-Type': 'json'}
    conn.request('GET',
                 (f'/v1/workflow/execution/{execution}'
                  f'?organization={config.organization_id}'),
                 headers=headers)
    
    response = json.loads(conn.getresponse().read())
    
    return (response['status'], response['resultPath'])

def download_image(config, result_path, file_path):
    authorise_device(config)
    
    conn = http.client.HTTPSConnection('api.autoretouch.com')
    formatted_result_path = urllib.parse.quote(result_path)
    url = f'/v1{formatted_result_path}?organization={config.organization_id}'
    headers = {'User-Agent': config.user_name,
               'Authorization': f'Bearer {config.access_token}'}
    conn.request('GET', url, headers=headers)
    
    response = conn.getresponse().read()

    output_dir = os.path.join(os.path.dirname(file_path), 'autoRetouch')
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    with open(os.path.join(output_dir, os.path.basename(result_path)),
              'wb') as f:
        f.write(response)

def main():
    # Obtain directory list and check it's not empty.
    directories = sys.argv[1:]
    if not directories:
        print('Please drag one or more folders onto the app.')
        sleep(2)
        return
    
    # Produce image file list, recursing through each directory.
    files = get_image_list(directories)
    if not files:
        print('No images detected.')
        sleep(2)
        return
    
    # Load config data and authorise device if necessary.
    config = Config('config.json')
    authorise_device(config)
    
    # Present workflows and ask the user to choose one.
    workflow = choose_workflow(list_workflows(config))

    # Execute workflow for each image.
    print('\n\nUploading images to be processed...')
    workflow_executions = []
    for f in files:
        workflow_executions.append((process_image(config, workflow, f), f))
        print(f'   {os.path.basename(f)} uploaded.')

    # Iterate over each execution, checking status.
    print('\nChecking for processed images...')
    failed_executions = []
    while workflow_executions:
        for w in workflow_executions:
            execution_status, execution_url = get_execution_status(config, w[0])
            if execution_status == 'COMPLETED':
                download_image(config, execution_url, w[1])
                print(f'   {os.path.basename(w[1])} downloaded.')
                workflow_executions.remove(w)
            elif any([execution_status == 'CREATED',
                      execution_status == 'ACTIVE']):
                continue
            else:
                failed_executions.append((os.path.basename(w[1]),
                                          execution_status))
                workflow_executions.remove(w)

    for f in failed_executions:
        print(f'   {f[0]} could not be processed. Status: {f[1]}')

    input('\nBatch complete. Press enter to quit.')
    
if __name__ == '__main__':
    main()
