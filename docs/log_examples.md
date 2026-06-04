# ????

??????? `my_Bookstore/app.exe` ? `syslog_udp_listener.py` ????????

## 1. ????

```text
ts=2026-06-04T13:38:09 level=INFO app=online_bookstore logger=online_bookstore event=http_request_completed request_id=f3520b3e0422 method=GET path=/api/books status=200 duration_ms=8 user=- client_ip=127.0.0.1 message=request_completed
```

## 2. ??????

```text
ts=2026-06-04T13:38:09 level=INFO app=online_bookstore logger=online_bookstore event=user_login_success request_id=ba62fda67233 method=POST path=/api/login status=- duration_ms=- user=reportuser_1780550963 client_ip=127.0.0.1 message=user_logged_in
```

## 3. ??????

```text
ts=2026-06-04T13:29:39 level=INFO app=online_bookstore logger=online_bookstore event=user_register_success request_id=16aa09587eeb method=POST path=/api/register status=- duration_ms=- user=reportuser_1780550963 client_ip=127.0.0.1 message=user_registered
```

## 4. ??????

```text
ts=2026-06-04T13:29:46 level=DEBUG app=online_bookstore logger=online_bookstore event=order_item_reserved request_id=a44f9785da2c method=POST path=/api/order status=- duration_ms=- user=reportuser_1780550963 client_ip=127.0.0.1 message=order_item_reserved book_id=1 book_title=Python��̡��������ŵ�ʵ�� order_id=6 quantity=1
ts=2026-06-04T13:29:46 level=INFO app=online_bookstore logger=online_bookstore event=order_create_success request_id=a44f9785da2c method=POST path=/api/order status=- duration_ms=- user=reportuser_1780550963 client_ip=127.0.0.1 message=order_created item_count=1 order_id=6 total_amount=76.2
```

## 5. ????????

```text
ts=2026-06-04T13:38:09 level=ERROR app=online_bookstore logger=online_bookstore event=order_create_failed request_id=e529453bcd24 method=POST path=/api/order status=- duration_ms=- user=reportuser_1780550963 client_ip=127.0.0.1 message=order_create_failed item_count=1 traceback="Traceback (most recent call last):\n  File \"app.py\", line 458, in create_order\nException: Python��̡��������ŵ�ʵ�� ��治��"
```

## 6. ??????

```text
ts=2026-06-04T13:37:16 level=DEBUG app=online_bookstore logger=online_bookstore event=image_lookup request_id=c8267b580967 method=GET path=/images/ǹ�ڡ����������.jpg status=- duration_ms=- user=- client_ip=127.0.0.1 message=image_requested image_name=ǹ�ڡ����������.jpg image_path=D:\\python\\Bookstore\\Online_Bookstore\\my_Bookstore\\images\\ǹ�ڡ����������.jpg
```

## 7. syslog??

```text
2026-06-04 13:29:50 from=127.0.0.1:62556 <134>online-bookstore level=INFO app=online_bookstore logger=online_bookstore event=http_request_completed request_id=7b00ec0e864a method=GET path=/api/books status=200 duration_ms=13 user=- client_ip=127.0.0.1 message=request_completed
```
