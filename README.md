# ChainGATE

블록체인을 이용한 출입관리시스템\_충북대학교 졸업작품

# Blockchain API GUIDE

### 1. nodes/register [POST]

    {
        "nodes": ["192.168.0.28", "192.168.0.31"]
    }

|   Key   |   Value   | Type |
| :-----: | :-------: | :--: |
| "nodes" | Node의 IP | List |

### 2. transaction/new [POST]

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

### 3. chain/search [POST]

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
