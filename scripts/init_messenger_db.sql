-- 슈퍼유저(postgres)로 psql / pgAdmin에서 실행하세요.
-- 비밀번호를 바꾸면 backend/.env 의 DATABASE_URL 도 같이 맞춥니다.

CREATE USER messenger WITH PASSWORD 'messenger';
CREATE DATABASE messenger OWNER messenger;
GRANT ALL PRIVILEGES ON DATABASE messenger TO messenger;
