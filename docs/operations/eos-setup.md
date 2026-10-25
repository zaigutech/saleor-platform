# EOS 接入初始化

前提：已按 [部署](deploy.md) 完成第 1～3 步。

用超级管理员登录 Dashboard，在 Playground 里执行。

## 1. 创建 EOS App

```graphql
mutation CreateEosApp {
  appCreate(
    input: {
      name: "EOS"
      permissions: [
        MANAGE_ORDERS
        MANAGE_PRODUCTS
        MANAGE_USERS
        MANAGE_CHECKOUTS
        MANAGE_CHANNELS
      ]
    }
  ) {
    authToken
    app {
      id
      name
    }
    errors {
      field
      message
    }
  }
}
```

返回里 `errors` 为空才算成功。

- `authToken`：**只在这次返回里出现一次**，之后查不到，立刻交给 EOS 配置。
- `app.id`：复制下来，第 2 步的 `appId` 就填它。

## 2. 创建订单 webhook

把下面的 mutation 粘进 Playground，Variables 面板粘贴下面的值（除 `appId` 外已按本地开发环境填好）：

```json
{
  "appId": "<第 1 步返回的 app.id>",
  "targetUrl": "http://172.20.0.1:8080/api/webhooks/saleor/order",
  "secretKey": "change-me"
}
```

| 参数 | 含义 |
|---|---|
| `appId` | 第 1 步返回的 `app.id`，每次创建都不同 |
| `targetUrl` | 从 Saleor api/worker 容器访问 EOS 的地址。本地是 `zaigu_network` 网关 `172.20.0.1` 上的 EOS 8080 端口 |
| `secretKey` | 必须和 EOS 的 `SALEOR_WEBHOOK_SECRET` 一致 |

> **生产环境**（只需执行一次）改这两项：
>
> - `targetUrl`：换成 EOS 对外域名，如 `https://<EOS 域名>/api/webhooks/saleor/order`。生产
>   `HTTP_IP_FILTER_ENABLED=True`，Saleor 会拒绝向私网地址发请求，不能用 `172.20.0.1`。
> - `secretKey`：换成生产 EOS 的 `SALEOR_WEBHOOK_SECRET`。

```graphql
mutation CreateEosOrderWebhook($appId: ID!, $targetUrl: String!, $secretKey: String!) {
  webhookCreate(
    input: {
      name: "EOS order sync"
      app: $appId
      targetUrl: $targetUrl
      secretKey: $secretKey
      isActive: true
      asyncEvents: [ORDER_CREATED, ORDER_PAID]
      query: """
      subscription {
        event {
          __typename
          ... on OrderCreated { order { ...EosOrder } }
          ... on OrderPaid { order { ...EosOrder } }
        }
      }

      fragment EosOrder on Order {
        id
        created
        channel { id }
        user { id }
        userEmail
        lines { variant { sku } quantity unitPrice { gross { amount currency } } }
        total { gross { amount currency } }
        payments { id pspReference }
        transactions { id pspReference }
      }
      """
    }
  ) {
    webhook { id name targetUrl isActive asyncEvents { eventType } }
    errors { field code message }
  }
}
```

mutation 里的 subscription 就是 EOS 收到的 payload 契约，这里是它唯一的定义，运维照抄执行即可。
（给开发：EOS 的 payload 解析要改字段时，改这里的 subscription，再对已有实例执行 `webhookUpdate`。）

返回里 `errors` 为空才算成功。记下返回的 `webhook.id`，后面改 URL 或密钥时要用（用 `webhookUpdate`，传同样的字段）。

## 3. 验证

下一单测试订单，然后查看投递记录。Variables：

```json
{ "appId": "<第 1 步返回的 app.id>" }
```

```graphql
query EosWebhookDeliveries($appId: ID!) {
  app(id: $appId) {
    webhooks {
      name
      eventDeliveries(first: 5) {
        edges {
          node {
            eventType
            status
            attempts(first: 3) { edges { node { status responseStatusCode response } } }
          }
        }
      }
    }
  }
}
```

`responseStatusCode` 是 EOS 的返回码，按下表排查：

| 返回码 | 含义 |
|---|---|
| `200` | 已送达 |
| `401` | 签名不对（`secretKey` 和 EOS 的不一致），或订单所在渠道没有在 EOS 登记 |
| `400` | payload 结构和 EOS 期望的不一致，按第 2 步重新核对 subscription |

webhook 创建之前已经下的订单，Saleor 不会补发。
