import requests

node_cert_path = '/home/node2/certs/node_cert.pem'
with open(node_cert_path, 'r') as f:
    cert = f.read()
data = {'cert': cert}
response = requests.post('http://192.168.0.29/nodes/register', json=data)
print(response.json())
