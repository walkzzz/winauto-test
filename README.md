# WinAuto Test Framework

## 项目概述

WinAuto Test Framework 是一个基于 pywinauto 的 Windows 应用自动化测试框架，提供了简单易用、功能强大的 API，用于自动化 Windows 桌面应用的测试。

### 核心优势

- **简单易用**: 提供简洁的 API，降低自动化测试门槛
- **强大的控件查找**: 支持多种匹配策略和自适应搜索深度
- **灵活的测试生成**: 支持 YAML 配置驱动的测试生成
- **丰富的控件操作**: 支持各种常见控件的操作和验证
- **集成 Allure 报告**: 生成美观、详细的测试报告
- **良好的可扩展性**: 易于扩展和定制，适应不同项目需求

## 安装说明

### 环境要求

- Python 3.7+
- Windows 操作系统
- pywinauto 依赖

### 安装步骤

1. 克隆或下载项目代码

2. 安装依赖包

```bash
pip install -r requirements.txt
```

3. （可选）安装 Allure 命令行工具以生成测试报告

## 快速开始

### 基本使用示例

```python
from winauto_helper import WinAuto

# 创建 WinAuto 实例
bot = WinAuto(r"D:\Program Files\YourApp\app.exe")

# 启动应用
bot.start()

# 获取窗口
login_window = bot.get_window(class_name='LoginDialog')

# 查找控件并操作
account_edit = bot.by_index(login_window, 'Edit0')
bot.input_text(account_edit, "username")

password_edit = bot.by_index(login_window, 'Edit1')
bot.input_text(password_edit, "password")

login_btn = bot.by_index(login_window, '登 录Button')
bot.click_ctrl(login_btn)

# 关闭应用
bot.close_app()
```

## 主要功能

### 1. 应用管理

- 启动应用
- 连接到已运行的应用
- 关闭应用

### 2. 窗口操作

- 获取窗口
- 获取顶层窗口
- 关闭窗口
- 最大化/最小化/恢复窗口
- 设置窗口焦点
- 获取窗口文本

### 3. 控件查找

- **find_control**: 通用控件检索函数，支持多种匹配策略
  - 支持按标题、类名、控件类型、自动化ID查找
  - 多种匹配策略：精确匹配、模糊匹配、正则匹配
  - 支持最佳匹配和自适应搜索深度
  - 详细的调试日志支持

- **by_index**: 使用 pywinauto 索引串直接定位控件

### 4. 控件交互

- 获取控件文本
- 输入文本
- 清空文本
- 点击控件
- 选择列表项
- 等待控件可见/启用

### 5. 截图功能

- 支持截取整个桌面、窗口或控件
- 支持保存到指定路径或返回 PIL.Image 对象
- 自动附加到 Allure 报告

### 6. 测试生成

- 支持 YAML 配置驱动的测试生成
- 动态执行测试步骤
- 支持步骤结果保存和引用
- 集成 Allure 报告

## API 参考

### WinAuto 类

#### 构造函数

```python
def __init__(self, exec_path: str = "", *, backend: str = "uia", poll_interval: float = 0.2)
```

**参数**:
- `exec_path`: 应用程序执行路径
- `backend`: 使用的 pywinauto 后端，默认为 "uia"
- `poll_interval`: 轮询间隔，默认为 0.2 秒

#### 核心方法

##### find_control

```python
def find_control(self, parent, *, title=None, class_name=None, control_type=None, auto_id=None, depth=10, timeout=5, match_strategy="exact", best_match=False, match_threshold=0.7, adaptive_depth=True, max_depth=20, enable_debug_log=False)
```

**功能**: 通用控件检索函数，支持多种匹配策略和自适应搜索深度

