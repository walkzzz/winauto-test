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

# 属性缓存，用于提高多次访问同一属性的效率
_attr_cache = {}

def _safe_call(obj: Any, attr: str, *a, **k):
    """
    安全调用对象方法或属性
    
    该函数提供了一种安全的方式来调用对象的方法或属性，
    可以处理属性不存在或调用过程中发生的异常。
    
    参数:
        obj: 要调用方法的对象
        attr: 方法或属性名称
        *a: 位置参数
        **k: 关键字参数
    
    返回:
        如果方法调用成功，返回方法调用结果；
        如果属性不存在，返回 None；
        如果调用过程中发生异常，返回 False
    """
    if not hasattr(obj, attr):
        return None
    try:
        return getattr(obj, attr)(*a, **k)
    except _PYWIN_EXCEPTIONS:
        return False
    except Exception as e:
        # 记录异常信息，便于调试
        logging.debug(f"_safe_call 调用 {attr} 时发生未知异常: {e}")
        return False


def _safe_get(obj: Any, attr: str, use_cache: bool = True):
    """
    安全获取对象属性，支持属性缓存
    
    该函数提供了一种安全的方式来获取对象的属性，
    可以处理属性不存在或获取过程中发生的异常，
    并支持属性缓存以提高性能。
    
    参数:
        obj: 要获取属性的对象
        attr: 属性名称
        use_cache: 是否使用缓存，默认为 True
    
    返回:
        如果属性获取成功，返回属性值（转换为字符串）；
        如果属性不存在或获取失败，返回空字符串
    """
    if obj is None:
        return ""
    
    # 计算缓存键，使用对象ID和属性名确保唯一性
    cache_key = (id(obj), attr)
    
    # 检查缓存，命中则直接返回
    if use_cache and cache_key in _attr_cache:
        return _attr_cache[cache_key]
    
    try:
        # 获取属性值，默认值为空字符串
        result = getattr(obj, attr, "")
        # 处理空值情况
        if result is None:
            result = ""
        elif not isinstance(result, str):
            # 确保返回字符串类型
            result = str(result)
        
        # 缓存结果，提高后续访问性能
        if use_cache:
            _attr_cache[cache_key] = result
        
        return result
    except _PYWIN_EXCEPTIONS:
        return ""
    except Exception as e:
        # 记录异常信息，便于调试
        logging.debug(f"_safe_get 获取 {attr} 时发生未知异常: {e}")
        return ""


def _clear_attr_cache():
    """
    清空属性缓存
    
    该函数用于清空全局属性缓存，
    适用于需要刷新缓存的场景，如控件树结构发生变化时。
    """
    global _attr_cache
    _attr_cache.clear()


def _safe_get_element_info(obj: Any, attr: str, use_cache: bool = True):
    """
    安全获取控件的 element_info 属性
    
    该函数专门用于获取控件的 element_info 属性，
    是 _safe_get 的封装，增加了对 element_info 属性的检查。
    
    参数:
        obj: 控件对象
        attr: 要获取的 element_info 属性名称
        use_cache: 是否使用缓存，默认为 True
    
    返回:
        如果 element_info 属性获取成功，返回属性值（转换为字符串）；
        如果获取失败，返回空字符串
    """
    if obj is None:
        return ""
    
    try:
        if hasattr(obj, "element_info"):
            return _safe_get(obj.element_info, attr, use_cache)
        return ""
    except Exception as e:
        logging.debug(f"_safe_get_element_info 获取 {attr} 时发生异常: {e}")
        return ""


