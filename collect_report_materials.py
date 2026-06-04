import atexit
import os
import re
import shutil
import socket
import subprocess
import sys
import textwrap
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


ROOT = Path(__file__).resolve().parent
DOCS_DIR = ROOT / "docs"
SCREENSHOT_DIR = DOCS_DIR / "screenshots"
RUNTIME_DIR = DOCS_DIR / "runtime"
MY_BOOKSTORE_DIR = ROOT / "my_Bookstore"
APP_EXE = MY_BOOKSTORE_DIR / "app.exe"
SYSLOG_SCRIPT = ROOT / "syslog_udp_listener.py"
APP_STDOUT = RUNTIME_DIR / "app_stdout.log"
APP_STDERR = RUNTIME_DIR / "app_stderr.log"
SYSLOG_STDOUT = RUNTIME_DIR / "syslog_listener.log"
SYSLOG_STDERR = RUNTIME_DIR / "syslog_listener.err.log"
BASE_URL = "http://127.0.0.1:5000"
CHROME_BINARY = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD_PATH = r"C:\Windows\Fonts\msyhbd.ttc"


def ensure_dirs():
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def kill_stale_processes():
    command = """
$targets = Get-CimInstance Win32_Process | Where-Object {
    ($_.ExecutablePath -eq 'D:\\python\\Bookstore\\Online_Bookstore\\my_Bookstore\\app.exe') -or
    ($_.CommandLine -like '*syslog_udp_listener.py*') -or
    ($_.CommandLine -like '*app_supervisor_alive.flag*')
}
$targets | ForEach-Object {
    try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {}
}
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    time.sleep(2)


def reset_dir(directory: Path):
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True, exist_ok=True)


def wait_for_http_ready(url: str, timeout: int = 90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(1)
    raise TimeoutError(f"{url} did not become ready in {timeout}s")


def wait_for_port(host: str, port: int, timeout: int = 30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            try:
                sock.bind((host, port))
            except OSError:
                time.sleep(0.5)
                continue
            return
    raise TimeoutError(f"UDP {host}:{port} did not become available in {timeout}s")


def http_get(path: str):
    request = urllib.request.Request(f"{BASE_URL}{path}")
    with urllib.request.urlopen(request, timeout=10) as response:
        body = response.read().decode("utf-8", errors="replace")
        headers = dict(response.headers.items())
        return response.status, headers, body


def font(size: int, bold: bool = False):
    return ImageFont.truetype(FONT_BOLD_PATH if bold else FONT_PATH, size=size)


def sanitize_filename(name: str):
    return re.sub(r"[^\w.-]", "_", name)


class FileTail:
    def __init__(self, path: Path):
        self.path = path
        self.offset = 0

    def mark(self):
        self.offset = self.path.stat().st_size if self.path.exists() else 0

    def read_new_lines(self):
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(self.offset)
            content = handle.read()
            self.offset = handle.tell()
        return [line for line in content.splitlines() if line.strip()]

    def read_all_lines(self):
        if not self.path.exists():
            return []
        return self.path.read_text(encoding="utf-8", errors="replace").splitlines()

    def wait_for(self, predicate, timeout=30, min_matches=1):
        deadline = time.time() + timeout
        matches = []
        while time.time() < deadline:
            for line in self.read_new_lines():
                if predicate(line):
                    matches.append(line)
            if len(matches) >= min_matches:
                return matches
            time.sleep(0.5)
        raise TimeoutError(f"Timed out waiting for log patterns in {self.path}")


def wrap_lines(lines, width=110):
    wrapped = []
    for line in lines:
        parts = textwrap.wrap(line, width=width, break_long_words=False, break_on_hyphens=False)
        wrapped.extend(parts or [""])
    return wrapped


def render_terminal_panel(lines, width=1600, title="Terminal", accent="#45d483"):
    content_lines = wrap_lines(lines, width=112)
    padding = 24
    line_height = 28
    height = max(200, 72 + padding * 2 + line_height * len(content_lines))
    image = Image.new("RGB", (width, height), "#101318")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((16, 16, width - 16, height - 16), radius=18, fill="#101318", outline="#2a2f36", width=2)
    draw.text((36, 28), title, font=font(26, bold=True), fill="#f8f8f2")
    draw.ellipse((width - 96, 28, width - 80, 44), fill="#ff5f57")
    draw.ellipse((width - 72, 28, width - 56, 44), fill="#febc2e")
    draw.ellipse((width - 48, 28, width - 32, 44), fill="#28c840")
    y = 76
    mono_font = font(22)
    for line in content_lines:
        fill = accent if "event=" in line or "X-Request-ID" in line else "#d7dde5"
        if "level=ERROR" in line or "traceback" in line:
            fill = "#ff8e8e"
        draw.text((36, y), line, font=mono_font, fill=fill)
        y += line_height
    return image


def render_devtools_panel(headers, path, status_code, request_id):
    width = 1600
    height = 420
    image = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 58), fill="#202124")
    draw.text((24, 16), "Network  >  Headers  >  Response Headers", font=font(28, bold=True), fill="#f1f3f4")
    draw.rectangle((0, 58, width, height), fill="#f7f8fa")
    draw.text((28, 84), f"Request URL: {BASE_URL}{path}", font=font(24, bold=True), fill="#202124")
    draw.text((28, 120), f"Status Code: {status_code}", font=font(22), fill="#202124")
    y = 166
    for key, value in headers.items():
        is_request_id = key.lower() == "x-request-id"
        label_color = "#0b57d0" if is_request_id else "#202124"
        value_color = "#c5221f" if is_request_id else "#3c4043"
        draw.text((40, y), f"{key}:", font=font(22, bold=True), fill=label_color)
        draw.text((280, y), value, font=font(22), fill=value_color)
        y += 34
    draw.text((28, height - 52), f"Matched request_id: {request_id}", font=font(22, bold=True), fill="#c5221f")
    return image


def render_browser_frame(page_image: Image.Image, url: str, title: str):
    width = max(1440, page_image.width + 80)
    top_bar_height = 92
    canvas = Image.new("RGB", (width, page_image.height + top_bar_height + 28), "#f0f2f5")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((20, 12, width - 20, canvas.height - 12), radius=24, fill="#ffffff", outline="#d5d7db", width=2)
    draw.rounded_rectangle((20, 12, width - 20, top_bar_height), radius=24, fill="#f7f8fa", outline="#d5d7db", width=2)
    draw.ellipse((44, 36, 58, 50), fill="#ff5f57")
    draw.ellipse((70, 36, 84, 50), fill="#febc2e")
    draw.ellipse((96, 36, 110, 50), fill="#28c840")
    draw.rounded_rectangle((150, 28, width - 48, 62), radius=18, fill="#ffffff", outline="#c9ccd1", width=2)
    draw.text((170, 32), url, font=font(22), fill="#202124")
    draw.text((32, top_bar_height + 12), title, font=font(22, bold=True), fill="#202124")
    canvas.paste(page_image, (40, top_bar_height + 44))
    return canvas


def compose_vertical(images, output_path: Path, background="#eef1f6", padding=24):
    width = max(image.width for image in images) + padding * 2
    height = sum(image.height for image in images) + padding * (len(images) + 1)
    canvas = Image.new("RGB", (width, height), background)
    y = padding
    for image in images:
        x = (width - image.width) // 2
        canvas.paste(image, (x, y))
        y += image.height + padding
    canvas.save(output_path)


def extract_request_id(log_line: str):
    match = re.search(r"request_id=([^\s]+)", log_line)
    return match.group(1) if match else "-"


def extract_header_subset(headers):
    subset = {}
    for key in ["Content-Type", "Content-Length", "X-Request-ID", "Server", "Date"]:
        if key in headers:
            subset[key] = headers[key]
    for key, value in headers.items():
        if key not in subset and len(subset) < 8:
            subset[key] = value
    return subset


@dataclass
class ScenarioArtifacts:
    request_log: str = ""
    login_success_log: str = ""
    register_success_log: str = ""
    order_success_log: str = ""
    order_item_reserved_log: str = ""
    order_failed_log: str = ""
    orders_query_log: str = ""
    image_lookup_log: str = ""
    syslog_log: str = ""
    request_id_log: str = ""
    request_id_header: str = ""


class ReportCollector:
    def __init__(self):
        self.tempdir = TemporaryDirectory()
        self.temp_path = Path(self.tempdir.name)
        self.processes = []
        self.driver = None
        self.artifacts = ScenarioArtifacts()
        self.username = f"reportuser_{int(time.time())}"
        self.password = "secret123"
        self.stdout_tail = FileTail(APP_STDOUT)
        self.syslog_tail = FileTail(SYSLOG_STDOUT)
        self.app_control_file = RUNTIME_DIR / "app_supervisor_alive.flag"
        self.app_pid_file = RUNTIME_DIR / "app_child.pid"

    def cleanup(self):
        if self.driver is not None:
            self.driver.quit()
            self.driver = None
        self.app_control_file.unlink(missing_ok=True)
        for proc in self.processes:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                pass
        self.tempdir.cleanup()

    def start_processes(self):
        for path in [APP_STDOUT, APP_STDERR, SYSLOG_STDOUT, SYSLOG_STDERR]:
            path.write_text("", encoding="utf-8")
        self.app_pid_file.write_text("", encoding="utf-8")
        self.app_control_file.write_text("alive", encoding="utf-8")

        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq 'D:\\python\\Bookstore\\Online_Bookstore\\my_Bookstore\\app.exe' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

        syslog_out = SYSLOG_STDOUT.open("w", encoding="utf-8")
        syslog_err = SYSLOG_STDERR.open("w", encoding="utf-8")
        listener = subprocess.Popen(
            [sys.executable, str(SYSLOG_SCRIPT)],
            cwd=str(ROOT),
            stdout=syslog_out,
            stderr=syslog_err,
            env=os.environ.copy(),
        )
        self.processes.append(listener)
        wait_for_port("127.0.0.1", 5514, timeout=10)

        ps_script = rf"""
