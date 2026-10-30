# 配置 OpenID Connect 插件

让 Saleor 认 Keycloak（realm `eos`）签发的 token，并让 Dashboard 经 Keycloak 登录：整个平台的超级管理员是
Keycloak 里的同一个用户，用同一套邮箱和密码登录 EOS、Saleor Dashboard 和 Odoo。Keycloak 的 client 由 middleware
的 `keycloak/provision-eos.sh` 创建。用超级管理员登录 Dashboard，在 Playground 里执行：

```graphql
mutation ConfigureOpenIdConnect {
  pluginUpdate(
    id: "mirumee.authentication.openidconnect"
    input: {
      active: true
      configuration: [
        { name: "client_id", value: "saleor-dashboard" }
        { name: "client_secret", value: "<saleor-dashboard 的 secret>" }
        { name: "oauth_authorization_url", value: "http://localhost:8081/realms/eos/protocol/openid-connect/auth" }
        { name: "oauth_token_url", value: "http://172.17.0.1:8081/realms/eos/protocol/openid-connect/token" }
        { name: "json_web_key_set_url", value: "http://172.17.0.1:8081/realms/eos/protocol/openid-connect/certs" }
        { name: "user_info_url", value: "http://172.17.0.1:8081/realms/eos/protocol/openid-connect/userinfo" }
        { name: "use_oauth_scope_permissions", value: "true" }
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

返回里 `errors` 为空、`globalConfiguration.active` 为 `true` 才算成功。之后 Dashboard 登录页出现
“Continue with SSO”。

| 参数 | 含义 |
|---|---|
| `client_id` | Keycloak 里的 client，固定 `saleor-dashboard`。插件不发 PKCE，所以不和要求 PKCE 的 `storefront` 共用 client；校验 storefront 送来的 token 不看 `client_id` |
| `client_secret` | Keycloak 控制台 Clients → saleor-dashboard → Credentials 里的 secret |
| `oauth_authorization_url` | 浏览器跳转的 Keycloak 登录地址，用 Keycloak 对外地址 |
| `oauth_token_url` | Saleor API 用登录回来的 code 换 token 的地址，从容器里访问 |
| `json_web_key_set_url` | Keycloak 公钥地址，Saleor 用它校验 token 签名 |
| `user_info_url` | Keycloak userinfo 地址，Saleor 用它取用户信息 |
| `use_oauth_scope_permissions` | `true`：Dashboard 会话的 staff 身份和后台权限只来自 Keycloak 授予的 `saleor:staff`、`saleor:<权限>` scope。关掉时插件把所有经 SSO 登录的用户当作非 staff，超级管理员也进不了 Dashboard |
| `oauth_logout_url` | 留空 |

本地从容器访问 Keycloak 用 docker 网关 `172.17.0.1` 上的 8081 端口：插件的 URL 校验不接受 `keycloak` 这样的单段主机名。

超级管理员首次经 Keycloak 登录时，Saleor 按邮箱认领用 `createsuperuser` 建的同邮箱超级管理员（见
[部署流程](deploy.md#2-创建超级管理员)），把它绑定到 Keycloak 用户并作废它在 Saleor 里的本地密码，此后只能经
Keycloak 登录。`saleor:*` scope 由 middleware 的 `provision-eos.sh` 建在 `saleor-dashboard` client 上，只授予持有
realm 角色 `saleor-admin` 的用户，即超级管理员；其他 Keycloak 用户经 SSO 登录只会得到无后台权限的普通账号。
`audience` 不配：storefront 送来的 Keycloak token 不带 `saleor:*` scope，也就不会被当作 staff。

> **生产环境**（只需执行一次）：四个 URL 都换成 Keycloak 对外域名，如
> `https://<Keycloak 域名>/realms/eos/protocol/openid-connect/auth`、`.../token`、`.../certs` 和 `.../userinfo`：
> 生产开启了出站 IP 过滤（`HTTP_IP_FILTER_ENABLED`），Saleor 不能访问内网地址。
