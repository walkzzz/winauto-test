import pytest
import shutil
from pathlib import Path

def pytest_configure(config):
    """配置测试环境"""
    # 创建报告目录
    reports_dir = Path("reports")
    if reports_dir.exists():
        shutil.rmtree(reports_dir)
    reports_dir.mkdir(exist_ok=True)
    
    # 配置 Allure（可选）
    config.option.allure_report_dir = "reports/allure"

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """自定义测试报告"""
    outcome = yield
    report = outcome.get_result()
    
    # 添加用例描述
    if hasattr(item, "callspec"):
        test_case = item.callspec.params.get("test_case")
        if test_case:
            report.nodeid = f"{test_case['case_id']} - {test_case['case_name']}"