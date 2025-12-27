# winauto_helper.py
import time
import logging
import functools
import importlib
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Union
from pywinauto.timings import TimeoutError as PyWinTimeoutError
from pywinauto import Application, ElementNotFoundError
from pywinauto.base_wrapper import BaseWrapper, ElementNotEnabled, ElementNotVisible
from pywinauto.application import WindowSpecification
from typing import Tuple, Literal
from PIL import Image, ImageGrab

# Allure 集成
try:
    import allure
    ALLURE_AVAILABLE = True
except ImportError:
    ALLURE_AVAILABLE = False

# -------------- 日志 --------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s %(levelname)s | %(message)s"
)


# 常用可抛异常白名单
_PYWIN_EXCEPTIONS = (
    AttributeError,
    NotImplementedError,
    ElementNotFoundError,
    ElementNotEnabled,
    ElementNotVisible,
    PyWinTimeoutError,
)


# -------------- 装饰器 --------------
def dump_ctrl_tree(func):
    @functools.wraps(func)
    def _wrapper(*args, **kwargs):
        ctrl = func(*args, **kwargs)
        if isinstance(ctrl, (WindowSpecification, BaseWrapper)):
            # 获取窗口名称
            window_name = ""
            try:
                if isinstance(ctrl, BaseWrapper):
                    window_name = ctrl.window_text()
                else:  # WindowSpecification
                    window_name = ctrl.wrapper_object().window_text()
            except Exception as e:
                window_name = "(获取窗口名称失败)"
            
            print(f"\n>>> 控件树来自 {func.__name__} - 窗口: {window_name} >>>")
            ctrl.print_control_identifiers()
        else:
            print(f"[W] {func.__name__} 返回的不是控件对象，跳过打印")
        return ctrl

    return _wrapper


# -------------- 后端兼容工具函数 --------------
def _safe_call(obj: Any, attr: str, *a, **k):
    """安全调用对象方法/属性；不存在返回 None，调用异常返回 False"""
    if not hasattr(obj, attr):
        return None
    try:
        return getattr(obj, attr)(*a, **k)
    except _PYWIN_EXCEPTIONS:
        return False


def _safe_get(obj: Any, attr: str):
    """安全获取属性；不存在返回空串"""
    return getattr(obj, attr, "") or ""


