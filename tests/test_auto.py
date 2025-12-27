import pytest
import allure
from utils.yaml_loader import YamlTestLoader
from utils.test_generator import YamlTestGenerator

# 加载所有测试用例
TEST_CASES = YamlTestLoader.load_all_test_cases()

def pytest_generate_tests(metafunc):
    """pytest 钩子：动态生成测试函数"""
    if "test_case" in metafunc.fixturenames:
        # 参数化测试用例
        metafunc.parametrize(
            "test_case",
            TEST_CASES,
            ids=[case["case_id"] for case in TEST_CASES]
        )

@pytest.fixture
def test_generator():
    """测试生成器 fixture"""
    return YamlTestGenerator()

def test_yaml_case(test_case: dict, test_generator: YamlTestGenerator):
    """
    动态生成的测试函数
    每个 YAML 用例生成一个独立的测试
    """
    # Allure 特性配置
    allure.dynamic.title(f"{test_case.get('case_id')} - {test_case.get('case_name')}")
    allure.dynamic.description(test_case.get('description', f"测试用例: {test_case.get('case_id')}"))
    allure.dynamic.story(test_case.get('story', '默认Story'))
    allure.dynamic.feature(test_case.get('feature', '登录模块'))
    allure.dynamic.severity(test_case.get('priority', 'normal'))
    allure.dynamic.tag(test_case.get('case_id'))
    
    # 如果有 test_suite 信息，可以添加到 Allure 中
    allure.dynamic.epic(test_case.get('epic', '登录测试'))
    # 初始化 WinAuto
    test_generator.setup_winauto()
    
    try:
        # 执行前置步骤
        for step in test_case.get("steps", []):
            test_generator.execute_step(step)
        
        # 验证预期结果
        expected = test_case.get("expected", [])
        last_result = None
        for exp in expected:
            if 'action' in exp:
                # 预期步骤应成功执行
                last_result = test_generator.execute_step(exp)
                assert last_result is not None, f"预期验证失败: {exp}"
            elif 'expected_text' in exp:
                # 验证预期文本 - 检查上一步的 get_text 结果
                expected_text = exp['expected_text']
                assert last_result == expected_text, f"预期文本验证失败: 预期 '{expected_text}'，实际 '{last_result}'"
                allure.attach(f"预期文本验证成功: '{last_result}'", name="文本验证结果")
            else:
                # 其他预期结果类型，执行默认处理
                last_result = test_generator.execute_step(exp)
                assert last_result is not None, f"预期验证失败: {exp}"
        
        # 成功截图
        test_generator.winauto.screenshot(
            filename=f"reports/success_{test_case['case_id']}.png"
        )
        
    except Exception as e:
        # 失败截图
        test_generator.winauto.screenshot(
            filename=f"reports/failed_{test_case['case_id']}.png"
        )
        pytest.fail(f"测试用例 {test_case['case_id']} 执行失败: {str(e)}")
    
    finally:
        # 清理
        test_generator.winauto.close_app()