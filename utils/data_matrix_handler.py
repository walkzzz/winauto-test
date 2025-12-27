# data_matrix_handler.py
# 数据矩阵处理器 - 用于加载和处理数据矩阵，生成参数化测试用例

import os
import re
import yaml
from typing import Any, Dict, List, Optional
from pathlib import Path


class DataMatrixHandler:
    """
    数据矩阵处理器
    负责加载数据矩阵文件，生成参数化测试用例
    """
    
    def __init__(self):
        self.data_matrix: Dict[str, Any] = {}
        self.base_config: Dict[str, Any] = {}
        self.step_templates: Dict[str, List[Dict[str, Any]]] = {}
    
    def load_data_matrix(self, file_path: str) -> bool:
        """
        加载数据矩阵文件
        :param file_path: 数据矩阵文件路径
        :return: 加载成功返回True，否则返回False
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.data_matrix = yaml.safe_load(f)
            
            # 提取基础配置
            self.base_config = self.data_matrix.get('base_config', {})
            
            # 提取步骤模板
            self.step_templates = self.data_matrix.get('step_templates', {})
            
            return True
        except Exception as e:
            print(f"加载数据矩阵失败: {e}")
            return False
    
    def generate_test_cases(self, template_name: str = 'login_flow') -> List[Dict[str, Any]]:
        """
        基于数据矩阵生成测试用例
        :param template_name: 步骤模板名称，默认为'login_flow'
        :return: 生成的测试用例列表
        """
        test_cases = []
        
        # 获取数据矩阵中的测试场景
        data_matrix = self.data_matrix.get('data_matrix', [])
        
        # 获取步骤模板
        step_template = self.step_templates.get(template_name, [])
        
        for scenario in data_matrix:
            # 合并基础配置和场景配置
            test_case = self.base_config.copy()
            test_case.update(scenario)
            
            # 生成测试步骤 - 替换模板中的参数
            test_steps = self._render_steps(step_template, scenario)
            test_case['steps'] = test_steps
            
            # 提取预期结果
            expected_results = scenario.get('expected_results', [])
            # 过滤掉非action类型的预期结果
            test_case['expected'] = [result for result in expected_results if 'action' in result]
            
            test_cases.append(test_case)
        
        return test_cases
    
    def _render_steps(self, step_template: List[Dict[str, Any]], scenario: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        渲染测试步骤 - 替换模板中的参数
        :param step_template: 步骤模板
        :param scenario: 测试场景数据
        :return: 渲染后的测试步骤
        """
        rendered_steps = []
        
        for step in step_template:
            # 深拷贝步骤模板，避免修改原模板
            rendered_step = step.copy()
            
            # 渲染参数
            if 'params' in rendered_step:
                rendered_step['params'] = self._render_params(rendered_step['params'], scenario)
            
            # 渲染文件名
            if 'filename' in rendered_step.get('params', {}):
                rendered_step['params']['filename'] = self._render_value(
                    rendered_step['params']['filename'], scenario
                )
            
            rendered_steps.append(rendered_step)
        
        return rendered_steps
    
    def _render_params(self, params: Dict[str, Any], scenario: Dict[str, Any]) -> Dict[str, Any]:
        """
        渲染参数值 - 替换参数中的模板变量
        :param params: 参数字典
        :param scenario: 测试场景数据
        :return: 渲染后的参数字典
        """
        rendered_params = {}
        
        for key, value in params.items():
            rendered_params[key] = self._render_value(value, scenario)
        
        return rendered_params
    
    def _render_value(self, value: Any, scenario: Dict[str, Any]) -> Any:
        """
        渲染值 - 替换值中的模板变量
        支持的模板格式：
        - {{input_params.username}}, {{case_id}}, {{case_name}}等
        - {{base_config.common.field_name}} 支持基础配置替换
        支持递归处理嵌套的字典和列表
        :param value: 要渲染的值
        :param scenario: 测试场景数据
        :return: 渲染后的值
        """
        if isinstance(value, str):
            # 检查是否是完整的模板变量（如 "{{expected_results}}"）
            import re
            full_var_match = re.fullmatch(r'\{\{([^}]+)\}\}', value)
            if full_var_match:
                var_path = full_var_match.group(1)
                # 完整变量，直接返回对应值
                if var_path.startswith('base_config.'):
                    # 从基础配置中获取值
                    config_path = var_path.replace('base_config.', '')
                    return self._get_value_from_path(self.base_config, config_path)
                elif '.' not in var_path:
                    return scenario.get(var_path, '')
                else:
                    return self._get_value_from_path(scenario, var_path)
            else:
                # 包含模板变量的字符串，如 "打开登录窗口_{{case_id}}"
                def replace_match(match):
                    var_path = match.group(1)
                    if var_path.startswith('base_config.'):
                        config_path = var_path.replace('base_config.', '')
                        return self._get_value_from_path(self.base_config, config_path)
                    elif '.' not in var_path:
                        return str(scenario.get(var_path, ''))
                    else:
                        return self._get_value_from_path(scenario, var_path)
                return re.sub(r'\{\{([^}]+)\}\}', replace_match, value)
        elif isinstance(value, dict):
            # 递归处理字典
            rendered_dict = {}
            for key, val in value.items():
                rendered_dict[key] = self._render_value(val, scenario)
            return rendered_dict
        elif isinstance(value, list):
            # 递归处理列表
            rendered_list = []
            for item in value:
                rendered_list.append(self._render_value(item, scenario))
            return rendered_list
        
        return value
    
    def _get_value_from_path(self, data: Dict[str, Any], path: str) -> str:
        """
        根据路径从数据中获取值
        支持的路径格式：input_params.username, case_id, case_name等
        :param data: 数据字典
        :param path: 值的路径
        :return: 获取到的值，字符串格式
        """
        try:
            keys = path.split('.')
            value = data
            
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key, '')
                else:
                    return ''
            
            return str(value)
        except Exception as e:
            print(f"获取值失败: {e}")
            return ''
    
    def load_all_data_matrices(self, directory: str = 'test_cases') -> List[Dict[str, Any]]:
        """
        加载指定目录下的所有数据矩阵文件
        :param directory: 数据矩阵文件目录，默认为'test_cases'
        :return: 所有生成的测试用例列表
        """
        all_test_cases = []
        
        # 获取目录下的所有YAML文件
        data_matrix_files = [f for f in os.listdir(directory) if f.endswith('_data_matrix.yaml')]
        
        for file in data_matrix_files:
            file_path = os.path.join(directory, file)
            
            # 加载数据矩阵
            if self.load_data_matrix(file_path):
                # 生成测试用例
                test_cases = self.generate_test_cases()
                all_test_cases.extend(test_cases)
        
        return all_test_cases


# 全局实例
_data_matrix_handler = DataMatrixHandler()


def get_data_matrix_handler() -> DataMatrixHandler:
    """获取数据矩阵处理器实例"""
    return _data_matrix_handler


def load_data_matrices(directory: str = 'test_cases') -> List[Dict[str, Any]]:
    """加载指定目录下的所有数据矩阵文件"""
    handler = get_data_matrix_handler()
    return handler.load_all_data_matrices(directory)


def generate_test_cases_from_file(file_path: str, template_name: str = 'login_steps') -> List[Dict[str, Any]]:
    """从指定文件生成测试用例"""
    handler = get_data_matrix_handler()
    if handler.load_data_matrix(file_path):
        return handler.generate_test_cases(template_name)
    return []
