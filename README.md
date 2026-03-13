# 12306 API Client

一个基于 Python 的 12306 命令行脚本，支持：

- 登录（含短信验证码流程）
- 二维码登录（生成后自动后台检查，不阻塞）
- 登录状态检查（已登录时返回用户关键信息）
- 查询当前账号乘车人信息
- 查询余票
- 查询中转车票
- 提交中转订单（按中转方案下单）
- 查询经停站
- 查询订单
- 查询候补排队状态
- 查询候补订单（进行中/已处理）
- 提交候补订单（基于“无票可候补”规则）
- 取消候补订单（按候补单号）
- 候补支付参数获取（输出支付网关 POST 参数）
- 订票（提交订单并轮询订单号）
- 支付信息获取（尝试生成支付链接）

脚本文件：`client.py`

## 环境要求

- Python 3.9+
- 依赖：`requests`

安装依赖：

```bash
pip install requests
```

## 快速开始

先看帮助：

```bash
python3 client.py -h
python3 client.py book -h
python3 client.py transfer-ticket -h
python3 client.py transfer-book -h
python3 client.py route -h
python3 client.py candidate-orders -h
python3 client.py candidate-submit -h
python3 client.py candidate-pay -h
python3 client.py qr-login-create -h
```

## 常用命令

说明：除 `login` 外，其他需要登录态的命令不再支持通过 `--username/--password` 自动补登录。若未登录，请先执行 `login` 或二维码登录更新 cookie。

### 1) 登录

先发短信验证码：

```bash
python3 client.py login --username <账号> --id-last4 <证件后4位> --send-sms
```

再带验证码登录：

```bash
python3 client.py login --username <账号> --id-last4 <证件后4位> --sms-code <6位验证码>
```

也可以直接传密码（不传则会交互输入，或读取 `KYFW_PASSWORD`）：

```bash
python3 client.py login --username <账号> --password <密码>
```

二维码登录（创建后自动后台检查，不阻塞）：

```bash
# 1) 生成二维码后立即退出
python3 client.py qr-login-create --qr-image-file ./12306_qr_login.png
```

如果不传 `--qr-image-file`，脚本会自动生成随机文件名，优先写到系统 `tmp` 目录，失败时回退到 `client.py` 所在目录，并输出最终路径。创建后会自动后台启动登录检查进程，并输出 PID 与日志路径。

可选参数：

- `qr-login-create --state-file`（二维码状态文件，默认从 `--cookie-file` 推导）

### 2) 查询登录状态

```bash
python3 client.py status
```

如果已登录，输出会包含：

- `登录状态`
- `user` 关键信息（如 `name`、`username`、`email`、`mobile`，按接口返回为准）

JSON 输出：

```bash
python3 client.py status --json
```

### 3) 查询余票

```bash
python3 client.py left-ticket --date 2026-03-23 --from 宁波 --to 宜春
```

可选参数：

- `--endpoint queryG|queryZ`（默认 `queryG`）
- `--purpose ADULT`（默认 `ADULT`）
- `--limit`（控制展示行数）

说明：

- 单程余票默认展示票价，票价由返回的余票数据本地解析，不额外请求票价接口。

### 4) 查询中转车票

```bash
python3 client.py transfer-ticket --date 2026-03-23 --from 南部 --to 成都东
```

可选参数：

- `--middle`（指定换乘站，可不传）
- `--result-index`（分页游标，默认 `0`）
- `--can-query Y|N`（是否继续查询更多方案，默认 `Y`）
- `--show-wz`（显示无座方案；默认不显示）
- `--purpose`（乘客类型编码，默认 `00`）
- `--channel`（默认 `E`）
- `--endpoint queryG|queryZ`（默认 `queryG`）
- `--limit`（控制展示行数）

说明：

- 中转结果默认展示两程坐席与票价，票价由每程返回的 `yp_info` 本地解析，不额外请求票价接口。

JSON 输出：

```bash
python3 client.py transfer-ticket --date 2026-03-23 --from NBE --to ICW --json
```

### 5) 查询经停站

```bash
python3 client.py route --train-code C956 --date 2026-03-23 --from 南部 --to 南充北
```

可选参数：

