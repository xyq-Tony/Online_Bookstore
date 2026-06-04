# 03-syslog-practice 原始素材来源

本文档记录 `sections/03-syslog-practice.tex` 的写作依据，便于后续修改课程报告时追溯内容来源。

## 1. 章节对应项目

- 报告工程：`C:\Users\alexa\Desktop\大三下\网络安全导论\wangluoxinxianquan`
- 被改写章节：`sections/03-syslog-practice.tex`
- 实验对象工程：`D:\python\Bookstore\Online_Bookstore`

## 2. 代码分析来源

### 2.1 日志初始化

- 文件：`bookstore_logging.py`
- 关键位置：
  - `class RequestContextFilter`：第 132 行
  - `class StructuredFormatter`：第 170 行
  - `def _build_syslog_handler()`：第 231 行
  - `def configure_logging()`：第 249 行
- 报告中对应内容：
  - 结构化 `key=value` 格式
  - 控制台 / syslog / both 三种输出模式
  - `request_id`、`method`、`path`、`status`、`duration_ms`、`user`、`client_ip` 自动补齐
  - `SysLogHandler` 用于发送 Syslog 消息

### 2.2 请求链路日志

- 文件：`app.py`
- 关键位置：
  - `def get_base_path()`：第 17 行
  - `def resource_path(relative_path)`：第 29 行
  - `@app.before_request`：第 79 行
  - `@app.after_request`：第 88 行
  - `@app.teardown_request`：第 113 行
- 报告中对应内容：
  - 每次请求生成唯一 `request_id`
  - 请求结束写入 `event=http_request_completed`
  - 异常时写入 `request_unhandled_exception`
  - 响应头增加 `X-Request-ID`
  - PyInstaller 环境下路径兼容

### 2.3 业务日志

- 文件：`app.py`
- 关键位置：
  - `def login()`：第 282 行
  - `def register()`：第 335 行
  - `def logout()`：第 382 行
  - `def create_order()`：第 425 行
  - `def my_orders()`：第 512 行
  - `def serve_images(filename)`：第 542 行
- 报告中对应内容：
  - 登录成功 / 失败
  - 注册成功 / 用户名冲突
  - 登出
  - 下单成功 / 下单失败 / 库存扣减
  - 我的订单查询
  - 图片访问定位

## 3. 真实运行日志来源

日志来源文件均来自已完成的实际运行验证，不是手工编造。

### 3.1 控制台日志

- 文件：`docs/runtime/app_stdout.log`
- 解码方式：`gb18030`

#### 请求完成日志

来源位置：第 4 行

```text
ts=2026-06-04T13:29:28 level=INFO app=online_bookstore logger=online_bookstore event=http_request_completed request_id=79a4d52ab5bf method=GET path=/ status=200 duration_ms=2 user=- client_ip=127.0.0.1 message=request_completed
```

#### 注册成功日志

来源位置：第 53 行

```text
ts=2026-06-04T13:29:39 level=INFO app=online_bookstore logger=online_bookstore event=user_register_success request_id=16aa09587eeb method=POST path=/api/register status=- duration_ms=- user=reportuser_1780550963 client_ip=127.0.0.1 message=user_registered
```

#### 登录成功日志

来源位置：第 55 行

```text
ts=2026-06-04T13:29:39 level=INFO app=online_bookstore logger=online_bookstore event=user_login_success request_id=0fc59c5eedbe method=POST path=/api/login status=- duration_ms=- user=reportuser_1780550963 client_ip=127.0.0.1 message=user_logged_in
```

#### 图片访问日志

来源位置：第 14 行

```text
ts=2026-06-04T13:29:34 level=DEBUG app=online_bookstore logger=online_bookstore event=image_lookup request_id=f82d516fcd8f method=GET path=/images/JavaScript高级程序设计.jpg status=- duration_ms=- user=- client_ip=127.0.0.1 message=image_requested image_name=JavaScript高级程序设计.jpg image_path=D:\\python\\Bookstore\\Online_Bookstore\\my_Bookstore\\images\\JavaScript高级程序设计.jpg
```

#### 库存扣减日志

来源位置：第 198 行

```text
ts=2026-06-04T13:29:46 level=DEBUG app=online_bookstore logger=online_bookstore event=order_item_reserved request_id=a44f9785da2c method=POST path=/api/order status=- duration_ms=- user=reportuser_1780550963 client_ip=127.0.0.1 message=order_item_reserved book_id=1 book_title=Python编程——从入门到实践 order_id=6 quantity=1
```

