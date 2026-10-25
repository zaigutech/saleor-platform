# fork 的部署流程

## 1. 迁移数据库(middleware目录下执行)

```bash
docker compose run --rm api python3 manage.py migrate
```

## 2. 创建超级管理员

```bash
docker compose run --rm -e DJANGO_SUPERUSER_PASSWORD=admin api python3 manage.py createsuperuser --noinput --email 129082@qq.com

```

## 3. 启动

```bash
docker compose up
```

- Dashboard：http://localhost:9000/ ，用 `129082@qq.com` / `admin` 登录
- API：http://localhost:8000/graphql/

> **生产环境**（只需执行一次）：
>
> - 所有 `docker compose` 命令都加 `-f docker-compose.yml`（如 `docker compose -f docker-compose.yml up -d`），
>   不加载开发专用的 `docker-compose.override.yml`。
> - `--email` 换成真实管理员邮箱，`DJANGO_SUPERUSER_PASSWORD` 换成强密码。

## 4. 接入 EOS

见 [EOS 接入初始化](eos-setup.md)。
