# EOS 接入

[`provision-eos.sh`](../../provision-eos.sh) 创建 EOS App 和它的订单 webhook，见 [部署流程](deploy.md#5-初始化)。

## EOS App

权限：`MANAGE_ORDERS`、`MANAGE_PRODUCTS`、`MANAGE_USERS`、`MANAGE_STAFF`、`MANAGE_CHECKOUTS`、`MANAGE_CHANNELS`。
`MANAGE_STAFF` 让 EOS 找到在商城购物的员工账户（如超级管理员）；Saleor 只对它显示员工。令牌写进 `../eos/.env` 的
`EOS_SALEOR_APPTOKEN`。

## 订单 webhook

[`graphql/eos-order-webhook.graphql`](../../graphql/eos-order-webhook.graphql)，用 EOS App 自己的令牌创建，所以属于 EOS App。

| 参数 | 含义 |
|---|---|
| `targetUrl` | `EOS_ORDER_WEBHOOK_URL`：从 Saleor api/worker 容器访问 EOS 的地址。本地默认是 `zaigu_network` 网关 `172.20.0.1` 上的 EOS 8080 端口 |
| `query` | EOS 收到的 payload 契约（subscription）：[`graphql/eos-order-payload.graphql`](../../graphql/eos-order-payload.graphql) |

不设 `secretKey`：Saleor 用自己的私钥给每个 payload 签 JWS（`Saleor-Signature` 头），EOS 用 Saleor 在
`/.well-known/jwks.json` 公布的公钥校验。