#### 下单成功日志

来源位置：第 199 行

```text
ts=2026-06-04T13:29:46 level=INFO app=online_bookstore logger=online_bookstore event=order_create_success request_id=a44f9785da2c method=POST path=/api/order status=- duration_ms=- user=reportuser_1780550963 client_ip=127.0.0.1 message=order_created item_count=1 order_id=6 total_amount=76.2
```

#### 我的订单查询日志

来源位置：第 246 行

```text
ts=2026-06-04T13:29:48 level=DEBUG app=online_bookstore logger=online_bookstore event=orders_query request_id=6483ce6eba80 method=GET path=/api/my_orders status=- duration_ms=- user=reportuser_1780550963 client_ip=127.0.0.1 message=orders_queried order_count=1
```

#### 库存不足失败日志

来源位置：第 726 行

```text
ts=2026-06-04T13:38:09 level=ERROR app=online_bookstore logger=online_bookstore event=order_create_failed request_id=e529453bcd24 method=POST path=/api/order status=- duration_ms=- user=reportuser_1780550963 client_ip=127.0.0.1 message=order_create_failed item_count=1 traceback="Traceback (most recent call last):\n  File \"app.py\", line 458, in create_order\nException: Python编程——从入门到实践 库存不足"
```

### 3.2 Syslog 接收日志

- 文件：`docs/runtime/syslog_listener.log`
- 解码方式：`gb18030`

#### Syslog 请求日志

来源位置：第 4 行

```text
2026-06-04 13:29:28 from=127.0.0.1:62556 <134>online-bookstore level=INFO app=online_bookstore logger=online_bookstore event=http_request_completed request_id=79a4d52ab5bf method=GET path=/ status=200 duration_ms=2 user=- client_ip=127.0.0.1 message=request_completed
```

#### Syslog 登录成功日志

来源位置：第 54 行

```text
2026-06-04 13:29:39 from=127.0.0.1:62556 <134>online-bookstore level=INFO app=online_bookstore logger=online_bookstore event=user_login_success request_id=0fc59c5eedbe method=POST path=/api/login status=- duration_ms=- user=reportuser_1780550963 client_ip=127.0.0.1 message=user_logged_in
```

#### Syslog 下单成功日志

来源位置：第 198 行

```text
2026-06-04 13:29:46 from=127.0.0.1:62556 <134>online-bookstore level=INFO app=online_bookstore logger=online_bookstore event=order_create_success request_id=a44f9785da2c method=POST path=/api/order status=- duration_ms=- user=reportuser_1780550963 client_ip=127.0.0.1 message=order_created item_count=1 order_id=6 total_amount=76.2
```

## 4. 截图来源与用途

截图目录：`docs/screenshots/`

- `01_homepage.png`
  - 用途：展示首页、地址栏、图书列表
  - 报告中对应：首页运行效果
- `02_login_success.png`
  - 用途：展示登录成功页面和 `event=user_login_success`
  - 报告中对应：认证日志验证
- `03_register_success.png`
  - 用途：展示注册成功页面和 `event=user_register_success`
  - 报告中对应：注册日志验证
- `04_order_success.png`
  - 用途：展示下单成功页面、`order_item_reserved`、`order_create_success`
  - 报告中对应：订单日志验证
- `05_my_orders.png`
  - 用途：展示“我的订单”页面和 `event=orders_query`
  - 报告中对应：查询日志验证
- `06_image_access.png`
  - 用途：展示图片正常显示和 `event=image_lookup`
  - 报告中对应：静态资源访问日志
- `07_request_id_header.png`
  - 用途：展示响应头中的 `X-Request-ID` 与同 request_id 日志
  - 报告中对应：请求链路追踪
- `08_syslog_output.png`
  - 用途：展示 `python syslog_udp_listener.py` 收到的 Syslog 消息
  - 报告中对应：Syslog 验证
- `09_exception_log.png`
  - 用途：展示库存不足业务异常，含 `level=ERROR`、`traceback`、`request_id`
  - 报告中对应：异常日志验证

## 5. 写作取舍说明

- 主报告正文围绕实际项目实现展开，避免写成泛泛的 Syslog 概念介绍。
- 由于报告模板未显式引入 `listings` 宏包，正文中的代码样例使用了可稳定编译的 `verbatim` 形式包裹在带 `caption` 的浮动体中。
- 截图在 LaTeX 章节中通过绝对路径插入，并使用 `\IfFileExists` 做缺失兜底，避免缺图时编译失败。