$env:BOOKSTORE_LOG_LEVEL='DEBUG'
$env:BOOKSTORE_LOG_MODE='both'
$env:BOOKSTORE_SYSLOG_HOST='127.0.0.1'
$env:BOOKSTORE_SYSLOG_PORT='5514'
$env:BOOKSTORE_SYSLOG_PROTO='udp'
$env:BOOKSTORE_SYSLOG_FACILITY='local0'
$proc = Start-Process -FilePath '{APP_EXE}' -WorkingDirectory '{MY_BOOKSTORE_DIR}' -RedirectStandardOutput '{APP_STDOUT}' -RedirectStandardError '{APP_STDERR}' -PassThru
Set-Content -LiteralPath '{self.app_pid_file}' -Value $proc.Id
while (Test-Path '{self.app_control_file}') {{ Start-Sleep -Seconds 1 }}
if (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue) {{ Stop-Process -Id $proc.Id -Force }}
"""
        app_supervisor = subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_script])
        self.processes.append(app_supervisor)
        wait_for_http_ready(BASE_URL, timeout=120)
        time.sleep(2)
        self.stdout_tail.mark()
        self.syslog_tail.mark()

    def start_browser(self):
        options = ChromeOptions()
        options.binary_location = CHROME_BINARY
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1600,1800")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--hide-scrollbars")
        self.driver = webdriver.Chrome(options=options)
        self.driver.set_window_size(1600, 1800)

    def wait_books_loaded(self):
        WebDriverWait(self.driver, 30).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "#book-grid .book-card")) > 0
        )

    def save_page_image(self, name: str):
        path = self.temp_path / name
        self.driver.save_screenshot(str(path))
        return Image.open(path).convert("RGB")

    def open_homepage(self):
        self.driver.get(BASE_URL)
        self.wait_books_loaded()
        time.sleep(2)

    def login_or_register_via_modal(self, username, password):
        WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#auth-panel button"))).click()
        WebDriverWait(self.driver, 20).until(EC.visibility_of_element_located((By.ID, "u_name"))).clear()
        self.driver.find_element(By.ID, "u_name").send_keys(username)
        password_box = self.driver.find_element(By.ID, "u_pass")
        password_box.clear()
        password_box.send_keys(password)
        self.driver.find_element(By.CSS_SELECTOR, "#authModal .btn-primary").click()
        WebDriverWait(self.driver, 30).until(
            lambda d: f"你好, {username}" in d.find_element(By.ID, "auth-panel").text
        )
        time.sleep(1)

    def logout(self):
        WebDriverWait(self.driver, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#auth-panel button"))
        ).click()
        WebDriverWait(self.driver, 20).until(
            EC.text_to_be_present_in_element((By.ID, "auth-panel"), "登录/注册")
        )
        time.sleep(1)

    def add_first_book_and_checkout(self):
        add_button = WebDriverWait(self.driver, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#book-grid .book-card button"))
        )
        add_button.click()
        time.sleep(0.5)
        self.driver.find_element(By.CSS_SELECTOR, ".cart-float").click()
        WebDriverWait(self.driver, 20).until(
            EC.visibility_of_element_located((By.ID, "cart-body"))
        )
        self.driver.find_element(By.CSS_SELECTOR, "#cartModal .btn-success").click()
        WebDriverWait(self.driver, 20).until(EC.alert_is_present())
        Alert(self.driver).accept()
        WebDriverWait(self.driver, 30).until(
            lambda d: f"你好, {self.username}" in d.find_element(By.ID, "auth-panel").text
        )
        time.sleep(1)

    def show_orders(self):
        self.driver.execute_script("showMyOrders();")
        WebDriverWait(self.driver, 20).until(
            EC.visibility_of_element_located((By.ID, "order-history"))
        )
        WebDriverWait(self.driver, 20).until(
            lambda d: "订单号" in d.find_element(By.ID, "order-history").text
        )
        time.sleep(1)

    def refresh_for_image_logs(self):
        self.driver.refresh()
        self.wait_books_loaded()
        time.sleep(2)

    def trigger_order_failure(self):
        self.driver.find_element(By.CSS_SELECTOR, "#book-grid .book-card button").click()
        time.sleep(0.5)
        self.driver.execute_script(
            """
            if (state.cart.length > 0) {
                state.cart[0].qty = 99999;
                updateCartBadge();
            }
            showCart();
            """
        )
        WebDriverWait(self.driver, 20).until(
            EC.visibility_of_element_located((By.ID, "cart-body"))
        )
        self.driver.find_element(By.CSS_SELECTOR, "#cartModal .btn-success").click()
        time.sleep(2)

    def capture_homepage(self):
        page = self.save_page_image("homepage.png")
        browser = render_browser_frame(page, BASE_URL, "在线书店首页")
        compose_vertical([browser], SCREENSHOT_DIR / "01_homepage.png")

    def capture_register_success(self):
        self.stdout_tail.mark()
        self.login_or_register_via_modal(self.username, self.password)
        page = self.save_page_image("register_success.png")
        lines = self.stdout_tail.wait_for(
            lambda line: "event=user_register_success" in line and f"user={self.username}" in line,
            timeout=30,
        )
        self.artifacts.register_success_log = lines[-1]
        browser = render_browser_frame(page, BASE_URL, "注册成功后的页面")
        terminal = render_terminal_panel(lines[-3:], title="app.exe Console")
        compose_vertical([browser, terminal], SCREENSHOT_DIR / "03_register_success.png")

    def capture_login_success(self):
        self.logout()
        self.stdout_tail.mark()
        self.login_or_register_via_modal(self.username, self.password)
        page = self.save_page_image("login_success.png")
        lines = self.stdout_tail.wait_for(
            lambda line: "event=user_login_success" in line and f"user={self.username}" in line,
            timeout=30,
        )
        self.artifacts.login_success_log = lines[-1]
        browser = render_browser_frame(page, BASE_URL, "登录成功后的页面")
        terminal = render_terminal_panel(lines[-4:], title="app.exe Console")
        compose_vertical([browser, terminal], SCREENSHOT_DIR / "02_login_success.png")

    def capture_order_success(self):
        self.stdout_tail.mark()
        self.add_first_book_and_checkout()
        page = self.save_page_image("order_success.png")
        lines = self.stdout_tail.wait_for(
            lambda line: "event=order_create_success" in line and f"user={self.username}" in line,
            timeout=30,
        )
        success = lines[-1]
        request_id = extract_request_id(success)
        order_lines = [line for line in self.stdout_tail.read_all_lines() if request_id in line]
        reserved = next(line for line in order_lines if "event=order_item_reserved" in line)
        self.artifacts.order_item_reserved_log = reserved
        self.artifacts.order_success_log = success
        browser = render_browser_frame(page, BASE_URL, "成功下单后的页面")
        terminal = render_terminal_panel([reserved, success], title="app.exe Console")
        compose_vertical([browser, terminal], SCREENSHOT_DIR / "04_order_success.png")

    def capture_my_orders(self):
        self.stdout_tail.mark()
        self.show_orders()
        page = self.save_page_image("my_orders.png")
        lines = self.stdout_tail.wait_for(
            lambda line: "event=orders_query" in line and f"user={self.username}" in line,
            timeout=30,
        )
        self.artifacts.orders_query_log = lines[-1]
        browser = render_browser_frame(page, BASE_URL, "我的订单页面")
        terminal = render_terminal_panel(lines[-3:], title="app.exe Console")
        compose_vertical([browser, terminal], SCREENSHOT_DIR / "05_my_orders.png")

    def capture_image_access(self):
        self.stdout_tail.mark()
        self.refresh_for_image_logs()
        page = self.save_page_image("image_access.png")
        lines = self.stdout_tail.wait_for(
            lambda line: "event=image_lookup" in line,
            timeout=30,
        )
        image_line = lines[-1]
        self.artifacts.image_lookup_log = image_line
        browser = render_browser_frame(page, BASE_URL, "图书封面图片访问")
        terminal = render_terminal_panel([image_line], title="app.exe Console")
        compose_vertical([browser, terminal], SCREENSHOT_DIR / "06_image_access.png")

    def capture_request_id_header(self):
        self.stdout_tail.mark()
        status, headers, _ = http_get("/api/books")
        request_id = headers.get("X-Request-ID", "-")
        lines = self.stdout_tail.wait_for(
            lambda line: "event=http_request_completed" in line and request_id in line,
            timeout=30,
        )
        matched = lines[-1]
        self.artifacts.request_log = matched
        self.artifacts.request_id_log = matched
        self.artifacts.request_id_header = request_id
        page = self.save_page_image("request_id_page.png")
        browser = render_browser_frame(page, BASE_URL, "Request Headers 对照")
        devtools = render_devtools_panel(extract_header_subset(headers), "/api/books", status, request_id)
        terminal = render_terminal_panel([matched], title="app.exe Console")
        compose_vertical([browser, devtools, terminal], SCREENSHOT_DIR / "07_request_id_header.png")

    def capture_syslog_output(self):
        self.syslog_tail.mark()
        status, headers, _ = http_get("/api/books?page=2")
        request_id = headers.get("X-Request-ID", "-")
        lines = self.syslog_tail.wait_for(
            lambda line: "event=http_request_completed" in line and request_id in line,
            timeout=30,
        )
        matched = lines[-1]
        self.artifacts.syslog_log = matched
        terminal = render_terminal_panel(lines[-4:], title="syslog_udp_listener.py")
        compose_vertical([terminal], SCREENSHOT_DIR / "08_syslog_output.png")

    def capture_exception_log(self):
        self.stdout_tail.mark()
        self.trigger_order_failure()
        lines = self.stdout_tail.wait_for(
            lambda line: "event=order_create_failed" in line and f"user={self.username}" in line,
            timeout=30,
        )
        error_line = lines[-1]
        self.artifacts.order_failed_log = error_line
        page = self.save_page_image("order_failure.png")
        browser = render_browser_frame(page, BASE_URL, "库存不足业务异常")
        terminal = render_terminal_panel([error_line], title="app.exe Console")
        compose_vertical([browser, terminal], SCREENSHOT_DIR / "09_exception_log.png")

    def write_log_examples(self):
        content = f"""# 日志样例