- `--train-code`（车次号，如 `C956`；会自动解析 `train_no`）
- `--train-no`（直接传列车内部 `train_no`）
- `--endpoint queryG|queryZ`（`--train-code` 模式下用于解析，默认 `queryG`）
- `--purpose`（`--train-code` 模式下用于解析，默认 `ADULT`）
- `--limit`（最多展示多少站，默认 `200`）
- `--json`（输出原始 JSON）

参数说明：

- `--train-no` 和 `--train-code` 二选一，至少传一个。
- 传 `--train-code` 时，脚本会先走一次余票查询自动解析 `train_no`。

### 6) 查询当前账号乘车人

```bash
python3 client.py passengers
```

可选参数：

- `--limit`（最多展示多少个乘车人）
- `--json`（输出原始 JSON）

### 7) 查询订单

```bash
python3 client.py orders --where G
```

说明：

- `--where G`：未出行/近期
- `--where H`：历史订单
- `--where H` 时，`--end-date` 必须早于今天（最大为昨天）；不传时默认按昨天处理
- `--query-type 1`：按订票日期查询（默认）
- `--query-type 2`：按乘车日期查询
- `--train-name`：按订单号/车次/姓名筛选（对应接口参数 `sequeue_train_name`）

若 cookie 未登录或失效，请先执行 `login`（或二维码登录）更新 cookie 后再查询。

### 8) 候补相关（查询 / 提交 / 取消）

候补排队状态：

```bash
python3 client.py candidate-queue
```

候补订单（默认查进行中）：

```bash
python3 client.py candidate-orders
```

查已处理候补订单：

```bash
python3 client.py candidate-orders --processed --start-date 2026-03-11 --end-date 2026-04-09
```

提交候补订单（建议在目标席别余票显示“无”时使用）：

```bash
python3 client.py candidate-submit \
  --date 2026-03-23 \
  --from 宁波 \
  --to 宜春 \
  --train-code G1234 \
  --seat second_class
```

取消候补订单：

```bash
python3 client.py candidate-cancel --reserve-no <候补单号>
```

候补支付参数（优先从当前候补队列自动读取 `reserve_no`）：

```bash
python3 client.py candidate-pay
```

按候补单号获取支付参数：

```bash
python3 client.py candidate-pay --reserve-no <候补单号>
```

直接生成可浏览器打开的支付链接（GET）：

```bash
python3 client.py candidate-pay --channel alipay
```

可选参数：

- `candidate-orders --processed`（查已处理记录，不加则查进行中）
- `candidate-orders --page-no`（页码，默认 `0`）
- `candidate-orders --start-date/--end-date`（日期区间）
- `candidate-orders --limit`（文本输出最多展示条数）
- `candidate-submit --seat`（候补席别；默认要求该席别余票为“无”）
- `candidate-submit --passengers`（乘客姓名，多个逗号分隔；不传默认取首位乘车人）
- `candidate-submit --force`（即使余票不是“无”也尝试提交）
- `candidate-submit --max-wait-seconds`（候补排队轮询最长等待秒数，默认 `30`）
- `candidate-submit --poll-interval`（候补排队轮询间隔秒数，默认 `1.0`）
- `candidate-cancel --reserve-no`（候补单号）
- `candidate-pay --reserve-no`（候补单号；不传则尝试从 `candidate-queue` 自动读取）
- `candidate-pay --channel`（`alipay`/`wechat`/`unionpay`，直接生成第三方 GET 支付链接）

说明：

- 候补命令需要登录态（可沿用已有 cookie）。
- 若 cookie 失效，请先执行 `login`（或二维码登录）更新 cookie 后再重试。
- `candidate-submit` 会继续执行候补确认与排队查询；若超时会返回“仍在排队中”，可继续用 `candidate-orders`/`candidate-queue` 查看。
- `candidate-pay` 默认输出支付网关 POST 参数（`epay.12306.cn/pay/payGateway`）。
- 若用户侧仅支持浏览器 GET 打开链接，使用 `candidate-pay --channel alipay|wechat|unionpay` 可直接返回第三方支付链接。
- `candidate-pay --channel` 会额外本地生成支付二维码图片（不调用在线二维码服务，优先写入系统 `tmp` 目录，失败时回退到项目目录），便于用户扫码支付。
- 本地生成二维码依赖 `qrcode` 或 `segno`（示例：`pip install qrcode[pil]`）。

