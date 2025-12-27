import yaml
from pathlib import Path
from typing import List, Dict, Any
from .data_matrix_handler import DataMatrixHandler

class YamlTestLoader:
    """YAML 测试用例加载器 - 支持传统测试用例和数据矩阵"""
    
    @staticmethod
    def load_yaml(file_path: str) -> Dict[str, Any]:
        """加载单个 YAML 文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    @staticmethod
    def load_all_test_cases(test_cases_dir: str = "test_cases") -> List[Dict[str, Any]]:
        """加载目录下所有 YAML 测试用例
        支持两种格式：
        1. 传统测试用例文件 - 直接包含 test_cases 字段
        2. 数据矩阵文件 - 以 _data_matrix.yaml 结尾，包含 data_matrix 和 step_templates 字段
        """
        test_cases = []
        test_dir = Path(test_cases_dir)
        
        for yaml_file in test_dir.glob("*.yaml"):
            yaml_file_str = str(yaml_file)
            
            # 检查是否为数据矩阵文件
            if yaml_file.name.endswith("_data_matrix.yaml"):
                # 使用数据矩阵处理器生成测试用例
                data_matrix_handler = DataMatrixHandler()
                if data_matrix_handler.load_data_matrix(yaml_file_str):
                    generated_cases = data_matrix_handler.generate_test_cases()
                    for case in generated_cases:
                        case["file"] = yaml_file.name  # 记录来源文件
                        test_cases.append(case)
            else:
                # 传统测试用例文件处理
                data = YamlTestLoader.load_yaml(yaml_file_str)
                if "test_cases" in data:
                    for case in data["test_cases"]:
                        case["file"] = yaml_file.name  # 记录来源文件
                        test_cases.append(case)
        
        return test_cases