以下日志均来自 `my_Bookstore/app.exe` 与 `syslog_udp_listener.py` 的真实运行结果。

## 1. 请求日志

```text
{self.artifacts.request_log}
```

## 2. 登录成功日志

```text
{self.artifacts.login_success_log}
```

## 3. 注册成功日志

```text
{self.artifacts.register_success_log}
```

## 4. 下单成功日志

```text
{self.artifacts.order_item_reserved_log}
{self.artifacts.order_success_log}
```

## 5. 库存不足失败日志

```text
{self.artifacts.order_failed_log}
```

## 6. 图片访问日志

```text
{self.artifacts.image_lookup_log}
```

## 7. syslog日志

```text
{self.artifacts.syslog_log}
```
"""
        (DOCS_DIR / "log_examples.md").write_text(content, encoding="utf-8")

    def write_report_material(self):
        content = """# 在线书店日志系统实验报告素材

## 1. 实验目的

为在线书店系统增加标准日志与 Syslog 支持，使系统在请求处理、用户行为、订单操作、异常故障等场景下都具备可观测性，便于开发调试与运维排障。

## 2. 系统架构

```mermaid
flowchart LR
    Browser[Browser]
    Flask[Flask]
    Logging[Python Logging]
    Syslog[Syslog]
    LogFile[Log File]

    Browser --> Flask
    Flask --> Logging
    Logging --> Syslog
    Logging --> LogFile
```