**参数**:
- `parent`: 父控件或应用对象
- `title`: 控件标题文本
- `class_name`: 控件类名
- `control_type`: 控件类型
- `auto_id`: 自动化ID
- `depth`: 初始搜索深度，默认 10
- `timeout`: 搜索超时时间，默认 5 秒
- `match_strategy`: 匹配策略，可选值："exact"（精确匹配）、"fuzzy"（模糊匹配）、"regex"（正则匹配）
- `best_match`: 是否返回最佳匹配结果，默认 False
- `match_threshold`: 模糊匹配阈值，默认 0.7
- `adaptive_depth`: 是否启用深度自适应，默认 True
- `max_depth`: 最大搜索深度，默认 20
- `enable_debug_log`: 是否启用调试日志，默认 False

**返回值**:
- 找到的控件对象，未找到返回 None

##### by_index

```python
def by_index(self, parent, best_match: str, timeout: float = 5)
```

**功能**: 使用 pywinauto 索引串直接定位控件

**参数**:
- `parent`: 父控件或应用对象
- `best_match`: pywinauto 索引串，如 'Edit0'、'登 录Button'
- `timeout`: 查找超时时间，默认 5 秒

**返回值**:
- 找到的控件对象，未找到返回 None

##### 其他常用方法

- `start(exec_path)`: 启动应用
- `connect(**connect_kwargs)`: 连接到已运行的应用
- `get_window(title=None, class_name=None, best_match=None, timeout=5)`: 获取窗口
- `input_text(ctrl, text, clear=True)`: 输入文本
- `click_ctrl(ctrl, method="auto", timeout=5)`: 点击控件
- `screenshot(target=None, filename=None, return_image=False, allure_attach=True, allure_name="Screenshot")`: 截图

## YAML 测试配置

### 测试用例结构

```yaml
case_id: TEST_001
case_name: 登录测试
description: 测试正常登录流程
priority: high
epic: 登录模块
feature: 登录功能
story: 正常登录流程
steps:
  - action: start
    params:
      exec_path: "D:\Program Files\YourApp\app.exe"
    save_as: app
  - action: get_window
    params:
      class_name: "LoginDialog"
    save_as: login_win
  - action: by_index
    params:
      parent: $login_win
      best_match: "Edit0"
    save_as: account_edit
  - action: input_text
    params:
      ctrl: $account_edit
      text: "username"
  - action: by_index
    params:
      parent: $login_win
      best_match: "Edit1"
    save_as: password_edit
  - action: input_text
    params:
      ctrl: $password_edit
      text: "password"
  - action: by_index
    params:
      parent: $login_win
      best_match: "登 录Button"
    save_as: login_btn
  - action: click_ctrl
    params:
      ctrl: $login_btn
```

## 运行测试

### 运行所有测试

```bash
python run_tests.py
```

### 查看测试报告

测试运行完成后，将在 `reports` 目录生成 HTML 报告。如果安装了 Allure 命令行工具，还将生成 Allure 报告。

## 项目结构

```
.
├── pages/              # 页面类目录
│   ├── __init__.py
│   └── login_page.py
├── test_cases/         # 测试用例目录
│   ├── login_data_matrix.yaml
│   └── login_test.yaml
├── tests/              # 测试执行目录
│   ├── __init__.py
│   └── test_auto.py
├── utils/              # 工具类目录
│   ├── __init__.py
│   ├── data_matrix_handler.py
│   ├── test_generator.py
│   └── yaml_loader.py
├── .gitignore
├── conftest.py
├── pytest.ini
├── requirements.txt
├── run_tests.py
└── winauto_helper.py   # 核心功能实现
```

## 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 联系方式

如有问题或建议，请通过以下方式联系：

- 项目地址：https://github.com/yourusername/winauto-test-framework
- 问题反馈：https://github.com/yourusername/winauto-test-framework/issues

## 更新日志

### v1.0.0

- 初始版本发布
- 实现核心自动化功能
- 支持 YAML 测试配置
- 集成 Allure 报告

### v1.1.0

- 增强 `find_control` 函数，支持多种匹配策略
- 添加自适应搜索深度功能
- 完善文档和示例
- 优化代码结构和性能
