# 베이스 이미지를 설정합니다. Python 3.9 이미지를 사용합니다.
FROM python:3.9

# 환경 변수를 설정합니다.
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# 패키지를 설치합니다. 여기서는 openssh-server를 설치합니다.
RUN apt-get update && \
    apt-get install -y openssh-server && \
    apt-get clean

# SSH 서버를 설정합니다..
RUN mkdir /var/run/sshd
RUN echo 'root:root' | chpasswd
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN sed -i 's/UsePAM yes/UsePAM no/' /etc/ssh/sshd_config
RUN sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Flask 애플리케이션을 위한 작업 디렉토리를 설정합니다.
WORKDIR /app

# 필요한 파일을 복사합니다.
COPY blockchain/blockAPI.py .
COPY blockchain/blockchain.py .

# Flask를 실행하기 위해 필요한 패키지를 설치합니다.
RUN pip install flask

# SSH 서버를 시작합니다.
CMD ["/usr/sbin/sshd", "-D"]