说明：

- `Browser` 发起页面访问、接口请求和用户操作。
- `Flask` 负责业务处理，并在请求生命周期与业务动作中调用日志记录。
- `Python Logging` 统一格式化日志、补充请求上下文并分发到不同输出目标。
- `Syslog` 用于集中式日志接收，便于后续主机级运维或日志平台采集。
- `Log File` 代表实验采集阶段归档的控制台/运行日志文件，用于样例整理与报告编写。

## 3. 日志设计

### request_id

- 每个 HTTP 请求在 `before_request` 阶段生成唯一 `request_id`。
- `request_id` 会写入结构化日志，同时通过响应头 `X-Request-ID` 返回给前端。
- 这样可以将浏览器请求、控制台日志、syslog 消息串联到同一条调用链。

### before_request

- 在请求开始时记录起始时间。
- 初始化 `request_id`、默认用户、状态码和时延字段。
- 为后续 `after_request`、`teardown_request` 统一补齐上下文。

### after_request

- 在请求结束时计算 `duration_ms`。
- 根据状态码区分日志级别：
  - `<400` 记为 `INFO`
  - `>=400` 记为 `WARNING`
  - `>=500` 记为 `ERROR`
- 同时在响应头写入 `X-Request-ID`。

### teardown_request

- 负责兜底记录未捕获异常。
- 异常日志中保留 `request_id`、请求路径、用户、`traceback` 等关键信息。
- 即使业务异常被返回为 JSON，也能在日志中完整保留错误现场。

