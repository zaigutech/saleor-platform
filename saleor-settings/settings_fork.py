# fork 的 Saleor settings 覆盖，开发和生产都加载。
#
# 挂载到 api / worker 容器的 /app/saleor/settings_fork.py，并设置
# DJANGO_SETTINGS_MODULE=saleor.settings_fork（见 docker-compose.override.yml 和
# docker-compose.prod.yml）。
from saleor.settings import *  # noqa: F403

# 去掉旧 Payments API 的 Dummy 插件（mirumee.payments.dummy 和
# mirumee.payments.dummy_credit_card）。前者在每个渠道里默认启用，不付钱也能下单；
# 支付统一走 Transactions API + 支付 App。
PLUGINS = [p for p in PLUGINS if not p.startswith("saleor.payment.gateways.dummy")]  # noqa: F405
