import requests
from config import CA_ADDRESS, CSR_URL, CSR_PATH, NODE_CERT_PATH 

with open(CSR_PATH, 'r') as f:
    csr = f.read()

data = {'csr': csr}
response = requests.post(CSR_URL, json=data)

# Check if request was successful
if response.status_code == 200:
    # Extract certificate from JSON response
    cert_pem = response.json().get('certificate')

    # Save certificate to file
    with open(NODE_CERT_PATH, 'w') as cert_file:
        cert_file.write(cert_pem)

    print(f"Certificate saved to {NODE_CERT_PATH}")
else:
    print(f"Failed to request certificate: {response.text}")
