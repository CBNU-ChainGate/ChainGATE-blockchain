# 베이스 이미지 선택
FROM ubuntu:latest

# SSH 서버 설치
RUN apt-get update && \
    apt-get install -y openssh-server && \
    mkdir /var/run/sshd && \
    echo 'root:root' | chpasswd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/UsePAM yes/UsePAM no/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Flask 설치를 위한 Python 및 pip 설치
RUN apt-get install -y python3 python3-pip

# Flask 설치
RUN pip3 install flask

# SSH 포트 열기
EXPOSE 22
EXPOSE 5000

# Flask 애플리케이션을 위한 디렉토리 생성 및 파일 복사
WORKDIR /app
COPY blockAPI.py /app
COPY blockchain.py /app

# SSH 서버 시작 및 Flask 애플리케이션 실행
CMD ["/usr/sbin/sshd", "-D"]
