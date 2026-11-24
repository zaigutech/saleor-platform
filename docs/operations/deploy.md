# fork 的部署流程

## 1. 迁移数据库(middleware目录下执行)

```bash
docker compose run --rm saleor-api python3 manage.py migrate
```

## 2. 创建超级管理员

```bash
docker compose run --rm -e DJANGO_SUPERUSER_PASSWORD=admin saleor-api python3 manage.py createsuperuser --noinput --email admin@example.com

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
docker compose exec -T saleor-api python3 manage.py install_app --activate --quiet http://dummy-payment-app.local:3000/api/manifest
```

> **生产环境**：
>
> - 不装 dummy-payment-app（生产不加载 `docker-compose.override.yml`，它不会启动），改装真实支付 App。
> - 必须带上 `docker-compose.prod.yml`：它加载 `settings_fork.py` 去掉旧 Dummy 插件，漏掉的话旧 Dummy
>   会在每个渠道默认启用，顾客不付钱就能下单并标记为已支付。

## 5. 初始化

Keycloak 先按 keycloak 仓库的部署流程初始化：它的 `provision-eos.sh` 把 `saleor-dashboard` client 的 secret 写进本仓库的
`.env`（`SALEOR_DASHBOARD_CLIENT_SECRET`）。服务启动后执行：

```bash
./provision-eos.sh
```

它把 [`graphql/`](../../graphql) 里的 mutation 发给 Saleor，依次：

- 创建不需要配送的商品类型 `Non Shippable` 和 `Service`，结账时不要求收货地址和配送方式；
- 配置 OpenID Connect 插件，见 [配置 OpenID Connect 插件](oidc-setup.md)；
- 创建 EOS App 和它的订单 webhook，见 [EOS 接入](eos-setup.md)，令牌写进 `../eos/.env` 的 `EOS_SALEOR_APPTOKEN`；
- 设了 `STOREFRONT_ENV_FILE` 时创建 Storefront App，令牌写进那个文件的 `SALEOR_APP_TOKEN`。storefront 只在本地开发中作为 eweb 商城的参考运行，不部署，只有 eos 的 dev-env 会设它。不需要配送的结账不收地址，storefront
  用渠道的默认国家生成账单地址，而 `channel.defaultCountry` 只对 App 和员工可见；没有这个令牌，这类订单会报“无法为此订单确定账单国家”。

前两步需要的权限 EOS App 没有，由临时的 `EOS provisioning` App 执行，执行完就停用。令牌只在创建时出现一次，目标文件不存在时
打印出来。执行完重启 EOS（本地还有 storefront）。只在全新的 Saleor 上执行一次：再执行会把这些都再建一遍。

> **生产环境**（只需执行一次）：生产开启了出站 IP 过滤（`HTTP_IP_FILTER_ENABLED`），Saleor 不能访问内网地址，所以用环境变量覆盖默认值：
>
> - `COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml`
> - `KEYCLOAK_PUBLIC_URL` 和 `KEYCLOAK_URL_FOR_SALEOR` 都设为 Keycloak 对外地址，如 `https://<Keycloak 域名>`
> - `EOS_ORDER_WEBHOOK_URL` 设为 `https://<EOS 域名>/api/webhooks/saleor/order`
> - 打印出来的 EOS App 令牌配在 EOS 的部署环境变量 `EOS_SALEOR_APPTOKEN` 里；生产不设 `STOREFRONT_ENV_FILE`，不创建 Storefront App

## 6. 对外提供 API（生产）

eweb 的商城是静态页面：构建时从这里读商品目录，访客的浏览器再直接调用它查库存和购物车，所以 API 对公网开放在
`https://commerce.zaigu.com`。匿名请求只能读已发布的商品、渠道里的价格和库存、做结账；写操作、订单、顾客和后台数据都要员工或
App 的令牌。`docker-compose.prod.yml` 为此：

- 关掉 Saleor 默认开着的 `DEBUG`（否则出错时把调用栈返回给客户端），关掉 GraphQL Playground；
- 把 `PUBLIC_URL` 设为这个地址，商品图片和缩略图的链接都指向它；
- API 的 8000 端口只绑定服务器本机，公网请求只能经过 caddy。

caddy 在 `zaigu_network` 上为 `commerce.zaigu.com` 终止 TLS，只对公网开放商城要用的三类路径，其余一律 404：

- `/graphql/`：反代到 `saleor-api:8000`，并按客户端 IP 限流（Saleor 只限制单个查询的成本，不限频率；标准 caddy 没有限流，
  需要带 `caddy-ratelimit` 模块的构建）；
- `/thumbnail/*`：反代到 `saleor-api:8000`，它生成缩略图后重定向到 `/media/`；
- `/media/*`：由 caddy 直接读媒体目录 `/mnt/data/saleor`（挂进 caddy 容器；`DEBUG` 关掉后 Saleor 不再提供这些文件）。

```caddyfile
commerce.zaigu.com {
	@api path /graphql/ /thumbnail/*
	handle @api {
		rate_limit {
			zone graphql {
				key {remote_host}
				events 300
				window 1m
			}
		}
		reverse_proxy saleor-api:8000
	}
	handle_path /media/* {
		root * /mnt/data/saleor
		file_server
	}
	respond 404
}
```

租户的商城用自己的域名时，把它加进 `ALLOWED_CLIENT_HOSTS`（账户邮件里允许跳转回的域名）。跨域不做限制
（`ALLOWED_GRAPHQL_ORIGINS` 保持 `*`）：API 本就公开，登录态放在请求头的令牌里而不是 cookie，限制来源挡不住任何人。
