# fork 的部署流程

## 1. 迁移数据库(middleware目录下执行)

```bash
docker compose run --rm api python3 manage.py migrate
```

## 2. 创建超级管理员

```bash
docker compose run --rm -e DJANGO_SUPERUSER_PASSWORD=admin api python3 manage.py createsuperuser --noinput --email admin@example.com

```

## 3. 启动

```bash
docker compose up
```

- Dashboard：http://localhost:9000/ ，配置 OpenID Connect 之前先用 `admin@example.com` / `admin` 登录
- API：http://localhost:8000/graphql/

> **生产环境**：
>
> - 所有 `docker compose` 命令都加 `-f docker-compose.yml -f docker-compose.prod.yml`（如
>   `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`），不加载开发专用的
>   `docker-compose.override.yml`。
> - `--email` 用平台超级管理员的邮箱，即 keycloak 仓库 `provision-eos.sh` 的 `EOS_ADMIN_USERNAME`；
>   `DJANGO_SUPERUSER_PASSWORD` 只在配置 OpenID Connect 之前用，换成强密码。配置之后它经 Keycloak 登录，见
>   [配置 OpenID Connect 插件](oidc-setup.md)。

## 4. 配置支付

结账走 Transactions API，需要一个有 `HANDLE_PAYMENTS` 权限的 App 处理支付 webhook。本地用
`dummy-payment-app`（随 `docker compose up` 启动，所有支付直接返回成功）。旧 Payments API 的 Dummy
插件已由 [`saleor-settings/settings_fork.py`](../../saleor-settings/settings_fork.py) 去掉，不用处理。

服务启动后安装并启用它，权限（`HANDLE_PAYMENTS`）取自它的 manifest：

```bash
docker compose exec -T api python3 manage.py install_app --activate --quiet http://dummy-payment-app.local:3000/api/manifest
```

> **生产环境**：
>
> - 不装 dummy-payment-app（生产不加载 `docker-compose.override.yml`，它不会启动），改装真实支付 App。
> - 必须带上 `docker-compose.prod.yml`：它加载 `settings_fork.py` 去掉旧 Dummy 插件，漏掉的话旧 Dummy
>   会在每个渠道默认启用，顾客不付钱就能下单并标记为已支付。

## 5. 创建商品类型

创建两个不需要配送的商品类型 `Non Shippable` 和 `Service`（`isShippingRequired: false`，结账时不要求收货地址和配送方式）。
在 Playground 里执行：

```graphql
mutation CreateNonShippingProductTypes {
  nonShippable: productTypeCreate(
    input: { name: "Non Shippable", kind: NORMAL, isShippingRequired: false }
  ) {
    productType { id name slug isShippingRequired }
    errors { field code message }
  }
  service: productTypeCreate(
    input: { name: "Service", kind: NORMAL, isShippingRequired: false }
  ) {
    productType { id name slug isShippingRequired }
    errors { field code message }
  }
}
```

## 6. 配置 OpenID Connect

见 [配置 OpenID Connect 插件](oidc-setup.md)。

## 7. 接入 EOS

见 [EOS 接入初始化](eos-setup.md)。

## 8. 接入 storefront

不需要配送的结账（第 5 步的商品类型）不收地址，storefront 用渠道的默认国家生成账单地址。`channel.defaultCountry`
只对 App 和员工可见，所以 storefront 需要一个 App 令牌；没有它，这类订单会报“无法为此订单确定账单国家”。

App 不需要任何权限。在 Playground 里执行：

```graphql
mutation CreateStorefrontApp {
  appCreate(input: { name: "Storefront" }) {
    authToken
    app { id name isActive }
    errors { field code message }
  }
}
```

`authToken` **只在这次返回里出现一次**。写进 storefront 仓库的 `.env.local`，然后重启 storefront：

```
SALEOR_APP_TOKEN=<authToken>
```

> **生产环境**：`SALEOR_APP_TOKEN` 配在 storefront 的部署环境变量里。
