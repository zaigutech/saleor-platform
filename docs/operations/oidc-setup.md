# 配置 OpenID Connect 插件

让 Saleor 认 Keycloak（realm `eos`）签发的 token。用超级管理员登录 Dashboard，在 Playground 里执行：

```graphql
mutation ConfigureOpenIdConnect {
  pluginUpdate(
    id: "mirumee.authentication.openidconnect"
    input: {
      active: true
      configuration: [
        { name: "client_id", value: "eos-storefront" }
        { name: "client_secret", value: "unused" }
        { name: "json_web_key_set_url", value: "http://172.17.0.1:8081/realms/eos/protocol/openid-connect/certs" }
        { name: "user_info_url", value: "http://172.17.0.1:8081/realms/eos/protocol/openid-connect/userinfo" }
        { name: "use_oauth_scope_permissions", value: "false" }
        { name: "oauth_authorization_url", value: "" }
        { name: "oauth_token_url", value: "" }
        { name: "oauth_logout_url", value: "" }
      ]
    }
  ) {
    plugin {
      id
      globalConfiguration {
        active
        configuration { name value }
      }
    }
    errors { field code message }
  }
}
```

返回里 `errors` 为空、`globalConfiguration.active` 为 `true` 才算成功。

| 参数 | 含义 |
|---|---|
| `client_id` | Keycloak 里的 client，固定 `eos-storefront` |
| `client_secret` | 填 `unused`。`oauth_*_url` 为空时 Saleor 只校验 token，不会使用它，填值只为通过启用插件时的非空检查。以后若填了 `oauth_*_url`，必须换成 Keycloak 里 `eos-storefront` → Credentials 的真实 secret |
| `json_web_key_set_url` | Keycloak 公钥地址，Saleor 用它校验 token 签名。本地是 docker 网关 `172.17.0.1` 上的 Keycloak 8081 端口 |
| `user_info_url` | Keycloak userinfo 地址，Saleor 用它取用户信息 |
| `use_oauth_scope_permissions` | `false`：不按 token 的 scope 授予 Saleor 后台权限 |
| `oauth_*_url` | 留空：登录流程由 EOS/Keycloak 自己完成，Saleor 只校验 token |

> **生产环境**（只需执行一次）：`json_web_key_set_url` / `user_info_url` 换成 Keycloak 对外域名，如
> `https://<Keycloak 域名>/realms/eos/protocol/openid-connect/certs` 和 `.../userinfo`。