### SysLogHandler

- 使用 `logging.handlers.SysLogHandler` 将日志发送到 `127.0.0.1:5514/udp`。
- 支持通过环境变量配置 `host`、`port`、`proto`、`facility`。
- 与控制台输出并行工作，适合本地调试和后续集中收集。

## 4. 功能实现

### 登录日志

- 登录成功记录 `event=user_login_success`
- 登录失败记录 `event=user_login_failed`

### 注册日志

- 注册成功记录 `event=user_register_success`
- 用户名冲突记录 `event=user_register_conflict`

### 下单日志

- 下单成功记录 `event=order_create_success`
- 每本书库存扣减记录 `event=order_item_reserved`

### 查询日志

- 查询我的订单记录 `event=orders_query`
- 普通接口请求统一记录 `event=http_request_completed`

### 图片访问日志

- 图片资源访问记录 `event=image_lookup`

### 异常日志

- 库存不足等业务异常记录 `event=order_create_failed`
- 异常日志包含 `level=ERROR`、`request_id`、`traceback`

## 5. 运行结果

### 01 首页

![01_homepage](screenshots/01_homepage.png)

### 02 登录成功

![02_login_success](screenshots/02_login_success.png)

### 03 注册成功

![03_register_success](screenshots/03_register_success.png)

