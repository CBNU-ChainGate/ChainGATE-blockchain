# ChainGATE

블록체인을 이용한 출입관리시스템\_충북대학교 졸업작품

# 1. Blockchain API GUIDE

### 1-1. nodes/register [POST]

    { "cert": cert }

|  Key   |         Value         |   Type    |
| :----: | :-------------------: | :-------: |
| "cert" | CA를 통해 받은 인증서 | .pem 파일 |

.

**❗각 노드에서 register.py를 별도로 실행**

_register.py_

```
### at 192.168.0.29 노드 ###
import requests

nodes = ['192.168.0.28', '192.168.0.31'] # 다른 노드에 등록을 원한다고 요청
node_cert_path = '/node/certs/path'
with open(node_cert_path, 'r') as f:
    cert = f.read()
data = {'cert': cert} # 등록할 노드의 인증서를 요청 데이터로 전송

for node in nodes:
    response = requests.post(f'http://{node}/nodes/register', json=data)
    print(f'{node}: ', end='')
    print(response.json())
```

### 1-2. transaction/new [POST]

    {
        "date": "2024-04-12",
        "time": "10:30:00",
        "name": "홍길동",
        "position": "팀원",
        "department": "개발부"
    }

|     Key      |    Value    |        Type         |
| :----------: | :---------: | :-----------------: |
|    "date"    |  출입날짜   | String [YYYY-MM-DD] |
|    "time"    |  출입시간   |  String [HH:MM:SS]  |
|    "name"    | 출입자 이름 |       String        |
|  "position"  | 출입자 직급 |       String        |
| "department" | 출입자 소속 |       String        |

### 1-3. chain/search [POST]

    {
        "date": "2024-04-12",
        "name": "",
        "department": "개발부"
    }

|     Key      |    Value    |           Type            |
| :----------: | :---------: | :-----------------------: |
|    "date"    |  출입날짜   | String [YYYY-MM-DD] OR "" |
|    "name"    | 출입자 이름 |       String OR ""        |
| "department" | 출입자 소속 |       String OR ""        |

**❗ 데이터가 없을 경우, _Value=""_ (최소 1개 이상의 데이터는 있어야 됨).**
