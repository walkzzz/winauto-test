# 调试脚本：检查测试用例是否正确加载
from utils.yaml_loader import YamlTestLoader
from utils.data_matrix_handler import DataMatrixHandler

# 测试1：直接测试YamlTestLoader
print("=== 测试YamlTestLoader ===")
test_cases = YamlTestLoader.load_all_test_cases()
print(f"加载的测试用例数量: {len(test_cases)}")
for case in test_cases:
    print(f"- {case.get('case_id')} - {case.get('case_name')}")

# 测试2：直接测试DataMatrixHandler
print("\n=== 测试DataMatrixHandler ===")
handler = DataMatrixHandler()
handler.load_data_matrix("test_cases/login_data_matrix.yaml")
generated_cases = handler.generate_test_cases()
print(f"生成的测试用例数量: {len(generated_cases)}")
for case in generated_cases:
    print(f"- {case.get('case_id')} - {case.get('case_name')}")