# -------------- 主类：WinAuto --------------
class WinAuto:
    def __init__(self,
                 exec_path: str = "",
                 *,
                 backend: str = "uia",
                 poll_interval: float = 0.2):
        self.exec_path = exec_path
        self.backend = backend
        self.poll_interval = poll_interval
        self.app: Optional[Application] = None
        self.logger = logging.getLogger(self.__class__.__name__)

    # ------ 启动 / 连接 ------
    def start(self, exec_path: Optional[str] = None) -> Optional[Application]:
        try:
            # 如果提供了新的执行路径，更新实例属性
            if exec_path:
                self.exec_path = exec_path
            
            # 验证执行路径
            if not self.exec_path:
                self.logger.error("应用启动失败：执行路径为空")
                return None
                
            self.app = Application(backend=self.backend).start(self.exec_path)
            self.logger.info("应用启动成功：%s", self.exec_path)
            return self.app
        except Exception as exc:
            self.logger.error("应用启动失败：%s", exc)
            return None

    def connect(self, **connect_kwargs) -> Optional[Application]:
        try:
            self.app = Application(backend=self.backend).connect(**connect_kwargs)
            self.logger.info("连接到已存在进程：%s", connect_kwargs)
            return self.app
        except Exception as exc:
            self.logger.error("连接失败：%s", exc)
            return None

    # ------ 获取窗口 ------
    @dump_ctrl_tree
    def get_window(self,
                   *,
                   title: Optional[str] = None,
                   class_name: Optional[str] = None,
                   best_match: Optional[str] = None,
                   timeout: float = 5) -> Optional[WindowSpecification]:
        if not any((title, class_name, best_match)):
            self.logger.warning("get_window 未提供任何过滤条件")
            return None
        if self.app is None:
            self.logger.error("Application 未初始化，请先 start / connect")
            return None

        elapsed = 0.0
        while True:
            try:
                # 打印所有可用窗口信息，用于调试
                self.logger.info("正在查找窗口，尝试获取所有可用窗口...")
                windows = self.app.windows()
                self.logger.info(f"当前可用窗口数量: {len(windows)}")
                for i, win in enumerate(windows):
                    try:
                        win_info = {
                            'title': win.window_text(),
                            'class_name': win.class_name(),
                            'handle': win.handle
                        }
                        self.logger.info(f"窗口 {i}: {win_info}")
                    except Exception as e:
                        self.logger.warning(f"获取窗口信息失败: {e}")

                # 尝试查找目标窗口 - 正确的方法是使用 self.app.window() 而不是 child_window
                self.logger.info("尝试使用 self.app.window() 查找目标窗口...")
                if title:
                    win = self.app.window(title=title)
                    self.logger.info(f"尝试查找 title='{title}' 的窗口")
                elif class_name:
                    win = self.app.window(class_name=class_name)
                    self.logger.info(f"尝试查找 class_name='{class_name}' 的窗口")
                else:
                    win = self.app.window(best_match=best_match)
                    self.logger.info(f"尝试查找 best_match='{best_match}' 的窗口")

                # 检查窗口是否存在
                if win.exists(timeout=0.5):
                    self.logger.info("找到目标窗口！")
                    return win
                else:
                    self.logger.info("目标窗口不存在，继续等待...")
            except _PYWIN_EXCEPTIONS as e:
                self.logger.warning(f"窗口查找异常: {e}")
            except Exception as e:
                self.logger.error(f"意外异常: {e}")

            if elapsed >= timeout:
                self.logger.error(f"窗口查找超时，尝试了 {timeout} 秒")
                return None
            time.sleep(self.poll_interval)
            elapsed += self.poll_interval

    # @dump_ctrl_tree # 调试用，打印控件树
    def get_top_window(self) -> Optional[WindowSpecification]:
        """获取应用程序顶层窗口"""
        if self.app is None:
            self.logger.error("Application 未初始化，请先 start / connect")
            return None
        try:
            win = self.app.top_window()
            self.logger.info("获取顶层窗口成功")
            return win
        except _PYWIN_EXCEPTIONS:
            self.logger.error("获取顶层窗口失败")
            return None

    # ------ 窗口操作 ------
    def close_app(self) -> bool:
        """关闭应用程序"""
        if self.app is None:
            self.logger.warning("未连接到应用程序，无需关闭")
            return False
        try:
            self.app.kill()
            self.app = None
            self.logger.info("应用程序关闭成功")
            return True
        except _PYWIN_EXCEPTIONS:
            self.logger.error("关闭应用程序失败")
            return False

    def close_window(self, win: Optional[WindowSpecification] = None) -> bool:
        """关闭指定窗口，默认关闭当前get_window获取的窗口"""
        if win is None:
            self.logger.error("close_window: 未提供窗口对象")
            return False
        try:
            win.close()
            self.logger.info("窗口关闭成功")
            return True
        except _PYWIN_EXCEPTIONS:
            self.logger.error("关闭窗口失败")
            return False

    def maximize_window(self, win: Optional[WindowSpecification] = None) -> bool:
        """最大化窗口"""
        if win is None:
            self.logger.error("maximize_window: 未提供窗口对象")
            return False
        return _safe_call(win, "maximize") is not False

    def minimize_window(self, win: Optional[WindowSpecification] = None) -> bool:
        """最小化窗口"""
        if win is None:
            self.logger.error("minimize_window: 未提供窗口对象")
            return False
        return _safe_call(win, "minimize") is not False

    def restore_window(self, win: Optional[WindowSpecification] = None) -> bool:
        """恢复窗口（从最小化/最大化状态恢复）"""
        if win is None:
            self.logger.error("restore_window: 未提供窗口对象")
            return False
        return _safe_call(win, "restore") is not False

    def set_focus(self, win: Optional[WindowSpecification] = None) -> bool:
        """设置窗口焦点"""
        if win is None:
            self.logger.error("set_focus: 未提供窗口对象")
            return False
        return _safe_call(win, "set_focus") is not False

    def get_window_text(self, win: Optional[WindowSpecification] = None) -> str:
        """获取窗口标题文本"""
        if win is None:
            self.logger.error("get_window_text: 未提供窗口对象")
            return ""
        text = _safe_get(win.wrapper_object(), "window_text") if isinstance(win, WindowSpecification) else _safe_get(win, "window_text")
        return text or ""

    # ------ 通用控件检索 ------
    def find_control(self,
                     parent: Union[Application, WindowSpecification, BaseWrapper],
                     *,
                     title: Optional[str] = None,
                     class_name: Optional[str] = None,
                     control_type: Optional[str] = None,
                     auto_id: Optional[str] = None,
                     depth: int = 3,
                     timeout: float = 5) -> Optional[BaseWrapper]:
        if parent is None:
            self.logger.error("parent 为 None，无法检索控件")
            return None

        # 统一转成 BaseWrapper
        if isinstance(parent, Application):
            parent = parent.child_window(found_index=0)
        if isinstance(parent, WindowSpecification):
            parent = parent.wrapper_object()

        def _match(ctrl: BaseWrapper) -> bool:
            if title and title.lower() not in _safe_get(ctrl, "window_text").lower():
                return False
            if class_name and class_name.lower() != _safe_get(ctrl, "friendly_class_name").lower():
                return False
            # control_type 可能来自 element_info.control_type 或 control_type()
            ct = _safe_get(ctrl.element_info, "control_type") or _safe_call(ctrl, "control_type") or ""
            if control_type and control_type.lower() != ct.lower():
                return False
            aid = _safe_get(ctrl.element_info, "automation_id") or _safe_call(ctrl, "automation_id") or ""
            if auto_id and auto_id != aid:
                return False
            return True

        elapsed = 0.0
        while True:
            dq = deque([(parent, 0)])
            while dq:
                cur, lvl = dq.popleft()
                if lvl > depth:
                    continue
                try:
                    if _match(cur):
                        self.logger.info("控件已找到：%s", cur)
                        return cur
                    for child in cur.children():
                        dq.append((child, lvl + 1))
                except _PYWIN_EXCEPTIONS:
                    continue

            if elapsed >= timeout:
                self.logger.warning("查找控件超时（%ss）", timeout)
                return None
            time.sleep(self.poll_interval)
            elapsed += self.poll_interval

    # ------ 控件交互 ------
    def get_text(self, ctrl: BaseWrapper) -> str:
        """获取控件文本"""
        if ctrl is None:
            self.logger.error("get_text: 控件为 None")
            return ""
        text = _safe_get(ctrl, "window_text")
        self.logger.info("获取控件文本: %s", text)
        return text

    def select_item(self, ctrl: BaseWrapper, item: Union[str, int], by: Literal['text', 'index'] = 'text') -> bool:
        """选择列表/下拉框中的项"""
        if ctrl is None:
            self.logger.error("select_item: 控件为 None")
            return False
        
        try:
            if by == 'text':
                ctrl.select(item)
            elif by == 'index':
                ctrl.select(index=item)
            else:
                self.logger.error("select_item: 不支持的by参数: %s", by)
                return False
            self.logger.info("项选择成功: %s", item)
            return True
        except _PYWIN_EXCEPTIONS:
            self.logger.error("选择项失败")
            return False

    def input_text(self, ctrl: BaseWrapper, text: str, clear: bool = True) -> bool:
        """通用输入封装：先可选清空，再输入字符串"""
        if ctrl is None:
            self.logger.error("input_text: 控件为 None")
            return False
        try:
            if clear:
                ctrl.type_keys('^a{DELETE}')  # Ctrl+A 再 Delete 清空
            ctrl.type_keys(text, with_spaces=True)
            self.logger.info("已输入文本：%s", text)
            return True
        except _PYWIN_EXCEPTIONS:
            self.logger.exception("输入失败")
            return False

    def clear_text(self, ctrl: BaseWrapper) -> bool:
        """清空控件文本"""
        if ctrl is None:
            self.logger.error("clear_text: 控件为 None")
            return False
        try:
            ctrl.type_keys('^a{DELETE}')  # Ctrl+A 再 Delete 清空
            self.logger.info("已清空文本")
            return True
        except _PYWIN_EXCEPTIONS:
            self.logger.exception("清空文本失败")
            return False

    # ------ 点击操作 ------
    def click0(self, ctrl: BaseWrapper) -> bool:
        """零警告通用点击"""
        if ctrl is None:
            self.logger.error("click0: 控件为 None")
            return False

        # 1. 优先 invoke
        res = _safe_call(ctrl, "invoke")
        if res is not None and res is not False:
            self.logger.info("invoke 点击成功：%s", ctrl)
            return True

        # 2. 判断按钮类名/类型后 click
        class_name = _safe_get(ctrl.element_info, "class_name").lower()
        control_type = (_safe_get(ctrl.element_info, "control_type") or
                        _safe_call(ctrl, "control_type") or "").lower()
        if class_name == "button" or control_type == "button":
            res = _safe_call(ctrl, "click")
            if res is not None and res is not False:
                self.logger.info("click 成功：%s", ctrl)
                return True

        # 3. 兜底 click_input
        res = _safe_call(ctrl, "click_input")
        if res is not None and res is not False:
            self.logger.info("click_input 成功：%s", ctrl)
            return True

        self.logger.error("所有点击方式均失败：%s", ctrl)
        return False

    def click_ctrl(self,
                   ctrl: BaseWrapper,
                   *,
                   method: Literal["invoke", "click", "click_input"] = "auto",
                   timeout: float = 5) -> bool:
        """
        通用控件点击
        method = auto   : 先 invoke → 再 click → 再 click_input 直到成功
               = invoke/click/click_input : 强制指定
        返回 True/False
        """
        if ctrl is None:
            self.logger.error("click_ctrl: 控件为 None")
            return False

        # 自动模式：按成功率从高到低尝试
        if method == "auto":
            for m in ("invoke", "click", "click_input"):
                if _safe_call(ctrl, m):
                    self.logger.info("%s 点击成功：%s", m, ctrl)
                    return True
            self.logger.error("所有点击方式失败：%s", ctrl)
            return False

        # 强制指定模式
        ok = _safe_call(ctrl, method)
        if ok:
            self.logger.info("%s 点击成功：%s", method, ctrl)
        else:
            self.logger.error("%s 点击失败：%s", method, ctrl)
        return bool(ok)

    def by_index(self,
                 parent: Union[Application, WindowSpecification],
                 best_match: str,
                 timeout: float = 5) -> Optional[BaseWrapper]:
        """用 pywinauto 索引串（如 'Edit0'、'Edit2'、'登 录Button'）直接定位"""
        if parent is None:
            self.logger.error("by_index: parent 为 None")
            return None
        
        try:
            self.logger.info(f"开始 by_index 查找: best_match='{best_match}', parent类型={type(parent).__name__}")
            
            # 如果 parent 是 Application 对象，尝试获取主窗口
            if isinstance(parent, Application):
                self.logger.info("parent 是 Application 对象，获取主窗口")
                parent = parent.window()
            
            # 激活父窗口
            if isinstance(parent, WindowSpecification):
                parent.set_focus()
                self.logger.info("已激活父窗口")
            
            # 尝试多种查找方式
            for search_mode in ['best_match', 'title']:
                try:
                    if search_mode == 'best_match':
                        self.logger.info(f"尝试查找: child_window(best_match='{best_match}')")
                        ctrl = parent.child_window(best_match=best_match)
                    else:
                        self.logger.info(f"尝试查找: child_window(title='{best_match}')")
                        ctrl = parent.child_window(title=best_match)
                    
                    if ctrl.exists(timeout=1):
                        self.logger.info(f"找到控件，等待就绪...")
                        if ctrl.wait('ready', timeout=timeout):
                            wrapper = ctrl.wrapper_object()
                            self.logger.info(f"控件查找成功: {wrapper}")
                            return wrapper
                except _PYWIN_EXCEPTIONS as e:
                    self.logger.warning(f"{search_mode} 查找失败: {e}")
        
        except _PYWIN_EXCEPTIONS as e:
            self.logger.error(f"by_index 执行异常: {e}")
        
        self.logger.error(f"by_index 最终查找失败: {best_match}")
        return None

    # ------ 等待机制 ------
    def wait_until_visible(self, ctrl: BaseWrapper, timeout: float = 10) -> bool:
        """等待控件可见"""
        if ctrl is None:
            self.logger.error("wait_until_visible: 控件为 None")
            return False
        try:
            ctrl.wait('visible', timeout=timeout)
            self.logger.info("控件已可见")
            return True
        except _PYWIN_EXCEPTIONS:
            self.logger.error("等待控件可见失败")
            return False

    def wait_until_enabled(self, ctrl: BaseWrapper, timeout: float = 10) -> bool:
        """等待控件启用"""
        if ctrl is None:
            self.logger.error("wait_until_enabled: 控件为 None")
            return False
        try:
            ctrl.wait('enabled', timeout=timeout)
            self.logger.info("控件已启用")
            return True
        except _PYWIN_EXCEPTIONS:
            self.logger.error("等待控件启用失败")
            return False

    def wait_until_active(self, win: Optional[WindowSpecification] = None, timeout: float = 10) -> bool:
        """等待窗口激活"""
        if win is None:
            self.logger.error("wait_until_active: 未提供窗口对象")
            return False
        try:
            win.wait('active', timeout=timeout)
            self.logger.info("窗口已激活")
            return True
        except _PYWIN_EXCEPTIONS:
            self.logger.error("等待窗口激活失败")
            return False

    # ------ 截图 ------
    def screenshot(self,
                   target: Optional[Union[BaseWrapper, WindowSpecification, Tuple[int, int, int, int]]] = None,
                   *,
                   filename: Optional[Union[str, Path]] = None,
                   return_image: bool = False,
                   allure_attach: bool = True,  # 是否附加到 Allure 报告
                   allure_name: str = "Screenshot") -> Optional[Union[str, Image.Image]]:
        """
        截图封装
        参数
        ----
        target :  None                -> 截整个桌面
                  WindowSpecification -> 截对应窗口（含边框）
                  BaseWrapper         -> 截控件本身
                  (x, y, w, h)        -> 截指定矩形区域
        filename : 保存路径，None 则自动生成文件名（当前目录）
        return_image : True 返回 PIL.Image；False 返回保存路径
        allure_attach : 是否将截图附加到 Allure 报告
        allure_name : Allure 报告中截图的名称
        返回
        ----
        保存路径 或 Image 对象；失败返回 None
        """
        try:
            # 1. 决定保存路径
            if not filename:
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                filename = f"shot_{stamp}.png"

            path = Path(filename).resolve()

            # 2. 截取逻辑
            if target is None:
                # 全屏
                ImageGrab.grab().save(path)
            elif isinstance(target, (WindowSpecification, BaseWrapper)):
                # 窗口或控件
                if isinstance(target, WindowSpecification):
                    target = target.wrapper_object()
                target.capture_as_image().save(str(path))
            elif isinstance(target, tuple) and len(target) == 4:
                # 矩形区域 (x, y, w, h)
                x, y, w, h = target
                ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(path)
            else:
                self.logger.error("screenshot: target 类型不支持")
                return None

            # 3. 附加到 Allure 报告
            if allure_attach and ALLURE_AVAILABLE:
                import allure
                try:
                    allure.attach.file(
                        str(path),
                        name=allure_name,
                        attachment_type=allure.attachment_type.PNG
                    )
                    self.logger.info("截图已附加到 Allure 报告: %s", path)
                except Exception as e:
                    self.logger.warning("附加截图到 Allure 报告失败: %s", e)

            # 4. 返回需求
            if return_image and Image is not None:
                return Image.open(path)
            return str(path)

        except Exception as e:
            self.logger.error("截图失败：%s", e)
            return None

    # ------ 动态调用外部模块 ------
    @staticmethod
    def call_module_func(module_path: str,
                         func_name: str = "",
                         *args,
                         instantiate: bool = False,
                         **kwargs) -> Optional[Any]:
        """
        动态加载模块并调用函数或类。
        参数
        ----
        module_path : 模块名，例如 'tools' 或 'utils.helper'
        func_name   : 支持两种写法
                      1) 函数名：'greet'
                      2) 链式类+方法：'MyClass.say_hello'
        instantiate : 当 func_name 是类名时，是否自动实例化
        *args, **kwargs : 传给函数/类构造/方法的参数
        返回
        ----
        调用结果；失败返回 None
        """
        try:
            mod = importlib.import_module(module_path)
        except ModuleNotFoundError:
            return False

        # 链式写法：'MyClass.say_hello'
        if '.' in func_name:
            class_name, method_name = func_name.split('.', 1)
            cls = getattr(mod, class_name, None)
            if not callable(cls):
                return False
            # 实例化 or 直接拿类
            obj = cls(*args, **kwargs) if instantiate else cls
            return getattr(obj, method_name, None)()

        # 普通函数 or 类
        target = getattr(mod, func_name, None)
        if not callable(target):
            return False

        # 如果是类，且要求实例化
        if instantiate and isinstance(target, type):
            return target(*args, **kwargs)
        # 否则直接当函数调用
        return target(*args, **kwargs)