# -------------- 主类：WinAuto --------------
class WinAuto:
    """
    WinAuto 自动化测试框架核心类，提供 Windows 应用自动化测试的各种功能。
    
    该类封装了 pywinauto 的核心功能，提供了更简单易用的 API，支持：
    - 应用程序的启动和连接
    - 窗口的获取和操作
    - 控件的查找和交互
    - 截图功能
    - 测试流程的自动化
    
    示例：
    >>> bot = WinAuto(r"D:\Program Files\YourApp\app.exe")
    >>> bot.start()
    >>> login_window = bot.get_window(class_name='LoginDialog')
    >>> # 进行控件操作...
    >>> bot.close_app()
    """
    def __init__(self,
                 exec_path: str = "",
                 *,
                 backend: str = "uia",
                 poll_interval: float = 0.2):
        """
        初始化 WinAuto 实例
        
        参数:
            exec_path: 应用程序执行路径，默认为空字符串
            backend: 使用的 pywinauto 后端，可选值："uia"（默认）或 "win32"
            poll_interval: 轮询间隔，默认 0.2 秒
        """
        self.exec_path = exec_path
        self.backend = backend
        self.poll_interval = poll_interval
        self.app: Optional[Application] = None
        self.logger = logging.getLogger(self.__class__.__name__)

    # ------ 启动 / 连接 ------
    def start(self, exec_path: Optional[str] = None) -> Optional[Application]:
        """
        启动应用程序
        
        参数:
            exec_path: 可选，应用程序执行路径。如果提供，将覆盖实例初始化时的 exec_path
            
        返回:
            启动成功返回 Application 对象，失败返回 None
        """
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
        """
        连接到已运行的应用程序
        
        参数:
            **connect_kwargs: pywinauto connect 方法的关键字参数，如 process、handle、title 等
            
        返回:
            连接成功返回 Application 对象，失败返回 None
        """
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
        """
        根据条件查找并返回窗口对象
        
        参数:
            title: 窗口标题文本，可选
            class_name: 窗口类名，可选
            best_match: 最佳匹配字符串，可选
            timeout: 查找超时时间，默认 5 秒
            
        返回:
            找到的窗口对象，未找到返回 None
            
        说明:
            1. 至少需要提供一个过滤条件
            2. 支持同时提供多个过滤条件
            3. 会持续尝试查找直到超时
        """
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
        """
        获取应用程序顶层窗口
        
        返回:
            顶层窗口对象，失败返回 None
        """
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
        """
        关闭应用程序
        
        返回:
            关闭成功返回 True，失败返回 False
        """
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
        """
        关闭指定窗口
        
        参数:
            win: 要关闭的窗口对象，必须提供
            
        返回:
            关闭成功返回 True，失败返回 False
        """
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
        """
        最大化窗口
        
        参数:
            win: 要最大化的窗口对象，必须提供
            
        返回:
            操作成功返回 True，失败返回 False
        """
        if win is None:
            self.logger.error("maximize_window: 未提供窗口对象")
            return False
        return _safe_call(win, "maximize") is not False

    def minimize_window(self, win: Optional[WindowSpecification] = None) -> bool:
        """
        最小化窗口
        
        参数:
            win: 要最小化的窗口对象，必须提供
            
        返回:
            操作成功返回 True，失败返回 False
        """
        if win is None:
            self.logger.error("minimize_window: 未提供窗口对象")
            return False
        return _safe_call(win, "minimize") is not False

    def restore_window(self, win: Optional[WindowSpecification] = None) -> bool:
        """
        恢复窗口（从最小化/最大化状态恢复到正常状态）
        
        参数:
            win: 要恢复的窗口对象，必须提供
            
        返回:
            操作成功返回 True，失败返回 False
        """
        if win is None:
            self.logger.error("restore_window: 未提供窗口对象")
            return False
        return _safe_call(win, "restore") is not False

    def set_focus(self, win: Optional[WindowSpecification] = None) -> bool:
        """
        设置窗口焦点
        
        参数:
            win: 要设置焦点的窗口对象，必须提供
            
        返回:
            操作成功返回 True，失败返回 False
        """
        if win is None:
            self.logger.error("set_focus: 未提供窗口对象")
            return False
        return _safe_call(win, "set_focus") is not False

    def get_window_text(self, win: Optional[WindowSpecification] = None) -> str:
        """
        获取窗口标题文本
        
        参数:
            win: 要获取文本的窗口对象，必须提供
            
        返回:
            窗口标题文本，获取失败返回空字符串
        """
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
                     depth: int = 10,
                     timeout: float = 5,
                     match_strategy: Literal["exact", "fuzzy", "regex"] = "exact",
                     best_match: bool = False,
                     match_threshold: float = 0.7,
                     adaptive_depth: bool = True,
                     max_depth: int = 20,
                     enable_debug_log: bool = False) -> Optional[BaseWrapper]:
        """
        通用控件检索函数
        
        参数:
            parent: 父控件或应用对象
            title: 控件标题文本
            class_name: 控件类名
            control_type: 控件类型
            auto_id: 自动化ID
            depth: 搜索深度，默认10
            timeout: 搜索超时时间，默认5秒
            match_strategy: 匹配策略，可选值：exact（精确匹配）、fuzzy（模糊匹配）、regex（正则匹配）
            best_match: 是否返回最佳匹配结果（当存在多个匹配时）
            match_threshold: 模糊匹配阈值，默认0.7
            adaptive_depth: 是否启用深度自适应，默认True
            max_depth: 最大搜索深度，默认20
            enable_debug_log: 是否启用调试日志，默认False
            
        返回:
            找到的控件对象，未找到返回None
        """
        if parent is None:
            self.logger.error("parent 为 None，无法检索控件")
            return None

        # 保存原始日志级别
        original_log_level = self.logger.level
        
        # 如果启用调试日志，设置日志级别为DEBUG
        if enable_debug_log:
            self.logger.setLevel(logging.DEBUG)
            self.logger.debug("调试日志已启用")

        # 统一转成 BaseWrapper
        self.logger.debug("开始统一转换父控件类型，当前类型: %s", type(parent).__name__)
        if isinstance(parent, Application):
            parent = parent.child_window(found_index=0)
            self.logger.debug("转换 Application 对象为 WindowSpecification")
        if isinstance(parent, WindowSpecification):
            parent = parent.wrapper_object()
            self.logger.debug("转换 WindowSpecification 对象为 BaseWrapper")
        
        self.logger.debug("父控件转换完成，最终类型: %s", type(parent).__name__)
        
        # 记录搜索条件
        search_conditions = {
            "title": title,
            "class_name": class_name,
            "control_type": control_type,
            "auto_id": auto_id,
            "depth": depth,
            "match_strategy": match_strategy,
            "best_match": best_match,
            "match_threshold": match_threshold
        }
        self.logger.info("开始搜索控件，搜索条件: %s", search_conditions)
        
        # 搜索路径跟踪，用于调试
        search_path = []
        matched_controls = []

        def _fuzzy_match(a: str, b: str) -> float:
            """模糊匹配算法，返回匹配相似度（0-1之间）"""
            a = a.lower()
            b = b.lower()
            if not a or not b:
                return 0.0
            if a == b:
                return 1.0
            if a in b or b in a:
                return 0.9
            # 简单的字符匹配相似度计算
            common_chars = set(a) & set(b)
            return len(common_chars) / max(len(a), len(b))

        def _match(ctrl: BaseWrapper) -> Union[bool, float]:
            """增强的匹配逻辑，返回匹配结果或匹配置信度"""
            match_score = 0.0
            match_count = 0
            total_criteria = sum(1 for x in [title, class_name, control_type, auto_id] if x)
            
            if total_criteria == 0:
                return True if best_match else 1.0

            # 获取控件属性，确保一致性
            ctrl_text = _safe_call(ctrl, "window_text") or ""
            ctrl_class = _safe_call(ctrl, "friendly_class_name") or ""
            # control_type 可能来自 element_info.control_type 或 control_type()
            ctrl_type = (_safe_get_element_info(ctrl, "control_type", use_cache=True) or 
                       _safe_call(ctrl, "control_type") or "")
            ctrl_auto_id = (_safe_get_element_info(ctrl, "automation_id", use_cache=True) or 
                         _safe_call(ctrl, "automation_id") or "")

            # 标题匹配
            if title:
                match_count += 1
                if match_strategy == "exact":
                    if title.lower() in ctrl_text.lower():
                        match_score += 1.0
                    else:
                        if not best_match:
                            return False
                elif match_strategy == "fuzzy":
                    score = _fuzzy_match(title, ctrl_text)
                    if score >= match_threshold:
                        match_score += score
                    else:
                        if not best_match:
                            return False
                elif match_strategy == "regex":
                    import re
                    try:
                        if re.search(title, ctrl_text, re.IGNORECASE):
                            match_score += 1.0
                        else:
                            if not best_match:
                                return False
                    except re.error:
                        # 正则表达式错误，降级为精确匹配
                        if title.lower() in ctrl_text.lower():
                            match_score += 1.0
                        else:
                            if not best_match:
                                return False

            # 类名匹配
            if class_name:
                match_count += 1
                if match_strategy == "exact":
                    if class_name.lower() == ctrl_class.lower():
                        match_score += 1.0
                    else:
                        if not best_match:
                            return False
                elif match_strategy == "fuzzy":
                    score = _fuzzy_match(class_name, ctrl_class)
                    if score >= match_threshold:
                        match_score += score
                    else:
                        if not best_match:
                            return False
                elif match_strategy == "regex":
                    import re
                    try:
                        if re.search(class_name, ctrl_class, re.IGNORECASE):
                            match_score += 1.0
                        else:
                            if not best_match:
                                return False
                    except re.error:
                        # 正则表达式错误，降级为精确匹配
                        if class_name.lower() == ctrl_class.lower():
                            match_score += 1.0
                        else:
                            if not best_match:
                                return False

            # 控件类型匹配
            if control_type:
                match_count += 1
                if control_type.lower() == ctrl_type.lower():
                    match_score += 1.0
                else:
                    if not best_match:
                        return False

            # 自动化ID匹配
            if auto_id:
                match_count += 1
                if match_strategy == "exact":
                    if auto_id == ctrl_auto_id:
                        match_score += 1.0
                    else:
                        if not best_match:
                            return False
                elif match_strategy == "fuzzy":
                    score = _fuzzy_match(auto_id, ctrl_auto_id)
                    if score >= match_threshold:
                        match_score += score
                    else:
                        if not best_match:
                            return False
                elif match_strategy == "regex":
                    import re
                    try:
                        if re.search(auto_id, ctrl_auto_id):
                            match_score += 1.0
                        else:
                            if not best_match:
                                return False
                    except re.error:
                        # 正则表达式错误，降级为精确匹配
                        if auto_id == ctrl_auto_id:
                            match_score += 1.0
                        else:
                            if not best_match:
                                return False

            if best_match:
                # 返回匹配置信度
                return match_score / total_criteria if total_criteria > 0 else 0.0
            else:
                # 精确匹配模式下，所有条件必须匹配
                return match_count == total_criteria

        elapsed = 0.0
        best_match_result = None
        best_match_score = 0.0
        current_depth = depth
        initial_depth = depth
        
        while True:
            self.logger.debug("开始搜索，当前深度: %d, 最佳置信度: %.2f", current_depth, best_match_score)
            
            # 重置最佳匹配结果，重新搜索
            iteration_best_match = None
            iteration_best_score = 0.0
            
            # 重置搜索路径
            search_path.clear()
            
            dq = deque([(parent, 0, [parent])])
            while dq:
                cur, lvl, current_path = dq.popleft()
                if lvl > current_depth:
                    continue
                try:
                    # 获取控件信息用于日志
                    ctrl_text = _safe_call(cur, "window_text") or ""
                    ctrl_class = _safe_call(cur, "friendly_class_name") or ""
                    ctrl_type = (_safe_get_element_info(cur, "control_type", use_cache=True) or 
                               _safe_call(cur, "control_type") or "")
                    
                    # 记录当前搜索路径
                    search_path.append({
                        "level": lvl,
                        "control": cur,
                        "text": ctrl_text,
                        "class_name": ctrl_class,
                        "control_type": ctrl_type
                    })
                    
                    self.logger.debug("搜索控件 [L%d]: text='%s', class='%s', type='%s'", 
                                   lvl, ctrl_text[:50], ctrl_class, ctrl_type)
                    
                    match_result = _match(cur)
                    if match_result:
                        if best_match:
                            # 记录最佳匹配结果
                            score = match_result
                            if score > iteration_best_score:
                                iteration_best_score = score
                                iteration_best_match = cur
                                self.logger.debug("找到更优匹配，置信度: %.2f, 控件: %s", score, cur)
                            # 更新全局最佳匹配
                            if score > best_match_score:
                                best_match_score = score
                                best_match_result = cur
                        else:
                            # 精确匹配模式，直接返回
                            self.logger.info("控件已找到：%s", cur)
                            self.logger.debug("匹配控件信息: text='%s', class='%s', type='%s'", 
                                           ctrl_text, ctrl_class, ctrl_type)
                            self.logger.debug("搜索路径长度: %d, 最终深度: %d", len(search_path), lvl)
                            return cur
                    # 继续搜索子控件
                    children = cur.children()
                    self.logger.debug("控件 [L%d] 有 %d 个子控件", lvl, len(children))
                    for child in children:
                        # 传递当前路径的副本，避免引用问题
                        child_path = current_path.copy()
                        child_path.append(child)
                        dq.append((child, lvl + 1, child_path))
                except _PYWIN_EXCEPTIONS as e:
                    self.logger.debug("搜索控件时发生异常: %s", e)
                    continue
                except Exception as e:
                    self.logger.error("搜索控件时发生未知异常: %s", e)
                    continue

            # 检查是否找到最佳匹配
            if best_match and iteration_best_match is not None:
                self.logger.info("找到最佳匹配控件，置信度: %.2f, 控件: %s", iteration_best_score, iteration_best_match)
                # 获取最佳匹配控件的详细信息
                best_text = _safe_get(iteration_best_match, "window_text", use_cache=True)
                best_class = _safe_get(iteration_best_match, "friendly_class_name", use_cache=True)
                best_type = (_safe_get_element_info(iteration_best_match, "control_type", use_cache=True) or 
                           _safe_call(iteration_best_match, "control_type") or "")
                self.logger.debug("最佳匹配控件信息: text='%s', class='%s', type='%s'", 
                               best_text, best_class, best_type)
                self.logger.debug("搜索路径长度: %d, 最终深度: %d", len(search_path), current_depth)
                return iteration_best_match

            # 深度自适应逻辑
            if adaptive_depth and current_depth < max_depth and elapsed < timeout:
                # 增加搜索深度，继续搜索
                new_depth = min(current_depth + 5, max_depth)
                self.logger.debug("当前深度 %d 未找到控件，自动增加深度到 %d", current_depth, new_depth)
                current_depth = new_depth
            else:
                # 不启用自适应深度或已达到最大深度，等待超时
                if elapsed >= timeout:
                    if best_match and best_match_result is not None:
                        self.logger.info("搜索超时，但找到最佳匹配控件，置信度: %.2f, 控件: %s", best_match_score, best_match_result)
                        return best_match_result
                    self.logger.warning("查找控件超时（%ss），未找到匹配控件，最终搜索深度: %d", timeout, current_depth)
                    self.logger.debug("搜索路径长度: %d, 搜索条件: %s", len(search_path), search_conditions)
                    # 记录搜索路径的最后几个控件，帮助调试
                    if search_path and enable_debug_log:
                        self.logger.debug("搜索路径最后5个控件:")
                        for i, ctrl_info in enumerate(search_path[-5:], 1):
                            self.logger.debug("  %d. [L%d] text='%s', class='%s', type='%s'",
                                           i, ctrl_info["level"],
                                           ctrl_info["text"][:50],
                                           ctrl_info["class_name"],
                                           ctrl_info["control_type"])
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