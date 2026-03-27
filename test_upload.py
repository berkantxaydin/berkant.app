import requests

# 1. Get presigned URL
print('Getting presigned URL...')
resp = requests.get('http://127.0.0.1:5000/api/jam/get_upload_url?filename=test/index.html&content_type=text/html')
if resp.status_code != 200:
    print('Failed to get url:', resp.text)
    exit(1)

data = resp.json()
url = data['url']
if 'mock-endpoint' in url:
    url = 'http://127.0.0.1:5000/api/jam/mock_upload'

# 2. Upload file
print('Uploading ' + url)
files = {'file': ('index.html', b'<h1>Hello Game</h1>', 'text/html')}
# Important: when passing fields as data, requests uses multipart/form-data
post_resp = requests.post(url, data=data['fields'], files=files)

print('Upload status:', post_resp.status_code)
print('Upload response:', post_resp.text)