# -------------- 使用示例 --------------
if __name__ == "__main__":
    bot = WinAuto(r"D:\Program Files\CBIM\modulelogin.exe")
    bot.start()
    login_window = bot.get_window(class_name='LoginDialog')
    pic_login_win = bot.screenshot(login_window, return_image=True)
    print("已保存", pic_login_win)
    
    # 1. 账号框：ComboBox 下的 Edit0
    account_edit = bot.by_index(login_window, 'Edit0')
    bot.input_text(account_edit, "10802")  # 清空并输入账号
    pic = bot.screenshot(account_edit, return_image=True)  # 返回 PIL.Image
    pic.show()

    # 2. 密码框：紧邻的下一个 Edit（无标题，索引 2）
    password_edit = bot.by_index(login_window, 'Edit2')
    bot.input_text(password_edit, "1")  # 清空并输入密码
    pic = bot.screenshot(password_edit, return_image=True)  # 返回 PIL.Image
    pic.show()

    # 3. 登录按钮：标题精确匹配「登 录」
    login_btn = bot.by_index(login_window, '登 录Button')
    bot.click_ctrl(login_btn)  # 点击登录按钮

    # 4. 获取窗口文本
    print("窗口标题:", bot.get_window_text(login_window))

    # 5. 最大化窗口
    bot.maximize_window(login_window)

    # 6. 等待窗口激活
    bot.wait_until_active(login_window)

    # 7. 关闭窗口
    bot.close_window(login_window)

    # 8. 关闭应用
    bot.close_app()

    # 9. 截矩形区域 (左上角 100,100 宽 300 高 200)
    pic = bot.screenshot((100, 100, 300, 200), filename="custom.png")

    # 10. 不指定 target → 截全屏
    bot.screenshot(filename="fullscreen.png")