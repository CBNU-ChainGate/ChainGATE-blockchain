import requests
from config import CA_ADDRESS

url = f'http://{CA_ADDRESS}/api/v1/cert/verify'
cert_path = '/home/node1/certs/node_cert.pem'

with open(cert_path, 'r') as f:
    cert = f.read()

data = {'cert': cert}
response = requests.post(url, json=data)
print(response.json())

