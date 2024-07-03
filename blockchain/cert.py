import requests
from config import CSR_URL, CSR_PATH, NODE_CERT_PATH, VERIFY_URL, REVOKE_URL


class Cert:
    def __init__(self):
        self.cert = None
        self.csr_cert()

    def csr_cert(self):
        with open(CSR_PATH, 'r') as f:
            csr = f.read()

        data = {'csr': csr}
        response = requests.post(CSR_URL, json=data)

        if response.status_code == 200:
            # 인증서 추출(json)
            cert_pem = response.json().get('certificate')

            # 추출한 인증서 저장
            with open(NODE_CERT_PATH, 'w') as cert_file:
                cert_file.write(cert_pem)
            # 인증서 불러와서 변수에 저장
            with open(NODE_CERT_PATH, 'r') as f:
                self.cert = f.read()
            print(f"Certificate saved to {NODE_CERT_PATH}")
        else:
            print(f"Failed to request certificate: {response.text}")

    def verify_cert(self, cert_pem):
        response = requests.post(VERIFY_URL, json=cert_pem)

        if response.status_code == 200:
            print('Certificate successfully verified.')
            print(response.json())
            return True
        else:
            print('Failed to verify certificate.')
            print(response.status_code, response.text)
            return False

    def revoke_cert(self):
        data = {'cert': self.cert}
        response = requests.post(REVOKE_URL, json=data)

        if response.status_code == 200:
            print('Certificate successfully revoked.')
            print(response.json())
        else:
            print('Failed to revoke certificate.')
            print(response.status_code, response.text)
