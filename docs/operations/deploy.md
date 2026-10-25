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
> - 所有 `docker compose` 命令都加 `-f docker-compose.yml -f docker-compose.prod.yml`（如
>   `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`），不加载开发专用的
>   `docker-compose.override.yml`。
> - `--email` 换成真实管理员邮箱，`DJANGO_SUPERUSER_PASSWORD` 换成强密码。

## 4. 配置支付

结账走 Transactions API，需要一个有 `HANDLE_PAYMENTS` 权限的 App 处理支付 webhook。本地用
`dummy-payment-app`（随 `docker compose up` 启动，所有支付直接返回成功）。旧 Payments API 的 Dummy
插件已由 [`saleor-settings/settings_fork.py`](../../saleor-settings/settings_fork.py) 去掉，不用处理。

用超级管理员登录 Dashboard，在 Playground 里执行。

```graphql
mutation InstallDummyPaymentApp {
  appInstall(
    input: {
      appName: "Dummy Payment App"
      manifestUrl: "http://dummy-payment-app.local:3000/api/manifest"
      permissions: [HANDLE_PAYMENTS]
    }
  ) {
    appInstallation { id status message }
    errors { field code message }
  }
}
```

安装由 worker 异步完成。几秒后确认：

```graphql
query DummyPaymentAppStatus {
  apps(first: 20) { edges { node { identifier name isActive } } }
  appsInstallations { appName status message }
}
```

`apps` 里出现 `saleor.io.dummy-payment-app` 且 `isActive: true` 才算成功；`appsInstallations` 里有
`FAILED` 时看 `message`。

> **生产环境**（只需执行一次）：
>
> - 不装 dummy-payment-app（生产不加载 `docker-compose.override.yml`，它不会启动），改装真实支付 App。
> - 必须带上 `docker-compose.prod.yml`：它加载 `settings_fork.py` 去掉旧 Dummy 插件，漏掉的话旧 Dummy
>   会在每个渠道默认启用，顾客不付钱就能下单并标记为已支付。

## 5. 接入 EOS

见 [EOS 接入初始化](eos-setup.md)。