### 9) 订票

先建议用 `--dry-run` 做预检（不提交最终排队确认）：

```bash
python3 client.py book \
  --date 2026-03-23 \
  --from 宁波 \
  --to 宜春 \
  --train-code G1234 \
  --seat second_class \
  --passengers 张三 \
  --dry-run
```

确认后正式提交：

```bash
python3 client.py book \
  --date 2026-03-23 \
  --from 宁波 \
  --to 宜春 \
  --train-code G1234 \
  --seat second_class \
  --passengers 张三
```

按支付渠道生成本地支付二维码（中转订单）：

```bash
python3 client.py transfer-book \
  --date 2026-03-23 \
  --from 南部 \
  --to 广安 \
  --plan-index 1 \
  --seat second_class \
  --passengers 张三 \
  --pay-channel alipay
```

按渠道解析并生成本地支付二维码（普通订单）：

```bash
python3 client.py book \
  --date 2026-03-23 \
  --from 宁波 \
  --to 宜春 \
  --train-code G1234 \
  --seat second_class \
  --passengers 张三 \
  --channel alipay
```

说明：

- 当前链路可以稳定完成下单并拿到订单号。
- 脚本会尝试调用 `payOrder/paycheckNew` 返回支付链接参数。
- 若传 `--channel`，脚本会尝试解析到渠道支付链接并本地生成二维码图片，方便扫码支付。
- 若未传 `--channel` 或支付参数缺失，仍建议在 12306 App 的“待支付订单”中完成支付。

多个乘客用逗号分隔：

```bash
--passengers 张三,李四
```

常用席别写法：

- 英文：`second_class`、`first_class`、`business`
- 中文：`二等座`、`一等座`、`硬卧` 等
- 代码：`O`、`M`、`9`、`3`、`4`、`1` 等

### 10) 提交中转订单

先建议用 `--dry-run` 做预检（不提交最终排队确认）：

```bash
python3 client.py transfer-book \
  --date 2026-03-23 \
  --from 南部 \
  --to 广安 \
  --plan-index 1 \
  --seat second_class \
  --passengers 张三 \
  --dry-run
```

确认后正式提交：

```bash
python3 client.py transfer-book \
  --date 2026-03-23 \
  --from 南部 \
  --to 广安 \
  --plan-index 1 \
  --seat second_class \
  --passengers 张三
```

说明：

- `--plan-index` 对应 `transfer-ticket` 文本结果中的方案序号（从 1 开始）。
- 中转下单链路基于 `lcQuery/lcConfirmPassenger`，按两程统一席别提交。
- 当前实现会轮询 `queryOrderWaitTime(tourFlag=lc)` 直到拿到订单号或返回失败信息。
- `--channel` 是中转查询渠道参数（默认 `E`），`--pay-channel` 才是支付渠道（`alipay/wechat/unionpay`）。
- 传 `--pay-channel` 时会尝试解析渠道支付链接并本地生成支付二维码。

## 全局参数

- `--base-url`：默认 `https://kyfw.12306.cn`
- `--timeout`：请求超时（秒）
- `--cookie-file`：cookie 持久化路径（默认 `~/.kyfw_12306_cookies.json`）
- `--no-browser-headers`：关闭浏览器风格请求头仿真（默认开启）
- `--json`：输出原始 JSON

## 订票流程说明

`book` 命令内部流程为：

1. 查询余票并定位目标车次
2. `submitOrderRequest`
3. `initDc` 解析 token 和关键字段
4. 拉取乘客列表并按姓名匹配
5. `checkOrderInfo`
6. `getQueueCount`
7. `confirmSingleForQueue`
8. 轮询 `queryOrderWaitTime` 获取订单号
9. `resultOrderForDcQueue`
10. `payOrder/init` + `payOrder/paycheckNew`（尝试生成支付链接）

## 注意事项

- 12306 风控较严格，可能出现 `error.html`、排队超时、或需要额外校验。
- 部分账号可能触发滑块/图片验证码（脚本当前不自动处理该场景）。
- 即使成功返回支付参数，网页侧也可能无法完成支付；请优先在 12306 App 的待支付订单中支付。
- 本工具仅供学习与自动化辅助，请遵守 12306 平台规则并控制请求频率。