### 04 下单成功

![04_order_success](screenshots/04_order_success.png)

### 05 我的订单

![05_my_orders](screenshots/05_my_orders.png)

### 06 图片访问

![06_image_access](screenshots/06_image_access.png)

### 07 Request ID 响应头

![07_request_id_header](screenshots/07_request_id_header.png)

### 08 Syslog 输出

![08_syslog_output](screenshots/08_syslog_output.png)

### 09 异常日志

![09_exception_log](screenshots/09_exception_log.png)

## 6. 日志示例分析

### 通用字段

- `ts`：日志时间戳。
- `level`：日志级别，如 `INFO`、`DEBUG`、`WARNING`、`ERROR`。
- `app`：应用名，固定为 `online_bookstore`。
- `logger`：记录日志的 logger 名称。
- `event`：事件类型，用于区分请求、登录、订单、异常等场景。
- `request_id`：请求唯一标识，用于链路追踪。
- `method`：HTTP 方法，如 `GET`、`POST`。
- `path`：请求路径。
- `status`：HTTP 状态码。
- `duration_ms`：请求处理耗时，单位毫秒。
- `user`：当前用户标识；匿名请求为 `-`。
- `client_ip`：客户端 IP 地址。
- `message`：日志摘要信息。

### 业务扩展字段

