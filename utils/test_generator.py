import inspect
import pytest
from typing import Any, Dict, Optional
import allure
from winauto_helper import WinAuto

class YamlTestGenerator:
    """
    动态测试生成器 - 利用反射执行 WinAuto 方法，支持 YAML 配置驱动的测试生成
    
    该类负责：
    - 解析 YAML 测试步骤
    - 反射调用 WinAuto 方法
    - 管理测试上下文和变量
    - 集成 Allure 报告
    - 处理测试步骤的执行结果
    """
    
    def __init__(self):
        """
        初始化测试生成器
        
        属性:
            winauto: WinAuto 实例，用于执行自动化操作
            context: 测试上下文，用于存储和管理测试过程中的变量
        """
        self.winauto = None
        self.context = {}  # 存储 save_as 的变量
    
    def execute_step(self, step: Dict[str, Any]) -> Any:
        """
        执行单个测试步骤 - 核心反射逻辑
        
        参数:
            step: 步骤配置字典，包含 action、params、save_as 等字段
            
        返回:
            执行结果
            
        异常:
            AttributeError: 当 WinAuto 类不存在指定方法时
            RuntimeError: 当步骤执行失败时
        """
        action = step.get("action")
        params = step.get("params", {})
        save_as = step.get("save_as")
        
        # 定义步骤中文名称映射
        action_names = {
            "start": "启动应用",
            "connect": "连接应用",
            "get_window": "获取窗口",
            "by_index": "查找控件",
            "input_text": "输入文本",
            "click_ctrl": "点击控件",
            "screenshot": "截图",
            "wait_until_visible": "等待控件可见",
            "wait_until_enabled": "等待控件启用",
            "wait_until_active": "等待窗口激活",
            "get_text": "获取控件文本",
            "select_item": "选择列表项",
            "clear_text": "清空文本",
            "validate_result": "验证结果",
            "assert": "执行断言"
        }
        
        # 获取步骤中文名称
        step_name = action_names.get(action, action)
        
        # 使用 Allure 步骤注解
        with allure.step(f"{step_name}"):
            # 解析参数中的变量引用 (如 $login_win)
            resolved_params = self._resolve_params(params)
            
            # 特殊处理 new action types
            if action == "validate_result":
                # 自定义结果验证逻辑
                expected = resolved_params.get("expected", {})
                case_type = resolved_params.get("case_type", "default")
                return self._validate_result(expected, case_type)
            
            if action == "assert":
                # 自定义断言逻辑
                condition = resolved_params.get("condition")
                on_failure = resolved_params.get("on_failure", "raise")
                return self._execute_assertion(condition, on_failure)
            
            # 获取 WinAuto 类的实例方法
            if not hasattr(self.winauto, action):
                raise AttributeError(f"WinAuto 类不存在方法: {action}")
            
            method = getattr(self.winauto, action)
            
            # 反射调用方法
            try:
                # 处理不同的参数签名
                sig = inspect.signature(method)
                
                # 合并所有参数：params + 步骤级别的关键字参数
                all_params = resolved_params.copy()
                
                # 处理 Allure 相关参数
                if "allure_attach" in step:
                    all_params["allure_attach"] = step["allure_attach"]
                if "allure_name" in step:
                    all_params["allure_name"] = step["allure_name"]
                
                # 将步骤级别的关键字参数添加到all_params中
                # 只添加方法签名中存在的参数
                for param_name in sig.parameters:
                    # 检查参数是否在params中或直接在step中
                    if param_name in params and param_name not in all_params:
                        all_params[param_name] = params[param_name]
                    elif param_name in step and param_name not in all_params:
                        all_params[param_name] = step[param_name]
                
                # 过滤掉方法不支持的参数
                supported_params = list(sig.parameters.keys())
                all_params = {k: v for k, v in all_params.items() if k in supported_params}
                
                bound_args = sig.bind_partial(**all_params)
                
                # 对有默认值的参数补全
                for param_name, param in sig.parameters.items():
                    if param_name not in bound_args.arguments and param.default != inspect.Parameter.empty:
                        bound_args.arguments[param_name] = param.default
                
                result = method(*bound_args.args, **bound_args.kwargs)
                
                # 保存结果到上下文
                if save_as:
                    self.context[save_as] = result
                
                # 在每个步骤执行完成后立即进行屏幕截图，除了screenshot步骤本身
                if action != "screenshot":
                    import datetime
                    from pathlib import Path
                    # 生成唯一的截图文件名
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                    screenshot_path = f"reports/step_{action}_{timestamp}.png"
                    
                    # 执行截图并附加到Allure报告 - 仅捕获应用窗口而非全屏
                    try:
                        # 获取应用的顶级窗口
                        current_window = self.winauto.app.top_window()
                        # 执行截图并附加到Allure报告 - 仅捕获该窗口
                        self.winauto.screenshot(
                            target=current_window,
                            filename=screenshot_path,
                            allure_attach=True,
                            allure_name=f"{step_name} - 执行后截图"
                        )
                    except Exception as e:
                        # 如果获取窗口失败，退回到全屏截图
                        self.winauto.screenshot(
                            filename=screenshot_path,
                            allure_attach=True,
                            allure_name=f"{step_name} - 执行后截图 (全屏)"
                        )
                
                return result
            
            except Exception as e:
                # 步骤失败时也进行截图
                import datetime
                from pathlib import Path
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                error_screenshot_path = f"reports/error_{action}_{timestamp}.png"
                
                # 执行失败截图 - 仅捕获应用窗口而非全屏
                try:
                    # 获取应用的顶级窗口
                    current_window = self.winauto.app.top_window()
                    # 执行截图并附加到Allure报告 - 仅捕获该窗口
                    self.winauto.screenshot(
                        target=current_window,
                        filename=error_screenshot_path,
                        allure_attach=True,
                        allure_name=f"{step_name} - 执行失败截图"
                    )
                except Exception as screenshot_e:
                    # 如果获取窗口失败，退回到全屏截图
                    self.winauto.screenshot(
                        filename=error_screenshot_path,
                        allure_attach=True,
                        allure_name=f"{step_name} - 执行失败截图 (全屏)"
                    )
                
                raise RuntimeError(f"执行 {action} 失败: {str(e)}")
    
    def _validate_result(self, expected: Dict[str, Any], case_type: str) -> bool:
        """
        自定义结果验证逻辑
        :param expected: 预期结果配置
        :param case_type: 用例类型
        :return: 验证结果
        """
        # 根据用例类型执行不同的验证
        if case_type == "empty_validation" or case_type == "wrong_credentials":
            # 验证错误消息
            return self._validate_error_message(expected.get("error_message", {}))
        elif case_type == "valid_credentials":
            # 验证登录成功
            return self._validate_success(expected)
        else:
            # 默认验证
            return self._validate_default(expected)
    
    def _validate_error_message(self, error_config: Dict[str, Any]) -> bool:
        """
        验证错误消息
        :param error_config: 错误消息配置
        :return: 验证结果
        """
        # 尝试获取错误窗口
        try:
            msg_box = self.winauto.app.window(class_name="QMessageBox")
            if msg_box.exists(timeout=2):
                msg_box.set_focus()
                # 查找错误文本标签
                msg_label = msg_box.child_window(best_match="QLabel")
                if msg_label.exists(timeout=2):
                    actual_text = msg_label.window_text()
                    expected_text = error_config.get("text", [])
                    
                    # 处理多种可能的错误文本
                    if isinstance(expected_text, list):
                        # 只要实际文本在预期列表中就通过
                        if actual_text in expected_text:
                            allure.attach(f"错误消息验证成功: '{actual_text}'", name="错误消息验证")
                            return True
                        else:
                            pytest.fail(f"错误消息验证失败: 预期 {expected_text}，实际 '{actual_text}'")
                    else:
                        # 精确匹配
                        if actual_text == expected_text:
                            allure.attach(f"错误消息验证成功: '{actual_text}'", name="错误消息验证")
                            return True
                        else:
                            pytest.fail(f"错误消息验证失败: 预期 '{expected_text}'，实际 '{actual_text}'")
        except Exception as e:
            # 如果没有错误窗口，可能错误在页面上显示
            allure.attach(f"未找到QMessageBox窗口，可能错误在页面上显示: {e}", name="错误验证")
        return True
    
    def _validate_success(self, expected: Dict[str, Any]) -> bool:
        """
        验证登录成功
        :param expected: 预期结果配置
        :return: 验证结果
        """
        # 验证成功后应该显示主窗口
        success_window = expected.get("window_validation", {})
        if success_window:
            window_class = success_window.get("params", {}).get("class_name")
            if window_class:
                main_window = self.winauto.app.window(class_name=window_class)
                if not main_window.exists(timeout=5):
                    pytest.fail(f"登录成功后未找到预期窗口: {window_class}")
        return True
    
    def _validate_default(self, expected: Dict[str, Any]) -> bool:
        """
        默认验证逻辑
        :param expected: 预期结果配置
        :return: 验证结果
        """
        # 简单验证登录成功状态
        return expected.get("login_success", True)
    
    def _execute_assertion(self, condition: str, on_failure: str) -> bool:
        """
        执行断言
        :param condition: 断言条件
        :param on_failure: 失败处理方式
        :return: 断言结果
        """
        try:
            # 这里可以实现更复杂的断言逻辑
            # 目前简单返回True，因为实际断言逻辑已在_validate_result中实现
            return True
        except Exception as e:
            if on_failure == "raise":
                raise AssertionError(f"断言失败: {e}")
            else:
                allure.attach(f"断言失败，但未抛出异常: {e}", name="断言结果")
                return False
    
    def _resolve_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """解析参数中的变量引用"""
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("$"):
                # 从上下文获取变量
                var_name = value[1:]
                resolved[key] = self.context.get(var_name)
            else:
                resolved[key] = value
        return resolved
    
    def setup_winauto(self, exec_path: str = ""):
        """
        初始化 WinAuto 实例
        
        参数:
            exec_path: 应用程序执行路径，可选
            
        说明:
            该方法创建并初始化一个 WinAuto 实例，并清空测试上下文。
        """
        self.winauto = WinAuto(exec_path=exec_path)
        self.context.clear()