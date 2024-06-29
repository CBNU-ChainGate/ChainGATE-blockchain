import requests
from OpenSSL import crypto
from config import CA_ADDRESS

def revoke_certificate(cert_pem):
    url = f'http://{CA_ADDRESS}/api/v1/cert/revoke'

    data = {'cert': cert_pem}
    response = requests.post(url, json=data)

    if response.status_code == 200:
        print('Certificate successfully revoked.')
        print(response.json())
    else:
        print('Failed to revoke certificate.')
        print(response.status_code, response.text)

if __name__ == '__main__':
    # 테스트할 인증서 파일 경로
    cert_path = '/home/node1/certs/node_cert.pem'

    # 인증서 파일을 읽어서 PEM 형식으로 가져옴
    with open(cert_path, 'r') as f:
        cert_pem = f.read()

    # 인증서 파기 요청 보내기
    revoke_certificate(cert_pem)

