# EOS 接入初始化

## 1. 创建 EOS App

```bash
docker compose exec -T api python3 manage.py create_app --activate \
  --permission MANAGE_ORDERS --permission MANAGE_PRODUCTS --permission MANAGE_USERS \
  --permission MANAGE_STAFF --permission MANAGE_CHECKOUTS --permission MANAGE_CHANNELS \
  EOS
```

`MANAGE_STAFF` 让 EOS 找到在商城购物的员工账户（如超级管理员）；Saleor 只对它显示员工。

输出里的 `auth_token` **只在这次出现一次**，之后查不到，立刻交给 EOS 配置。

App 的 ID（如 `QXBwOjI=`）第 2 步要用，从 `app_list` 输出里 `"name": "EOS"` 那行的 `id` 取：

```bash
docker compose exec -T api python3 manage.py app_list
```

## 2. 创建订单 webhook

Saleor 没有创建 webhook 的命令。用超级管理员登录 Dashboard，把下面的 mutation 粘进 Playground，Variables 面板粘贴下面的值（除 `appId` 外已按本地开发环境填好）：

```json
{
  "appId": "QXBwOjI=",
  "targetUrl": "http://172.20.0.1:8080/api/webhooks/saleor/order",
  "query": "subscription { event { __typename ... on OrderPaid { order { ...EosOrder } } } } fragment EosOrder on Order { id created channel { id } user { id } lines { variant { sku } quantity unitPrice { net { amount currency } } } total { gross { amount currency } } transactions { id pspReference } }"
}
```

| 参数 | 含义 |
|---|---|
| `appId` | 第 1 步 `app_list` 里 EOS 的 `id`，每次创建都不同 |
| `targetUrl` | 从 Saleor api/worker 容器访问 EOS 的地址。本地是 `zaigu_network` 网关 `172.20.0.1` 上的 EOS 8080 端口 |
| `query` | EOS 收到的 payload 契约（subscription），见下方说明 |

不设 `secretKey`：Saleor 用自己的私钥给每个 payload 签 JWS（`Saleor-Signature` 头），EOS 用 Saleor 在
`/.well-known/jwks.json` 公布的公钥校验。

> **生产环境**（只需执行一次）：`targetUrl` 换成 EOS 对外域名，如
> `https://<EOS 域名>/api/webhooks/saleor/order`。生产 `HTTP_IP_FILTER_ENABLED=True`，Saleor 会拒绝向私网地址发请求，
> 不能用 `172.20.0.1`。

```graphql
mutation CreateEosOrderWebhook(
  $appId: ID!
  $targetUrl: String!
  $query: String!
) {
  webhookCreate(
    input: {
      name: "EOS order sync"
      app: $appId
      targetUrl: $targetUrl
      isActive: true
      asyncEvents: [ORDER_PAID]
      query: $query
    }
  ) {
    webhook { id name targetUrl isActive asyncEvents { eventType } }
    errors { field code message }
  }
}
```