- `order_id`：订单编号。
- `item_count`：订单项数量。
- `total_amount`：订单总金额。
- `book_id` / `book_title` / `quantity`：库存预占对应的图书信息。
- `image_name` / `image_path`：图片访问的资源信息。
- `traceback`：异常调用栈，用于快速定位故障原因。

### 分析价值

- 请求日志能快速定位慢请求、404、500 等问题。
- 用户行为日志可以审计登录与注册动作。
- 订单日志能追踪下单流程和库存扣减过程。
- 异常日志为问题复现和排查提供直接证据。
- `request_id` 将浏览器端和服务端日志联通，提高故障定位效率。

## 7. 实验结论

本实验基于 Python 标准日志体系完成了在线书店的结构化运行日志建设，实现了控制台与 Syslog 双通道输出，并通过 `request_id` 将请求链路、用户行为、订单过程和异常信息统一串联。实验结果表明，系统的可观测性得到明显提升：开发者能够从日志中快速还原一次业务操作的完整路径，运维人员也可以借助 Syslog 对日志进行集中收集和后续分析，为线上排障和运行维护提供了可靠基础。
"""
        (DOCS_DIR / "logging_report_material.md").write_text(content, encoding="utf-8")

    def run(self):
        kill_stale_processes()
        ensure_dirs()
        reset_dir(SCREENSHOT_DIR)
        reset_dir(RUNTIME_DIR)
        self.start_processes()
        self.start_browser()
        self.open_homepage()
        self.capture_homepage()
        self.capture_register_success()
        self.capture_login_success()
        self.capture_order_success()
        self.capture_my_orders()
        self.capture_image_access()
        self.capture_request_id_header()
        self.capture_syslog_output()
        self.capture_exception_log()
        self.write_log_examples()
        self.write_report_material()


def main():
    collector = ReportCollector()
    atexit.register(collector.cleanup)
    try:
        collector.run()
    finally:
        collector.cleanup()


if __name__ == "__main__":
    main()
